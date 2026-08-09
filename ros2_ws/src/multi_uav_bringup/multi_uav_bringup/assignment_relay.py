"""Convert tracked targets into typed decisions from the shared solver."""

from pathlib import Path

import rclpy
from rclpy.node import Node

from multi_uav_interfaces.msg import Assignment, TargetArray

from .assignment_logic import load_assignment_config, solve_targets
from .qos import command_qos


class AssignmentRelay(Node):
    """Publish configured Greedy/Hungarian assignment decisions for ROS targets."""

    def __init__(self) -> None:
        super().__init__("assignment_relay")
        self.declare_parameter("algorithm", "hungarian")
        self.declare_parameter("config_path", "")
        config_path = self.get_parameter("config_path").value
        if not config_path:
            config_path = str(Path(__file__).resolve().parents[4] / "configs/priority_assignment.yaml")
        self._config = load_assignment_config(str(config_path))
        self._algorithm = str(self.get_parameter("algorithm").value)
        self._publisher = self.create_publisher(Assignment, "assignment/decisions", command_qos())
        self.create_subscription(TargetArray, "perception/targets", self._on_targets, command_qos())
        self.get_logger().info(
            "configured algorithm=%s config_path=%s" % (self._algorithm, config_path)
        )

    def _on_targets(self, targets: TargetArray) -> None:
        solved, elapsed_ms = solve_targets(targets.targets, self._config, self._algorithm)
        result = solved["result"]
        targets_by_id = solved["targets"]
        for decision in result.assignments:
            target = targets_by_id[decision.target_id]
            assignment = Assignment()
            assignment.header.stamp = self.get_clock().now().to_msg()
            assignment.header.frame_id = targets.header.frame_id
            assignment.source_id = targets.source_id
            assignment.source_sequence = targets.sequence
            assignment.track_id = target.track_id
            assignment.vehicle_id = decision.uav_id
            assignment.priority_hint = decision.priority
            self._publisher.publish(assignment)
            self.get_logger().info(
                "published source_sequence=%s track_id=%s vehicle_id=%s priority=%.3f"
                % (
                    assignment.source_sequence,
                    assignment.track_id,
                    assignment.vehicle_id,
                    assignment.priority_hint,
                )
            )
        self.get_logger().info(
            "solved source_sequence=%s algorithm=%s assigned=%s unassigned=%s elapsed_ms=%.4f"
            % (
                targets.sequence,
                result.algorithm,
                len(result.assignments),
                len(result.unassigned_target_ids),
                elapsed_ms,
            )
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
