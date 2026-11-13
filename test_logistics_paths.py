"""Delivery vans stay on existing roads and use genuine river crossings."""
from copy import deepcopy
import math
import unittest

from logistics_paths import bridge_used, path_length, point_on_path, road_path
from lisbon_scene import bridge_at
from tycoon import COLLISION_BOUNDS, SITES, Town
from vehicles import on_road


def entrance(site):
    return site.door[0], site.door[1]+18


class LogisticsPathTest(unittest.TestCase):
    def test_every_valid_supplier_factory_pair_has_walkable_paved_route(self):
        town = Town()
        for source in SITES:
            for factory in SITES:
                if source.role != "SUPPLIER" or factory.role != "FACTORY" or source.trade != factory.trade:
                    continue
                with self.subTest(source=source.name, factory=factory.name):
                    points = road_path(entrance(source), entrance(factory))
                    self.assertEqual((points[0], points[-1]), (entrance(source), entrance(factory)))
                    self.assertGreater(path_length(points), 0)
                    for first, last in zip(points, points[1:]):
                        samples = max(1, math.ceil(math.dist(first, last)/8))
                        for index in range(samples+1):
                            amount = index/samples
                            x = first[0]+(last[0]-first[0])*amount
                            y = first[1]+(last[1]-first[1])*amount
                            # Short access aprons connect doorsteps to painted lanes.
                            apron = (math.dist((x, y), entrance(source)) <= 20
                                     or math.dist((x, y), entrance(factory)) <= 20)
                            self.assertTrue(on_road(x, y, COLLISION_BOUNDS) or apron,
                                            (source.name, factory.name, x, y))
                            self.assertTrue(town.can_walk(x, y), (source.name, factory.name, x, y))
                            if 718 <= y <= 900:
                                self.assertIsNotNone(bridge_at(x, y, 3))

    def test_crossings_choose_actual_shortest_useful_bridge(self):
        self.assertEqual(bridge_used(road_path((1098, 1057), (356, 467))), "25 de Abril")
        self.assertEqual(bridge_used(road_path((2148, 1552), (1628, 652))), "Vasco da Gama")
        self.assertIsNone(bridge_used(road_path((1368, 282), (356, 282))))

    def test_same_bank_path_does_not_detour_through_the_river(self):
        points = road_path((1368, 282), (356, 282))
        self.assertTrue(all(y < 718 for x, y in points))
        self.assertGreaterEqual(path_length(points), math.dist(points[0], points[-1]))

    def test_sampling_clamps_to_ends_and_preserves_the_original_polyline(self):
        points = road_path((1368, 282), (356, 282))
        before = deepcopy(points)
        self.assertEqual(point_on_path(points, -1), points[0])
        self.assertEqual(point_on_path(points, 2), points[-1])
        self.assertEqual(point_on_path((points[0],), .5), points[0])
        self.assertNotEqual(point_on_path(points, .5), points[0])
        self.assertEqual(points, before)

    def test_search_is_cached_across_frame_sampling(self):
        road_path.cache_clear()
        args = ((1368, 282), (356, 282))
        first = road_path(*args)
        for _ in range(120):
            self.assertIs(road_path(*args), first)
            point_on_path(first, .25)
        cache = road_path.cache_info()
        self.assertEqual((cache.misses, cache.hits), (1, 120))


if __name__ == "__main__":
    unittest.main()
