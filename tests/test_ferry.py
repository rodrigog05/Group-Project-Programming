from collections import deque
import math
import unittest

from ferry import FERRY_FARE, FERRY_PIERS, nearby_pier, other_pier, ride_ferry
from browser_game import greeting
from lisbon_scene import RIVER_BOTTOM, RIVER_TOP, WORLD_BOTTOM, WORLD_WIDTH
from tycoon import MAP_TOP, REACH, SITES, Town, pack_save, unpack_save


def reachable_on_foot(town, start):
    """Every point a walking player can reach from start, on an 8-unit grid."""
    visited = {start}
    queue = deque(visited)
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((8, 0), (-8, 0), (0, 8), (0, -8)):
            point = nx, ny = x+dx, y+dy
            if point in visited or not (17 <= nx <= WORLD_WIDTH-17 and MAP_TOP+15 <= ny <= WORLD_BOTTOM-15):
                continue
            if town.can_walk(nx, ny):
                visited.add(point)
                queue.append(point)
    return visited


class FerryTest(unittest.TestCase):
    def test_one_pier_on_each_bank(self):
        north, south = FERRY_PIERS
        self.assertLess(north.y, RIVER_TOP)
        self.assertGreater(south.y, RIVER_BOTTOM)
        self.assertIs(other_pier(north), south)
        town = Town()
        for pier in FERRY_PIERS:
            self.assertTrue(town.can_walk(*pier.position), pier.name)
            self.assertIs(nearby_pier(*pier.position), pier)

    def test_each_pier_has_a_ticket_kiosk_beside_its_boarding_point(self):
        for pier in FERRY_PIERS:
            left, top, right, bottom = pier.kiosk
            with self.subTest(pier=pier.name):
                # The kiosk stands on the jetty over the water, so it never blocks the quay.
                self.assertTrue(RIVER_TOP <= top and bottom <= RIVER_BOTTOM)
                self.assertFalse(left <= pier.x <= right and top <= pier.y <= bottom)
                # Close enough that the yellow outline appears exactly where E works.
                nearest_x, nearest_y = min(max(pier.x, left), right), min(max(pier.y, top), bottom)
                self.assertLess(math.dist(pier.position, (nearest_x, nearest_y)), 25)

    def test_crossing_charges_the_fare_and_keeps_cargo(self):
        town = Town()
        town.x, town.y = FERRY_PIERS[0].position
        town.goods[0] = 3
        self.assertEqual(ride_ferry(town), FERRY_PIERS)
        self.assertEqual((town.x, town.y), FERRY_PIERS[1].position)
        self.assertEqual((town.cash, town.other_expenses_today, town.goods[0]), (60-FERRY_FARE, FERRY_FARE, 3))
        self.assertEqual(ride_ferry(town), FERRY_PIERS[::-1])
        self.assertEqual((town.x, town.y), FERRY_PIERS[0].position)
        restored, _ = unpack_save(pack_save(town, 1000))
        self.assertEqual(restored.cash, 60-2*FERRY_FARE)

    def test_failed_trips_cost_nothing(self):
        town = Town()
        self.assertIsNone(ride_ferry(town))  # Not at a pier
        self.assertEqual(town.cash, 60)
        town.x, town.y = FERRY_PIERS[0].position
        town.cash = FERRY_FARE-1
        self.assertIsNone(ride_ferry(town))
        self.assertEqual((town.cash, town.x, town.y), (FERRY_FARE-1, *FERRY_PIERS[0].position))
        self.assertIn("ferry ticket", town.message)

    def test_walkers_reach_every_business_with_the_ferry(self):
        town = Town()
        north = reachable_on_foot(town, (480, 321))
        north_pier, south_pier = FERRY_PIERS
        self.assertTrue(any(math.dist(point, north_pier.position) <= 30 for point in north))
        self.assertFalse(any(y > RIVER_BOTTOM for _, y in north), "walkers must not cross the bridges")
        south = reachable_on_foot(town, (round(south_pier.x), round(south_pier.y)))
        everywhere = north | south
        for site in SITES:
            self.assertTrue(any(math.hypot(x-site.door[0], y-site.door[1]) <= REACH for x, y in everywhere), site.name)

    def test_garage_salesperson_mentions_the_bridge_rule_to_walkers(self):
        town = Town()
        garage = next(site for site in SITES if site.role == "GARAGE")
        self.assertIn("vehicles only", greeting(town, garage))
        town.vehicle = "car"
        self.assertIn("car", greeting(town, garage))


if __name__ == "__main__":
    unittest.main()
