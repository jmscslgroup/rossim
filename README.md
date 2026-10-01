# rossim -- ROS Simulation for Adaptive Cruise Control

A ROS 1 (Noetic) catkin workspace for simulating Adaptive Cruise Control (ACC) in a Dockerized environment. Developed for Vanderbilt University's CS 3892 *Autonomous Vehicles & Traffic* course.

Recorded driving data from a real vehicle is replayed as a lead car, and one or more simulated ego vehicles follow it using an ACC controller -- all running as ROS nodes inside a Docker container.

## Citation
To cite the usage of this repository, use the following:

Kate Sanborn, Daniel B. Work, Jonathan Sprinkle. "Single Vehicle to Traffic Scale: a Model-Based Workflow." in 2026 IEEE International Conference on Intelligent Transportation Systems (ITSC), (in press) 2026.

or using bibtex:

```
@inproceedings{sanborn2026single,
  author    = {Sanborn, Kate and Work, Daniel B. and Sprinkle, Jonathan},
  title      = {Single Vehicle to Traffic Scale: A Model-Based Workflow},
  booktitle  = {2026 IEEE International Conference on Intelligent Transportation Systems (ITSC)},
  year       = {2026},
  note       = {in press}
}
```

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
docker pull sprinkjm/rosempty
```

### Verify Docker works

Run the image and confirm you get a shell prompt:

```bash
docker run --rm -it sprinkjm/rosempty /bin/bash
```

You should see a root prompt like `root@<container_id>:/#`. Inside it, verify ROS is available:

```bash
roscore &
sleep 2 && rostopic list
```

You should see `/rosout` and `/rosout_agg` listed. If so, ROS is working. Type `exit` to leave the container.

---

## Step 3: Verify the workspace mount

This step confirms that your host files are visible inside the container. We use
[Docker Compose](https://docs.docker.com/compose/) (included with Docker Desktop
and modern Docker Engine) so you don't have to type long `docker run --mount ...`
commands -- the image and mount are defined once in `compose.yaml`.

From the `rossim/` directory on your host:

```bash
docker compose run --rm ros ls
```

You should see `README.md`, `scripts/`, `src/`, etc. -- the contents of your
`rossim/` directory, which is mounted at `/ros/catkin_ws` inside the container.
If you see an empty listing or an error, double-check that you are in the
`rossim/` directory and that Docker has permission to access it.

---

## Optional: a `rosempty` command-line shortcut

`docker compose` only works from inside `rossim/`. For everyday ROS chores
-- inspecting a bag with `rosbag info`, repairing a bag, poking around with
ROS tools -- it is handy to have one short command that starts the container
**on whatever folder you are currently in**. That is what
[`scripts/rosempty`](scripts/rosempty) does:

```bash
rosempty                              # interactive ROS shell in the current folder
rosempty rosbag info mytest.bag       # run a single command, then exit
```

The current folder is mounted at `/ros/catkin_ws` inside the container (the
same place `compose.yaml` puts it), so files you see on the host are the files
the container sees, and anything the container writes (a repaired bag, a new
recording) shows up back in that folder. The container is removed when you
exit.

