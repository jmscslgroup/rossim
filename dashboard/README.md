# rossim live dashboard

A small web dashboard for watching a car's ROS topics in real time. It runs as
a ROS node that subscribes to the topics and serves a web page at
`http://localhost:8888` -- starting as plain data tiles (speed, commanded
acceleration, lead distance, ...) and intended to grow into speedometer-style
SVG gauges.

It has **no external dependencies**: just `rospy` (already in the ROS container)
and the Python standard library (`http.server` + Server-Sent Events). No
rosbridge, no websocket library, nothing to `pip install`.

## Quick start

From the host, with a simulation already running (`./scripts/run.sh`):

```bash
./scripts/dashboard.sh
```

Then open <http://localhost:8888>.

Or run it by hand inside the container:

```bash
./scripts/join.sh
python3 /ros/catkin_ws/dashboard/dashboard.py --mode sim
```

## sim vs live

The same script serves two field sets, selected by `--mode`:

| Mode | Fields |
|------|--------|
| `sim` (default) | speed, commanded accel, lead distance, relative velocity, odometer |
| `live` | the `sim` fields **plus** extra real-vehicle fields |

`live` is a superset for when this runs on the real car. Add real-car fields by
editing `LIVE_EXTRA_FIELDS` in `dashboard.py` (each entry binds a tile to a
topic); they appear automatically in `--mode live` once those topics publish.

## Options

```
--mode sim|live       which field set to show (default: sim)
--namespace egocar    namespace for relative topics (default: egocar)
--port 8888           HTTP port inside the container (default: 8888)
--rate 10             dashboard refresh rate in Hz (default: 10)
--stale-after 1.0     seconds without an update before a value greys out
```

## How it fits together

```
ROS topics  --(rospy subscribers)-->  dashboard.py  --(HTTP + SSE)-->  index.html
 /egocar/...                          latest values    localhost:8888    (browser)
```

- `dashboard.py` keeps the latest value per topic and streams a JSON snapshot
  over Server-Sent Events at `/stream`.
- `index.html` fetches the field list from `/config`, builds one tile per field,
  and updates them from the stream. Tiles grey out when a value goes stale and
  color by sign for signed fields (e.g. commanded acceleration).

To extend the look toward real gauges, edit `index.html` only -- the data
plumbing does not change.
