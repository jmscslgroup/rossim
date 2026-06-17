#!/usr/bin/env python3
"""
Smoke-check the multi-car live dashboard.

Run this *inside the container* while the simulation and dashboard are running.
It fetches /config, reads a few /stream (SSE) frames, reports the cars that were
discovered and which of their tiles went live, and PASSES iff at least one ego
car (one that commands acceleration) has its required tiles live.

    python3 dashboard/smoke_check.py [--url http://127.0.0.1:8888] [--seconds 8]
"""

import argparse
import json
import sys
import time
import urllib.request

# Tiles that must go live on an ego car for the test to pass.
REQUIRED = ["speed", "cmd_accel", "lead_dist"]


def get_json(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))


def read_stream(url, seconds):
    deadline = time.monotonic() + seconds
    frames = []
    with urllib.request.urlopen(url + "/stream", timeout=seconds + 5) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if line.startswith("data:"):
                try:
                    frames.append(json.loads(line[5:].strip()))
                except json.JSONDecodeError:
                    pass
            if time.monotonic() > deadline:
                break
    return frames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8888")
    ap.add_argument("--seconds", type=float, default=8.0)
    args = ap.parse_args()

    cfg = get_json(args.url + "/config")
    print("config: mode=%s, position_key=%s, %d field defs"
          % (cfg["mode"], cfg["position_key"], len(cfg["fields"])))

    frames = read_stream(args.url, args.seconds)
    print("read %d stream frame(s) over ~%.0fs\n" % (len(frames), args.seconds))

    # Aggregate, per car: available fields, and which fields ever went live.
    available = {}    # car -> set(keys)
    went_live = {}    # car -> set(keys that were non-null and not stale)
    for fr in frames:
        for car, info in (fr.get("cars") or {}).items():
            available.setdefault(car, set()).update(info.get("available", []))
            live = went_live.setdefault(car, set())
            for key, d in (info.get("fields") or {}).items():
                if d.get("value") is not None and not d.get("stale", True):
                    live.add(key)

    cars = sorted(available)
    if not cars:
        print("SMOKE TEST FAILED: no cars discovered.")
        return 1

    ego_ok = False
    print("%-10s %-6s %-7s %s" % ("car", "role", "live", "live fields"))
    print("-" * 60)
    for car in cars:
        is_ego = "cmd_accel" in available[car]
        role = "ego" if is_ego else "lead"
        live = went_live.get(car, set())
        req_live = is_ego and all(k in live for k in REQUIRED)
        if req_live:
            ego_ok = True
        mark = "OK" if (req_live or not is_ego) else "MISS"
        print("%-10s %-6s %-7s %s" % (car, role, mark, ", ".join(sorted(live)) or "(none)"))

    print()
    print("discovered %d car(s): %s" % (len(cars), ", ".join(cars)))
    if ego_ok:
        print("SMOKE TEST PASSED: an ego car has all required tiles live.")
        return 0
    print("SMOKE TEST FAILED: no ego car had all of %s live." % ", ".join(REQUIRED))
    return 1


if __name__ == "__main__":
    sys.exit(main())
