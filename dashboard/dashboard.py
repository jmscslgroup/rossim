#!/usr/bin/env python3
"""
rossim live dashboard.

A self-contained ROS node that subscribes to a car's topics and serves a small
web dashboard (data tiles now, gauges later) at http://localhost:8888.

No external dependencies: it uses rospy (already in the ROS container) and the
Python standard library only -- http.server with Server-Sent Events (SSE).
There is no rosbridge, no websocket library, and nothing to pip install.

Run it inside the running simulation container (see scripts/dashboard.sh for a
host-side shortcut):

    ./scripts/join.sh
    python3 /ros/catkin_ws/dashboard/dashboard.py --mode sim

Then open http://localhost:8888 in a browser on your host.

Modes:
    --mode sim    fields available in simulation (default)
    --mode live   superset for the real vehicle; extra fields are listed in
                  LIVE_EXTRA_FIELDS below and appear automatically once their
                  real-car topics are publishing.
"""

import argparse
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import rospy
from std_msgs.msg import Float64

HERE = os.path.dirname(os.path.abspath(__file__))

# --- Field configuration -----------------------------------------------------
# Each field is one tile on the dashboard, bound to one ROS topic. Topics that
# do not start with "/" are taken relative to --namespace (default "egocar"),
# matching the launch files where each car lives in its own namespace.
#
# Keys:
#   key       short id used internally and in the HTML
#   label     text shown on the tile
#   topic     ROS topic (relative to the namespace, or absolute if it starts /)
#   unit      unit string shown next to the value
#   precision decimal places to display
#   signed    True -> show a leading +/- and color the tile by sign

SIM_FIELDS = [
    {"key": "speed",     "label": "Speed",     "topic": "car/state/vel_x", "unit": "m/s",      "precision": 2, "signed": False},
    {"key": "cmd_accel", "label": "Cmd Accel", "topic": "cmd_accel",       "unit": "m/s²", "precision": 2, "signed": True},
    {"key": "lead_dist", "label": "Lead Dist", "topic": "lead_dist",       "unit": "m",        "precision": 2, "signed": False},
    {"key": "rel_vel",   "label": "Rel Vel",   "topic": "rel_vel",         "unit": "m/s",      "precision": 2, "signed": True},
    {"key": "odom",      "label": "Odometer",  "topic": "odom_x",          "unit": "m",        "precision": 1, "signed": False},
]

# Extra fields only available on the real vehicle. Add entries here (same shape
# as above) as real-car topics come online; they appear only in --mode live.
# Examples are commented out -- adjust the topics to match your hardware.
LIVE_EXTRA_FIELDS = [
    # {"key": "accel_meas", "label": "Accel (IMU)",  "topic": "/imu/accel_x",      "unit": "m/s²", "precision": 2, "signed": True},
    # {"key": "steer",      "label": "Steering",     "topic": "/can/steer_angle",  "unit": "deg",       "precision": 1, "signed": True},
    # {"key": "gps_speed",  "label": "GPS Speed",    "topic": "/gps/speed",        "unit": "m/s",       "precision": 2, "signed": False},
]


class Dashboard(object):
    """Subscribes to each field's topic and keeps the latest value."""

    def __init__(self, fields, namespace, stale_after):
        self.fields = fields
        self.namespace = namespace.strip("/")
        self.stale_after = stale_after
        self._lock = threading.Lock()
        # key -> (value, monotonic_timestamp), or None until first message
        self._state = {f["key"]: None for f in fields}
        self._subs = []
        for f in fields:
            topic = self._resolve(f["topic"])
            self._subs.append(
                rospy.Subscriber(topic, Float64, self._make_cb(f["key"]), queue_size=1)
            )
            rospy.loginfo("dashboard: %-28s -> tile '%s'", topic, f["key"])

    def _resolve(self, topic):
        if topic.startswith("/"):
            return topic
        if self.namespace:
            return "/{}/{}".format(self.namespace, topic)
        return "/" + topic

    def _make_cb(self, key):
        def cb(msg):
            with self._lock:
                self._state[key] = (msg.data, time.monotonic())
        return cb

    def snapshot(self):
        now = time.monotonic()
        out = {}
        with self._lock:
            for key, entry in self._state.items():
                if entry is None:
                    out[key] = {"value": None, "stale": True, "age": None}
                else:
                    value, ts = entry
                    age = now - ts
                    out[key] = {"value": value, "stale": age > self.stale_after, "age": round(age, 2)}
        return out


def config_payload(mode, namespace, fields):
    return {
        "mode": mode,
        "namespace": namespace,
        "fields": [
            {"key": f["key"], "label": f["label"], "unit": f["unit"],
             "topic": f["topic"], "precision": f["precision"], "signed": f["signed"]}
            for f in fields
        ],
    }


class DashServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # keep the ROS console quiet

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send_bytes(self.server.html, "text/html; charset=utf-8")
        elif self.path == "/config":
            self._send_bytes(json.dumps(self.server.config_payload).encode("utf-8"),
                             "application/json")
        elif self.path == "/stream":
            self._send_stream()
        else:
            self.send_error(404)

    def _send_bytes(self, body, content_type):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            while not rospy.is_shutdown():
                payload = json.dumps(self.server.dashboard.snapshot())
                self.wfile.write("data: {}\n\n".format(payload).encode("utf-8"))
                self.wfile.flush()
                time.sleep(self.server.interval)
        except (BrokenPipeError, ConnectionResetError):
            pass  # browser tab closed / navigated away


def main():
    parser = argparse.ArgumentParser(description="rossim live dashboard")
    parser.add_argument("--mode", choices=["sim", "live"], default="sim")
    parser.add_argument("--namespace", default="egocar",
                        help="car namespace for relative topics (default: egocar)")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8888)
    parser.add_argument("--rate", type=float, default=10.0,
                        help="dashboard refresh rate in Hz (default: 10)")
    parser.add_argument("--stale-after", type=float, default=1.0,
                        help="seconds without an update before a value greys out")
    # rospy.myargv() strips ROS remapping args (e.g. __name:=, __log:=)
    args = parser.parse_args(rospy.myargv()[1:])

    rospy.init_node("dashboard", anonymous=True)

    fields = list(SIM_FIELDS)
    if args.mode == "live":
        fields = fields + LIVE_EXTRA_FIELDS

    dash = Dashboard(fields, args.namespace, args.stale_after)

    with open(os.path.join(HERE, "index.html"), "r") as fh:
        html = fh.read()

    server = DashServer((args.host, args.port), Handler)
    server.dashboard = dash
    server.config_payload = config_payload(args.mode, args.namespace, fields)
    server.html = html
    server.interval = 1.0 / max(args.rate, 1.0)

    threading.Thread(target=server.serve_forever, daemon=True).start()
    rospy.loginfo("dashboard: serving mode=%s namespace=%s on %s:%d",
                  args.mode, args.namespace, args.host, args.port)
    rospy.loginfo("dashboard: open http://localhost:%d in your browser", args.port)

    try:
        rospy.spin()
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
