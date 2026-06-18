#!/usr/bin/env python3
"""
rossim text dashboard.

A terminal version of the live dashboard, for when you are logged into the car
over SSH with no web access. It uses the same car discovery as the web dashboard
(dashboard.py) and prints a table of every discovered car that refreshes in
place, plus a simple front-to-back ordering (the "overhead" idea, in text).

No browser, no ports, no extra dependencies -- just rospy and the standard
library. Run it wherever ROS is sourced and the car/sim stack is running:

    python3 /ros/catkin_ws/dashboard/dashboard_tui.py --mode live

Options:
    --mode sim|live     which field set to show (default: sim)
    --rate 4            refresh rate in Hz (default: 4)
    --scan-period 1.0   seconds between car-discovery scans
    --stale-after 1.0   seconds without an update before a value is flagged (*)
    --once              print a single snapshot and exit (good for scripts/logs)
    --no-clear          append frames instead of redrawing in place (for logs)
"""

import argparse
import sys
import time

import rospy

from cardata import POSITION_KEY, CarRegistry, format_value, get_fields

CLEAR_HOME = "\033[2J\033[H"   # clear screen, cursor home
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"

COL = 11   # data column width


def cell(field_state, field):
    """Render one table cell from a {value, stale} dict (or None)."""
    if not field_state or field_state.get("value") is None:
        return "--"
    s = format_value(field_state["value"], field)
    if field_state.get("stale"):
        s += "*"
    return s


def render(fields, snapshot, mode, stamp):
    cars = sorted(snapshot.keys())
    lines = []
    lines.append("rossim text dashboard   mode=%s   %d car(s)   %s"
                 % (mode, len(cars), stamp))
    lines.append("")

    if not cars:
        lines.append("  no cars discovered yet ...")
        lines.append("  (a car = a namespace publishing 'car/state/vel_x';")
        lines.append("   check 'rostopic list' if this stays empty on the real vehicle)")
        return "\n".join(lines)

    # Header row: car name + one column per field.
    header = "{:<12}".format("car") + "".join("{:<{w}}".format(f["key"], w=COL) for f in fields)
    lines.append(header)
    lines.append("-" * len(header))

    for car in cars:
        info = snapshot[car]
        avail = set(info.get("available", []))
        row = "{:<12}".format(car)
        for f in fields:
            text = cell(info["fields"].get(f["key"]), f) if f["key"] in avail else ""
            row += "{:<{w}}".format(text, w=COL)
        lines.append(row)

    # Front-to-back ordering by position, with gaps -- the "overhead" in text.
    positioned = []
    for car in cars:
        d = snapshot[car]["fields"].get(POSITION_KEY)
        if d and d.get("value") is not None:
            positioned.append((car, d["value"]))
    positioned.sort(key=lambda cv: cv[1], reverse=True)  # front (highest) first
    if positioned:
        lines.append("")
        parts = []
        for i, (car, pos) in enumerate(positioned):
            if i > 0:
                gap = positioned[i - 1][1] - pos
                parts.append("--%.1fm--" % gap)
            parts.append("%s %.1fm" % (car, pos))
        lines.append("order (front -> back):  " + "  ".join(parts))

    lines.append("")
    units = ", ".join("%s %s" % (f["key"], f["unit"]) for f in fields)
    lines.append("units: " + units)
    lines.append("* = stale (no recent update)    Ctrl+C to quit")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="rossim text dashboard")
    parser.add_argument("--mode", choices=["sim", "live"], default="sim")
    parser.add_argument("--rate", type=float, default=4.0, help="refresh rate in Hz")
    parser.add_argument("--scan-period", type=float, default=1.0)
    parser.add_argument("--stale-after", type=float, default=1.0)
    parser.add_argument("--once", action="store_true", help="print one snapshot and exit")
    parser.add_argument("--no-clear", action="store_true",
                        help="append frames instead of redrawing (for logging)")
    args = parser.parse_args(rospy.myargv()[1:])

    rospy.init_node("dashboard_tui", anonymous=True)
    fields = get_fields(args.mode)
    registry = CarRegistry(fields, scan_period=args.scan_period)
    registry.start()

    interactive = not args.once and not args.no_clear
    if args.once:
        # Give discovery + the first messages a moment to arrive.
        time.sleep(max(args.scan_period, 1.0) + 0.5)

    try:
        if interactive:
            sys.stdout.write(HIDE_CURSOR)
        while not rospy.is_shutdown():
            stamp = time.strftime("%H:%M:%S")
            frame = render(fields, registry.snapshot(args.stale_after), args.mode, stamp)
            if interactive:
                sys.stdout.write(CLEAR_HOME + frame)
            else:
                sys.stdout.write(frame + "\n")
            sys.stdout.flush()
            if args.once:
                break
            time.sleep(1.0 / max(args.rate, 0.5))
    except KeyboardInterrupt:
        pass
    finally:
        if interactive:
            sys.stdout.write(SHOW_CURSOR + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
