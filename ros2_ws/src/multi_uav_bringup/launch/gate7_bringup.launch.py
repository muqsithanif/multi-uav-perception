from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription(
        [
            Node(
                package="multi_uav_bringup",
                executable="perception_source",
                name="perception_source",
                output="screen",
            ),
            Node(
                package="multi_uav_bringup",
                executable="assignment_relay",
                name="assignment_relay",
                output="screen",
            ),
            Node(
                package="multi_uav_bringup",
                executable="mission_relay",
                name="mission_relay",
                output="screen",
            ),
            Node(
                package="multi_uav_monitor",
                executable="mission_monitor",
                name="mission_monitor",
                output="screen",
            ),
        ]
    )
