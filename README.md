# SO-101 arm setup — CAS Physical AI & Robotics, Module C

How to get an SO-ARM101 from "assembled" to "moving in simulation and on the real arm"
with ROS 2 Jazzy. Used in Session 2 (URDF/Xacro), Session 3 (Gazebo + ros2_control)
and Session 8 (MoveIt pick).

Status of each part: ✅ tested end to end · 🚧 not tested yet / still being written.

## How the pieces fit together

```
SO-101 arm ──USB── laptop / Jetson ──network── cluster (RAP or RunPod)
                   servo driver only           Gazebo, RViz, MoveIt, your nodes
```

The arm is a USB device, so a small driver always runs on the computer it is plugged
into. Everything heavy (Gazebo, RViz, MoveIt) runs on the cluster, so you never need a
GPU or a ROS install on your own laptop for the simulation parts.

## What's in this repo

| Folder | Convention | Contents |
|---|---|---|
| `so_arm101_moveit_config/` | `<robot>_moveit_config` | MoveIt config for the SO-101: SRDF, kinematics, planners, controllers, RViz, `demo.launch.py` |
| `setup.sh` | — | loads ROS and the workspace (Part 2) |

The robot model itself (URDF/Xacro, meshes) is not here: it comes from
`so_arm101_description` in [ros2_so_arm](https://github.com/ros-physical-ai/ros2_so_arm).
The students' pick code will get its own package (`so101_pick_lab`).

**Tested with:** Ubuntu 24.04 laptop · LeRobot v0.6.1 (source, commit `2774d9bd`) ·
Python 3.12 · ROS 2 Jazzy on the RAP cluster · `ros2_so_arm` + `feetech_ros2_driver` `main`.

---

## Part 1 — Prepare the arm (once per arm) ✅

Done on a Linux laptop with both arms plugged in via USB. This writes the servo IDs
and calibration into the servos themselves, so it survives unplugging and is later
used by the ROS driver too.

### 1.1 Python environment

LeRobot supports Python 3.12 and 3.13 only. On Python 3.14 every command crashes with
`TypeError: str | None is not callable`, so use a dedicated environment:

```bash
conda create -y -n lerobot -c conda-forge python=3.12 ffmpeg
conda activate lerobot
pip install "lerobot[feetech,core_scripts]==0.6.1"
```

- `feetech` — driver for the STS3215 servos.
- `core_scripts` — dataset tools, keyboard controls and the Rerun viewer.

Every later command in Part 1 assumes `conda activate lerobot`.

### 1.2 Permission to use the USB ports

The ports (`/dev/ttyACM*`) belong to the `dialout` group. Add yourself once:

```bash
sudo usermod -aG dialout $USER
```

Then **log out of the desktop session** (system menu → power icon → *Log Out*) or reboot.
Locking the screen is not enough: new terminals keep the old groups until you log in
again. To use it right away in one terminal only: `newgrp dialout`.

Check: `groups` lists `dialout`. Without it you get `Permission denied: '/dev/ttyACM0'`.

### 1.3 Find which port is which arm

```bash
lerobot-find-port
```

Unplug the arm it asks for and press Enter; it prints that arm's port. Repeat for the
second arm. Write the result down — the two ports are easy to swap by accident.
Below, the follower is `/dev/ttyACM1` and the leader `/dev/ttyACM0`; replace with yours.

### 1.4 Motor setup (only for brand-new servos, before assembly) 🚧

New servos all ship with ID 1, so each one needs its own ID. This has to happen
**before the arm is assembled**, one motor connected at a time:

```bash
lerobot-setup-motors --robot.type=so101_follower --robot.port=/dev/ttyACM1
lerobot-setup-motors --teleop.type=so101_leader  --teleop.port=/dev/ttyACM0
```

Our arms arrived with this already done. If calibration fails with missing motor IDs,
this step was skipped.

### 1.5 Calibrate both arms

```bash
lerobot-calibrate --robot.type=so101_follower --robot.port=/dev/ttyACM1 --robot.id=lab_follower_01
lerobot-calibrate --teleop.type=so101_leader  --teleop.port=/dev/ttyACM0 --teleop.id=lab_leader_01
```

1. Move every joint to the middle of its range, press Enter.
2. Move each joint slowly through its full range, press Enter.

Give every physical arm its own `id` and label the arm with it. The calibration is
saved to `~/.cache/huggingface/lerobot/calibration/` under that id **and** written into
the servos' memory (zero point and movement limits).

> The ROS driver uses the zero point stored in the servos. So in ROS, "all joints at 0"
> is the middle pose you held in step 1.

### 1.6 Test with teleoperation

```bash
lerobot-teleoperate --robot.type=so101_follower --robot.port=/dev/ttyACM1 --robot.id=lab_follower_01 \
                    --teleop.type=so101_leader  --teleop.port=/dev/ttyACM0 --teleop.id=lab_leader_01
```

Move the leader by hand; the follower must mirror it smoothly. A joint that moves the
wrong way or is offset means a bad calibration — redo 1.5 for that arm.

### 1.7 Optional: see the camera

Add a camera and the Rerun viewer to the command above:

```bash
  --robot.cameras="{ wrist: {type: opencv, index_or_path: /dev/video4, width: 640, height: 480, fps: 30}}" \
  --display_data=true --display_compressed_images=true
```

`lerobot-find-cameras opencv` saves a snapshot per camera to `outputs/captured_images/`
to find the right `/dev/video*`. Keep `--display_compressed_images=true`: without it the
viewer can't keep up and slows the control loop
(`Sender has been blocked for over 5 seconds`).

---

## Part 2 — ROS workspace on the RAP cluster ✅

### What you need

| Source | What it is | How you get it |
|---|---|---|
| [ros-physical-ai/ros2_so_arm](https://github.com/ros-physical-ai/ros2_so_arm) | SO-101 model, controllers, Gazebo | `git clone` |
| [JafarAbdi/feetech_ros2_driver](https://github.com/JafarAbdi/feetech_ros2_driver) | servo driver; `ros2_so_arm` depends on it, not available via apt | `git clone` |
| [michaljohnson/cas-so101](https://github.com/michaljohnson/cas-so101) (this repo) | `setup.sh`, the SO-101 MoveIt config (Part 5) | `git clone` |

### 2.1 Where to put it

On RAP only `~/rap` survives a pod restart; the home folder (including `~/.bashrc`)
is reset. Check with `findmnt -T ~/rap` — it must show its own device (e.g. `/dev/vdb`).
Keep the course in its own folder there:

```
~/rap/cas/
├── COLCON_IGNORE          # stops a colcon build started in ~/rap from building this
├── setup.sh -> so101_ws/src/cas-so101/setup.sh    # a link, so git pull updates it
└── so101_ws/
    ├── src/
    │   ├── ros2_so_arm/                   # from GitHub, untouched
    │   ├── feetech_ros2_driver/           # from GitHub, untouched
    │   └── cas-so101/                     # this repo: so_arm101_moveit_config
    ├── build/  install/  log/             # created by colcon, safe to delete
```

colcon finds the packages inside `cas-so101/` by itself; the README and `setup.sh`
next to them are ignored by the build.

### 2.2 Get the code

```bash
mkdir -p ~/rap/cas/so101_ws/src
touch ~/rap/cas/COLCON_IGNORE
cd ~/rap/cas/so101_ws/src
git clone https://github.com/ros-physical-ai/ros2_so_arm.git
git clone https://github.com/JafarAbdi/feetech_ros2_driver.git
git clone https://github.com/michaljohnson/cas-so101.git
ln -sf ~/rap/cas/so101_ws/src/cas-so101/setup.sh ~/rap/cas/setup.sh
```

To get course updates later: `cd ~/rap/cas/so101_ws/src/cas-so101 && git pull`.

What `setup.sh` does, line by line:

| Line | Why |
|---|---|
| `deactivate` / `conda deactivate` | a Python venv or conda env makes colcon and `ros2` use the wrong Python |
| `export DISPLAY=:0` (only if empty) | over SSH there is no screen; this sends Gazebo/RViz windows to the web desktop |
| `source /opt/ros/jazzy/setup.bash` | loads ROS 2 itself |
| `export ROS_DOMAIN_ID=42` | own "channel" for this workspace, so nodes from other projects on the same machine or network don't mix in |
| `source $ws/install/setup.bash` | loads your built packages on top of ROS |
| `rosdep check` | warns if system packages vanished after a pod restart |

### 2.3 Build

```bash
source ~/rap/cas/setup.sh so101
rosdep install --from-paths src --ignore-src -r -y     # system packages the code needs
colcon build --symlink-install
source ~/rap/cas/setup.sh so101                        # again, to load the fresh build
```

`--symlink-install` links Python launch files and configs from `install/` back to
`src/` instead of copying them, so editing a launch file or YAML needs no rebuild.
Only new packages or C++ changes need `colcon build` again.

After moving a workspace to another folder, delete `build/ install/ log/` and rebuild —
they contain absolute paths.

### 2.4 After every pod restart

```bash
source ~/rap/cas/setup.sh so101
```

If it prints `dependencies missing`, run the `rosdep install` line it shows: packages
installed by rosdep live outside `~/rap` and are lost on restart; your build is not.
Every new terminal needs this `source` line too.

---

## Part 3 — Simulation: Gazebo + ros2_control (Session 3)

Gazebo and RViz need a screen: use a terminal in the web desktop, or SSH with
`setup.sh` (which sets `DISPLAY=:0`).

### 3.1 Start Gazebo ✅

```bash
# terminal 1
source ~/rap/cas/setup.sh so101
ros2 launch so_arm_gz so_arm_gz_bringup.launch.py        # SO-101 is the default arm
```

Gazebo and RViz open with the arm. Press ▶ in Gazebo if the simulation is paused.

### 3.2 Command the joints 🚧

```bash
# terminal 2
source ~/rap/cas/setup.sh so101
ros2 control list_controllers          # joint_state_broadcaster, forward_position_controller
ros2 topic echo /joint_states --once
```

Move the arm — 5 values in radians: shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll:

```bash
ros2 topic pub --once /forward_position_controller/commands std_msgs/msg/Float64MultiArray "{data: [0.5, -0.5, 0.5, 0.3, 0.0]}"
ros2 topic pub --once /forward_position_controller/commands std_msgs/msg/Float64MultiArray "{data: [0.0, 0.0, 0.0, 0.0, 0.0]}"
```

Switch to the trajectory controller, which moves smoothly over a given time instead
of jumping:

```bash
ros2 control load_controller --set-state inactive joint_trajectory_controller
ros2 control switch_controllers --deactivate forward_position_controller --activate joint_trajectory_controller
ros2 topic pub --once /joint_trajectory_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
  "{joint_names: [shoulder_pan_joint, shoulder_lift_joint, elbow_flex_joint, wrist_flex_joint, wrist_roll_joint],
    points: [{positions: [0.5, -0.3, 0.3, 0.0, 0.0], time_from_start: {sec: 2}}]}"
```

---

## Part 4 — The real arm with ROS 🚧

To be written. Known so far: `ros2_so_arm` supports `hardware_type:=real usb_port:=<device>`.
Before executing any motion, compare the arm in RViz with the physical arm — the zero
pose comes from the LeRobot calibration (1.5) and may differ from the model's zero pose.

## Part 5 — MoveIt (Session 8)

Status: `mock_components` ✅ · `gazebo` ✅ (plan & execute moves the arm in Gazebo) ·
marker dragging ✅ (*Approx IK Solutions*, preset in the course RViz config) · `real` 🚧

`ros2_so_arm` ships a MoveIt config for the SO-100 only, but its helper code already
expects an `so_arm101_moveit_config` package. The course provides that package,
adapted from the SO-100 one:

- same joint names, planning group `manipulator`, gripper group `gripper`;
- planning tip `gripper_frame_link` — the point between the fingers, handy for picking;
- named poses `zero`, `extended`, `rest`, `open`, `closed`, kept inside the SO-101 limits;
- `demo.launch.py` with `hardware_type:=mock_components | gazebo | real`.
  For Gazebo it reuses `so_arm_gz` (the SO-101 controller launch in `ros2_so_arm`
  has no Gazebo mode) and adds the gripper controller.

Only the **follower** arm is needed for MoveIt; the leader is just for teleoperation.

### 5.1 Build

The package comes with this repo (Part 2.2), so the build in 2.3 already includes it.

### 5.2 Run it

Stop any Gazebo that is still running (Ctrl+C) first.

```bash
# fastest check: MoveIt + RViz, no physics
ros2 launch so_arm101_moveit_config demo.launch.py hardware_type:=mock_components

# with Gazebo
ros2 launch so_arm101_moveit_config demo.launch.py hardware_type:=gazebo
```

In RViz, drag the marker at the gripper, then *Plan & Execute* in the MotionPlanning
panel. Or pick a named pose under *Goal State* (e.g. `extended`) and execute.

The SO-101 has 5 joints, so most combinations of gripper position *and* tilt are
unreachable and exact IK fails while dragging the marker. The course RViz config
therefore ticks *Approx IK Solutions* (Planning tab): the goal follows the marker as
closely as the arm allows. This only affects RViz — in your own code, MoveIt still
tries to reach the exact pose you ask for, so choose poses the arm can reach
(e.g. gripper pointing down, turned towards the object). Named poses always work.

### 5.3 Pick an object in simulation 🚧

Start the Gazebo demo from 5.2 and add objects in Gazebo with the **Resource Spawner**
(Gazebo menu ⋮ top right → *Resource Spawner*). Where things are: the arm stands on
the ground at the world origin and reaches towards **+x** (e.g. an object at
x = 0.2, y = 0 on the floor is in reach). MoveIt plans in the same `world` frame, so
Gazebo and MoveIt coordinates are identical. (`so_arm_gz` has `x/y/z` launch arguments,
but the SO-101 model ignores them.)

Pick it by hand in RViz — for each step choose the planning group and goal, then
*Plan & Execute*:

1. group `gripper` → `open`
2. group `manipulator` → marker ~5 cm above the object, gripper pointing down
3. marker straight down, jaws around the object
4. group `gripper` → `closed`
5. group `manipulator` → up: does the object come along?

Objects added in Gazebo are **not** in MoveIt's planning scene: RViz doesn't show them
and MoveIt plans as if they weren't there. To add one by hand: MotionPlanning panel →
*Scene Objects* → pick a shape, set the same size and x/y/z as in Gazebo (select the
object in Gazebo → *Component Inspector* → Pose). In code, adding the object to the
planning scene and attaching it to the gripper (with the allowed touch links) is part
of the pick lab.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `TypeError: str \| None is not callable` | Python 3.14 | Use the Python 3.12 env (1.1) |
| `Permission denied: '/dev/ttyACM0'` | not in `dialout`, or not logged out yet | 1.2 — log out, not lock |
| Follower doesn't move / wrong arm reacts | ports swapped | `lerobot-find-port` again (1.3) |
| `Sender has been blocked for over 5 seconds` | Rerun viewer can't keep up | `--display_compressed_images=true` |
| `No module named 'catkin_pkg'` during colcon build | a Python venv/conda env is active | `deactivate` / `conda deactivate`, or use `setup.sh` |
| `CMake Error: The source directory ".../src/<pkg>" does not exist` | the package was moved; colcon's cache in `build/<pkg>` still points to the old place | `rm -rf build/<pkg> install/<pkg>`, then `colcon build` |
| `Package 'so_arm_gz' not found` | workspace not loaded in this terminal | `source ~/rap/cas/setup.sh so101` |
| RViz shows the arm moving, Gazebo doesn't | a second (old) `move_group` or mock `ros2_control_node` gets the commands; `ros2 node list` warns about duplicate names | stop all launches, `ros2 daemon stop`, check `ros2 node list` is empty, relaunch |
| `ros2 node list` shows nodes that aren't running | the ROS 2 daemon caches old nodes | `ros2 daemon stop` |
| Marker in RViz too big / too small | RViz setting | MotionPlanning → Planning Request → *Interactive Marker Size* (course config: 0.08) |
| `rviz2: could not connect to display` / Gazebo doesn't open | no screen (SSH session) | `export DISPLAY=:0` (done by `setup.sh`) or use the web desktop terminal |
| Every new terminal prints `No such file ... setup.bash` | `~/.bashrc` loads `~/env.sh`, which points to a moved workspace | fix or remove the stale line in that `env.sh` |

---

## Credits

- Michal Johnson — setup, testing on the RAP cluster and RunPod, course integration.
- [ros-physical-ai/ros2_so_arm](https://github.com/ros-physical-ai/ros2_so_arm) (Jafar Uruç) —
  SO-101 description, Gazebo and the SO-100 MoveIt config that `so_arm101_moveit_config` is derived from.
- Written with help from Claude (Anthropic): setup steps, the SO-101 MoveIt config and this README.
