#!/usr/bin/env python3
"""
Smoke-check the live dashboard.

Run this *inside the container* while the simulation and dashboard are running.
It fetches /config, reads a few /stream (SSE) frames, and reports which tiles
reached a live (non-null, non-stale) value. Exits 0 if the required tiles went
live, 1 otherwise -- so it can gate an automated smoke test.

    python3 dashboard/smoke_check.py [--url http://127.0.0.1:8888] [--seconds 8]
"""

import argparse
import json
import sys
import time
import urllib.request

# Tiles that MUST go live for the test to pass (the rest are reported but not
# required -- e.g. odometer may lag, rel_vel depends on both cars moving).
REQUIRED = ["speed", "cmd_accel", "lead_dist"]


def get_config(url):
    with urllib.request.urlopen(url + "/config", timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))


def read_stream(url, seconds):
    """Read SSE 'data:' frames for `seconds`, returning the list of snapshots."""
    deadline = time.monotonic() + seconds
    snapshots = []
    req = urllib.request.Request(url + "/stream")
    with urllib.request.urlopen(req, timeout=seconds + 5) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if line.startswith("data:"):
                try:
                    snapshots.append(json.loads(line[5:].strip()))
                except json.JSONDecodeError:
                    pass
            if time.monotonic() > deadline:
                break
    return snapshots


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8888")
    ap.add_argument("--seconds", type=float, default=8.0)
    args = ap.parse_args()

    cfg = get_config(args.url)
    fields = cfg["fields"]
    print("config: mode=%s namespace=%s, %d tiles"
          % (cfg["mode"], cfg["namespace"], len(fields)))

    snapshots = read_stream(args.url, args.seconds)
    print("read %d stream frame(s) over ~%.0fs\n" % (len(snapshots), args.seconds))

    # For each field, find the best (live) value seen across all frames.
    went_live = {}
    last_value = {}
    for f in fields:
        k = f["key"]
        went_live[k] = False
        last_value[k] = None
        for snap in snapshots:
            d = snap.get(k)
            if not d:
                continue
            if d.get("value") is not None:
                last_value[k] = d["value"]
            if d.get("value") is not None and not d.get("stale", True):
                went_live[k] = True

    print("%-12s %-10s %-8s %s" % ("tile", "topic", "live?", "last value"))
    print("-" * 52)
    ok = True
    for f in fields:
        k = f["key"]
        live = went_live[k]
        req = k in REQUIRED
        mark = "LIVE" if live else ("MISS" if req else "--")
        if req and not live:
            ok = False
        val = "n/a" if last_value[k] is None else ("%.3f" % last_value[k])
        print("%-12s %-10s %-8s %s%s"
              % (k, f["topic"], mark, val, "   (required)" if req else ""))

    print()
    if ok:
        print("SMOKE TEST PASSED: all required tiles went live.")
        return 0
    print("SMOKE TEST FAILED: a required tile never went live (check topic names).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
