from types import SimpleNamespace
import unittest

from lisbon_landmarks import LANDMARKS, LANDMARK_SOLIDS
from places_menu import directory_entries, destination_for_landmark, neighborhood_for
from tycoon import SITES


class PlacesDirectoryTest(unittest.TestCase):
    def test_tourism_effects_are_explained_for_shops_and_monuments(self):
        rows = directory_entries(SITES)
        pastry = next(entry for entry in rows["sell"] if entry.name == "Pastéis de Belém")
        self.assertIn("+9 extra buyers", pastry.instruction)
        self.assertIn("Mosteiro", pastry.instruction)
        square = next(entry for entry in rows["landmarks"] if entry.name == "Praça do Comércio")
        self.assertIn("Daily Bread Market", square.instruction)
        self.assertIn("The Pottery Shop", square.instruction)

    def test_every_tram_stop_has_a_safe_service_destination(self):
        from tram import TRAM_FARE, TRAM_STOPS
        from tycoon import Town
        rows = directory_entries(SITES)
        town = Town()
        for stop in TRAM_STOPS:
            entry = next(entry for entry in rows["services"] if entry.name == f"Tram · {stop.name}")
            self.assertEqual(entry.destination, stop.position)
            self.assertTrue(town.can_walk(*entry.destination))
            self.assertIn(f"${TRAM_FARE}", entry.instruction)

    def test_businesses_use_current_doorstep_positions_and_correct_tabs(self):
        rows = directory_entries(SITES)
        for site in SITES:
            categories = {"SUPPLIER": ("buy",), "FACTORY": ("make",), "PUBLIC SHOP": ("sell",),
                          "TIER2": ("make", "sell"), "PASTELARIA": ("make", "sell"),
                          "SHIPYARD": ("make", "sell"), "CASINO": ("services",),
                          "GARAGE": ("services",), "WAREHOUSE": ("services",)}[site.role]
            with self.subTest(site=site.name):
                for category in categories:
                    entry = next(entry for entry in rows[category] if entry.name == site.name)
                    self.assertEqual(entry.destination, (site.door[0], site.door[1]+18))
                    self.assertTrue(entry.instruction)
                    self.assertTrue(entry.neighborhood)
                for key in rows:
                    if key not in categories:
                        self.assertNotIn(site.name, [entry.name for entry in rows[key]])

    def test_directory_respects_new_positions_without_a_hardcoded_business_list(self):
        site = SimpleNamespace(name="New timber supplier", role="SUPPLIER", trade=1,
                               x=2100, y=1200, door=(2188, 1304))
        entry = directory_entries((site,), landmarks=())["buy"][0]
        self.assertEqual(entry.destination, (2188, 1322))
        self.assertEqual(entry.neighborhood, "Seixal")
        self.assertIn("Timber", entry.detail)

    def test_landmark_destinations_avoid_monument_walls_and_water(self):
        rows = directory_entries(())["landmarks"]
        self.assertEqual({entry.name for entry in rows}, {landmark.name for landmark in LANDMARKS})
        for landmark in LANDMARKS:
            x, y = destination_for_landmark(landmark)
            with self.subTest(landmark=landmark.name):
                self.assertLess(y, 708)
                for left, top, right, bottom in LANDMARK_SOLIDS:
                    self.assertFalse(left-10 < x < right+10 and top-10 < y < bottom+10)
        tower = next(landmark for landmark in LANDMARKS if landmark.kind == "tower")
        self.assertEqual(destination_for_landmark(tower), (140, 700))

    def test_basic_neighborhood_labels_match_the_playable_map(self):
        for point, expected in (((28, 160), "Belém"), ((748, 160), "Alfama · Graça"),
                                ((1280, 160), "Marvila"), ((2080, 530), "Parque das Nações"),
                                ((650, 935), "Almada · Tejo"), ((1540, 1180), "Cacilhas"),
                                ((2060, 1430), "Palmela")):
            self.assertEqual(neighborhood_for(*point), expected)


if __name__ == "__main__":
    unittest.main()
