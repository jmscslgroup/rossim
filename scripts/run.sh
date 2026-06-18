#!/usr/bin/env bash
#
# run.sh
#
# Builds the workspace and launches a profacc simulation inside the ROS
# container via Docker Compose -- a one-command shortcut for the build +
# source + roslaunch sequence.
#
# The container is given a predictable name (default: "rossim") so you can
# open extra terminals into it with ./scripts/join.sh -- no need to look up
# the auto-generated container name.
#
# The dashboard port (container 8888) is published to the host so the live
# dashboard is reachable at http://localhost:8888. Override with --port for a
# second car (e.g. --port 8889).
#
# Usage:
#   ./scripts/run.sh                                  # default launch + name "rossim"
#   ./scripts/run.sh profaccDocker_complex.launch     # pick a launch file
#   ./scripts/run.sh --name egocarB profacc.launch    # custom name (e.g. a 2nd car
#                                                      # with its own ROS master)
#   ./scripts/run.sh --name carB --port 8889 ...       # 2nd car, dashboard on 8889
#
set -e

NAME="${ROSSIM_NAME:-rossim}"
PORT="${ROSSIM_DASH_PORT:-8888}"
LAUNCH=""

while [ $# -gt 0 ]; do
  case "$1" in
    -n|--name) NAME="$2"; shift 2 ;;
    -p|--port) PORT="$2"; shift 2 ;;
    -h|--help)
      grep '^#' "$0" | grep -v '^#!' | sed 's/^# \{0,1\}//'
      exit 0 ;;
    -*) echo "Unknown option: $1" >&2; exit 1 ;;
    *) LAUNCH="$1"; shift ;;
  esac
done
LAUNCH="${LAUNCH:-profaccDocker.launch}"
export ROSSIM_DASH_PORT="$PORT"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$WORKSPACE_DIR"

# The default launch files replay mytest.bag as the lead car.
if [ ! -f "$WORKSPACE_DIR/mytest.bag" ]; then
  echo "WARNING: mytest.bag not found in $WORKSPACE_DIR"
  echo "         Most launch files replay mytest.bag as the lead car and will"
  echo "         wait forever without it. Download hwilexample.bag from"
  echo "         Brightspace and copy it here as mytest.bag first:"
  echo "             cp /path/to/hwilexample.bag mytest.bag"
  echo ""
fi

echo "==> Container name: $NAME   (dashboard port: $PORT)"
echo "==> Open another terminal in it with:  ./scripts/join.sh $NAME"
echo "==> Start the live dashboard with:     ./scripts/dashboard.sh --name $NAME"
echo "==> Building workspace and launching $LAUNCH (Ctrl+C to stop)"
echo ""
# --service-ports publishes the service's ports (compose run does not by default).
exec docker compose run --rm --service-ports --name "$NAME" ros /bin/bash -lc "\
  catkin_make && \
  source devel/setup.bash && \
  roslaunch profacc $LAUNCH"
