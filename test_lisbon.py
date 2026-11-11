from pathlib import Path
import unittest
import wave

from lisbon_scene import RIVER_BOTTOM, RIVER_TOP, bridge_center
from tycoon import SITES, Town, pack_save, unpack_save


class LisbonMapTest(unittest.TestCase):
    def test_river_blocks_walking_but_both_bridges_connect_banks(self):
        town = Town()
        for y in range(RIVER_TOP-5, RIVER_BOTTOM+6, 5):
            self.assertFalse(town.can_walk(600, y))
            self.assertTrue(town.can_walk(bridge_center(y), y))
            self.assertTrue(town.can_walk(bridge_center(y, True), y))

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
