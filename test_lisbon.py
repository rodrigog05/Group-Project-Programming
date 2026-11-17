from pathlib import Path
import unittest
import wave

from lisbon_scene import (RIVER_BOTTOM, RIVER_TOP, STREET_TREES, bridge_center, south,
                          SOUTH_PARK_BOUNDS, SOUTH_PARK_TUNNEL)
from tycoon import SITES, Town, pack_save, unpack_save
from vehicles import in_tunnel, on_road


class LisbonMapTest(unittest.TestCase):
    def test_added_trees_keep_doors_and_bridge_crossings_clear(self):
        town = Town()
        self.assertGreaterEqual(len(STREET_TREES), 60)
        for x, y, size in STREET_TREES:
            self.assertTrue(town.can_walk(x, y), (x, y))
            self.assertFalse(RIVER_TOP <= y <= RIVER_BOTTOM, (x, y))
            for site in SITES:
                door_x, door_y = site.door
                self.assertGreater((x-door_x)**2+(y-door_y)**2, (size+20)**2, site.name)

    def test_river_blocks_walking_but_both_bridges_connect_banks_for_vehicles(self):
        walker, driver = Town(), Town()
        driver.vehicle = "car"
        for y in range(RIVER_TOP-5, RIVER_BOTTOM+6, 5):
            for town in (walker, driver):
                self.assertFalse(town.can_walk(600, y))
            # Only vehicles may use the bridges; walkers take the ferry.
            self.assertTrue(driver.can_walk(bridge_center(y), y))
            self.assertTrue(driver.can_walk(bridge_center(y, True), y))
            if RIVER_TOP+10 < y < RIVER_BOTTOM-10:
                self.assertFalse(walker.can_walk(bridge_center(y), y))
                self.assertFalse(walker.can_walk(bridge_center(y, True), y))

    def test_river_is_wider_than_the_original_channel(self):
        self.assertGreaterEqual(RIVER_BOTTOM-RIVER_TOP, 2*182-10)

    def test_vasco_crossing_is_by_parque_das_nacoes_and_old_channel_is_water(self):
        town = Town()
        town.vehicle = "car"
        market = next(site for site in SITES if site.name == "Mercado das Nações")
        self.assertLess(abs(bridge_center(RIVER_TOP, True)-market.x), 100)
        for y in range(RIVER_TOP, RIVER_BOTTOM+1, 5):
            old_x = 1055-.32*(y-RIVER_TOP)
            self.assertFalse(town.can_walk(old_x, y))
            self.assertTrue(town.can_walk(bridge_center(y, True), y))

    def test_save_on_previous_vasco_bridge_recovers_without_losing_progress(self):
        town = Town()
        town.x, town.y = 1055-.32*(800-RIVER_TOP), 800
        town.cash, town.goods[0] = 234, 2
        town.bridge_journey = {"origin": "south", "bridge": "Vasco da Gama"}
        restored, _ = unpack_save(pack_save(town, 1000))
        self.assertTrue(restored.can_walk(restored.x, restored.y))
        self.assertEqual((restored.cash, restored.cargo), (234, 2))
        self.assertIsNone(restored.bridge_journey)
        self.assertEqual(restored.tolls_paid_total, 0)

    def test_south_bank_garden_keeps_surface_clear_above_a_drivable_tunnel(self):
        left, top, right, bottom = SOUTH_PARK_BOUNDS
        self.assertEqual((left, right), (60, 550))
        self.assertEqual(SOUTH_PARK_TUNNEL[2], south(1370))
        self.assertTrue(in_tunnel(300, south(1370)))
        self.assertTrue(on_road(300, south(1370)))
        self.assertFalse(in_tunnel(300, south(1320)))
        self.assertFalse(on_road(300, south(1320)))
        self.assertTrue(on_road(40, south(1370)))

    def test_every_business_entrance_is_reachable(self):
        town = Town()
        for site in SITES:
            town.x, town.y = site.door[0], site.door[1]+10
            with self.subTest(site=site.name):
                self.assertTrue(town.can_walk(town.x, town.y))
                self.assertIs(town.nearby(), site)

    def test_old_save_in_new_river_moves_to_safe_land_and_keeps_inventory(self):
        town = Town()
        town.x, town.y = 600, 800
        town.cash = 234
        town.goods[0] = 2
        town.tier2_goods = 1
        restored, _ = unpack_save(pack_save(town, 1000))
        self.assertTrue(restored.can_walk(restored.x, restored.y))
        self.assertEqual(restored.cash, 234)
        self.assertEqual(restored.cargo, 3)

    def test_original_soundtrack_is_bundled_as_stereo_audio(self):
        path = Path(__file__).parent / "assets" / "saudade_do_tejo.wav"
        with wave.open(str(path), "rb") as audio:
            self.assertEqual(audio.getnchannels(), 2)
            self.assertEqual(audio.getsampwidth(), 2)
            self.assertGreaterEqual(audio.getnframes()/audio.getframerate(), 59)


if __name__ == "__main__":
    unittest.main()
