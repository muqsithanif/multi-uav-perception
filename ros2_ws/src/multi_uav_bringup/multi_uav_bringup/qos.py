"""Shared ROS QoS policy for the local Gate 7 transport graph."""

from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy


def command_qos() -> QoSProfile:
    """Deliver source, assignment, and mission records reliably on one host."""
    return QoSProfile(
        depth=10,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.VOLATILE,
    )