> **Where to run it:** normally, run `rosempty` from your `rossim/` clone (or
> the folder holding the bag files you're working with). If that folder has
> been built with `catkin_make`, `devel/setup.bash` is sourced for you, so your
> packages work too. It runs fine from **any** folder, but only that folder
> (and its subfolders) will be visible inside the container -- e.g. you can't
> reach `../other.bag`. `cd` to the right place first.

### Install it (once)

Put the script on your `PATH`. The easiest way is a symlink into a personal
`bin` folder, so it stays up to date when you `git pull`. From the `rossim/`
directory:

```bash
mkdir -p ~/.local/bin
ln -sf "$PWD/scripts/rosempty" ~/.local/bin/rosempty
```

Then make sure `~/.local/bin` is on your `PATH`. Add this line to your shell's
startup file -- **`~/.zshrc`** if you use zsh (the macOS default) or
**`~/.bashrc`** if you use bash (most Linux / WSL setups):

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Not sure which shell you have? Run `echo $SHELL`. Open a **new terminal** (or
run `source ~/.zshrc` / `source ~/.bashrc`) and check that it works:

```bash
which rosempty     # should print .../.local/bin/rosempty
cd ~/Downloads     # or any folder
rosempty ls        # lists the folder's contents, as seen from inside the container
```

<details>
<summary>Alternatives: put <code>scripts/</code> on your PATH, or use an alias</summary>

Instead of the symlink, you can add the whole `scripts/` folder to your `PATH`
in `~/.zshrc` / `~/.bashrc` (replace the path with where you cloned `rossim`):

```bash
export PATH="$HOME/path/to/rossim/scripts:$PATH"
```

Or define an alias:

```bash
alias rosempty="$HOME/path/to/rossim/scripts/rosempty"
```

If you skip installing entirely, `rossim/scripts/rosempty` still works when
called by its full path from any folder.
</details>

### Common uses

```bash
# Summary of a bag: duration, topics, message counts
rosempty rosbag info mytest.bag

# Repair a bag whose recording was interrupted (Ctrl+C, crash, power loss).
# "rosbag info" will report the bag is unindexed. reindex fixes it in place
# and keeps the original as broken.orig.bag.
rosempty rosbag reindex broken.bag

# Migrate a bag recorded with older message definitions
rosempty rosbag fix old.bag fixed.bag

# Pull one topic out of a bag into CSV
rosempty bash -c "rostopic echo -b mytest.bag -p /leadcar/car/state/vel_x > vel_x.csv"
```

Run `rosempty --help` for all options. A few details:

- Commands containing shell features (`>`, `|`, `&&`, `*`) need to be wrapped
  in `bash -c "..."`, as in the CSV example above. Otherwise your host shell
  handles them, not the container.
- `rosempty -p 8888 ...` also publishes a port to the host (for example, to view
  a dashboard).
- Each `rosempty` call starts its **own** fresh container with no `roscore`
  running. Use it for standalone tools like `rosbag`. To talk to a running
  simulation, use `./scripts/join.sh` instead (see Step 7).
- **Linux only:** files created by the container are owned by `root`. Fix
  them with `sudo chown $USER <file>` if needed. (macOS and Windows Docker
  Desktop map ownership to your user automatically.)
- **Windows:** run it from WSL (recommended) or Git Bash, not PowerShell/cmd.

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

Open an interactive shell in the container (the workspace is already mounted):

```bash
docker compose run --rm ros
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

If you are already in the container shell from Step 6 (with the workspace
sourced), launch directly:

```bash
roslaunch profacc profaccDocker.launch
```

Or, from your host, use the one-command shortcut that builds, sources, and
launches in a fresh container:

```bash
./scripts/run.sh                          # default: profaccDocker.launch
./scripts/run.sh profaccDocker_complex.launch   # any launch file in src/profacc/launch/
```

You will see ROS start up several nodes. The bag file replays the lead car velocity trace, the ACC controller computes acceleration commands, and the ego car model responds. All topics are recorded to a new bag file (`profacc_*.bag`) in the workspace root.

When the bag file finishes playing (or you want to stop early), press **Ctrl+C**.

### What to expect

The terminal will show log output from the various nodes. To see the simulation
in action, open a **second terminal on your host** and join the running
container (the workspace is sourced for you automatically):

```bash
./scripts/join.sh
```

`join.sh` connects to the container named `rossim` (the default that
`run.sh` creates), so there is no need to look up the container name or type a
long `docker exec` command. If you started the simulation with a custom name
(`./scripts/run.sh --name egocarB ...`), pass the same name: `./scripts/join.sh egocarB`.

Then try:

```bash
# List all active topics
rostopic list

# Watch the ego car velocity in real time
rostopic echo /egocar/car/state/vel_x

# Watch the ACC acceleration commands
rostopic echo /egocar/cmd_accel
```

### Running two simulations at once (separate ROS masters)

Each `run.sh` invocation starts its own container with its own `roscore`, so you
can run two independent simulations side by side -- just give them different
names. In two host terminals:

```bash
./scripts/run.sh --name carA --port 8888 profaccDocker.launch
./scripts/run.sh --name carB --port 8889 profaccDocker_complex.launch
```

Give each one a different `--port` so their dashboards don't collide on the host
(carA on `localhost:8888`, carB on `localhost:8889`). Join either one from
another terminal:

```bash
./scripts/join.sh carA
./scripts/join.sh carB
```

Because each container has its own ROS master, the two simulations do not see
each other's topics -- they are fully isolated.

---

## Live Dashboard

A small web dashboard shows the cars in the simulation updating in real time in
your browser. It runs as a ROS node and needs **no extra software** -- just
`rospy` and the Python standard library (details in
[`dashboard/README.md`](dashboard/README.md)). It has two views:

- **Overhead** -- an ego-centric top-down view of the selected car, the car
  ahead, and any cars behind, placed by their odometry.
- **Data** -- value tiles for the selected car (speed, commanded acceleration,
  lead distance, relative velocity, odometer).

The dashboard **discovers the cars** automatically (any namespace publishing
`car/state/vel_x`), so `leadcar`, `egocar`, `egocar1`, ... all appear as
buttons at the top -- click to **swap** which car you are watching. This works
for a single car or a whole platoon.

With a simulation running (`./scripts/run.sh`), start the dashboard from a second
host terminal:

```bash
./scripts/dashboard.sh
```

Then open <http://localhost:8888> in your browser. Press **Ctrl+C** to stop the
dashboard; the simulation keeps running.

### Text dashboard (SSH / no browser)

When you are logged into the car over SSH with no web access, use the text
version instead. It does the same car discovery and prints a refreshing table
(plus a front-to-back ordering) right in the terminal -- no browser, no ports:

```bash
./scripts/dashboard.sh --text            # the sim, in the container
# or, directly on the real vehicle where ROS is sourced:
python3 dashboard/dashboard_tui.py --mode live
```

There are two modes:

| Mode | What it shows |
|------|---------------|
| `sim` (default) | the fields available in simulation |
| `live` | the same fields plus extra real-vehicle fields, for running on the actual car |

```bash
./scripts/dashboard.sh --mode live
```

The `live` set is a superset that grows as real-car topics come online -- see
`dashboard/dashboard.py` (the `LIVE_EXTRA_FIELDS` list) and `dashboard/README.md`.

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
