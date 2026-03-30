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
echo "  2. Launch Docker:"
echo "     cd $WORKSPACE_DIR"
echo "     docker run --mount type=bind,source=\$(pwd),target=/ros/catkin_ws -it sprinkjm/rosempty:latest"
echo ""
echo "  3. Inside the container, build and run:"
echo "     catkin_make"
echo "     source devel/setup.bash"
echo "     roslaunch profacc profaccDocker.launch"
