import ctypes as ct
import sys
import unittest

import test_retained_player as retained_tests
from benchmark_world import frame_statistics
from windows_canvas import WindowsCanvas


class BenchmarkStatisticsTest(unittest.TestCase):
    def test_uniform_completed_frames_report_their_rate_and_interval(self):
        stats = frame_statistics([(i+1)/120 for i in range(1200)], 10, 10)
        self.assertEqual(stats["average_fps"], 120)
        self.assertGreaterEqual(stats["lowest_one_second_fps"], 119)
        self.assertAlmostEqual(stats["p99_frame_ms"], 1000/120)

    def test_a_stall_keeps_empty_complete_windows_in_the_low_fps_count(self):
        frames = [i/10 for i in range(1, 10)]+[2+i/10 for i in range(1, 10)]
        stats = frame_statistics(frames, 3, 3)
        self.assertEqual(stats["one_second_counts"], [9, 0, 9])
        self.assertEqual(stats["lowest_one_second_fps"], 0)
        self.assertGreater(stats["p99_frame_ms"], 1000)


@unittest.skipUnless(sys.platform == "win32", "Windows renderer")
class WindowsPlayerTest(retained_tests.RetainedPlayerTest):
    canvas_class = WindowsCanvas

    def test_sprite_pixels_have_transparency_and_premultiplied_edges(self):
        self.canvas.create_oval(0, 0, 20, 20, fill="#ff0000", outline="", tags="test")
        items = [self.canvas.items[key] for key in self.canvas.find_withtag("test")]
        signature, left, top = self.canvas._sprite("test", items)
        sprite = self.canvas.sprite_cache[signature]
        pixels = ct.string_at(sprite.pixels, sprite.width()*sprite.height()*4)
        alpha = pixels[3::4]
        self.assertEqual((min(alpha), max(alpha)), (0, 255))
        self.assertTrue(any(0 < a < 255 for a in alpha))
        for offset in range(0, len(pixels), 4):
            b, g, r, a = pixels[offset:offset+4]
            self.assertEqual((b, g), (0, 0))
            self.assertLessEqual(r, a)

    def test_moving_a_cached_group_reuses_its_bitmap(self):
        self.draw(False)
        items = [self.canvas.items[key] for key in self.canvas.find_withtag("player")]
        signature, left, top = self.canvas._sprite("player", items)
        bitmap = self.canvas.sprite_cache[signature]
        self.canvas.move("player", 12, 7)
        self.assertEqual(self.canvas.cached_groups["player"], [signature, left+12, top+7])
        self.assertNotIn("player", self.canvas.dirty)
        self.assertIs(self.canvas.sprite_cache[signature], bitmap)

    def test_destroy_releases_bitmap_contexts_and_timer_request(self):
        self.draw(False)
        items = [self.canvas.items[key] for key in self.canvas.find_withtag("player")]
        signature, left, top = self.canvas._sprite("player", items)
        sprite = self.canvas.sprite_cache[signature]
        self.canvas.destroy()
        self.assertIsNone(sprite.dc)
        self.assertEqual(self.canvas.graphics.token.value, 0)
        self.assertFalse(self.canvas.graphics.timer_active)

    def tearDown(self):
        if self.canvas.winfo_exists():
            self.canvas.destroy()
        self.reference.destroy()


if __name__ == "__main__":
    unittest.main()
