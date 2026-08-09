import pytest

from multi_uav_core.mission import MissionState, transition


@pytest.mark.parametrize(
    ("current", "event", "expected"),
    [
        (MissionState.IDLE, "start", MissionState.SEARCHING),
        (MissionState.SEARCHING, "assigned", MissionState.ASSIGNED),
        (MissionState.ASSIGNED, "assigned", MissionState.ASSIGNED),
        (MissionState.TRACKING, "assigned", MissionState.ASSIGNED),
        (MissionState.FOLLOWING, "assigned", MissionState.ASSIGNED),
        (MissionState.REACQUIRE, "assigned", MissionState.ASSIGNED),
        (MissionState.ASSIGNED, "arrived", MissionState.TRACKING),
        (MissionState.TRACKING, "follow", MissionState.FOLLOWING),
        (MissionState.FOLLOWING, "lost", MissionState.REACQUIRE),
        (MissionState.REACQUIRE, "found", MissionState.TRACKING),
        (MissionState.REACQUIRE, "timeout", MissionState.SEARCHING),
        (MissionState.ASSIGNED, "hold", MissionState.HOLD),
        (MissionState.HOLD, "resume", MissionState.SEARCHING),
        (MissionState.RETURNING, "complete", MissionState.IDLE),
        (MissionState.FOLLOWING, "return", MissionState.RETURNING),
        (MissionState.IDLE, "unavailable", MissionState.UNAVAILABLE),
    ],
)
def test_every_permitted_transition_is_explicit(
    current: MissionState, event: str, expected: MissionState
) -> None:
    assert transition(current, event) == expected


def test_invalid_transition_is_rejected() -> None:
    with pytest.raises(ValueError, match="invalid transition"):
        transition(MissionState.IDLE, "arrived")
