import unittest

from menu_scene import KEYFRAMES, SKY, START_POSITION, mix, sky_state, smooth_profile


class MenuSceneTest(unittest.TestCase):
    def test_mix_blends_colors(self):
        self.assertEqual(mix("#000000", "#ffffff", 0), "#000000")
        self.assertEqual(mix("#000000", "#ffffff", 1), "#ffffff")
        self.assertEqual(mix("#000000", "#ffffff", .5), "#808080")

    def test_menu_opens_in_daylight(self):
        sky_top, *_, dark = sky_state(START_POSITION)
        self.assertEqual(dark, 0)
        self.assertEqual(sky_top, SKY["day"][0])

    def test_night_is_dark_and_the_cycle_loops(self):
        self.assertEqual(sky_state(.75)[-1], 1)
        self.assertEqual(sky_state(0), sky_state(1))
        positions = [position for position, *_ in KEYFRAMES]
        self.assertEqual(positions, sorted(positions))

    def test_hill_profile_passes_through_its_points(self):
        points = ((0, 10), (10, 20), (20, 5))
        self.assertEqual(smooth_profile(points, 10), 20)
        self.assertEqual(smooth_profile(points, -5), 10)
        self.assertEqual(smooth_profile(points, 25), 5)
        self.assertTrue(10 < smooth_profile(points, 5) < 20)


if __name__ == "__main__":
    unittest.main()
