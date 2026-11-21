import unittest

from tycoon import CASH_GOAL, Town, pack_save, unpack_save


class VehicleTest(unittest.TestCase):
    def test_cash_goal_marks_player_as_winner(self):
        town = Town()
        town.add_cash(CASH_GOAL - town.cash)
        self.assertTrue(town.won)

    def test_motorcycle_and_car_increase_travel_speed(self):
        distances = []
        for vehicle in (None, "motorcycle", "car"):
            town = Town()
            town.vehicle = vehicle
            town.move(1, 0, 1)
            distances.append(town.x - 480)
        self.assertLess(distances[0], distances[1])
        self.assertLess(distances[1], distances[2])

    def test_vehicle_is_saved_and_old_saves_default_to_on_foot(self):
        town = Town()
        town.vehicle = "motorcycle"
        saved = pack_save(town, 1_000)
        restored, _ = unpack_save(saved)
        self.assertEqual(restored.vehicle, "motorcycle")

        saved["state"].pop("vehicle")
        restored, _ = unpack_save(saved)
        self.assertIsNone(restored.vehicle)

    def test_warehouse_capacity_and_level_are_saved(self):
        town = Town()
        town.cash -= 300
        town.bag_size += 12
        town.warehouse_level += 1
        restored, _ = unpack_save(pack_save(town, 1_000))
        self.assertEqual((restored.bag_size, restored.warehouse_level), (24, 1))


if __name__ == "__main__":
    unittest.main()
