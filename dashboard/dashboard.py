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
    --mode sim    namespaced simulation cars (leadcar, egocar, ...) (default)
    --mode live   a single real vehicle read from absolute topics
                  (/car/state/vel_x, /cmd_accel, ...). See cardata.py.
"""

import argparse
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import rospy

from cardata import CarRegistry, get_config

HERE = os.path.dirname(os.path.abspath(__file__))


def config_payload(cfg):
    return {
        "mode": cfg["mode"],
        "position_key": cfg["position_key"],
        "fields": [
            {"key": f["key"], "label": f["label"], "unit": f["unit"],
             "topic": f["topic"], "precision": f["precision"], "signed": f["signed"]}
            for f in cfg["fields"]
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

    cfg = get_config(args.mode)

    registry = CarRegistry(cfg, scan_period=args.scan_period)
    registry.start()

    with open(os.path.join(HERE, "index.html"), "r") as fh:
        html = fh.read()

    server = DashServer((args.host, args.port), Handler)
    server.registry = registry
    server.config_payload = config_payload(cfg)
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
