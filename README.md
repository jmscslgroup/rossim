# rossim -- ROS Simulation for Adaptive Cruise Control

A ROS 1 (Noetic) catkin workspace for simulating Adaptive Cruise Control (ACC) in a Dockerized environment. Developed for Vanderbilt University's CS 3892 *Autonomous Vehicles & Traffic* course.

Recorded driving data from a real vehicle is replayed as a lead car, and one or more simulated ego vehicles follow it using an ACC controller -- all running as ROS nodes inside a Docker container.

---

## Step 1: Clone this repository

```bash
git clone https://github.com/jmscslgroup/rossim rossim
cd rossim
```

This gives you the workspace skeleton: launch files, setup scripts, and this README. The ROS packages themselves are cloned in Step 4.

---

## Step 2: Install and verify Docker

### Install Docker

- **macOS / Windows:** Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- **Linux:** Install [Docker Engine](https://docs.docker.com/engine/install/)

### Pull the ROS Docker image

```bash
docker pull sprinkjm/rosempty:latest
```

### Verify Docker works

Run the image and confirm you get a shell prompt:

```bash
docker run --rm -it sprinkjm/rosempty:latest /bin/bash
```

You should see a root prompt like `root@<container_id>:/#`. Inside it, verify ROS is available:

```bash
roscore &
sleep 2 && rostopic list
```

You should see `/rosout` and `/rosout_agg` listed. If so, ROS is working. Type `exit` to leave the container.

---

## Step 3: Verify the workspace mount

This step confirms that your host files are visible inside the container.

From the `rossim/` directory on your host:

```bash
docker run --rm --mount type=bind,source=$(pwd),target=/ros/catkin_ws -it sprinkjm/rosempty:latest ls /ros/catkin_ws
```

You should see `README.md`, `scripts/`, `src/`, etc. -- the contents of your `rossim/` directory. If you see an empty listing or an error, double-check the path and that Docker has permission to access the directory.

---

## Step 4: Clone the ROS packages for profacc

A setup script clones all the packages needed for the profacc ACC simulation:

```bash
./scripts/setup_profacc.sh
```

This clones the following into `src/`:

| Package | Description |
|---------|-------------|
| [profacc](https://github.com/jmscslgroup/profacc) | Time-headway ACC controller (Simulink-generated) |
| [subtractor](https://github.com/jmscslgroup/subtractor) | Computes difference of two Float64 topics |
| [odometer](https://github.com/jmscslgroup/odometer) | Integrates velocity to produce position |
| [carsimplesimulink](https://github.com/jmscslgroup/carsimplesimulink) | Simple point-mass vehicle model |
| [carcomplexsimulink](https://github.com/jmscslgroup/carcomplexsimulink) | Higher-fidelity vehicle model |

---

## Step 5: Add a test bag file

Download the example bag file from Brightspace (`hwilexample.bag`) and place it in the `rossim/` root directory as `mytest.bag`:

```bash
cp /path/to/hwilexample.bag mytest.bag
```

This file contains a recorded velocity trace from a real vehicle and is replayed as the lead car in simulation.

---

## Step 6: Build the workspace

Launch the Docker container with the workspace mounted:

```bash
docker run --mount type=bind,source=$(pwd),target=/ros/catkin_ws -it sprinkjm/rosempty:latest
```

Inside the container, build:

```bash
catkin_make
```

If the build succeeds you will see a summary like:

```
[100%] Built target profacc
[100%] Built target carsimplesimulink
...
```

Then source the workspace:

```bash
source devel/setup.bash
```

---

## Step 7: Run the profacc simulation

```bash
roslaunch profacc profaccDocker.launch
```

You will see ROS start up several nodes. The bag file replays the lead car velocity trace, the ACC controller computes acceleration commands, and the ego car model responds. All topics are recorded to a new bag file (`profacc_*.bag`) in the workspace root.

When the bag file finishes playing (or you want to stop early), press **Ctrl+C**.

### What to expect

The terminal will show log output from the various nodes. To see the simulation in action, open a second terminal and connect to the running container:

```bash
# Find the container name
docker ps

# Connect to it
docker exec -it <container_name> /bin/bash
source /ros/catkin_ws/devel/setup.bash
```

Then try:

```bash
# List all active topics
rostopic list

# Watch the ego car velocity in real time
rostopic echo /egocar/car/state/vel_x

# Watch the ACC acceleration commands
rostopic echo /egocar/cmd_accel
```

---

## How the Simulation Works

Each Docker launch file sets up this pipeline:

```
 Recorded bag file          Lead car             Ego car
 (real driving data)        (odometer)           (ACC + vehicle model)
        |                      |                       |
  /leadcar/car/state/vel_x    odom_x      profacc <-- subtractor (rel_vel)
                                    \       |    \--- subtractor (lead_dist)
                                     \      v
                                      carsimplesimulink --> vel_x, odom_x
```

1. **`rosbag play`** replays the recorded velocity trace as the lead car
2. **`odometer`** integrates lead car velocity into position
3. **`subtractor`** nodes compute relative velocity and distance between lead and ego
4. **`profacc`** computes an acceleration command using the ACC control law
5. **`carsimplesimulink`** simulates the ego car's response to that command
6. **`rosbag record`** captures everything to a new bag file

---

## The profacc Control Law

The controller implements a time-headway ACC law:

```
cmd_accel = alpha * (lead_dist - tau * vel_x) + lambda * rel_vel
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `alpha`   | 1.1     | Proportional gain |
| `tau`     | 2.0     | Time headway (seconds) |
| `lambda`  | 0.1     | Relative velocity gain |

Output is saturated to **[-3.0, 1.5] m/s^2**.

### ROS Interface

| Direction   | Topic              | Type                | Description |
|-------------|--------------------|---------------------|-------------|
| Subscribes  | `car/state/vel_x`  | `std_msgs/Float64`  | Ego car velocity |
| Subscribes  | `lead_dist`        | `std_msgs/Float64`  | Distance to lead car |
| Subscribes  | `rel_vel`          | `std_msgs/Float64`  | Relative velocity (lead - ego) |
| Publishes   | `cmd_accel`        | `std_msgs/Float64`  | Acceleration command |

Parameters can be changed at runtime:

```bash
rosparam set /egocar/profacc_node/tau 3.0
```

---

## Available Launch Files

All Docker launch files are in `src/profacc/launch/`:

| Launch file | Ego cars | Vehicle model | Description |
|-------------|----------|---------------|-------------|
| `profaccDocker.launch` | 1 | simple | Basic scenario. Replays `mytest.bag` from t=100s. Lead starts at x=20m. |
| `profaccDocker_test1.launch` | 1 | simple | Ego starts closer (x0=15m) and faster (v0=2.5 m/s). |
| `profaccDocker_test2.launch` | 1 | complex | Adds 10m extra buffer to `lead_dist`. |
| `profaccDocker_complex.launch` | 1 | complex | Same as basic but with the complex vehicle model. |
| `profaccDocker_homework3.launch` | 1 | complex | Uses a different bag file, starts at t=310s. |
| `profaccDocker_homework3extra.launch` | 4 | complex | Multi-car cascade (see below). |

### Multi-car cascade

`profaccDocker_homework3extra.launch` chains 4 ACC-controlled vehicles behind a lead car:

```
leadcar (x0=120m) --> egocar (x0=100m) --> egocar1 (x0=70m) --> egocar2 (x0=45m) --> egocar3 (x0=20m)
```

Each ego car runs its own `profacc` node and follows the car directly ahead. This is useful for studying string stability -- how disturbances propagate (or dampen) through a platoon.

```bash
roslaunch profacc profaccDocker_homework3extra.launch
```

---

## Post-Processing with MATLAB

After a simulation, the recorded `.bag` file is written to the `rossim/` directory. Open MATLAB, run the provided `testResult` script, and select the bag file when prompted.

---

## Useful Repositories

- https://github.com/jmscslgroup/profacc
- https://github.com/jmscslgroup/subtractor
- https://github.com/jmscslgroup/odometer
- https://github.com/jmscslgroup/carsimplesimulink
- https://github.com/jmscslgroup/carcomplexsimulink
- https://github.com/jmscslgroup/cs3891proj2023
