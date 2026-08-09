from pathlib import Path
import os

from launch import LaunchDescription
from launch.actions import SetEnvironmentVariable
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    project_root = Path(os.environ.get("MULTI_UAV_PROJECT_ROOT", Path(__file__).resolve().parents[4]))
    source_root = project_root / "src"
    config_path = project_root / "configs" / "priority_assignment.yaml"
    return LaunchDescription(
        [
            SetEnvironmentVariable("MULTI_UAV_CORE_SOURCE", str(source_root)),
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
                parameters=[{"algorithm": "hungarian", "config_path": str(config_path)}],
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
