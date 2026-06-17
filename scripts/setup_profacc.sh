#!/usr/bin/env bash
#
# setup_profacc.sh
#
# Clones the ROS packages needed to run the profacc ACC simulation.
# Run this from the rossim/ root directory.
#
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC_DIR="$WORKSPACE_DIR/src"

REPOS=(
  "https://github.com/jmscslgroup/profacc"
  "https://github.com/jmscslgroup/subtractor"
  "https://github.com/jmscslgroup/odometer"
  "https://github.com/jmscslgroup/carsimplesimulink"
  "https://github.com/jmscslgroup/carcomplexsimulink"
)

echo "==> Setting up profacc workspace in $WORKSPACE_DIR"
echo ""

# Ensure src/ exists
mkdir -p "$SRC_DIR"

# Clone each repo if it doesn't already exist
for repo in "${REPOS[@]}"; do
  name=$(basename "$repo")
  if [ -d "$SRC_DIR/$name" ]; then
    echo "  [skip] $name already exists"
  else
    echo "  [clone] $name"
    git clone "$repo" "$SRC_DIR/$name"
  fi
done

echo ""
echo "==> All packages cloned."
echo ""
echo "Next steps:"
echo "  1. Place a test bag file in $WORKSPACE_DIR/mytest.bag"
echo "     (download hwilexample.bag from Brightspace and copy it here)"
echo ""
echo "  2. Build and run the simulation in one command (uses Docker Compose):"
echo "     cd $WORKSPACE_DIR"
echo "     ./scripts/run.sh"
echo ""
echo "     ...or work interactively in the container:"
echo "     docker compose run --rm ros"
echo "       catkin_make"
echo "       source devel/setup.bash"
echo "       roslaunch profacc profaccDocker.launch"
echo ""
echo "  3. Open another terminal in the running simulation (from the host):"
echo "     ./scripts/join.sh"
