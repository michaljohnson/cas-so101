"""MoveIt demo for the SO-ARM101: controllers + move_group + RViz.

hardware_type:=mock_components | real | mujoco
    controller_manager from so_arm101_description/controllers_bringup.launch.py
hardware_type:=gazebo
    so_arm101_description's bringup has no Gazebo branch (unlike the SO-100's),
    so Gazebo comes from so_arm_gz, whose gz_ros2_control runs the
    controller_manager; we only add the gripper controller.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import AnyLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, PythonExpression
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    hardware_type = LaunchConfiguration("hardware_type")
    usb_port = LaunchConfiguration("usb_port")
    is_gazebo = PythonExpression(["'", hardware_type, "' == 'gazebo'"])
    use_sim_time = PythonExpression(["'", hardware_type, "' in ('gazebo', 'mujoco')"])

    def launch_file(package, name):
        return AnyLaunchDescriptionSource(
            PathJoinSubstitution([FindPackageShare(package), "launch", name])
        )

    controllers_launch = IncludeLaunchDescription(
        launch_file("so_arm101_description", "controllers_bringup.launch.py"),
        launch_arguments={"hardware_type": hardware_type, "usb_port": usb_port}.items(),
        condition=UnlessCondition(is_gazebo),
    )

    gazebo_launch = IncludeLaunchDescription(
        launch_file("so_arm_gz", "so_arm_gz_bringup.launch.py"),
        launch_arguments={
            "arm_id": "so_arm101",
            "initial_joint_controller": "joint_trajectory_controller",
            "launch_rviz": "false",
        }.items(),
        condition=IfCondition(is_gazebo),
    )
    gazebo_gripper_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["gripper_controller"],
        parameters=[{"use_sim_time": True}],
        condition=IfCondition(is_gazebo),
    )

    moveit_launch = IncludeLaunchDescription(
        launch_file("so_arm101_moveit_config", "move_group.launch.py"),
        launch_arguments={"use_sim_time": use_sim_time}.items(),
    )
    rviz_launch = IncludeLaunchDescription(
        launch_file("so_arm101_moveit_config", "moveit_rviz.launch.py"),
        launch_arguments={"use_sim_time": use_sim_time}.items(),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "hardware_type",
                default_value="mock_components",
                description="mock_components, gazebo, mujoco or real",
            ),
            DeclareLaunchArgument(
                "usb_port",
                default_value="/dev/LeRobotFollower",
                description="Follower arm USB device, only used with hardware_type:=real",
            ),
            controllers_launch,
            gazebo_launch,
            gazebo_gripper_spawner,
            moveit_launch,
            rviz_launch,
        ],
    )
