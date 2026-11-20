"""Foundry Town's pygame frontend. prepare.py supplies the shared desktop model."""

import asyncio
from functools import lru_cache, partial
import json
import math
from pathlib import Path
import sys
import time

import pygame
import tycoon as model
from actors import Camera
from interiors import INTERIOR_ROLES, actions_for, vendor_greeting
from ferry import nearby_pier
from prayer import at_monastery
from services import service_options

ASSETS = Path(__file__).parent / "assets"
WEB = sys.platform == "emscripten"
SAVE_KEY = "foundry-town.progress.v1"
W, H = 800, 540
GOLD, PAPER, DARK = "#ffd681", "#f4eee0", "#20383c"


@lru_cache(maxsize=48)
def picture(name):
    return pygame.image.load(str(ASSETS / name)).convert_alpha()


from main_ui import label
from graphics import avatar
from scenes import Scenes, Roulette
from city import City


class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("Foundry Town")
        self.t = model.Town()
        self.t.x, self.t.y = 1368, 650
        self.started = time.time()
        self.storage = None
        self.warning = ""
        if WEB:
            import platform

            try:
                self.storage = platform.window.localStorage
                raw = self.storage.getItem(SAVE_KEY)
                if raw:
                    self.t, self.started = model.unpack_save(json.loads(str(raw)))
            except Exception:
                self.storage = None
                self.warning = "Save unavailable. This session will not overwrite existing progress."
        self.camera = Camera(W, 400, 1)
        self.camera.follow(self.t.x, self.t.y, snap=True)
        self.keys = set()
        self.focus = True
        self.panel = "Welcome"
        self.site = None
        self.reply = ""
        self.buttons = []
        self.labels = []
        self.selection = -1
        self.history = []
        self.accessible = ""
        self.page = 0
        self.target = None
        self.minimap = False
        self.music = False
        self.music_started = False
        self.last_save = time.monotonic()
        self.traffic = True
        self.walking = False
        self.context = {"quantity": 1}
        self.reader_lines = []
        self.city = City(self)
        self.scenes = Scenes(self)
        self.profile_name = ""
        self.zoom = 1.0
        self.actors_enabled = True

    def save(self):
        if self.storage is not None:
            try:
                snapshot = model.pack_save(self.t, self.started)
                editing = self.context.get("paused_route")
                if editing:
                    for route in snapshot["state"]["logistics"]["routes"]:
                        if route["id"] == editing[0]:
                            route["enabled"] = editing[1]
                table = getattr(getattr(self, "scenes", None), "table", None)
                if table and table.spin:
                    snapshot["state"]["cash"] += table.spin["payout"]
                    snapshot["state"]["other_income_today"] += table.spin["payout"]
                    if snapshot["state"]["cash"] >= model.CASH_GOAL:
                        snapshot["state"]["won"] = True
                self.storage.setItem(SAVE_KEY, json.dumps(snapshot))
            except Exception:
                self.warning = "Browser storage is full or unavailable. Progress could not be saved."
        self.last_save = time.monotonic()

    def toggle_music(self):
        try:
            if self.music:
                pygame.mixer.music.pause()
            else:
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                pygame.mixer.music.load(str(ASSETS / "saudade_do_tejo.ogg"))
                pygame.mixer.music.play(-1)
            self.music = not self.music
        except pygame.error as exc:
            self.reply = f"Audio unavailable: {exc}"

    def open(self, panel):
        self.panel, self.page = panel, 0
        self.selection = -1
        if panel in ("Player name", "Quantity"):
            self.profile_name = self.t.profile["name"] if panel == "Player name" else ""
            pygame.key.start_text_input()
        else:
            pygame.key.stop_text_input()
        self.buttons.clear()
        self.keys.clear()
        self.reply = ""

    def read(self, title, text):
        import textwrap

        self.reader_lines = [
            line
            for paragraph in text.splitlines()
            for line in (textwrap.wrap(paragraph, 83) or [""])
        ]
        self.context["reader_title"] = title
        self.subpage("Details")

    def subpage(self, panel):
        self.history.append((self.panel, self.site, self.page))
        self.site = None
        self.open(panel)

    def restore_route(self):
        editing = self.context.pop("paused_route", None)
        if editing:
            identifier, enabled = editing
            self.t.set_delivery_enabled(identifier, enabled)

    def back(self):
        if self.panel == "Choose supplier":
            self.restore_route()
        if self.history:
            panel, self.site, page = self.history.pop()
            self.open(panel)
            self.page = page
        else:
            self.leave()

    def leave(self):
        if (
            self.panel in ("Welcome", "Character", "New game")
            and not self.music_started
        ):
            self.music_started = True
            self.toggle_music()
        self.restore_route()
        self.history.clear()
        if self.site and self.site.role == "CASINO" and self.scenes.table:
            self.scenes.table.settle_spin()
        self.open(None)
        self.site = None
        self.save()

    def enter(self):
        t = self.t
        self.site = t.nearby()
        if self.site:
            self.open(self.site.name)
            if self.site.role == "CASINO":
                self.scenes.table = Roulette(self)
            if self.site.role in INTERIOR_ROLES:
                self.reply = vendor_greeting(t, self.site)
        elif nearby_pier(t.x, t.y):
            self.open("Ferry")
        elif at_monastery(t):
            self.open("Mosteiro dos Jerónimos")
            t.visit_monastery()
            self.reply = t.message

    def trade(self, key):
        if key in ("e", "q"):
            self.t.interact(bulk=key == "q")
        else:
            self.t.buy_eggs(bulk=key == "r")
        self.reply = self.t.message
        self.save()

    def button(self, rect, title, action, primary=False):
        rect = pygame.Rect(rect)
        pygame.draw.rect(
            self.screen, GOLD if primary else "#38585b", rect, border_radius=5
        )
        label(
            self.screen, title, (rect.x + 7, rect.y + 7), 19, DARK if primary else PAPER
        )
        self.buttons.append((rect, action))
        self.labels.append(title)

    def key(self, key):
        if self.panel and key == "home":
            self.selection = 0
            return
        if (
            self.panel
            and self.buttons
            and key in ("down", "up", "tab")
            and self.panel not in ("Player name", "Quantity")
        ):
            self.selection = (self.selection + (-1 if key == "up" else 1)) % len(
                self.buttons
            )
            return
        if (
            key == "return"
            and self.selection >= 0
            and self.selection < len(self.buttons)
        ):
            self.buttons[self.selection][1]()
            self.save()
            return
        if self.panel == "Welcome" and key in ("return", "space"):
            self.leave()
        elif self.panel == "Quantity":
            if (
                key == "return"
                and self.profile_name.isdecimal()
                and int(self.profile_name) > 0
            ):
                self.context["quantity"] = int(self.profile_name)
                self.back()
            elif key == "backspace":
                self.profile_name = self.profile_name[:-1]
            elif key == "escape":
                self.back()
        elif self.panel == "Player name":
            if key == "return":
                self.t.set_profile({"name": self.profile_name})
                self.open("Character")
                self.save()
            elif key == "backspace":
                self.profile_name = self.profile_name[:-1]
            elif key == "escape":
                self.open("Character")
        elif self.site and self.site.role == "CASINO":
            self.scenes.table.casino_key(key)
        elif (
            self.site and self.site.role == "GARAGE" and key in "1234" and len(key) == 1
        ):
            self.scenes.buy_vehicle(list(model.VEHICLES)[int(key) - 1])
        elif key == "escape":
            self.back()
        elif self.panel:
            if self.site and self.site.role in INTERIOR_ROLES:
                if key in [k for _, k in actions_for(self.t, self.site)]:
                    self.trade(key)
            elif key in ("page down", "page up"):
                self.page = max(0, self.page + (1 if key == "page down" else -1))
        elif key in ("p", "j", "b", "c", "l", "f1", "i"):
            self.open(
                {
                    "p": "Places",
                    "j": "Journal",
                    "b": "Businesses",
                    "c": "Contracts",
                    "l": "Deliveries",
                    "f1": "Settings",
                    "i": "Inventory",
                }[key]
            )
        elif key == "m":
            self.minimap = not self.minimap
        elif key == "e":
            self.enter()
        elif (
            key in ("q", "r", "f")
            and self.t.nearby()
            and self.t.nearby().role == "SUPPLIER"
        ):
            self.trade(key)

    def tick(self, dt):
        t = self.t
        if self.panel in ("Welcome", "New game", "Character", "Player name"):
            return
        t.sync_market(time.time() - self.started)
        if not self.focus:
            return
        if not t.won or t.milestone_acknowledged:
            model.advance_city(t, dt)
            t.advance_research(dt)
            t.advance_deliveries(dt)
            t.advance_contracts(dt)
            t.advance_businesses(dt)
        if t.won and not t.milestone_acknowledged and self.panel != "Cash milestone":
            self.site = None
            self.open("Cash milestone")
        if (
            not self.panel
            or (self.site and self.site.role in (*INTERIOR_ROLES, "GARAGE"))
            or self.panel == "Crossing"
        ):
            t.advance(dt)
        dx = int(bool(self.keys & {"right", "d"})) - int(
            bool(self.keys & {"left", "a"})
        )
        dy = int(bool(self.keys & {"down", "s"})) - int(bool(self.keys & {"up", "w"}))
        self.walking = False
        if not self.panel:
            previous = t.x, t.y
            steps = max(1, math.ceil(dt / 0.05))
            for _ in range(steps):
                t.move(dx, dy, dt / steps)
            self.walking = previous != (t.x, t.y)
        self.camera.zoom = self.zoom
        self.camera.follow(t.x, t.y, dt)
        if time.monotonic() - self.last_save > 8:
            self.save()

    def world(self):
        t, s = self.t, self.screen
        self.city.draw()
        nearby = t.nearby()
        hint = (
            f"E   Enter {nearby.name}"
            if nearby
            else "WASD / arrows to walk     E to enter"
        )
        if not nearby and nearby_pier(t.x, t.y):
            hint = "E   Board ferry"
        if at_monastery(t):
            hint = "E   Visit Mosteiro dos Jerónimos"
        label(s, hint, (14, 444), 25, GOLD)
        if not t.won:
            label(s, f"Goal  ${model.CASH_GOAL}", (665, 447), 21, GOLD)
        if self.target:
            from guidance import next_step

            (tx, ty), via = next_step(t.x, t.y, *self.target.destination)
            from guidance import compass
            from ferry import FERRY_PIERS

            if not t.vehicle and (t.y < model.RIVER_TOP) != (
                self.target.y < model.RIVER_TOP
            ):
                pier = next(
                    p for p in FERRY_PIERS if p.north == (t.y < model.RIVER_TOP)
                )
                tx, ty = pier.position
                via = "via " + pier.name + " ferry"
            label(
                s,
                f"{self.target.name}   {compass(tx - t.x, ty - t.y)}   {math.hypot(tx - t.x, ty - t.y):.0f}   {via}",
                (14, 474),
            )
        elif t.notice and t.notice_until > t.elapsed:
            label(s, t.notice, (14, 474), 20, GOLD)
        else:
            label(
                s, "Goldenfield Farm → Sunrise Bakery → Daily Bread Market", (14, 474)
            )
        for i, (shortcut, name) in enumerate(
            (
                ("P", "Places"),
                ("J", "Journal"),
                ("B", "Businesses"),
                ("L", "Deliveries"),
                ("C", "Contracts"),
                ("I", "Inventory"),
                ("F1", "Settings"),
            )
        ):
            self.button(
                (8 + 112 * i, 501, 108, 31),
                shortcut + " " + name,
                partial(self.open, name),
            )

    def menu(self):
        t, s = self.t, self.screen
        site = self.site
        if self.panel == "Details":
            rows = 15
            pages = max(1, math.ceil(len(self.reader_lines) / rows))
            self.page = min(self.page, pages - 1)
            label(s, self.context["reader_title"], (22, 50), 28, GOLD)
            for i, line in enumerate(
                self.reader_lines[rows * self.page : rows * (self.page + 1)]
            ):
                label(s, line, (22, 89 + i * 23), 20)
            if pages > 1:
                for x, title, delta in ((22, "Previous", -1), (165, "Next", 1)):
                    self.button(
                        (x, 448, 125, 35),
                        title,
                        partial(setattr, self, "page", (self.page + delta) % pages),
                    )
            self.button((674, 498, 110, 32), "Esc  Back", self.back)
            return
        if self.panel == "Welcome":
            self.scenes.title()
            return
        if site and site.role == "GARAGE":
            self.scenes.garage()
        elif site and site.role == "CASINO":
            self.scenes.table.draw()
        elif self.panel == "Mosteiro dos Jerónimos":
            self.scenes.monastery()
        elif self.panel == "Crossing":
            self.scenes.crossing()
        elif site and site.role in INTERIOR_ROLES:
            trade = t.business_site(site).trade
            img = picture(f"interiors/{site.role.replace(' ', '_')}_{trade}.png")
            s.blit(img, (80, 36))
            label(s, self.reply, (343, 66), 20, DARK, 190)
            label(s, t.site_status(site), (420, 394), 16, PAPER, 155)
            sprite = avatar(
                t.profile["body"], t.profile["hair"], t.profile["costume"], None, 1, 0
            )
            s.blit(pygame.transform.scale(sprite, (224, 168)), (124, 276))
            actions = actions_for(t, site)
            for i, (title, key) in enumerate(actions):
                self.button(
                    (12 + i * 155, 453, 148, 36),
                    title,
                    partial(self.trade, key),
                    i == 0,
                )
        else:
            options = service_options(self)
            is_exchange = site and site.role == "EXCHANGE"
            count = 4 if is_exchange else 8
            top = 235 if is_exchange else 48
            if is_exchange:
                self.scenes.exchange()
            pages = max(1, math.ceil(len(options) / count))
            self.page = min(self.page, pages - 1)
            for i, (title, action) in enumerate(
                options[self.page * count : (self.page + 1) * count]
            ):
                self.button((20, top + i * 42, W - 40, 36), title, action)
            if pages > 1:
                for x, title, delta in ((20, "Previous", -1), (160, "Next", 1)):
                    self.button(
                        (x, 392, 120, 32),
                        title,
                        partial(setattr, self, "page", (self.page + delta) % pages),
                    )
                label(s, f"{self.page + 1} / {pages}", (300, 398))
            label(s, self.reply, (20, 434), 19, GOLD, 740)
        self.button(
            (W - 126, H - 42, 112, 32),
            "Esc  Back" if self.history else "Esc  Outside",
            self.back,
        )
        if self.panel == "Character":
            sprite = avatar(
                t.profile["body"], t.profile["hair"], t.profile["costume"], None, 1, 0
            )
            s.blit(pygame.transform.scale(sprite, (224, 168)), (290, 260))

    def draw(self):
        self.buttons.clear()
        self.labels.clear()
        self.screen.fill(DARK)
        if self.panel:
            self.menu()
        else:
            self.world()
        if self.panel and 0 <= self.selection < len(self.buttons):
            pygame.draw.rect(
                self.screen, GOLD, self.buttons[self.selection][0], 2, border_radius=4
            )
        if WEB:
            description = (
                (self.panel or "Foundry Town") + " | " + " | ".join(self.labels)
            )
            if description != self.accessible:
                import platform

                platform.window.eval(
                    "document.getElementById('canvas').setAttribute('aria-label',"
                    + json.dumps(description)
                    + ")"
                )
                self.accessible = description
        if self.panel == "Welcome":
            return pygame.display.flip()
        label(self.screen, self.panel or "Foundry Town", (12, 8), 24, GOLD)
        t = self.t
        label(
            self.screen,
            f"Day {t.day}    ${t.cash}    Bag {t.cargo}/{t.carry_capacity}",
            (530, 9),
            21,
        )
        if self.warning:
            label(self.screen, self.warning, (12, H - 25), 16, GOLD)
        pygame.display.flip()


