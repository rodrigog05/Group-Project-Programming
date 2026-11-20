"""Pygame draws the original map, character frames, and illustrated store interiors."""

import math
from functools import lru_cache
from pathlib import Path

import pygame
from catalog import FERRY_FARE, GARAGES, PIERS, ROUTES, VEHICLES, WAREHOUSE, entrance
from controller import FERRY_SECONDS
from economy import UPGRADE_PRICE
from world import HEIGHT, RIVER_BOTTOM, RIVER_TOP, WIDTH

from menu_scene import GOLD as MENU_GOLD
from menu_scene import INK, MINT, WHITE, LisbonMenuScene

W, H = 1280, 720
HEADER = 64
FOOTER = 620
MAP_VIEW = pygame.Rect(0, HEADER, W, FOOTER - HEADER)
DARK = "#101f28"
PANEL = "#16303a"
EDGE = "#31515d"
GOLD = "#ffda86"
PAPER = "#fff3dc"


@lru_cache(maxsize=18)
def image(name):
    return pygame.image.load(
        str(Path(__file__).parent / "assets" / name)
    ).convert_alpha()


@lru_cache(maxsize=8)
def font(size):
    return pygame.font.Font(None, size)


VEHICLE_FRAME = (104, 79, 52, 56)  # Width, height and the vehicle's anchor in vehicles.png


@lru_cache(maxsize=16)
def vehicle_art(index, scale=1.0, flip=False):
    width, height, _, _ = VEHICLE_FRAME
    art = image("vehicles.png").subsurface((index * width, 0, width, height))
    if scale != 1:
        art = pygame.transform.smoothscale_by(art, scale)
    return pygame.transform.flip(art, True, False) if flip else art


@lru_cache(maxsize=12)
def shop_art(name):
    art = image(name)
    return pygame.transform.smoothscale_by(art, 1.3)


def text(surface, message, x, y, size=22, color=PAPER, width=None):
    line = ""
    for word in message.split():
        longer = (line + " " + word).strip()
        if line and width and font(size).size(longer)[0] > width:
            surface.blit(font(size).render(line, True, color), (x, y))
            line = word
            y += font(size).get_linesize()
        else:
            line = longer
    surface.blit(font(size).render(line, True, color), (x, y))


