"""Compare the retained player with the character editor's reference drawing."""
import tkinter as tk
from types import SimpleNamespace
import unittest

from lisbon_scene import draw_character
from living_world import LivingWorld
from tycoon import BODY_COLORS, COSTUMES, HAIR_COLORS, Town


class RetainedPlayerTest(unittest.TestCase):
    canvas_class = tk.Canvas

    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except tk.TclError as exc:
            raise unittest.SkipTest(f"Tk display unavailable: {exc}")
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def setUp(self):
        self.canvas = self.canvas_class(self.root)
        self.reference = tk.Canvas(self.root)
        self.town = Town()
        self.view = SimpleNamespace(canvas=self.canvas, game=SimpleNamespace(town=self.town),
                                    zoom=1.25, font="Segoe UI", player_style=None, player_stride=None, player_position=(0, 0))

    def tearDown(self):
        self.canvas.destroy()
        self.reference.destroy()

    def draw(self, moving):
        LivingWorld.update_player(self.view, BODY_COLORS, HAIR_COLORS, COSTUMES, moving)

    def test_movement_and_walking_reuse_character_objects(self):
        self.draw(False)
        items = self.canvas.find_withtag("player")
        for moving, elapsed, x, y in ((True, .12, 500, 350), (True, .22, 530, 360), (False, .5, 540, 360)):
            self.town.x, self.town.y, self.town.elapsed = x, y, elapsed
            self.draw(moving)
            self.assertEqual(self.canvas.find_withtag("player"), items)
            shadow = self.canvas.coords(items[0])
            self.assertAlmostEqual(shadow[0], round(x*self.view.zoom)-11*self.view.zoom)
            self.assertAlmostEqual(shadow[1], round(y*self.view.zoom)+8*self.view.zoom)

    def test_all_outfits_vehicles_and_zoom_levels_match_reference_animation(self):
        for zoom in (1, 1.25, 1.5):
            self.view.zoom, self.view.player_style = zoom, None
            for vehicle in (None, "motorcycle", "car", "van"):
                self.town.vehicle = vehicle
                for costume in COSTUMES:
                    self.town.profile["costume"] = costume
                    for facing in (-1, 1):
                        self.town.facing = facing
                        for moving, elapsed in ((True, .14), (True, .39), (False, .51)):
                            self.town.x, self.town.y = 580.37+elapsed, 450.23+elapsed
                            self.town.elapsed = elapsed
                            self.draw(moving)
                            self.reference.delete("all")
                            draw_character(self.reference, self.town.profile, BODY_COLORS, HAIR_COLORS,
                                           COSTUMES, round(self.town.x*zoom)/zoom, round(self.town.y*zoom)/zoom,
                                           elapsed, moving, facing, tag="reference")
                            self.reference.scale("reference", 0, 0, zoom, zoom)
                            reference = self.reference.find_withtag("reference")
                            with self.subTest(zoom=zoom, vehicle=vehicle, costume=costume, facing=facing, moving=moving):
                                self.assertEqual(len(self.view.player_parts), len(reference))
                                for actual, expected in zip(self.view.player_parts, reference):
                                    self.assertEqual(self.canvas.type(actual), self.reference.type(expected))
                                    for a, b in zip(self.canvas.coords(actual), self.reference.coords(expected)):
                                        self.assertAlmostEqual(a, b, delta=.051)


if __name__ == "__main__":
    unittest.main()
