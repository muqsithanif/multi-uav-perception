"""Adapt typed ROS target fields to the shared priority and assignment engine."""

from __future__ import annotations

from math import hypot
import os
from pathlib import Path
import sys
from typing import Any, Iterable

import yaml


def _add_project_source_to_path() -> None:
    """Make the repository's shared core importable in a source workspace.

    Gate 9 runs from the checked-out ROS workspace, where the pure-Python core
    remains the single implementation used by the standalone simulation too.
    The launch file also exports this location for the node process.
    """
    source_root = Path(
        os.environ.get("MULTI_UAV_CORE_SOURCE", Path(__file__).resolve().parents[4] / "src")
    )
    if source_root.is_dir() and str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))


_add_project_source_to_path()

from multi_uav_core import Target, Uav, assign_targets  # noqa: E402


def load_assignment_config(config_path: str) -> dict[str, Any]:
    """Load the one priority-and-assignment configuration used across Gate 8/9."""
    with Path(config_path).open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def configured_uavs(config: dict[str, Any]) -> list[Uav]:
    """Return the synthetic, non-flight image-space UAV positions from config."""
    return [
        Uav(
            uav_id=str(item["uav_id"]),
            x=float(item["x"]),
            y=float(item["y"]),
            available=bool(item.get("available", True)),
            load=int(item.get("load", 0)),
        )
        for item in config["ros_assignment"]["uavs"]
    ]


def solve_targets(
    ros_targets: Iterable[Any], config: dict[str, Any], algorithm: str
) -> tuple[dict[str, Any], float]:
    """Score and assign ROS-like targets with the shared configured solver.

    ``ros_targets`` intentionally uses a narrow duck-typed interface so this
    adapter can be unit-tested without starting ROS middleware.
    """
    target_by_id: dict[str, Any] = {}
    core_targets: list[Target] = []
    for item in ros_targets:
        target_id = str(item.track_id)
        target_by_id[target_id] = item
        core_targets.append(
            Target(
                target_id=target_id,
                class_label=item.class_label,
                confidence=float(item.confidence),
                x=float(item.center_x_px),
                y=float(item.center_y_px),
                speed=hypot(float(item.velocity_x_px_s), float(item.velocity_y_px_s)),
            )
        )
    result, elapsed_ms = assign_targets(configured_uavs(config), core_targets, config, algorithm)
    return {"result": result, "targets": target_by_id}, elapsed_ms
