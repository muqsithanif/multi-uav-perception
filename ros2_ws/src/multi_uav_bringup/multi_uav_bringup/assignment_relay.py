"""Convert Gate 7 tracked-target messages into deterministic typed assignments."""

import rclpy
from rclpy.node import Node

from multi_uav_interfaces.msg import Assignment, TargetArray

from .qos import command_qos
from .routing import route_track_id


class AssignmentRelay(Node):
    """Relay each target with deterministic routing for the transport smoke test."""

    def __init__(self) -> None:
        super().__init__("assignment_relay")
        self._publisher = self.create_publisher(Assignment, "assignment/decisions", command_qos())
        self.create_subscription(TargetArray, "perception/targets", self._on_targets, command_qos())

    def _on_targets(self, targets: TargetArray) -> None:
        for target in sorted(targets.targets, key=lambda item: (-item.priority_hint, item.track_id)):
            assignment = Assignment()
            assignment.header.stamp = self.get_clock().now().to_msg()
            assignment.header.frame_id = targets.header.frame_id
            assignment.source_id = targets.source_id
            assignment.source_sequence = targets.sequence
            assignment.track_id = target.track_id
            assignment.vehicle_id = route_track_id(target.track_id)
            assignment.priority_hint = target.priority_hint
            self._publisher.publish(assignment)
            self.get_logger().info(
                "published source_sequence=%s track_id=%s vehicle_id=%s"
                % (assignment.source_sequence, assignment.track_id, assignment.vehicle_id)
            )


def main() -> None:
    rclpy.init()
    node = AssignmentRelay()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
