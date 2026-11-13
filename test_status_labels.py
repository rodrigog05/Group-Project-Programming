"""Detailed floating figures remain available near the player and guided place."""
from types import SimpleNamespace
import unittest

from living_world import Camera, STATUS_LABEL_RADIUS, status_label_visible


class StatusLabelVisibilityTest(unittest.TestCase):
    def setUp(self):
        self.camera = Camera(1920, 900, 1.25)
        self.site = SimpleNamespace(name="Visible factory", x=1000, y=345)

    def test_nearby_status_is_visible(self):
        self.assertTrue(status_label_visible(self.camera, 1000, 321, self.site))

    def test_distant_details_are_hidden_even_when_building_is_in_camera(self):
        self.assertTrue(self.camera.sees(1088, 445, 140))
        self.assertFalse(status_label_visible(self.camera, 200, 321, self.site))

    def test_guided_place_keeps_details_when_it_is_onscreen(self):
        self.assertTrue(status_label_visible(self.camera, 200, 321, self.site, self.site.name))

    def test_guidance_does_not_draw_offscreen_labels(self):
        self.site.x = 2200
        self.assertFalse(status_label_visible(self.camera, 200, 321, self.site, self.site.name))

    def test_nearby_radius_boundary_is_inclusive(self):
        self.assertTrue(status_label_visible(self.camera, 1088-STATUS_LABEL_RADIUS, 445, self.site))
        self.assertFalse(status_label_visible(self.camera, 1087-STATUS_LABEL_RADIUS, 445, self.site))


if __name__ == "__main__":
    unittest.main()
