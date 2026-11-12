from copy import deepcopy
import json
from types import SimpleNamespace
import unittest

from lisbon_scene import LisbonScene, WORLD_WIDTH
from tram import TRAM_FARE, TRAM_STOPS, TRAM_REACH, nearby_stop, ride_tram
from tycoon import Town, pack_save, unpack_save


class TramTravelTest(unittest.TestCase):
    def at_stop(self, index=0):
        town = Town()
        town.x, town.y = TRAM_STOPS[index].position
        return town

    def assets(self, town):
        return (town.x, town.y, town.cash, town.other_expenses_today,
                town.cargo, town.vehicle, town.tolls_paid_total)

    def test_all_stops_are_safe_and_interaction_range_is_local(self):
        town = Town()
        for stop in TRAM_STOPS:
            self.assertTrue(town.can_walk(*stop.position), stop.name)
            self.assertEqual(nearby_stop(*stop.position), stop)
            self.assertEqual(nearby_stop(stop.x, stop.y-TRAM_REACH), stop)
        self.assertIsNone(nearby_stop(480, 321))

    def test_fare_is_charged_once_and_cargo_orders_vehicle_are_preserved(self):
        town = self.at_stop()
        town.supplies[0], town.goods[1], town.eggs = 3, 2, 1
        town.vehicle = "car"
        town.bridge_journey = {"origin": "south", "bridge": "25 de Abril"}
        preserved = deepcopy((town.supplies, town.goods, town.orders, town.industry_orders, town.profile, town.vehicle))
        self.assertTrue(ride_tram(town, TRAM_STOPS[-1].name))
        self.assertEqual((town.x, town.y), TRAM_STOPS[-1].position)
        self.assertEqual((town.cash, town.other_expenses_today), (60-TRAM_FARE, TRAM_FARE))
        self.assertEqual(town.tolls_paid_total, 0)
        self.assertIsNone(town.bridge_journey)
        self.assertEqual((town.supplies, town.goods, town.orders, town.industry_orders, town.profile, town.vehicle), preserved)
        self.assertEqual(town.cargo, 6)
        assets = self.assets(town)
        self.assertFalse(ride_tram(town, TRAM_STOPS[-1].name))
        self.assertEqual(self.assets(town), assets)

    def test_wrong_origin_unknown_stop_same_stop_and_no_funds_are_atomic(self):
        for failure in ("origin", "unknown", "same", "cash", "blocked"):
            town = self.at_stop()
            destination = TRAM_STOPS[-1].name
            if failure == "origin":
                town.x, town.y = 480, 321
            elif failure == "unknown":
                destination = "Unknown place"
            elif failure == "same":
                destination = TRAM_STOPS[0].name
            elif failure == "cash":
                town.cash = TRAM_FARE-1
            elif failure == "blocked":
                original = town.can_walk
                town.can_walk = lambda x, y: original(x, y) and (x, y) != TRAM_STOPS[-1].position
            before = self.assets(town)
            with self.subTest(failure=failure):
                self.assertFalse(ride_tram(town, destination))
                self.assertEqual(self.assets(town), before)

    def test_exact_fare_and_trip_state_survive_json_save_reload(self):
        town = self.at_stop(1)
        town.cash = TRAM_FARE
        self.assertTrue(ride_tram(town, TRAM_STOPS[3].name))
        restored, _ = unpack_save(json.loads(json.dumps(pack_save(town, 1000))))
        self.assertEqual(self.assets(restored), self.assets(town))
        self.assertEqual(restored.cash, 0)
        self.assertEqual(restored.daily_expenses, TRAM_FARE)

    def test_animation_reaches_new_districts_without_creating_canvas_items(self):
        moves = []
        scene = LisbonScene(SimpleNamespace(canvas=SimpleNamespace(move=lambda *args: moves.append(args)), scale_x=1), (), draw=False)
        scene.animate(0)
        self.assertEqual(scene.tram_position, 80)
        scene.animate(17)
        self.assertEqual(scene.tram_position, WORLD_WIDTH-100)
        scene.animate(37)
        self.assertEqual(scene.tram_position, 80)
        self.assertEqual(len(moves), 3)


if __name__ == "__main__":
    unittest.main()
