from enum import StrEnum


class MissionState(StrEnum):
    IDLE = "IDLE"
    SEARCHING = "SEARCHING"
    ASSIGNED = "ASSIGNED"
    TRACKING = "TRACKING"
    FOLLOWING = "FOLLOWING"
    HOLD = "HOLD"
    REACQUIRE = "REACQUIRE"
    RETURNING = "RETURNING"
    UNAVAILABLE = "UNAVAILABLE"


def transition(current: MissionState, event: str) -> MissionState:
    """Explicit high-level simulation state transition table."""
    transitions = {
        (MissionState.IDLE, "start"): MissionState.SEARCHING,
        (MissionState.SEARCHING, "assigned"): MissionState.ASSIGNED,
        (MissionState.ASSIGNED, "assigned"): MissionState.ASSIGNED,
        (MissionState.TRACKING, "assigned"): MissionState.ASSIGNED,
        (MissionState.FOLLOWING, "assigned"): MissionState.ASSIGNED,
        (MissionState.REACQUIRE, "assigned"): MissionState.ASSIGNED,
        (MissionState.ASSIGNED, "arrived"): MissionState.TRACKING,
        (MissionState.TRACKING, "follow"): MissionState.FOLLOWING,
        (MissionState.FOLLOWING, "lost"): MissionState.REACQUIRE,
        (MissionState.REACQUIRE, "found"): MissionState.TRACKING,
        (MissionState.REACQUIRE, "timeout"): MissionState.SEARCHING,
        (MissionState.ASSIGNED, "hold"): MissionState.HOLD,
        (MissionState.HOLD, "resume"): MissionState.SEARCHING,
        (MissionState.RETURNING, "complete"): MissionState.IDLE,
    }
    if event == "unavailable":
        return MissionState.UNAVAILABLE
    if event == "return":
        return MissionState.RETURNING
    if (current, event) not in transitions:
        raise ValueError(f"invalid transition {current} --{event}--> ?")
    return transitions[(current, event)]
