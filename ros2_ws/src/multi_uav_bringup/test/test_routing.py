import pytest

from multi_uav_bringup.routing import VEHICLE_IDS, route_track_id


def test_route_track_id_cycles_over_configured_vehicles() -> None:
    assert [route_track_id(track_id) for track_id in (1, 2, 3, 4)] == [
        *VEHICLE_IDS,
        VEHICLE_IDS[0],
    ]


def test_route_track_id_rejects_non_positive_ids() -> None:
    with pytest.raises(ValueError, match="positive"):
        route_track_id(0)
