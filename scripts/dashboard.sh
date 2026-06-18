#!/usr/bin/env bash
#
# dashboard.sh -- start the live dashboard inside a running rossim container.
#
# A host-side shortcut so you don't have to join the container and type the
# python command by hand. Run the simulation first (./scripts/run.sh), then:
#
#   ./scripts/dashboard.sh                 # web dashboard, mode sim, container "rossim"
#   ./scripts/dashboard.sh --mode live     # superset of fields (real vehicle)
#   ./scripts/dashboard.sh --name carB     # a container started with --name carB
#   ./scripts/dashboard.sh --text          # TEXT dashboard in this terminal (no browser)
#
# Web dashboard: open http://localhost:8888 in your browser (the port run.sh
# published). Text dashboard: renders right here in the terminal.
#
set -e

NAME="${ROSSIM_NAME:-rossim}"
MODE="sim"
TEXT=0

while [ $# -gt 0 ]; do
  case "$1" in
    -n|--name) NAME="$2"; shift 2 ;;
    -m|--mode) MODE="$2"; shift 2 ;;
    -t|--text) TEXT=1; shift ;;
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

if [ "$TEXT" -eq 1 ]; then
  SCRIPT="dashboard_tui.py"
  echo "==> Starting '$MODE' TEXT dashboard in container '$NAME' (Ctrl+C to stop)"
else
  SCRIPT="dashboard.py"
  echo "==> Starting '$MODE' web dashboard in container '$NAME'"
  echo "==> Open http://localhost:8888 in your browser (or the --port you gave run.sh)"
  echo "==> Ctrl+C to stop the dashboard (the simulation keeps running)"
fi

exec docker exec -it "$NAME" /bin/bash -lc "\
  source devel/setup.bash 2>/dev/null || true; \
  python3 /ros/catkin_ws/dashboard/$SCRIPT --mode $MODE"
