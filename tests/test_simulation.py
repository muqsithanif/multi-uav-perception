from pathlib import Path

import pytest
import yaml

from multi_uav_core.simulation import run_scenario


@pytest.fixture
def inputs() -> tuple[dict, dict]:
    root = Path(__file__).parents[1]
    return (
        yaml.safe_load((root / "configs/priority_assignment.yaml").read_text()),
        yaml.safe_load((root / "configs/simulation_scenarios.yaml").read_text()),
    )


@pytest.mark.parametrize("scenario_name", ["fewer_targets", "equal_targets", "overloaded", "critical_arrival", "uav_unavailable", "lost_reacquired"])
def test_required_scenarios_are_deterministic_and_emit_frames(inputs: tuple[dict, dict], scenario_name: str) -> None:
    config, scenarios = inputs
    result = run_scenario(scenario_name, scenarios["scenarios"][scenario_name], config, scenarios["simulation"], "hungarian")
    assert len(result["frames"]) == scenarios["simulation"]["steps"]
    assert result["frames"][-1]["step"] == scenarios["simulation"]["steps"] - 1


def test_unavailable_uav_and_reacquisition_are_recorded(inputs: tuple[dict, dict]) -> None:
    config, scenarios = inputs
    unavailable = run_scenario("uav_unavailable", scenarios["scenarios"]["uav_unavailable"], config, scenarios["simulation"], "greedy")
    assert any(item["state"] == "UNAVAILABLE" for item in unavailable["frames"][-1]["uavs"])
    reacquired = run_scenario("lost_reacquired", scenarios["scenarios"]["lost_reacquired"], config, scenarios["simulation"], "greedy")
    assert any(event["type"] == "reacquire" for event in reacquired["events"])
