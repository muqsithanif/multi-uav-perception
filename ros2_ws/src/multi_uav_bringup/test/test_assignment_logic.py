from types import SimpleNamespace
from pathlib import Path

from multi_uav_bringup.assignment_logic import load_assignment_config, solve_targets


def _target(track_id: int, x: float, y: float) -> SimpleNamespace:
    return SimpleNamespace(
        track_id=track_id,
        class_label="person",
        confidence=0.9,
        center_x_px=x,
        center_y_px=y,
        velocity_x_px_s=0.0,
        velocity_y_px_s=0.0,
    )


def test_adapter_uses_shared_hungarian_solver_instead_of_track_id_routing() -> None:
    config_path = Path(__file__).resolve().parents[4] / "configs" / "priority_assignment.yaml"
    config = load_assignment_config(str(config_path))
    solved, elapsed_ms = solve_targets([_target(7, 320.0, 640.0)], config, "hungarian")

    assignment = solved["result"].assignments[0]
    assert (assignment.target_id, assignment.uav_id) == ("7", "uav_3")
    assert elapsed_ms >= 0.0
