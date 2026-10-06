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

## Step 0: Install your tools (macOS and Windows differ!)

Every later step is the same on all platforms **once you have a Linux-style
terminal with `docker` and `git`**. Getting there is the one place where macOS
and Windows diverge:

|  | macOS | Windows | Linux |
|--|-------|---------|-------|
| Terminal to use | Terminal (zsh) | **Ubuntu in WSL** (not PowerShell, cmd, or Git Bash) | your usual terminal |
| Docker | Docker Desktop | Docker Desktop **+ WSL integration for Ubuntu** | Docker Engine + compose plugin |
| git | Xcode Command Line Tools | comes with Ubuntu | your package manager |
| Clone the repo into | anywhere, e.g. `~/cs3892` | WSL home, `~` (**not** `/mnt/c/...`) | anywhere |
| Shell startup file | `~/.zshrc` | `~/.bashrc` | `~/.bashrc` (usually) |

### macOS

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
   (pick **Apple Silicon** or **Intel** to match *Apple menu → About This Mac*).
   Start it and wait until it reports the engine is running.
2. Open **Terminal** and run `git --version`. If git is missing, macOS offers to
   install the Command Line Tools; accept.

### Windows: use WSL (Ubuntu)

The helper scripts (`./scripts/*.sh`) are Linux shell scripts. If you type them
into **PowerShell** or **cmd**, Windows pops up a dialog asking which program
should open the `.sh` file. (Windows Terminal and the VS Code terminal open
PowerShell by default.) Do every step in this README in an **Ubuntu (WSL)**
terminal instead:

1. Install WSL **with Ubuntu** once, from an administrator PowerShell, then reboot:
   ```powershell
   wsl --install -d Ubuntu
   ```
   The first time Ubuntu opens, it asks you to create a Linux username and password.
2. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
   (keep the default "Use WSL 2" option). In Docker Desktop, open
   **Settings → Resources → WSL integration** and turn it on for **Ubuntu**.
3. Make Ubuntu the default, so `wsl` doesn't drop you into Docker's own
   internal distribution. In PowerShell:
   ```powershell
   wsl -l -v                      # lists Ubuntu, docker-desktop, ...
   wsl --set-default Ubuntu
   ```
   `docker-desktop` (and `docker-desktop-data` on older versions) belong to
   Docker Desktop. They are normal and must stay installed, but **never work
   in them**: they have no `git` and odd prompts like `/tmp/docker-desktop-root/...#`.
4. Open a WSL shell: the **Ubuntu** app from the Start menu, the Ubuntu tab in
   Windows Terminal, or type `wsl` in PowerShell. You're in the right place when
   the prompt looks like `you@PC:~$`, not `PS C:\Users\you>` or `...docker-desktop...#`.
5. Clone **inside WSL's home folder** (`cd ~` first, in Step 1), not under
   `/mnt/c/...`. Docker mounts are much faster there, and Git for Windows won't
   convert the scripts to Windows line endings. You can still open the folder
   from Windows Explorer (see below), or in VS Code with `code .`.

**Moving files between Windows and WSL.** The two see each other's files at
these paths:

| From | To reach | Use this path |
|------|----------|---------------|
| Windows (Explorer, MATLAB, ...) | your WSL home | `\\wsl.localhost\Ubuntu\home\<linux-user>` (older Windows 10: `\\wsl$\Ubuntu\...`), or **Linux → Ubuntu** in Explorer's sidebar |
| Ubuntu (WSL) | your Windows files | `/mnt/c/Users/<windows-user>/` (e.g. `.../Downloads`) |

- From inside WSL, `explorer.exe .` opens the current folder in Windows Explorer.
  Drag files in and out there.
- Copy a download into the repo from the Ubuntu terminal:
  `cp /mnt/c/Users/<windows-user>/Downloads/hwilexample.bag ~/rossim/mytest.bag`
