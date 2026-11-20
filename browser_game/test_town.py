import unittest

from browser_game.game.town import Town, car_position


class FarmTest(unittest.TestCase):
    def test_walk_from_spawn_and_buy_exactly_one_wheat(self):
        town = Town()
        town.buy()
        self.assertEqual((town.cash, town.wheat), (60, 0))
        for _ in range(10):
            town.walk(-1, 0, 1/60)
        self.assertTrue(town.at_farm)
        town.buy()
        self.assertEqual((town.cash, town.wheat), (56, 1))

    def test_full_bag_and_insufficient_cash_preserve_balance(self):
        for cash, wheat in [(60, 12), (3, 0)]:
            town = Town(168, 200, cash, wheat)
            town.buy()
            self.assertEqual((town.cash, town.wheat), (cash, wheat))

    def test_diagonal_speed_and_solid_farm_wall(self):
        town = Town(168, 210)
        town.walk(1, 1, 0.02)
        self.assertAlmostEqual(((town.x-168)**2 + (town.y-210)**2)**0.5, 228*.02)
        for _ in range(150):
            town.walk(0, -1, 1/60)
        self.assertGreaterEqual(town.y, 194)

    def test_opposing_cars_return_to_start_after_one_lap(self):
        for direction in (1, -1):
            start = car_position(0, direction)
            self.assertGreater((car_position(.1, direction)-start)*direction, 0)
            self.assertEqual(car_position(616/380, direction), start)
