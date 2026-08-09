from pathlib import Path

import pytest
import yaml

from multi_uav_core import Target, Uav, assign_targets, priority_level, priority_score


@pytest.fixture
def config() -> dict:
    return yaml.safe_load((Path(__file__).parents[1] / "configs/priority_assignment.yaml").read_text())


def test_priority_combines_configured_class_zone_motion_and_confidence(config: dict) -> None:
    target = Target("t1", "person", 0.9, 0, 0, zone="restricted", speed=9, heading_change_deg=50)
    score = priority_score(target, config)
    assert score == pytest.approx(0.89)
    assert priority_level(score, config) == "critical"


@pytest.mark.parametrize("algorithm", ["greedy", "hungarian"])
@pytest.mark.parametrize(("uav_count", "target_count", "expected_assignments"), [(3, 2, 2), (2, 2, 2), (2, 3, 2)])
def test_assignment_handles_unequal_and_equal_fleet_counts(config: dict, algorithm: str, uav_count: int, target_count: int, expected_assignments: int) -> None:
    uavs = [Uav(f"u{index}", index * 10, 0) for index in range(uav_count)]
    targets = [Target(f"t{index}", "person" if index == 0 else "car", 0.9, index * 10, 0) for index in range(target_count)]
    result, elapsed_ms = assign_targets(uavs, targets, config, algorithm)
    assert len(result.assignments) == expected_assignments
    assert len(result.unassigned_target_ids) == target_count - expected_assignments
    assert elapsed_ms >= 0.0


def test_greedy_selects_critical_target_before_lower_priority_target(config: dict) -> None:
    uavs = [Uav("u1", 0, 0)]
    targets = [Target("low", "car", 0.9, 1, 0), Target("critical", "person", 0.99, 20, 0, zone="restricted", speed=10)]
    result, _ = assign_targets(uavs, targets, config, "greedy")
    assert result.assignments[0].target_id == "critical"


@pytest.mark.parametrize("algorithm", ["greedy", "hungarian"])
def test_lost_targets_and_unavailable_uavs_are_not_assigned(config: dict, algorithm: str) -> None:
    uavs = [Uav("offline", 0, 0, available=False), Uav("online", 10, 0)]
    targets = [Target("lost", "person", 0.9, 0, 0, lost=True), Target("live", "car", 0.9, 11, 0)]
    result, _ = assign_targets(uavs, targets, config, algorithm)
    assert [(item.target_id, item.uav_id) for item in result.assignments] == [("live", "online")]
    assert result.skipped_target_ids == ("lost",)


@pytest.mark.parametrize("algorithm", ["greedy", "hungarian"])
def test_critical_target_can_reassign_busy_uav_above_configured_margin(config: dict, algorithm: str) -> None:
    uavs = [Uav("busy", 0, 0, current_target_id="low", current_target_priority=0.28)]
    targets = [Target("critical", "person", 0.99, 20, 0, zone="restricted", speed=10)]
    result, _ = assign_targets(uavs, targets, config, algorithm)
    assert [(item.target_id, item.uav_id) for item in result.assignments] == [("critical", "busy")]