- Your Linux and Windows usernames can differ. `ls /mnt/c/Users` lists the
  Windows ones. If the distribution is called `Ubuntu-22.04` or similar,
  `wsl -l` in PowerShell shows the exact name to use in the path.
- Use the files **in place** from Windows (e.g. open a recorded `profacc_*.bag`
  in MATLAB via the `\\wsl.localhost\...` path) or copy them out; just keep the
  repo itself inside WSL.

Seeing `/usr/bin/env: 'bash\r': No such file or directory`? The scripts got
Windows (CRLF) line endings, usually from cloning with Git for Windows. In the
Ubuntu terminal, from inside `rossim/`:

```bash
sed -i 's/\r$//' scripts/*.sh scripts/rosempty   # quick fix: strip the CRs
git config --global core.autocrlf false           # keep WSL's git from converting
```

For a clean long-term setup, re-clone inside WSL's home folder as in item 5
and copy over your `mytest.bag` and any files of your own.

### Linux

Install [Docker Engine](https://docs.docker.com/engine/install/) and the
Docker Compose plugin, then let your user run Docker without `sudo`:

```bash
sudo usermod -aG docker $USER     # then log out and back in
```

### Check (all platforms)

In the terminal from above (on Windows: the Ubuntu terminal):

```bash
git --version
docker --version
docker compose version
```

All three should print a version. `Cannot connect to the Docker daemon`
means Docker Desktop isn't running (or, on Windows, WSL integration is off for Ubuntu).

---

## Step 1: Clone this repository

In your terminal from Step 0 (Windows: the Ubuntu terminal, after `cd ~`):

```bash
git clone https://github.com/jmscslgroup/rossim rossim
cd rossim
```

This gives you the workspace skeleton: launch files, setup scripts, and this README. The ROS packages themselves are cloned in Step 4.

---

## Step 2: Pull and verify the ROS image

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
- **Linux and Windows (WSL):** files created by the container may be owned by
  `root`. Fix them with `sudo chown $USER <file>` if needed. (macOS Docker
  Desktop maps ownership to your user automatically.)
- **Windows:** run it from the Ubuntu (WSL) terminal (see Step 0), not
  PowerShell or cmd.

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

On Windows, run this in the Ubuntu terminal; your Windows Downloads folder is
`/mnt/c/Users/<windows-user>/Downloads/` (see Step 0).

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
roslaunch profacc profaccDocker_complex.launch
```

Or, from your host, use the one-command shortcut that builds, sources, and
launches in a fresh container:

```bash
./scripts/run.sh                                   # default: profacc profaccDocker_complex.launch
./scripts/run.sh profaccDocker.launch              # another launch file in src/profacc/launch/
```

You will see ROS start up several nodes. The bag file replays the lead car velocity trace, the ACC controller computes acceleration commands, and the ego car model responds. All topics are recorded to a new bag file (`profacc_complex_*.bag` for the default) in the workspace root.

### Choosing what `run.sh` launches

`run.sh` takes the same `PACKAGE FILE.launch` words as `roslaunch`, so you can
run a launch file from **any** package in `src/` (for example your own
generated controller) without editing the script:

```bash
./scripts/run.sh myacc myacc_sim.launch            # launch file from another package
./scripts/run.sh --pkg myacc myacc_sim.launch      # same thing, as an option
./scripts/run.sh launch/myproject.launch           # a launch file by path (inside rossim/)
./scripts/run.sh profaccDocker.launch bagfileout:=/ros/catkin_ws/trial1
                                                   # set a launch file <arg>
```

| You give | It runs |
|----------|---------|
| nothing | `roslaunch profacc profaccDocker_complex.launch` |
| `FILE.launch` | `roslaunch profacc FILE.launch` |
| `PACKAGE FILE.launch` or `--pkg PACKAGE FILE.launch` | `roslaunch PACKAGE FILE.launch` |
| a path such as `launch/x.launch` | `roslaunch /ros/catkin_ws/launch/x.launch` |
| `name:=value` (any number) | passed on to `roslaunch` as launch arguments |

These combine with `--name` and `--port`. The workspace is rebuilt with
`catkin_make` first, so a package you just added to `src/` is found
automatically. Run `./scripts/run.sh --help` for the full list.

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

Then open the URL it prints (normally <http://localhost:8888>) in your browser.
Press **Ctrl+C** to stop the dashboard; the simulation keeps running.

**Port 8888 already taken (e.g. Jupyter)?** The host port is chosen when
`run.sh` starts the container, not by `dashboard.sh`. If 8888 is busy,
`run.sh` automatically uses the next free port (8889, 8890, ...) and prints it,
and `dashboard.sh` prints the matching URL. To choose the port yourself,
restart the simulation with:

```bash
./scripts/run.sh --port 8890
```

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

`alpha` and `tau` are read from the parameter server on every step, in the
car's namespace (`/egocar/alpha`, `/egocar/tau` -- not under the node name), so
they can be changed while the simulation runs (`lambda` is fixed in the model):

```bash
rosparam set /egocar/tau 3.0
```

To set them from a launch file, put `<param name="tau" value="3.0" />` inside
the `<group ns="egocar">` block.

---

## Available Launch Files

All Docker launch files are in `src/profacc/launch/`:

| Launch file | Ego cars | Vehicle model | Description |
|-------------|----------|---------------|-------------|
| `profaccDocker.launch` | 1 | simple | Basic scenario. Replays `mytest.bag` from t=100s. Lead starts at x=20m. |
| `profaccDocker_test1.launch` | 1 | simple | Ego starts closer (x0=15m) and faster (v0=2.5 m/s). |
| `profaccDocker_test2.launch` | 1 | complex | Adds 10m extra buffer to `lead_dist`. |
| `profaccDocker_complex.launch` | 1 | complex | Same as basic but with the complex vehicle model. **Default for `run.sh`.** |

---

## Your own launch files

### A project scenario

Don't edit the provided files in `src/profacc/` (a cloned repo -- a `git pull`
could overwrite your changes). Copy the closest one into a `launch/` folder in
`rossim/` and edit the copy:

```bash
mkdir -p launch
cp src/profacc/launch/profaccDocker_complex.launch launch/myproject.launch
```

Typical edits: initial conditions (`/leadcar/x0`, `/egocar/v0`, ...), where
the bag starts (`-s N` skips the first N seconds), controller gains (see
above), and the output bag name (`bagfileout`). Paths inside launch files are
**container** paths: `/ros/catkin_ws` is your `rossim/` folder.

Check the file without running it, then run it:

```bash
./scripts/rosempty roslaunch --nodes launch/myproject.launch   # lists the nodes it would start
./scripts/run.sh launch/myproject.launch
```

### Your generated (Simulink) controller

Building a Simulink model for ROS produces a catkin package named after the
model. Put it in `src/` (e.g. `src/myacc/`, containing `package.xml`), and give
it its own launch file:

```bash
mkdir -p src/myacc/launch
cp launch/myproject.launch src/myacc/launch/myacc_sim.launch
```

In the copy, **replace** the profacc node inside `<group ns="egocar">` (don't
add yours beside it, or two controllers publish `cmd_accel`):

```xml
<!-- was: <node pkg="profacc" type="profacc" name="profacc_node" /> -->
<node pkg="myacc" type="myacc" name="myacc_node" output="screen">
  <remap from="my_accel" to="cmd_accel" />   <!-- only if your topic names differ -->
</node>
```

Your node should subscribe to `car/state/vel_x`, `lead_dist` and `rel_vel`
and publish `cmd_accel` (names without a leading `/` land in `/egocar/...`).
Then build and run it -- `run.sh` runs `catkin_make` first:

```bash
./scripts/run.sh myacc myacc_sim.launch
# second terminal: ./scripts/join.sh, then
rosnode list                       # /egocar/myacc_node there?
rostopic info /egocar/cmd_accel    # published by myacc_node?
```

Regenerate and re-copy the package whenever the model changes.

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
