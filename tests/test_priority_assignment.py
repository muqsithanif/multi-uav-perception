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
def test_assignment_handles_more_targets_than_uavs(config: dict, algorithm: str) -> None:
    uavs = [Uav("u1", 0, 0), Uav("u2", 10, 0)]
    targets = [Target("t1", "person", 0.9, 1, 0), Target("t2", "car", 0.9, 9, 0), Target("t3", "car", 0.9, 20, 0)]
    result, elapsed_ms = assign_targets(uavs, targets, config, algorithm)
    assert len(result.assignments) == 2
    assert len(result.unassigned_target_ids) == 1
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
