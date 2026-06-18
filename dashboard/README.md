# rossim live dashboard

A small dashboard for watching the simulated (or, later, real) cars in real
time, in **two forms** that share the same car discovery:

- **Web** (`dashboard.py`) -- a browser dashboard at `http://localhost:8888`.
- **Text** (`dashboard_tui.py`) -- a terminal dashboard for SSH / no browser.

The shared discovery and field configuration live in `cardata.py`, so both
forms find cars and read the same fields identically.

The web version runs as a ROS node that **discovers the cars** running in the
system and serves a web page with two views:

- **Overhead** -- an ego-centric top-down view of the selected car, the car
  ahead, and any cars behind, positioned by their odometry.
- **Data** -- value tiles for the selected car (speed, commanded acceleration,
  lead distance, relative velocity, odometer), intended to grow into
  speedometer-style gauges.

You can **swap between cars** with the buttons at the top; the list updates
automatically as cars appear or disappear in the simulation.

It has **no external dependencies**: just `rospy` (already in the ROS container)
and the Python standard library (`http.server` + Server-Sent Events). No
rosbridge, no websocket library, nothing to `pip install`.

## Quick start (web)

From the host, with a simulation already running (`./scripts/run.sh`):

```bash
./scripts/dashboard.sh
```

Then open <http://localhost:8888>. Or run it by hand inside the container:

```bash
./scripts/join.sh
python3 /ros/catkin_ws/dashboard/dashboard.py --mode sim
```

## Text dashboard (SSH / no browser)

When you are logged into the car over SSH with no web access, use the text
version. It does the same car discovery and prints a table that refreshes in
place, plus a front-to-back ordering of the cars. No browser, no ports.

Run it directly wherever ROS is sourced (e.g. on the real vehicle):

```bash
python3 dashboard/dashboard_tui.py --mode live
```

Or, for the sim in the container, from the host:

```bash
./scripts/dashboard.sh --text          # add --mode live for the real vehicle
```

Example output:

```
car         speed      cmd_accel  lead_dist  rel_vel    odom
-------------------------------------------------------------------
egocar      4.20       +0.85      18.30      -0.40      73.1
leadcar     5.00                                        80.0

order (front -> back):  leadcar 80.0m  --6.9m--  egocar 73.1m
```

Blank cells mean the field does not exist for that car (e.g. the replayed lead
car has no controller). A `*` after a value means it is stale. Extra flags:
`--once` prints a single snapshot and exits; `--no-clear` appends frames instead
of redrawing (handy when piping to a log).

## sim vs live (two different topic layouts)

The simulation and the real vehicle publish on different topics, so `--mode`
selects between two layouts defined in `cardata.py`:

| Mode | Layout | Cars | Topics |
|------|--------|------|--------|
| `sim` (default) | namespaced, discovered | `leadcar`, `egocar`, `egocar1`, ... | relative, e.g. `/egocar/cmd_accel` |
| `live` | a single real vehicle | one car (`car`) | absolute, e.g. `/cmd_accel`, `/car/state/vel_x` |

**sim discovery.** Any namespace that publishes `<ns>/car/state/vel_x` is a car,
found automatically; each car subscribes only to the fields that exist for it
(so the replayed lead car shows fewer tiles than an ego car). A car that
commands acceleration (`cmd_accel`) is labelled **ego**, the rest **lead**.
Positions in the overhead view come from each car's odometer (`odom_x`).

**live.** The real vehicle publishes one car's data at absolute topics. The
field map (`LIVE_FIELDS` in `cardata.py`) was taken from a bag recorded on the
car: `speed` ← `/car/state/vel_x`, `cmd_accel` ← `/cmd_accel`, `accel_in` ←
`/car/cruise/accel_input`, `lead_dist` ← `/lead_dist`, `rel_vel` ← `/rel_vel`.
There is no odometry on the vehicle, so live mode has no position field and the
overhead view shows the single vehicle (the data tiles are the main view; the
web UI defaults to **Data** in live mode). Add more real-vehicle fields by
appending to `LIVE_FIELDS`; `std_msgs/Float64` topics work as-is, other message
types need handling added in `CarRegistry`.

You can exercise live mode locally without a car by replaying the recording
(it publishes the real absolute topics):

```bash
rosbag play mytest.bag                       # in one shell
python3 dashboard/dashboard_tui.py --mode live   # in another
```

## Options

```
--mode sim|live       which field set to show (default: sim)
--port 8888           HTTP port inside the container (default: 8888)
--rate 10             dashboard refresh rate in Hz (default: 10)
--scan-period 1.0     seconds between car-discovery scans (default: 1.0)
--stale-after 1.0     seconds without an update before a value greys out
```

## HTTP endpoints

| Path | Returns |
|------|---------|
| `/`        | the dashboard page (`index.html`) |
| `/config`  | field definitions + `position_key` + mode |
| `/cars`    | the list of currently discovered cars |
| `/stream`  | Server-Sent Events: a JSON snapshot of every car each tick |

A `/stream` frame looks like:

```json
{"cars": {
  "egocar":  {"available": ["cmd_accel","lead_dist","odom","rel_vel","speed"],
              "fields": {"speed": {"value": 4.2, "stale": false, "age": 0.1}, ...}},
  "leadcar": {"available": ["odom","speed"],
              "fields": {"odom": {"value": 20.0, "stale": false, "age": 0.1}, ...}}
}}
```

The browser receives every car each tick, so swapping cars and drawing the
overhead view are instant and client-side -- no reconnect.

## Testing

`smoke_check.py` is a dependency-free verifier: it reads `/config` and a few
`/stream` frames, reports the discovered cars and which tiles went live, and
exits non-zero unless an ego car has its required tiles (speed, cmd accel, lead
distance) live. Run it inside the container while a sim + dashboard are running:

```bash
python3 dashboard/smoke_check.py
```

## Extending

- **Gauges:** edit `index.html` only -- the data plumbing does not change. The
  `position_key` and per-field metadata are already exposed via `/config`.
- **New fields:** add to `SIM_FIELDS` (or `LIVE_EXTRA_FIELDS`) in `dashboard.py`.
- **Other message types:** fields are currently `std_msgs/Float64`; add handling
  in `CarRegistry` for other types as real-car topics require.
