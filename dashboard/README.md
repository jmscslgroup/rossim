# rossim live dashboard

A small web dashboard for watching the simulated (or, later, real) cars in real
time. It runs as a ROS node that **discovers the cars** running in the system
and serves a web page at `http://localhost:8888` with two views:

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

## Quick start

From the host, with a simulation already running (`./scripts/run.sh`):

```bash
./scripts/dashboard.sh
```

Then open <http://localhost:8888>. Or run it by hand inside the container:

```bash
./scripts/join.sh
python3 /ros/catkin_ws/dashboard/dashboard.py --mode sim
```

## How cars are discovered

Any ROS namespace that publishes `<car>/car/state/vel_x` is treated as a car, so
`leadcar`, `egocar`, `egocar1`, ... are all found automatically with no
configuration. For each car the node subscribes to the standard fields that
actually exist for it -- so the replayed lead car (which has no controller)
simply shows fewer tiles than an ego car. A car that commands acceleration
(publishes `cmd_accel`) is labelled **ego**; the rest are **lead**.

Positions in the overhead view come from each car's odometer (`odom_x`): the
selected car sits at the centre, others are offset by their distance relative to
it (`+` ahead, `-` behind), and the nearest car ahead and behind are highlighted.

## sim vs live

The same script serves two field sets, selected by `--mode`:

| Mode | Fields |
|------|--------|
| `sim` (default) | speed, commanded accel, lead distance, relative velocity, odometer |
| `live` | the `sim` fields **plus** extra real-vehicle fields |

`live` is a superset for when this runs on the real car. Add real-car fields by
editing `LIVE_EXTRA_FIELDS` in `dashboard.py`; they appear automatically in
`--mode live` once those topics publish.

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
