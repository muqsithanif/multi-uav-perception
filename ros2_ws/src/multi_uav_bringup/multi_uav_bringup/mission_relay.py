"""Publish typed mission commands and status from Gate 7 assignment records."""

import rclpy
from rclpy.node import Node

from multi_uav_interfaces.msg import Assignment, MissionCommand, MissionStatus

from .qos import command_qos


class MissionRelay(Node):
    """Turn each synthetic assignment into a high-level, non-flight command."""

    def __init__(self) -> None:
        super().__init__("mission_relay")
        self._command_publisher = self.create_publisher(
            MissionCommand, "mission/commands", command_qos()
        )
        self._status_publisher = self.create_publisher(MissionStatus, "mission/status", command_qos())
        self.create_subscription(Assignment, "assignment/decisions", self._on_assignment, command_qos())

    def _on_assignment(self, assignment: Assignment) -> None:
        stamp = self.get_clock().now().to_msg()
        command = MissionCommand()
        command.header.stamp = stamp
        command.header.frame_id = assignment.header.frame_id
        command.source_id = assignment.source_id
        command.source_sequence = assignment.source_sequence
        command.track_id = assignment.track_id
        command.vehicle_id = assignment.vehicle_id
        command.command = "MOVE_TO_TARGET"
        self._command_publisher.publish(command)

        status = MissionStatus()
        status.header.stamp = stamp
        status.header.frame_id = assignment.header.frame_id
        status.source_id = assignment.source_id
        status.source_sequence = assignment.source_sequence
        status.track_id = assignment.track_id
        status.vehicle_id = assignment.vehicle_id
        status.state = "DISPATCHED"
        status.detail = "gate7_transport_stub"
        self._status_publisher.publish(status)
        self.get_logger().info(
            "published source_sequence=%s track_id=%s state=%s"
            % (status.source_sequence, status.track_id, status.state)
        )


def main() -> None:
    rclpy.init()
    node = MissionRelay()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
