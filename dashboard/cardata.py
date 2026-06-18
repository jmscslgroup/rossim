#!/usr/bin/env python3
"""
Shared car-discovery and field configuration for the rossim dashboards.

Both the web dashboard (dashboard.py) and the text dashboard (dashboard_tui.py)
import from here, so they discover cars and read the same fields identically.

A "car" is any ROS namespace that publishes CAR_DETECT_SUFFIX, so leadcar,
egocar, egocar1, ... are found automatically as they appear, with no config.

Depends only on rospy + the Python standard library.
"""

import re
import threading
import time

import rospy
from std_msgs.msg import Float64

# --- Per-car field configuration --------------------------------------------
# Each field is one reading, bound to a topic *relative to a car's namespace*.
#
# Keys:
#   key       short id used internally and in the UIs
#   label     human label
#   topic     topic suffix within the car namespace (egocar -> /egocar/<topic>)
#   unit      unit string
#   precision decimal places to display
#   signed    True -> show a leading +/- and color/flag by sign

POSITION_KEY = "odom"                   # field used as a car's position (overhead view)
CAR_DETECT_SUFFIX = "car/state/vel_x"   # a namespace with this topic is treated as a car

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


def get_fields(mode):
    """Return the field list for the given mode ('sim' or 'live')."""
    fields = list(SIM_FIELDS)
    if mode == "live":
        fields = fields + LIVE_EXTRA_FIELDS
    return fields


def format_value(value, field):
    """Format a numeric value per a field's precision/sign rules."""
    if value is None:
        return "--"
    s = "{:.{p}f}".format(value, p=field["precision"])
    if field["signed"] and value >= 0:
        s = "+" + s
    return s


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
        """Return {car: {"available": [keys], "fields": {key: {value, stale, age}}}}."""
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