async def main():
    pygame.display.init()
    pygame.font.init()
    g = Game()
    last = time.monotonic()
    while True:
        now = time.monotonic()
        dt, last = min(0.25, now - last), now
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                g.save()
                return
            if e.type == pygame.WINDOWFOCUSLOST:
                g.keys.clear()
                g.focus = False
                g.save()
            elif e.type == pygame.WINDOWFOCUSGAINED:
                g.focus = True
            elif e.type == pygame.KEYDOWN:
                key = pygame.key.name(e.key)
                if key not in g.keys:
                    g.key(key)
                    g.keys.add(key)
            elif e.type == pygame.TEXTINPUT and g.panel == "Quantity":
                if e.text.isascii() and e.text.isdecimal():
                    g.profile_name = (g.profile_name + e.text)[:6]
            elif e.type == pygame.TEXTINPUT and g.panel == "Player name":
                g.profile_name = (g.profile_name + e.text)[:24]
            elif e.type == pygame.KEYUP:
                g.keys.discard(pygame.key.name(e.key))
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                for rect, action in g.buttons:
                    if rect.collidepoint(e.pos):
                        action()
                        g.save()
                        break
        g.tick(dt)
        g.draw()
        await asyncio.sleep(0)


if __name__ == "__main__":
    asyncio.run(main())
