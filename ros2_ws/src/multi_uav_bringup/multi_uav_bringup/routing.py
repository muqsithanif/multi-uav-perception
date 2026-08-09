"""Small deterministic routing helper used only by the Gate 7 transport smoke."""

VEHICLE_IDS = ("uav_1", "uav_2", "uav_3")


def route_track_id(track_id: int) -> str:
    """Map a positive synthetic track ID to one of the configured vehicle IDs.

    This is not the configurable greedy/Hungarian assignment required by Gate 8.
    It only provides a deterministic typed hand-off for the Gate 7 ROS graph.
    """
    if track_id <= 0:
        raise ValueError("track_id must be positive")
    return VEHICLE_IDS[(track_id - 1) % len(VEHICLE_IDS)]
