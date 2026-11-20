"""Pygame draws the original map, character frames, and illustrated store interiors."""

from functools import lru_cache
from pathlib import Path
import math
import pygame
from catalog import ROUTES, WAREHOUSE, entrance
from economy import UPGRADE_PRICE
from world import WIDTH, HEIGHT, RIVER_TOP, RIVER_BOTTOM

W, H = 800, 540
DARK = "#20383c"
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

    def button(self, x, y, w, title, key):
        r = pygame.Rect(x, y, w, 32)
        pygame.draw.rect(self.surface, "#426568", r, border_radius=5)
        text(self.surface, title, x + 9, y + 7, 20)
        self.buttons.append((r, key))

    def street(self, g):
        t = g.town
        x = max(0, min(WIDTH - W, round(t.x - W / 2)))
        y = max(104, min(HEIGHT - 390, round(t.y - 195)))
        s = self.surface
        s.blit(image("world_100_day.png"), (0, 42), (x, y, W, 390))
        s.set_clip((0, 42, W, 390))
        target = g.target()
        pygame.draw.ellipse(s, GOLD, (target.x - x - 13, target.y - y + 46, 26, 10), 3)
        frame = 1 + int(g.elapsed * 16) % 8 if g.moving else 0
        player = image("builder.png").subsurface((frame * 32, 0, 32, 50))
        if g.facing < 0:
            player = pygame.transform.flip(player, True, False)
        s.blit(player, (round(t.x) - x - 16, round(t.y) - y + 10))
        s.set_clip(None)
        dest = target.name
        tx, ty = target.x, target.y + 16
        if (t.y < RIVER_TOP and ty > RIVER_BOTTOM) or (
            t.y > RIVER_BOTTOM and ty < RIVER_TOP
        ):
            north = t.y < RIVER_TOP
            ty = RIVER_TOP - 12 if north else RIVER_BOTTOM + 12
            tx = min(
                (300, 2035 - 0.32 * (ty - RIVER_TOP)),
                key=lambda bx: abs(t.x - bx) + abs(target.x - bx),
            )
            dest += " via bridge"
        dx, dy = tx - t.x, ty - t.y
        directions = ("E", "SE", "S", "SW", "W", "NW", "N", "NE")
        compass = directions[round(math.atan2(dy, dx) * 4 / math.pi) % 8]
        text(
            s,
            f"{dest}   ·   {compass}   {round(math.hypot(dx, dy))} m",
            16,
            443,
            24,
            GOLD,
        )
        place = entrance(t.x, t.y)
        if place:
            i, role = place
            shop = WAREHOUSE if role == "warehouse" else getattr(ROUTES[i], role)
            self.button(16, 484, 306, "E   Enter " + shop.name, "e")
        else:
            text(s, "Walk with WASD or arrow keys", 16, 491, 21)
        self.button(472, 484, 310, "P   Routes, inventory and upgrade", "p")

    def shop(self, g):
        s, t = self.surface, g.town
        i, role = entrance(t.x, t.y)
        if role == "warehouse":
            text(s, WAREHOUSE.name, 68, 110, 40, GOLD)
            text(s, "Upgrade your bag", 68, 180, 29)
            text(
                s, f"12 extra slots · ${UPGRADE_PRICE} · one purchase per game", 68, 227
            )
            text(s, g.message or f"Current capacity: {t.capacity}", 68, 296)
            action = "E   Upgrade bag"
        else:
            r = ROUTES[i]
            art = {
                "supplier": "SUPPLIER",
                "workshop": "FACTORY",
                "market": "PUBLIC_SHOP",
            }[role]
            s.blit(image(f"{art}_{i}.png"), (80, 42))
            status = {
                "supplier": f"{r.material} · ${r.cost} each",
                "workshop": f"{r.material} → {r.product}",
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
            text(s, g.message or greeting, 344, 76, 21, DARK, 194)
            text(s, status, 423, 399, 17, PAPER, 154)
            text(s, getattr(r, role).name, 16, 450, 24, GOLD)
            text(
                s,
                f"{r.material}: {t.materials[i]}     {r.product}: {t.goods[i]}",
                375,
                450,
            )
            action = {
                "supplier": "E   Buy one",
                "workshop": "E   Drop off / collect",
                "market": "E   Sell goods",
            }[role]
            if role == "supplier":
                self.button(224, 484, 155, "Q   Buy up to 4", "q")
        self.button(16, 484, 194, action, "e")
        self.button(621, 484, 163, "Esc   Outside", "escape")

    def guide(self, g):
        s, t = self.surface, g.town
        text(s, "Trading routes", 20, 62, 34, GOLD)
        text(
            s,
            "Choose a route to see your stock, then choose a doorstep to mark on the map.",
            20,
            105,
        )
        for i, r in enumerate(ROUTES):
            x = 20 + i * 192
            self.button(x, 148, 180, f"{i + 1}   {r.product}", str(i + 1))
            text(s, f"{r.material}: {t.materials[i]}", x, 192)
            text(s, f"{r.product}: {t.goods[i]}", x, 220)
        r = ROUTES[g.route]
        text(s, f"{r.material} → {r.product}", 20, 282, 32, GOLD)
        for i, (prefix, shop) in enumerate(
            zip(("Buy", "Make", "Sell"), (r.supplier, r.workshop, r.market))
        ):
            self.button(
                20 + i * 254, 337, 246, f"{'ABC'[i]}  {prefix}: {shop.name}", "abc"[i]
            )
        text(
            s,
            f"Bag {t.carried}/{t.capacity}   ·   {t.reserved} slots reserved by production",
            20,
            405,
        )
        self.button(20, 484, 310, "U   Mark Foundry Warehouse", "u")
        self.button(621, 484, 163, "Esc   Outside", "escape")

    def draw(self, g):
        self.buttons.clear()
        self.surface.fill(DARK)
        {"street": self.street, "shop": self.shop, "guide": self.guide}[g.screen](g)
        text(self.surface, "Foundry Town   /   Core Edition", 15, 11, 26, GOLD)
        text(
            self.surface,
            f"${g.town.cash}      Bag  {g.town.carried}/{g.town.capacity}",
            565,
            12,
            23,
        )
        if g.storage.notice:
            text(self.surface, g.storage.notice, 16, 521, 16, GOLD)
        pygame.display.flip()
