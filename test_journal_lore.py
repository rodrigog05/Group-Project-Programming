from dataclasses import FrozenInstanceError
import unittest
from urllib.parse import urlparse

from journal_lore import ALL_LORE, GAME_MAP_NOTE, LANDMARK_LORE, TEJO_LORE
from lisbon_landmarks import LANDMARKS


class JournalLoreTest(unittest.TestCase):
    def test_every_game_landmark_has_an_offline_lore_entry(self):
        self.assertEqual({entry.title for entry in LANDMARK_LORE}, {landmark.name for landmark in LANDMARKS})
        self.assertGreaterEqual(len(TEJO_LORE), 3)
        self.assertEqual(len({entry.key for entry in ALL_LORE}), len(ALL_LORE))
        for entry in ALL_LORE:
            with self.subTest(entry=entry.title):
                self.assertTrue(entry.body)
                self.assertLessEqual(len(entry.body.split()), 160)
                self.assertTrue(entry.sources)

    def test_sources_are_titled_https_references_to_named_authorities(self):
        authorities = {
            "whc.unesco.org", "castelodesaojorge.pt", "www.visitportugal.com",
            "www.cadc-albufeira.eu", "www.portodelisboa.pt", "resources.natural.pt", "www.ccdr-lvt.pt",
        }
        for entry in ALL_LORE:
            for source in entry.sources:
                with self.subTest(entry=entry.title, source=source.title):
                    self.assertTrue(source.title)
                    url = urlparse(source.url)
                    self.assertEqual(url.scheme, "https")
                    self.assertIn(url.netloc, authorities)
                    self.assertTrue(url.path and url.path != "/")

    def test_entries_are_immutable_and_separate_history_from_game_rules(self):
        with self.assertRaises(FrozenInstanceError):
            LANDMARK_LORE[0].title = "Changed"
        self.assertIn("fictional game rules", GAME_MAP_NOTE)


if __name__ == "__main__":
    unittest.main()
