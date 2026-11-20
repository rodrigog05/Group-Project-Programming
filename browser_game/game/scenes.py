"""Playable adaptations of the desktop start, garage, monastery, casino and ferry scenes."""

import time
from functools import partial
import pygame

from casino_table import CasinoTable
from ferry_scene import CROSSING_SECONDS, ScenePainter, draw_backdrop, draw_moving
from garage import draw_showroom, greeting
from graphics import Drawing
from interiors import Painter
from menu_scene import LisbonMenuScene
from prayer import draw_prayer
import tycoon as m


class Roulette(CasinoTable):
    def __init__(self, game):
        self.game = game
        self.town = game.t
        self.chip_index = 0
        self.spin = self.ball_pocket = None
        self.wheel_angle = 0
        self.roulette_history = []
        self.casino_result = ("Choose your chip and a colour.", m.GOLD)
        self.frame = pygame.Surface((1200, 940))

    def label(
        self, x, y, value, size=11, color=m.WHITE, bold=False, anchor="w", tag=None
    ):
        self.canvas.create_text(
            x,
            y,
            text=value,
            fill=color,
            font=("sans", size, "bold" if bold else "normal"),
            anchor=anchor,
        )

    def box(self, x, y, x2, y2, color, tag):
        self.canvas.create_rectangle(x, y, x2, y2, fill=color)

    def close_casino(self):
        self.game.leave()

    def draw(self):
        if self.spin and time.perf_counter() - self.spin["start"] >= m.SPIN_SECONDS:
            self.settle_spin()
            self.game.save()
        self.canvas = Drawing()
        self.draw_casino_screen()
        self.canvas.paint(self.frame)
        scale = 0.55
        self.game.screen.blit(
            pygame.transform.smoothscale(
                self.frame.subsurface((0, 100, 1200, 820)), (660, 451)
            ),
            (70, 40),
        )
        for x, y, r, b, fn in self.casino_buttons:
            rect = pygame.Rect(
                70 + x * scale, 40 + (y - 100) * scale, (r - x) * scale, (b - y) * scale
            )
            self.game.buttons.append((rect, fn))


class Scenes:
    def __init__(self, game):
        self.g = game
        self.intro = Drawing()
        self.sky = LisbonMenuScene(self.intro, "sans")
        self.sky.build(800, 540)
        self.scene_started = time.monotonic()
        self.table = None
        self.ferry = None
        self.cache = {}

    def title(self):
        g = self.g
        self.sky.animate(time.monotonic() - self.scene_started)
        self.intro.paint(g.screen)
        g.button((265, 305, 270, 42), "Enter town", g.leave, True)
        g.button(
            (265, 355, 270, 42), "Customize character", partial(g.open, "Character")
        )
        g.button((265, 405, 270, 42), "Start a new town", partial(g.open, "New game"))

    def buy_vehicle(self, key):
        self.g.t.purchase_vehicle(key)
        self.g.reply = self.g.t.message
        self.g.save()

    def garage(self):
        g = self.g
        key = (g.site.name, g.t.vehicle, g.t.bag_size, tuple(g.t.profile.values()))
        if key not in self.cache:
            drawing = Drawing()
            speech, cards = draw_showroom(Painter(drawing), g.t, g.site)
            surface = pygame.Surface((800, 400))
            drawing.paint(surface)
            self.cache.clear()
            self.cache[key] = (surface, cards)
        surface, cards = self.cache[key]
        g.screen.blit(surface, (0, 36))
        for bounds, vehicle in cards:
            x, y, r, b = bounds
            g.buttons.append(
                (
                    pygame.Rect(x, y + 36, r - x, b - y),
                    partial(self.buy_vehicle, vehicle),
                )
            )
        from main_ui import label

        label(g.screen, g.reply or greeting(g.t), (473, 57), 18, "#20383c", 290)
        g.button(
            (16, 455, 205, 34),
            "Manage delivery fleet",
            lambda: (setattr(g, "site", None), g.open("Deliveries")),
        )

    def exchange(self):
        from types import SimpleNamespace
        from exchange import portfolio_rows
        from exchange_panel import _draw_market_board

        rows = portfolio_rows(self.g.t)
        key = tuple((r["ask"], r["bid"], r["activity"]) for r in rows)
        if key not in self.cache:
            board = Drawing()
            board.winfo_width = lambda: 800
            board.winfo_height = lambda: 270
            board.winfo_exists = lambda: True
            _draw_market_board(SimpleNamespace(rows=rows, market_board=board))
            image = pygame.Surface((800, 270))
            board.paint(image)
            self.cache.clear()
            self.cache[key] = pygame.transform.smoothscale(image, (800, 185))
        self.g.screen.blit(self.cache[key], (0, 40))

    def monastery(self):
        g = self.g
        drawing = Drawing()
        draw_prayer(drawing, g.t.profile, m.BODY_COLORS, m.HAIR_COLORS, m.COSTUMES)
        drawing.move("all", 80, 36)
        drawing.paint(g.screen)
        from main_ui import label

        label(g.screen, g.t.message, (16, 450), 20, "#ffd681")

    def crossing(self):
        g = self.g
        began, heading, night = self.ferry
        age = time.monotonic() - began
        if age >= CROSSING_SECONDS:
            g.leave()
            return
        scenery = Drawing()
        draw_backdrop(ScenePainter(scenery, night))
        draw_moving(scenery, g.t.profile, age / CROSSING_SECONDS, age, heading, night)
        scenery.move("all", 80, 36)
        scenery.paint(g.screen)
