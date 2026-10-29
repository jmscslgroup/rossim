#!/usr/bin/env python3
"""
Shared car-discovery and field configuration for the rossim dashboards.

Both the web dashboard (dashboard.py) and the text dashboard (dashboard_tui.py)
import from here, so they discover cars and read the same fields identically.

There are two layouts, selected by mode:

* sim  -- the simulation namespaces each vehicle (/leadcar/..., /egocar/...),
          so cars are discovered by scanning for "<ns>/car/state/vel_x" and the
          field topics are read relative to that namespace.
* live -- the real vehicle publishes a single car's data at absolute topics
          (/car/state/vel_x, /cmd_accel, /lead_dist, ...), so there is one car
          read from those absolute topics. (Names taken from a bag recorded on
          the car.)

Depends only on rospy + the Python standard library.
"""

import re
import threading
import time

import rospy
from sensor_msgs.msg import NavSatFix
from std_msgs.msg import Bool, Float64, Int16

# Message types a field may use (see "msg" below).
MSG_TYPES = {"Float64": Float64, "Int16": Int16, "Bool": Bool, "NavSatFix": NavSatFix}

# --- field definitions -------------------------------------------------------
# Each field is one reading. Keys:
#   key       short id used internally and in the UIs
#   label     human label
#   topic     in sim: a suffix relative to the car namespace (egocar -> /egocar/<topic>)
#             in live: an absolute topic (starts with "/")
#   unit, precision, signed   display formatting
#   msg       optional message type name from MSG_TYPES (default "Float64")
#   attr      optional message attribute to show (default "data"); lets one
#             topic feed several fields, e.g. NavSatFix latitude / longitude

# --- sim layout (namespaced, discovered) ------------------------------------
SIM_POSITION_KEY = "odom"               # field used as a car's position (overhead view)
SIM_DETECT_SUFFIX = "car/state/vel_x"   # /<ns>/car/state/vel_x -> car <ns>

SIM_FIELDS = [
    {"key": "speed",            "label": "Speed",     "topic": "car/state/vel_x", "unit": "m/s",  "precision": 2, "signed": False},
    {"key": "cmd_accel",        "label": "Cmd Accel", "topic": "cmd_accel",       "unit": "m/s²", "precision": 2, "signed": True},
    {"key": "lead_dist",        "label": "Lead Dist", "topic": "lead_dist",       "unit": "m",    "precision": 2, "signed": False},
    {"key": "rel_vel",          "label": "Rel Vel",   "topic": "rel_vel",         "unit": "m/s",  "precision": 2, "signed": True},
    {"key": SIM_POSITION_KEY,   "label": "Odometer",  "topic": "odom_x",          "unit": "m",    "precision": 1, "signed": False},
]

# --- live layout (single real vehicle, absolute topics) ---------------------
# Topic names verified against a bag recorded on the car. Add more real-vehicle
# fields here (absolute topics) as you want them on the dashboard; they appear
# automatically once they are publishing.
LIVE_CAR_NAME = "car"
LIVE_DETECT_TOPIC = "/car/state/vel_x"  # the car is "present" when this publishes

LIVE_FIELDS = [
    {"key": "cmd_accel",  "label": "Cmd Accel",       "topic": "/cmd_accel",            "unit": "m/s²", "precision": 2, "signed": True},
    {"key": "cmd_accel_speedlimit_pre",  "label": "Cmd Accel after controller",       "topic": "/cmd_accel_speedlimit_pre",            "unit": "m/s²", "precision": 2, "signed": True},
    {"key": "lead_dist",  "label": "Lead Dist",       "topic": "/lead_dist",            "unit": "m",    "precision": 2, "signed": False},
    {"key": "lead_extra", "label": "Lead Dist Extra", "topic": "/lead_dist_extra",      "unit": "m",    "precision": 2, "signed": False},
    {"key": "radar_used", "label": "Radar Used",      "topic": "/lead_dist_radar_used", "unit": "1=yes", "precision": 0, "signed": False, "msg": "Bool"},
    {"key": "rel_vel",    "label": "Rel Vel",         "topic": "/rel_vel",              "unit": "m/s",  "precision": 2, "signed": True},
    {"key": "set_speed",  "label": "Set Speed",       "topic": "/acc/set_speed",        "unit": "m/s",  "precision": 0, "signed": False, "msg": "Int16"},
    {"key": "speed",      "label": "Speed",           "topic": "/car/state/vel_x",      "unit": "m/s",  "precision": 2, "signed": False},
    {"key": "gps_lat",    "label": "GPS Lat",         "topic": "/car/gps/fix",          "unit": "deg",  "precision": 6, "signed": True, "msg": "NavSatFix", "attr": "latitude"},
    {"key": "gps_lon",    "label": "GPS Lon",         "topic": "/car/gps/fix",          "unit": "deg",  "precision": 6, "signed": True, "msg": "NavSatFix", "attr": "longitude"},
    # Further real-vehicle topics available in the recording, for later:
    #   /car/cruise/accel_input (Float64), /car/gps/heading (Float64),
    #   /acc/set_speed2 (Float64), /lead_dist_radar (Float64),
    #   /steer_torque_cmd (Float64), /highbeams (Float64)
    # Other message types: add them to MSG_TYPES and set "msg"/"attr" here.
]


def get_config(mode):
    """Return the layout config for a mode ('sim' or 'live')."""
    if mode == "live":
        return {
            "mode": "live",
            "fields": LIVE_FIELDS,
            "position_key": None,          # no odometry on the real vehicle (yet)
            "discovery": "single",
            "car_name": LIVE_CAR_NAME,
            "detect": LIVE_DETECT_TOPIC,
        }
    return {
        "mode": "sim",
        "fields": SIM_FIELDS,
        "position_key": SIM_POSITION_KEY,
        "discovery": "namespace",
        "car_name": None,
        "detect": SIM_DETECT_SUFFIX,
    }


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

    def __init__(self, config, scan_period=1.0):
        self.fields = config["fields"]
        self.discovery = config["discovery"]   # "namespace" | "single"
        self.detect = config["detect"]
        self.car_name = config.get("car_name")
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

        if self.discovery == "single":
            present = self._scan_single(names)
        else:
            present = self._scan_namespace(names)

        with self._lock:
            new_cars = [c for c in present if c not in self._present]
            self._present = present
        for c in new_cars:
            rospy.loginfo("dashboard: discovered car '%s' (%d fields)", c, len(present[c]))

    def _scan_namespace(self, names):
        detect = re.compile(r"^/([^/]+)/" + re.escape(self.detect) + r"$")
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
        return present

    def _scan_single(self, names):
        present = {}
        if self.detect in names:
            car = self.car_name
            avail = set()
            for f in self.fields:
                topic = f["topic"]  # absolute
                if topic in names:
                    avail.add(f["key"])
                    self._ensure_sub(car, f, topic)
            present[car] = avail
        return present

    def _ensure_sub(self, car, field, topic):
        key = (car, field["key"])
        if key in self._subs:
            return
        msg_type = MSG_TYPES[field.get("msg", "Float64")]
        self._subs[key] = rospy.Subscriber(
            topic, msg_type, self._make_cb(car, field["key"], field.get("attr", "data")),
            queue_size=1)

    def _make_cb(self, car, key, attr):
        def cb(msg):
            value = float(getattr(msg, attr))   # Bool -> 1.0/0.0, Int16 -> float
            with self._lock:
                self._values[(car, key)] = (value, time.monotonic())
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
