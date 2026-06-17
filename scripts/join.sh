#!/usr/bin/env bash
#
# join.sh
#
# Opens a new interactive bash shell inside a already-running rossim container,
# with the catkin workspace sourced -- so you can run rostopic/rosnode/etc.
# without looking up the container name or typing a long `docker exec` command.
#
# Usage:
#   ./scripts/join.sh                # joins the default container ("rossim")
#   ./scripts/join.sh egocarB        # joins a container started with --name egocarB
#
# (The container name is whatever you passed to ./scripts/run.sh via --name,
#  default "rossim".)
#
set -e

NAME="${1:-${ROSSIM_NAME:-rossim}}"

if ! docker ps --format '{{.Names}}' | grep -qx "$NAME"; then
  echo "No running container named '$NAME'."
  echo ""
  echo "Currently running containers:"
  docker ps --format '  {{.Names}}  ({{.Image}}, {{.Status}})' || true
  echo ""
  echo "Start one first with:  ./scripts/run.sh            (name: rossim)"
  echo "                  or:  ./scripts/run.sh --name $NAME ..."
  exit 1
fi

# Source the workspace if it has been built, then drop into an interactive shell.
exec docker exec -it "$NAME" /bin/bash -lc '
  cd /ros/catkin_ws 2>/dev/null || true
  if [ -f devel/setup.bash ]; then
    source devel/setup.bash
  else
    echo "(note: devel/setup.bash not found yet -- run catkin_make in the main terminal)"
  fi
  exec bash'
