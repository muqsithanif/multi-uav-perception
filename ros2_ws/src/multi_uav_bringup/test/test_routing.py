import unittest

from multi_uav_bringup.routing import VEHICLE_IDS, route_track_id


class RoutingTest(unittest.TestCase):
    def test_route_track_id_cycles_over_configured_vehicles(self) -> None:
        self.assertEqual(
            [route_track_id(track_id) for track_id in (1, 2, 3, 4)],
            [*VEHICLE_IDS, VEHICLE_IDS[0]],
        )

    def test_route_track_id_rejects_non_positive_ids(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            route_track_id(0)
