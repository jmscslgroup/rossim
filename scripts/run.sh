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
# second car (e.g. --port 8889), or if 8888 is already used by something else
# (Jupyter uses 8888 by default). If you don't pass --port and 8888 is busy,
# the next free port (8889, 8890, ...) is picked automatically and printed.
#
# Usage:
#   ./scripts/run.sh                                  # default launch + name "rossim"
#   ./scripts/run.sh profaccDocker_complex.launch     # pick a launch file
#   ./scripts/run.sh --name egocarB profacc.launch    # custom name (e.g. a 2nd car
#                                                      # with its own ROS master)
#   ./scripts/run.sh --name carB --port 8889 ...       # 2nd car, dashboard on 8889
#   ./scripts/run.sh --port 8890                       # dashboard on 8890 (e.g. Jupyter has 8888)
#
set -e

# Git Bash / MSYS on Windows rewrites arguments that look like Unix paths
# (e.g. /bin/bash -> C:/Program Files/Git/usr/bin/bash) before Docker sees them,
# which breaks the container. Turn that rewriting off; harmless elsewhere.
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

NAME="${ROSSIM_NAME:-rossim}"
PORT="${ROSSIM_DASH_PORT:-8888}"
PORT_CHOSEN="${ROSSIM_DASH_PORT:+1}"   # 1 if the user picked the port
LAUNCH=""

while [ $# -gt 0 ]; do
  case "$1" in
    -n|--name) NAME="$2"; shift 2 ;;
    -p|--port) PORT="$2"; PORT_CHOSEN=1; shift 2 ;;
    -h|--help)
      grep '^#' "$0" | grep -v '^#!' | sed 's/^# \{0,1\}//'
      exit 0 ;;
    -*) echo "Unknown option: $1" >&2; exit 1 ;;
    *) LAUNCH="$1"; shift ;;
  esac
done
LAUNCH="${LAUNCH:-profaccDocker.launch}"

# Is something on the host already using this port? (Jupyter, another sim's
# dashboard, ...) Docker doesn't always refuse a clash -- it can publish the
# port anyway, and then http://localhost:PORT silently reaches the wrong thing.
port_in_use() {
  (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null && return 0
  docker ps --format '{{.Ports}}' 2>/dev/null | grep -q ":$1->"
}

if port_in_use "$PORT"; then
  if [ -n "$PORT_CHOSEN" ]; then
    echo "ERROR: port $PORT is already in use on this machine (Jupyter? another sim?)." >&2
    echo "       Pick another, e.g.:  ./scripts/run.sh --port $((PORT + 2)) ..." >&2
    exit 1
  fi
  for try in $(seq $((PORT + 1)) $((PORT + 20))); do
    if ! port_in_use "$try"; then
      echo "NOTE: port $PORT is already in use (Jupyter uses 8888 by default)."
      echo "      Using port $try for the dashboard instead."
      echo ""
      PORT="$try"
      break
    fi
  done
fi
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

echo "==> Container name: $NAME   (dashboard: http://localhost:$PORT)"
echo "==> Open another terminal in it with:  ./scripts/join.sh $NAME"
echo "==> Start the live dashboard with:     ./scripts/dashboard.sh --name $NAME"
echo "==> Building workspace and launching $LAUNCH (Ctrl+C to stop)"
echo ""
# --service-ports publishes the service's ports (compose run does not by default).
exec docker compose run --rm --service-ports --name "$NAME" ros /bin/bash -lc "\
  catkin_make && \
  source devel/setup.bash && \
  roslaunch profacc $LAUNCH"
