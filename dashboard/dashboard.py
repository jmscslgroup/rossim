#!/usr/bin/env python3
"""
rossim live dashboard (multi-car).

A self-contained ROS node that DISCOVERS the cars running in the simulation and
serves a small web dashboard at http://localhost:8888. The browser can swap
between cars to see each one's data, and shows an ego-centric overhead view
(the selected car, the car ahead, and any cars behind).

A "car" is any ROS namespace that publishes the car-detect topic (by default
"<car>/car/state/vel_x"), so leadcar, egocar, egocar1, ... are all found
automatically as they appear, with no configuration.

No external dependencies: rospy + the Python standard library only
(http.server + Server-Sent Events). No rosbridge, no websockets, no pip.

Run inside the running simulation container (or use scripts/dashboard.sh):

    python3 /ros/catkin_ws/dashboard/dashboard.py --mode sim

Then open http://localhost:8888 in your browser.

Modes:
    --mode sim    fields available in simulation (default)
    --mode live   superset for the real vehicle; extra fields live in
                  LIVE_EXTRA_FIELDS below and appear once their topics publish.
"""

import argparse
import json
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import rospy
from std_msgs.msg import Float64

HERE = os.path.dirname(os.path.abspath(__file__))

# --- Per-car field configuration --------------------------------------------
# Each field is one tile, bound to a topic *relative to a car's namespace*.
#
# Keys:
#   key       short id used internally and in the HTML
#   label     text shown on the tile
#   topic     topic suffix within the car namespace (e.g. egocar -> /egocar/<topic>)
#   unit      unit string shown next to the value
#   precision decimal places to display
#   signed    True -> show a leading +/- and color the tile by sign

POSITION_KEY = "odom"            # field used as the car's position in the overhead view
CAR_DETECT_SUFFIX = "car/state/vel_x"  # a namespace with this topic is treated as a car

SIM_FIELDS = [
    {"key": "speed",      "label": "Speed",     "topic": "car/state/vel_x", "unit": "m/s",  "precision": 2, "signed": False},
    {"key": "cmd_accel",  "label": "Cmd Accel", "topic": "cmd_accel",       "unit": "m/s²", "precision": 2, "signed": True},
    {"key": "lead_dist",  "label": "Lead Dist", "topic": "lead_dist",       "unit": "m",    "precision": 2, "signed": False},
    {"key": "rel_vel",    "label": "Rel Vel",   "topic": "rel_vel",         "unit": "m/s",  "precision": 2, "signed": True},
    {"key": POSITION_KEY, "label": "Odometer",  "topic": "odom_x",          "unit": "m",    "precision": 1, "signed": False},
]

# Extra fields only available on the real vehicle. Add entries here (same shape)
# as real-car topics come online; they appear only in --mode live.
LIVE_EXTRA_FIELDS = [
    # {"key": "accel_meas", "label": "Accel (IMU)", "topic": "imu/accel_x",     "unit": "m/s²", "precision": 2, "signed": True},
    # {"key": "steer",      "label": "Steering",    "topic": "can/steer_angle", "unit": "deg",       "precision": 1, "signed": True},
]


