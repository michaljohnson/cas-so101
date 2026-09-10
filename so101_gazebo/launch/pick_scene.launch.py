"""SO-101 pick scene: the MoveIt + Gazebo demo, a table and a pen.

so_arm_gz spawns the arm at (0, -0.488, 0.845), rotated 180 deg, so its reach
direction is world -x. The table top is at 0.842, just under the arm; the pen lies on
it ~22 cm in front of the base, across the reach direction.

ros2 launch so101_gazebo pick_scene.launch.py pen_x:=-0.22 pen_y:=-0.488
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, RegisterEventHandler
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import AnyLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def spawn(name, pose):
    model = PathJoinSubstitution([FindPackageShare("so101_gazebo"), "models", name, "model.sdf"])
    return Node(
        package="ros_gz_sim",
        executable="create",
        output="screen",
        # No -world: create asks Gazebo which world is running, so this works with any world.
        arguments=["-name", name, "-file", model] + pose,
    )


def generate_launch_description():
    demo = IncludeLaunchDescription(
        AnyLaunchDescriptionSource(
            PathJoinSubstitution(
                [FindPackageShare("so_arm101_moveit_config"), "launch", "demo.launch.py"]
            )
        ),
        launch_arguments={"hardware_type": "gazebo"}.items(),
    )

    table = spawn("table", ["-x", "-0.15", "-y", "-0.488", "-z", "0.421"])
    pen = spawn(
        "pen",
        ["-x", LaunchConfiguration("pen_x"), "-y", LaunchConfiguration("pen_y"),
         "-z", "0.865", "-R", "1.5708"],
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("pen_x", default_value="-0.22", description="Pen position x [m]"),
            DeclareLaunchArgument("pen_y", default_value="-0.488", description="Pen position y [m]"),
            demo,
            table,
            # The pen only after the table exists, so it drops onto it, not the floor.
            RegisterEventHandler(OnProcessExit(target_action=table, on_exit=[pen])),
        ]
    )
