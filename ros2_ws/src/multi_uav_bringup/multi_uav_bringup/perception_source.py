"""Publish deterministic synthetic tracked targets for the ROS transport gate."""

import rclpy
from rclpy.node import Node

from multi_uav_interfaces.msg import TargetArray, TrackedTarget

from .qos import command_qos


class PerceptionSource(Node):
    """Emit two synthetic image-space targets at a fixed cadence."""

    def __init__(self) -> None:
        super().__init__("perception_source")
        self._publisher = self.create_publisher(TargetArray, "perception/targets", command_qos())
        self._sequence = 0
        self.create_timer(0.5, self._publish_targets)

    def _publish_targets(self) -> None:
        self._sequence += 1
        message = TargetArray()
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = "synthetic_image_px"
        message.source_id = "synthetic_gate7"
        message.sequence = self._sequence
        message.targets = [
            self._target(101, "car", 0.91, 320.0, 180.0, 12.0, 0.0, 0.80),
            self._target(202, "person", 0.86, 520.0, 360.0, -4.0, 6.0, 0.65),
        ]
        self._publisher.publish(message)
        self.get_logger().info(
            f"published source_sequence={message.sequence} target_count={len(message.targets)}"
        )

    @staticmethod
    def _target(
        track_id: int,
        class_label: str,
        confidence: float,
        center_x_px: float,
        center_y_px: float,
        velocity_x_px_s: float,
        velocity_y_px_s: float,
        priority_hint: float,
    ) -> TrackedTarget:
        target = TrackedTarget()
        target.track_id = track_id
        target.class_label = class_label
        target.confidence = confidence
        target.center_x_px = center_x_px
        target.center_y_px = center_y_px
        target.velocity_x_px_s = velocity_x_px_s
        target.velocity_y_px_s = velocity_y_px_s
        target.priority_hint = priority_hint
        return target


def main() -> None:
    rclpy.init()
    node = PerceptionSource()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
