from copy import deepcopy
import unittest

from lisbon_scene import FOUNTAIN_BASIN, SCENERY_BLOCKS, SCENERY_PLOTS
from logistics import create_route, normalize_state
from test_logistics import FakeTown
from tycoon import SITES, TRADES, Town


class SimplifiedTownTest(unittest.TestCase):
    def test_one_timber_supplier_remains(self):
        timber = [site.name for site in SITES if site.role == "SUPPLIER" and site.trade == 1]
        self.assertEqual(timber, ["Pine Mill"])

    def test_saved_depot_route_moves_to_pine_mill_and_keeps_its_vehicle(self):
        town = FakeTown()
        self.assertTrue(create_route(town, "van", "Pine Mill", "Oak Workshop", SITES, TRADES))
        saved = deepcopy(town.logistics)
        saved["routes"][0]["source"] = "Marvila Timber Depot"
        restored = normalize_state(saved, SITES)
        self.assertEqual(len(restored["routes"]), 1)
        self.assertEqual((restored["routes"][0]["source"], restored["routes"][0]["kind"]), ("Pine Mill", "van"))

    def test_empty_plots_are_flats_parks_or_fountains(self):
        kinds = [kind for _, kind in SCENERY_PLOTS]
        self.assertEqual(set(kinds), {"flats", "park", "fountain"})
        business_plots = {(site.x, site.y) for site in SITES}
        for position, _ in SCENERY_PLOTS:
            self.assertNotIn(position, business_plots)

    def test_parks_and_squares_are_walkable_but_flats_and_basins_are_solid(self):
        town = Town()
        for (x, y), kind in SCENERY_PLOTS:
            center = (x+88, y+(FOUNTAIN_BASIN[1]+FOUNTAIN_BASIN[3])/2 if kind == "fountain" else y+52)
            corner = (x+20, y+90)
            with self.subTest(kind=kind, plot=(x, y)):
                if kind == "park":
                    self.assertTrue(town.can_walk(*center))
                elif kind == "fountain":
                    self.assertFalse(town.can_walk(*center))
                    self.assertTrue(town.can_walk(*corner))
                else:
                    self.assertFalse(town.can_walk(*center))
        self.assertEqual(len(SCENERY_BLOCKS), sum(kind != "park" for _, kind in SCENERY_PLOTS))


if __name__ == "__main__":
    unittest.main()