class View:
    def __init__(self, surface):
        self.surface = surface
        self.buttons = []
        self.menu_scene = LisbonMenuScene((W, H))

    def panel(self, rect, border=EDGE):
        pygame.draw.rect(self.surface, PANEL, rect, border_radius=10)
        pygame.draw.rect(self.surface, border, rect, width=2, border_radius=10)

    def button(self, x, y, w, title, key, *, fill="#365b64", color=PAPER):
        r = pygame.Rect(x, y, w, 48)
        if key is not None and r.collidepoint(pygame.mouse.get_pos()):
            fill = pygame.Color(fill).lerp(pygame.Color("#ffffff"), 0.14)
        pygame.draw.rect(self.surface, fill, r, border_radius=7)
        label = font(26).render(title, True, color)
        self.surface.blit(label, label.get_rect(midleft=(x + 14, r.centery)))
        if key is not None:
            self.buttons.append((r, key))

    def menu(self, game):
        s = self.surface
        self.menu_scene.draw(s, game.menu_elapsed)
        pygame.draw.rect(s, "#0a141b", (398, 22, 492, 82), border_radius=10)
        self.panel((394, 18, 492, 82), MENU_GOLD)
        for title, size, y, color in (
            ("FOUNDRY TOWN", 46, 46, MENU_GOLD),
            ("LISBOA  ·  Build your fortune along the Tejo", 23, 77, MINT),
        ):
            label = font(size).render(title, True, color)
            s.blit(label, label.get_rect(center=(W // 2, y)))

        if game.screen == "rules":
            self.panel((255, 341, 770, 348), MENU_GOLD)
            text(s, "Rules & How to Play", 287, 365, 40, MENU_GOLD)
            for y, line in (
                (
                    421,
                    "WASD or arrows to walk. E opens a shop and performs its action.",
                ),
                (
                    468,
                    "Buy supplies with E or buy up to four with Q. Take them to a workshop, wait for your batch, collect it and sell it at the market.",
                ),
                (
                    536,
                    "Press P for routes and inventory. Upgrade your bag at Foundry Warehouse for $100. Your progress saves in this browser.",
                ),
            ):
                text(s, line, 287, y, 25, WHITE, width=706)
            self.button(287, 615, 174, "Esc   Back", "escape")
        elif game.screen == "confirm_new":
            self.panel((305, 475, 670, 204), MENU_GOLD)
            text(s, "Start a new game?", 337, 499, 40, MENU_GOLD)
            text(
                s,
                "This will replace your saved progress in this browser.",
                337,
                550,
                26,
            )
            self.button(
                337, 603, 267, "Y   Replace save", "y", fill=MENU_GOLD, color=INK
            )
            self.button(625, 603, 318, "Esc   Keep my save", "escape")
        else:
            self.panel((280, 451, 720, 230), MENU_GOLD)
            pygame.draw.line(s, EDGE, (615, 479), (615, 653), 2)
            text(s, "CORE EDITION", 312, 492, 34, MENU_GOLD)
            if game.storage.notice:
                status = game.storage.notice
            elif game.storage.has_save:
                status = f"Saved in this browser · ${game.town.cash:,}"
            else:
                status = "No saved game yet"
            text(s, status, 312, 543, 25, MINT, width=269)
            self.button(644, 477, 324, "New Game   [N]", "n", fill=MENU_GOLD, color=INK)
            if game.storage.has_save:
                self.button(
                    644, 541, 324, "Continue   [C]", "c", fill=MENU_GOLD, color=INK
                )
            else:
                self.button(
                    644, 541, 324, "Continue", None, fill="#253e48", color="#a0b2b8"
                )
            self.button(644, 605, 324, "Rules & How to Play   [R]", "r")

    def street(self, g):
        t = g.town
        x = max(0, min(WIDTH - W, round(t.x - W / 2)))
        y = max(104, min(HEIGHT - MAP_VIEW.height, round(t.y - MAP_VIEW.height / 2)))
        s = self.surface
        s.blit(image("world_100_day.png"), MAP_VIEW.topleft, (x, y, *MAP_VIEW.size))
        s.set_clip(MAP_VIEW)
        target = g.target()
        pygame.draw.ellipse(
            s, GOLD, (target.x - x - 13, target.y - y + HEADER + 4, 26, 10), 3
        )
        if t.ride:
            _, _, anchor_x, anchor_y = VEHICLE_FRAME
            index = next(i for i, v in enumerate(VEHICLES) if v.key == t.vehicle)
            art = vehicle_art(index, 1.0, g.facing < 0)
            s.blit(art, (round(t.x) - x - anchor_x, round(t.y) - y + HEADER - anchor_y))
        else:
            frame = 1 + int(g.elapsed * 16) % 8 if g.moving else 0
            player = image("builder.png").subsurface((frame * 32, 0, 32, 50))
            if g.facing < 0:
                player = pygame.transform.flip(player, True, False)
            s.blit(player, (round(t.x) - x - 16, round(t.y) - y + HEADER - 32))
        s.set_clip(None)
        dest = target.name
        tx, ty = target.x, target.y + 16
        if (t.y < RIVER_TOP and ty > RIVER_BOTTOM) or (
            t.y > RIVER_BOTTOM and ty < RIVER_TOP
        ):
            north = t.y < RIVER_TOP
            if t.ride:
                ty = RIVER_TOP - 12 if north else RIVER_BOTTOM + 12
                tx = min(
                    (300, 2035 - 0.32 * (ty - RIVER_TOP)),
                    key=lambda bx: abs(t.x - bx) + abs(target.x - bx),
                )
                dest += " via bridge"
            else:
                pier = PIERS[0 if north else 1]  # On foot, head for the ferry on this bank.
                tx, ty = pier.x, pier.y
                dest += " via ferry"
        dx, dy = tx - t.x, ty - t.y
        directions = ("E", "SE", "S", "SW", "W", "NW", "N", "NE")
        compass = directions[round(math.atan2(dy, dx) * 4 / math.pi) % 8]
        text(
            s,
            f"{dest}   ·   {compass}   {round(math.hypot(dx, dy))} m",
            476,
            658,
            28,
            GOLD,
        )
        place = entrance(t.x, t.y)
        if place and place[1] == "ferry":
            other = PIERS[1 - place[0]].name
            self.button(24, 644, 430, f"E   Ferry to {other}  ·  ${FERRY_FARE}", "e")
        elif place:
            i, role = place
            if role == "warehouse":
                shop = WAREHOUSE
            elif role == "garage":
                shop = GARAGES[i]
            else:
                shop = getattr(ROUTES[i], role)
            self.button(24, 644, 420, "E   Enter " + shop.name, "e")
        elif g.message:
            text(s, g.message, 24, 648, 22, GOLD, width=440)
        else:
            text(s, "Walk with WASD or arrow keys", 24, 657, 26)
        self.button(930, 644, 326, "P   Routes and inventory", "p")

    def garage(self, g, index):
        """Showroom: the four vehicles with price, trunk and speeds. Keys 1-4 buy."""
        s, t = self.surface, g.town
        text(s, GARAGES[index].name, 24, 84, 44, GOLD)
        text(s, g.message or "The bridges carry vehicles only. Pick a ride and drive across the Tejo.",
             24, 128, 26, MINT if not g.message else GOLD, width=1220)
        for i, ride in enumerate(VEHICLES):
            x, current = 24 + i * 312, t.vehicle == ride.key
            self.panel((x, 166, 296, 438), GOLD if current else EDGE)
            art = vehicle_art(i, 2.0)
            s.blit(art, art.get_rect(midbottom=(x + 148, 352)))
            pygame.draw.ellipse(s, "#2c4a55", (x + 48, 344, 200, 18), 2)
            text(s, ride.label, x + 18, 372, 34, GOLD)
            if current:
                text(s, "YOUR RIDE", x + 18, 410, 30, MINT)
            else:
                text(s, f"${ride.price}", x + 18, 410, 34, PAPER)
            room = 12 * (2 if t.upgraded else 1) + ride.trunk
            text(s, f"Trunk +{ride.trunk}  ·  {room} cargo slots", x + 18, 452, 23)
            text(s, f"Road {ride.road_speed}  ·  Off-road {ride.offroad_speed}", x + 18, 482, 23)
            if not current:
                self.button(x + 18, 530, 260, f"{i + 1}   Buy", str(i + 1), fill=GOLD, color=DARK)
        self.button(1036, 644, 220, "Esc   Outside", "escape")

    def ferry(self, g):
        """The cacilheiro crossing the Tejo, over the animated Lisbon river scene."""
        s, t = self.surface, g.town
        self.menu_scene.draw(s, g.ferry_elapsed)
        progress = min(1, g.ferry_elapsed / (FERRY_SECONDS - 0.6))
        eased = progress * progress * (3 - 2 * progress)
        # Lisbon is on the right of this view and Almada on the left.
        start, end = (930, 330) if g.ferry_heading > 0 else (330, 930)
        bx = start + (end - start) * eased
        by = 540 + math.sin(g.ferry_elapsed * 2.4) * 3
        bow = -1 if end < start else 1
        pygame.draw.rect(s, "#f5efe2", (bx - 60, by - 54, 104, 40))
        for w in range(5):
            pygame.draw.rect(s, "#2f4b5a", (bx - 52 + w * 18, by - 46, 12, 12))
        pygame.draw.rect(s, "#2f3d45", (bx - 10, by - 78, 18, 24))
        pygame.draw.rect(s, "#d33a35", (bx - 10, by - 78, 18, 7))
        # The player stands at the bow; the hull, drawn next, hides their legs.
        player = image("builder.png").subsurface((0, 0, 32, 50))
        if bow < 0:
            player = pygame.transform.flip(player, True, False)
        s.blit(player, (bx + bow * 66 - 16, by - 50))
        hull = [(bx - 92, by - 8), (bx + 92, by - 8), (bx + 92 + bow * 18, by - 24),
                (bx + 72, by + 24), (bx - 72, by + 24)]
        if bow < 0:
            hull = [(2 * bx - px, py) for px, py in hull]
        pygame.draw.polygon(s, "#e07a2e", hull)
        pygame.draw.rect(s, "#f5efe2", (bx - 88, by - 14, 176, 7))
        for trail in range(1, 5):
            tx = bx - bow * (100 + trail * 22)
            pygame.draw.line(s, "#eaf6f4", (tx, by + 12 + trail * 3), (tx - bow * 26, by + 16 + trail * 4), 2)
        pygame.draw.rect(s, DARK, (0, 0, W, HEADER))
        names = (PIERS[0].name, PIERS[1].name)[:: 1 if g.ferry_heading > 0 else -1]
        self.panel((330, 600, 620, 44), GOLD)
        text(s, f"Ferry  ·  {names[0]}  to  {names[1]}", 352, 611, 28, GOLD)
        self.button(1036, 644, 220, "Esc   Skip", "escape")

    def shop(self, g):
        s, t = self.surface, g.town
        i, role = entrance(t.x, t.y)
        if role == "garage":
            self.garage(g, i)
            return
        if role == "warehouse":
            self.panel((24, 88, 1232, 504))
            text(s, WAREHOUSE.name, 60, 132, 47, GOLD)
            text(s, "Upgrade your bag", 60, 226, 38)
            text(
                s,
                f"12 extra slots · ${UPGRADE_PRICE} · one purchase per game",
                60,
                284,
                28,
            )
            text(s, g.message or f"Current capacity: {t.capacity}", 60, 363, 26)
            action = "E   Upgrade bag"
        else:
            r = ROUTES[i]
            art = {
                "supplier": "SUPPLIER",
                "workshop": "FACTORY",
                "market": "PUBLIC_SHOP",
            }[role]
            s.blit(shop_art(f"{art}_{i}.png"), (24, 80))
            status = {
                "supplier": f"{r.material} · ${r.cost} each",
                "workshop": f"{r.material} to {r.product}",
                "market": f"{r.product} · ${r.price} each",
            }[role]
            order = t.orders[i]
            if role == "workshop" and order:
                status = (
                    f"{order.quantity} ready"
                    if order.remaining <= 0
                    else f"Ready in {math.ceil(order.remaining)}s"
                )
            greeting = {
                "supplier": f"I sell {r.material} for ${r.cost} each.",
                "workshop": f"Bring me {r.material}. I'll make {r.product} in {r.seconds} seconds.",
                "market": f"I buy {r.product} for ${r.price} each.",
            }[role]
            text(s, greeting, 369, 123, 24, DARK, 240)
            text(s, status, 467, 535, 22, PAPER, 193)
            self.panel((880, 80, 376, 520))
            text(s, getattr(r, role).name, 906, 111, 39, GOLD, 324)
            text(s, status, 906, 205, 29, MINT, 324)
            pygame.draw.line(s, EDGE, (906, 259), (1230, 259), 2)
            text(s, f"{r.material} in bag: {t.materials[i]}", 906, 290, 27)
            text(s, f"{r.product} in bag: {t.goods[i]}", 906, 333, 27)
            if g.message:
                text(s, g.message, 906, 431, 26, GOLD, 324)
            action = {
                "supplier": "E   Buy one",
                "workshop": "E   Drop off / collect",
                "market": "E   Sell goods",
            }[role]
            if role == "supplier":
                self.button(300, 644, 230, "Q   Buy up to 4", "q")
        self.button(24, 644, 254, action, "e")
        self.button(1036, 644, 220, "Esc   Outside", "escape")

    def guide(self, g):
        s, t = self.surface, g.town
        text(s, "Trading routes", 24, 88, 44, GOLD)
        text(
            s,
            "Choose a route to see your stock, then choose a doorstep to mark on the map.",
            24,
            139,
            26,
        )
        for i, r in enumerate(ROUTES):
            x = 24 + i * 312
            selected = i == g.route
            self.panel((x, 184, 296, 172), GOLD if selected else EDGE)
            self.button(x + 12, 196, 272, f"{i + 1}   {r.product}", str(i + 1))
            text(s, f"{r.material}: {t.materials[i]}", x + 16, 263, 25)
            text(s, f"{r.product}: {t.goods[i]}", x + 16, 304, 25)
        r = ROUTES[g.route]
        self.panel((24, 382, 1232, 208))
        text(s, f"{r.material} to {r.product}", 42, 401, 36, GOLD)
        for i, (prefix, shop) in enumerate(
            zip(("Buy", "Make", "Sell"), (r.supplier, r.workshop, r.market))
        ):
            self.button(
                42 + i * 402, 453, 384, f"{'ABC'[i]}   {prefix} · {shop.name}", "abc"[i]
            )
        text(
            s,
            f"Bag {t.carried}/{t.capacity}   ·   {t.reserved} slots reserved by production",
            42,
            536,
            26,
        )
        self.button(24, 644, 344, "U   Mark Foundry Warehouse", "u")
        self.button(1036, 644, 220, "Esc   Outside", "escape")

    def draw(self, g):
        self.buttons.clear()
        if g.screen in g.MENU_SCREENS:
            self.menu(g)
            pygame.display.flip()
            return
        self.surface.fill(DARK)
        {"street": self.street, "shop": self.shop, "guide": self.guide, "ferry": self.ferry}[g.screen](g)
        text(self.surface, "Foundry Town   /   Core Edition", 24, 20, 32, GOLD)
        text(
            self.surface,
            f"Cash  ${g.town.cash:,}",
            620,
            23,
            27,
            GOLD,
        )
        text(self.surface, f"Bag  {g.town.carried}/{g.town.capacity}", 880, 23, 27)
        text(self.surface, g.town.ride.label if g.town.ride else "On foot", 1080, 23, 27, MINT)
        if g.storage.notice:
            text(self.surface, g.storage.notice, 24, 699, 19, GOLD)
        pygame.display.flip()
