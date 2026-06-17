#!/usr/bin/env bash
#
# dashboard.sh -- start the live web dashboard inside a running rossim container.
#
# A host-side shortcut so you don't have to join the container and type the
# python command by hand. Run the simulation first (./scripts/run.sh), then:
#
#   ./scripts/dashboard.sh                 # mode sim, container "rossim"
#   ./scripts/dashboard.sh --mode live     # superset of fields (real vehicle)
#   ./scripts/dashboard.sh --name carB     # a container started with --name carB
#
# Then open http://localhost:8888 in your browser (the port run.sh published).
#
set -e

NAME="${ROSSIM_NAME:-rossim}"
MODE="sim"

while [ $# -gt 0 ]; do
  case "$1" in
    -n|--name) NAME="$2"; shift 2 ;;
    -m|--mode) MODE="$2"; shift 2 ;;
    -h|--help) grep '^#' "$0" | grep -v '^#!' | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "Unknown option: $1" >&2; exit 1 ;;
    *) echo "Unexpected argument: $1" >&2; exit 1 ;;
  esac
done

if ! docker ps --format '{{.Names}}' | grep -qx "$NAME"; then
  echo "No running container named '$NAME'."
  echo "Start the simulation first:  ./scripts/run.sh"
  exit 1
fi

echo "==> Starting '$MODE' dashboard in container '$NAME'"
echo "==> Open http://localhost:8888 in your browser (or the --port you gave run.sh)"
echo "==> Ctrl+C to stop the dashboard (the simulation keeps running)"
exec docker exec -it "$NAME" /bin/bash -lc "\
  source devel/setup.bash 2>/dev/null || true; \
  python3 /ros/catkin_ws/dashboard/dashboard.py --mode $MODE"
