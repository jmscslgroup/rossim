#!/usr/bin/env bash
#
# run.sh
#
# Builds the workspace and launches a simulation inside the ROS container via
# Docker Compose -- a one-command shortcut for the build + source + roslaunch
# sequence. By default it runs profaccDocker_complex.launch from the profacc
# package, but any package/launch file in the workspace works.
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
#   ./scripts/run.sh [options] [PACKAGE] [FILE.launch] [arg:=value ...]
#   ./scripts/run.sh [options] path/to/FILE.launch     [arg:=value ...]
#
#   ./scripts/run.sh                                   # profacc profaccDocker_complex.launch
#   ./scripts/run.sh profaccDocker.launch              # another launch file in profacc
#   ./scripts/run.sh myacc myacc_sim.launch            # launch file from another package
#   ./scripts/run.sh --pkg myacc myacc_sim.launch      # same thing, as an option
#   ./scripts/run.sh launch/myproject.launch           # a launch file by path (inside rossim/)
#   ./scripts/run.sh profaccDocker.launch bagfileout:=/ros/catkin_ws/trial1
#                                                      # pass <arg> values to roslaunch
#   ./scripts/run.sh --name egocarB ...                # custom container name (e.g. a 2nd
#                                                      # car with its own ROS master)
#   ./scripts/run.sh --name carB --port 8889 ...       # 2nd car, dashboard on 8889
#   ./scripts/run.sh --port 8890                       # dashboard on 8890 (e.g. Jupyter has 8888)
#
# Options:
#   -k, --pkg PACKAGE   ROS package that holds the launch file (default: profacc)
#   -n, --name NAME     container name (default: rossim)
#   -p, --port PORT     host port for the dashboard (default: 8888, or next free)
#
# Defaults can also come from the environment: ROSSIM_PKG, ROSSIM_LAUNCH,
# ROSSIM_NAME, ROSSIM_DASH_PORT.
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
DEFAULT_PKG="profacc"
DEFAULT_LAUNCH="profaccDocker_complex.launch"
PKG=""
POSITIONAL=()
LAUNCH_ARGS=()      # name:=value pairs, passed through to roslaunch

need_value() {
  if [ $# -lt 2 ] || [ -z "$2" ]; then
    echo "Option $1 needs a value (see ./scripts/run.sh --help)" >&2
    exit 1
  fi
}

while [ $# -gt 0 ]; do
  case "$1" in
    -k|--pkg)  need_value "$@"; PKG="$2"; shift 2 ;;
    -n|--name) need_value "$@"; NAME="$2"; shift 2 ;;
    -p|--port) need_value "$@"; PORT="$2"; PORT_CHOSEN=1; shift 2 ;;
    -h|--help)
      awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"
      exit 0 ;;
    -*) echo "Unknown option: $1 (see ./scripts/run.sh --help)" >&2; exit 1 ;;
    *:=*) LAUNCH_ARGS+=("$1"); shift ;;
    *) POSITIONAL+=("$1"); shift ;;
  esac
done

# Work out what to launch: [PACKAGE] FILE.launch, or a path to a .launch file.
case ${#POSITIONAL[@]} in
  0) LAUNCH="" ;;
  1) LAUNCH="${POSITIONAL[0]}" ;;
  2) if [ -n "$PKG" ]; then
       echo "Give the package either with --pkg or as the first word, not both." >&2
       exit 1
     fi
     PKG="${POSITIONAL[0]}"; LAUNCH="${POSITIONAL[1]}" ;;
  *) echo "Too many arguments: ${POSITIONAL[*]}" >&2
     echo "Expected: [PACKAGE] FILE.launch [arg:=value ...]  (see --help)" >&2
     exit 1 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

LAUNCH_PATH=""      # set when launching a file by path instead of by package
if [ -z "$PKG" ] && [ -n "$LAUNCH" ] && { [[ "$LAUNCH" == */* ]] || [ -f "$LAUNCH" ]; }; then
  # A path: resolve it on the host and map it to the same file in the container.
  if [ ! -f "$LAUNCH" ]; then
    echo "Launch file not found: $LAUNCH" >&2
    exit 1
  fi
  ABS="$(cd "$(dirname "$LAUNCH")" && pwd)/$(basename "$LAUNCH")"
  case "$ABS" in
    "$WORKSPACE_DIR"/*) LAUNCH_PATH="/ros/catkin_ws/${ABS#"$WORKSPACE_DIR"/}" ;;
    *) echo "Launch file must be inside $WORKSPACE_DIR (only that folder is" >&2
       echo "mounted in the container): $LAUNCH" >&2
       exit 1 ;;
  esac
else
  if [ -n "$PKG" ] && [ -z "$LAUNCH" ] && [ -z "${ROSSIM_LAUNCH:-}" ]; then
    echo "Which launch file in package '$PKG'?  e.g. ./scripts/run.sh $PKG FILE.launch" >&2
    exit 1
  fi
  PKG="${PKG:-${ROSSIM_PKG:-$DEFAULT_PKG}}"
  LAUNCH="${LAUNCH:-${ROSSIM_LAUNCH:-$DEFAULT_LAUNCH}}"
fi

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
# Build the roslaunch command, quoting each word for the container's shell.
if [ -n "$LAUNCH_PATH" ]; then
  ROSLAUNCH=(roslaunch "$LAUNCH_PATH")
else
  ROSLAUNCH=(roslaunch "$PKG" "$LAUNCH")
fi
# (the ${arr[@]+...} form keeps an empty array safe on macOS's bash 3.2)
ROSLAUNCH+=(${LAUNCH_ARGS[@]+"${LAUNCH_ARGS[@]}"})
ROSLAUNCH_CMD="$(printf '%q ' "${ROSLAUNCH[@]}")"

echo "==> Building workspace, then: ${ROSLAUNCH[*]}   (Ctrl+C to stop)"
echo ""
# --service-ports publishes the service's ports (compose run does not by default).
exec docker compose run --rm --service-ports --name "$NAME" ros /bin/bash -lc "\
  catkin_make && \
  source devel/setup.bash && \
  $ROSLAUNCH_CMD"
