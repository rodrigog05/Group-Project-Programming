"""The original city drawing groups, projected into the browser viewport."""

from types import SimpleNamespace
import time
import pygame

from actors import underground
from business_signs import BusinessSigns
from casino_art import CasinoLights
from fountain_water import FountainWater
from graphics import Drawing, avatar
from lisbon_scene import LisbonScene
from logistics_view import FleetView
from world_art import LivingWorld
import tycoon as m


class City(LivingWorld):
    def __init__(self, game):
        self.g = game
        self.game = SimpleNamespace(town=game.t, scale_x=1, display_scale=1)
        self.camera = game.camera
        self.canvas = Drawing()
        self.zoom = 1
        self.sites = m.SITES
        self.font = "sans"
        self.game.canvas = self.canvas
        self.game.label = self.label
        self.scene = LisbonScene(self.game, self.sites, draw=False)
        self.scene.create_tram()
        self.actors = []
        self.light_items = []
        self.create_actors()
        self.fleet = FleetView(self.canvas, self.sites, 1)
        self.lights = CasinoLights(self.canvas, self.sites, 1)
        self.water = FountainWater(self.canvas, 1)
        self.business_signs = BusinessSigns(self.canvas, self.sites, 1, self.font)
        self.destination = None
        self.labels = {}
        self.night = None
        self.next_update = 0
        self.minimap = Drawing()
        self.build_minimap()
        self.map_surface = pygame.Surface((248, 214))
        self.viewport = None

    def draw(self):
        from main_ui import label

        g = self.g
        t = g.t
        self.game.town = t
        camera = self.camera
        width, height = round(800 / g.zoom), round(400 / g.zoom)
        if self.viewport is None or self.viewport.get_size() != (width, height):
            self.viewport = pygame.Surface((width, height))
        s = self.viewport
        night = t.market_elapsed % m.DAY_SECONDS >= m.DAYLIGHT_SECONDS
        if self.night != night:
            self.scene.set_night(night)
            self.fleet.set_night(night)
            for item in self.light_items:
                self.canvas.itemconfigure(item, fill="#f5dca0" if night else "#aac5c8")
            self.night = night
        from pathlib import Path

        if not hasattr(self, "maps"):
            root = Path(__file__).parent / "assets"
            self.maps = {
                n: pygame.image.load(str(root / f"world_100_{phase}.png")).convert()
                for n, phase in ((False, "day"), (True, "night"))
            }
        ox, oy = round(camera.x), round(camera.y)
        s.blit(self.maps[night], (0, 0), (ox, oy, width, height))
        for actor in self.actors:
            x, y = actor.position(t.elapsed)
            enabled = g.traffic if actor.kind == "car" else g.actors_enabled
            visible = enabled and camera.sees(x, y) and not underground(actor, x, y)
            if visible != actor.visible:
                self.canvas.itemconfigure(
                    actor.tag, state="normal" if visible else "hidden"
                )
                actor.visible = visible
            if visible:
                x, y = round(x), round(y)
                self.canvas.move(actor.tag, x - actor.drawn_x, y - actor.drawn_y)
                actor.drawn_x, actor.drawn_y = x, y
        self.scene.animate(t.elapsed)
        self.water.update(t.elapsed)
        self.lights.update(t.elapsed)
        self.fleet.paint(t.logistics, camera)
        self.destination = (g.target.name, *g.target.destination) if g.target else None
        if time.monotonic() > self.next_update:
            self.update_labels(t.elapsed)
            self.next_update = time.monotonic() + 0.15
        self.canvas.paint(s, (-ox, -oy))
        if g.target:
            pygame.draw.circle(
                s, "#ffde86", (round(g.target.x) - ox, round(g.target.y) - oy), 17, 2
            )
        site = t.nearby()
        if site:
            l, top, r, b = site.bounds
            pygame.draw.rect(s, "#ffde86", (l - ox, top - oy, r - l, b - top), 2)
        if t.power_up is not None:
            _, symbol, color, px, py = m.POWER_UPS[t.power_up]
            pygame.draw.circle(s, color, (px - ox, py - oy), 12)
            label(s, symbol, (px - ox - 5, py - oy - 8), 20, "#20383c")
        player = avatar(
            t.profile["body"],
            t.profile["hair"],
            t.profile["costume"],
            t.vehicle,
            t.facing,
            1 + int(t.elapsed * 16) % 8 if g.walking else 0,
        )
        s.blit(player, (round(t.x) - ox - 56, round(t.y) - oy - 60))
        g.screen.blit(
            s if g.zoom == 1 else pygame.transform.scale(s, (800, 400)), (0, 36)
        )
        if g.minimap:
            x, y = self.map_point(t.x, t.y)
            self.minimap.coords(self.map_player, x - 3, y - 3, x + 3, y + 3)
            self.minimap.coords(
                self.map_view,
                *self.map_point(ox, oy),
                *self.map_point(ox + width, oy + height),
            )
            self.minimap.itemconfigure(
                self.map_destination, state="normal" if g.target else "hidden"
            )
            if g.target:
                x, y = self.map_point(*g.target.destination)
                self.minimap.coords(self.map_destination, x - 6, y - 6, x + 6, y + 6)
            self.map_surface.fill("#18343f")
            self.minimap.paint(self.map_surface)
            g.screen.blit(self.map_surface, (542, 44))
