import unittest

from guidance import compass, next_step
from lisbon_scene import bridge_center


class GuidanceTest(unittest.TestCase):
    def test_same_bank_destination_is_direct(self):
        self.assertEqual(next_step(480, 321, 1500, 652), ((1500, 652), ""))

    def test_river_directions_choose_a_nearby_bridge_on_each_side(self):
        west, west_hint = next_step(200, 650, 450, 1050)
        east, east_hint = next_step(2100, 650, 2200, 1250)
        self.assertIn("25 de Abril", west_hint)
        self.assertIn("Vasco da Gama", east_hint)
        self.assertEqual(west[0], bridge_center(west[1]))
        self.assertEqual(east[0], bridge_center(east[1], True))
        north, hint = next_step(2100, 1250, 2200, 650)
        self.assertIn("Vasco da Gama", hint)
        self.assertGreater(north[1], 900)

    def test_directions_from_mid_crossing_keep_current_bridge(self):
        x, y = bridge_center(800, True), 800
        point, hint = next_step(x, y, 100, 500)
        self.assertEqual(point[0], bridge_center(point[1], True))
        self.assertLess(point[1], 718)
        self.assertIn("Vasco da Gama", hint)

    def test_compass_covers_all_directions(self):
        for vector, expected in (((1, 0), "E"), ((0, 1), "S"), ((-1, 0), "W"), ((0, -1), "N")):
            self.assertTrue(compass(*vector).startswith(expected))


if __name__ == "__main__":
    unittest.main()