class CarRegistry(object):
    """Discovers cars from the ROS graph and tracks the latest value per field."""

    def __init__(self, fields, scan_period=1.0):
        self.fields = fields
        self._scan_period = scan_period
        self._lock = threading.Lock()
        self._values = {}    # (car, key) -> (value, monotonic_ts)
        self._subs = {}      # (car, key) -> rospy.Subscriber  (created once, kept)
        self._present = {}   # car -> set(available field keys), from the last scan

    def start(self):
        self._scan()
        rospy.Timer(rospy.Duration(self._scan_period), lambda _evt: self._scan())

    def _scan(self):
        try:
            published = rospy.get_published_topics()
        except Exception as exc:  # master transiently unavailable, etc.
            rospy.logwarn_throttle(10.0, "dashboard: topic scan failed: %s", exc)
            return
        names = set(t for t, _type in published)

        detect = re.compile(r"^/([^/]+)/" + re.escape(CAR_DETECT_SUFFIX) + r"$")
        cars = sorted({m.group(1) for m in (detect.match(t) for t in names) if m})

        present = {}
        for car in cars:
            avail = set()
            for f in self.fields:
                topic = "/{}/{}".format(car, f["topic"])
                if topic in names:
                    avail.add(f["key"])
                    self._ensure_sub(car, f, topic)
            present[car] = avail

        with self._lock:
            new_cars = [c for c in present if c not in self._present]
            self._present = present
        for c in new_cars:
            rospy.loginfo("dashboard: discovered car '%s' (%d fields)", c, len(present[c]))

    def _ensure_sub(self, car, field, topic):
        key = (car, field["key"])
        if key in self._subs:
            return
        self._subs[key] = rospy.Subscriber(
            topic, Float64, self._make_cb(car, field["key"]), queue_size=1)

    def _make_cb(self, car, key):
        def cb(msg):
            with self._lock:
                self._values[(car, key)] = (msg.data, time.monotonic())
        return cb

    def snapshot(self, stale_after):
        now = time.monotonic()
        out = {}
        with self._lock:
            present = {c: set(a) for c, a in self._present.items()}
            for car, avail in present.items():
                fields_out = {}
                for key in avail:
                    entry = self._values.get((car, key))
                    if entry is None:
                        fields_out[key] = {"value": None, "stale": True, "age": None}
                    else:
                        value, ts = entry
                        age = now - ts
                        fields_out[key] = {
                            "value": value,
                            "stale": age > stale_after,
                            "age": round(age, 2),
                        }
                out[car] = {"available": sorted(avail), "fields": fields_out}
        return out


def config_payload(mode, fields):
    return {
        "mode": mode,
        "position_key": POSITION_KEY,
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
            self._send_json(self.server.config_payload)
        elif self.path == "/cars":
            cars = sorted(self.server.registry.snapshot(self.server.stale_after).keys())
            self._send_json({"cars": cars})
        elif self.path == "/stream":
            self._send_stream()
        else:
            self.send_error(404)

    def _send_json(self, obj):
        self._send_bytes(json.dumps(obj).encode("utf-8"), "application/json")

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
                payload = json.dumps({"cars": self.server.registry.snapshot(self.server.stale_after)})
                self.wfile.write("data: {}\n\n".format(payload).encode("utf-8"))
                self.wfile.flush()
                time.sleep(self.server.interval)
        except (BrokenPipeError, ConnectionResetError):
            pass  # browser tab closed / navigated away


def main():
    parser = argparse.ArgumentParser(description="rossim live dashboard (multi-car)")
    parser.add_argument("--mode", choices=["sim", "live"], default="sim")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8888)
    parser.add_argument("--rate", type=float, default=10.0,
                        help="dashboard refresh rate in Hz (default: 10)")
    parser.add_argument("--scan-period", type=float, default=1.0,
                        help="seconds between car-discovery scans (default: 1.0)")
    parser.add_argument("--stale-after", type=float, default=1.0,
                        help="seconds without an update before a value greys out")
    args = parser.parse_args(rospy.myargv()[1:])

    rospy.init_node("dashboard", anonymous=True)

    fields = list(SIM_FIELDS)
    if args.mode == "live":
        fields = fields + LIVE_EXTRA_FIELDS

    registry = CarRegistry(fields, scan_period=args.scan_period)
    registry.start()

    with open(os.path.join(HERE, "index.html"), "r") as fh:
        html = fh.read()

    server = DashServer((args.host, args.port), Handler)
    server.registry = registry
    server.config_payload = config_payload(args.mode, fields)
    server.html = html
    server.interval = 1.0 / max(args.rate, 1.0)
    server.stale_after = args.stale_after

    threading.Thread(target=server.serve_forever, daemon=True).start()
    rospy.loginfo("dashboard: mode=%s serving on %s:%d", args.mode, args.host, args.port)
    rospy.loginfo("dashboard: open http://localhost:%d in your browser", args.port)

    try:
        rospy.spin()
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
