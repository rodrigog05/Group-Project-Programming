import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))

from catalog import ROUTES, entrance
from controller import Session
from storage import Storage
from world import move, walkable


class Streets(unittest.TestCase):
    def test_both_bridges_are_crossable_in_both_directions(self):
        for east in (False, True):
            x, y = (2035, 700) if east else (300, 700)
            for direction in (1, -1):
                target = 1100 if direction == 1 else 700
                for _ in range(180):
                    if (target - y) * direction <= 0:
                        break
                    dx = -0.32 * direction if east else 0
                    x, y = move(x, y, dx, direction, 0.02)
                self.assertLessEqual((target - y) * direction, 0)

    def test_no_water_wall_or_map_tunnelling(self):
        for point in ((500, 800), (1368, 560), (-3, 520), (400, 1800)):
            self.assertFalse(walkable(*point))
        _, y = move(1368, 650, 0, -1, 100)
        self.assertGreaterEqual(y, 644)
        _, y = move(500, 710, 0, 1, 100)
        self.assertLessEqual(y, 710)

    def test_all_doors_have_reachable_approaches(self):
        for i, r in enumerate(ROUTES):
            for role in ("supplier", "workshop", "market"):
                shop = getattr(r, role)
                pos = (shop.x, shop.y + 16)
                self.assertTrue(walkable(*pos))
                self.assertEqual(entrance(*pos), (i, role))

    def test_diagonal_speed_and_key_release(self):
        x, y = move(1368, 650, 1, 1, 0.05)
        self.assertAlmostEqual(math.hypot(x - 1368, y - 650), 228 * 0.05)
        g = Session(Storage())
        g.key("d")
        g.tick(0.1)
        g.keys.clear()
        before = g.town.x
        g.tick(0.1)
        self.assertEqual(g.town.x, before)

    def test_held_e_opens_without_purchasing_and_focus_pauses_production(self):
        g = Session(Storage())
        g.key("e")
        g.key("e")
        self.assertEqual((g.screen, g.town.cash), ("shop", 60))
        g.keys.clear()
        g.key("e")
        self.assertEqual(g.town.cash, 56)
        g.town.x = 1628
        g.town.trade()
        g.focus = False
        g.tick(0.25)
        self.assertEqual(g.town.orders[3].remaining, 4)
