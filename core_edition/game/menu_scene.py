"""Animated Lisbon backdrop for the start menu.

The view looks west along the Tejo towards the 25 de Abril bridge: Almada and
Cristo Rei on the left, Alcântara and Alfama's hills on the right. Traffic
crosses the bridge, boats sail the river, and a slow day/night cycle lights
up windows and bridge lamps in the game's flat, pastel style.
"""

import math
import random
from functools import lru_cache
from itertools import pairwise

import pygame

CYCLE_SECONDS = 60
START_POSITION = 0.30  # Open in daylight, a few seconds before sunset.

SKY = {
    "day": ("#8cc4d8", "#f4e6c4"),
    "dusk": ("#5a6aa0", "#f3a577"),
    "night": ("#0f1830", "#2e3d60"),
}
WATER = {
    "day": ("#78b9c6", "#3b8197"),
    "dusk": ("#8d93ad", "#3f5a7c"),
    "night": ("#22385a", "#0e1b31"),
}
# Cycle position, palette and darkness. Dawn reuses the dusk palette.
KEYFRAMES = (
    (0.0, "day", 0.0),
    (0.42, "day", 0.0),
    (0.52, "dusk", 0.35),
    (0.62, "night", 1.0),
    (0.88, "night", 1.0),
    (0.95, "dusk", 0.35),
    (1.0, "day", 0.0),
)
NIGHT_TINT = "#17223f"
INK, GOLD, MINT, WHITE = "#101f28", "#ffc66c", "#6de0b3", "#f2f7f6"
BRIDGE_RED, BRIDGE_DARK = "#c4442f", "#8e2d20"
WALLS = ("#f2e3c6", "#e9c4b6", "#c9dbe0", "#f1d58e", "#e8b7a0", "#d9e2c4", "#f5efe2")
ROOFS = ("#c8693f", "#b85a36", "#d47a4e")
CAR_COLORS = (
    "#d65655",
    "#86caff",
    "#ffc66c",
    "#80dab9",
    "#bea0ec",
    "#e6e9df",
    "#9b584e",
)


def hex_rgb(color):
    return tuple(int(color[index : index + 2], 16) for index in (1, 3, 5))


@lru_cache(maxsize=4096)
def mix(first, second, amount):
    amount = min(1, max(0, amount))
    return "#" + "".join(
        f"{round(a + (b - a) * amount):02x}"
        for a, b in zip(hex_rgb(first), hex_rgb(second))
    )


def sky_state(position):
    """Sky top, sky bottom, water top, water bottom and darkness at a cycle position."""
    position %= 1
    for (start, first, dark_start), (end, second, dark_end) in pairwise(KEYFRAMES):
        if start <= position <= end:
            amount = (position - start) / (end - start) if end > start else 0
            sky = [mix(a, b, amount) for a, b in zip(SKY[first], SKY[second])]
            water = [mix(a, b, amount) for a, b in zip(WATER[first], WATER[second])]
            return (*sky, *water, dark_start + (dark_end - dark_start) * amount)
    return (*SKY["day"], *WATER["day"], 0.0)


def smooth_profile(points, x):
    """Height of a hill outline at x, eased between its control points."""
    if x <= points[0][0]:
        return points[0][1]
    for (x1, y1), (x2, y2) in pairwise(points):
        if x1 <= x <= x2:
            amount = (x - x1) / (x2 - x1)
            amount = amount * amount * (3 - 2 * amount)
            return y1 + (y2 - y1) * amount
    return points[-1][1]


class SceneShapes:
    """Ordered Pygame primitives, grouped so each moving actor keeps its shape."""

    def __init__(self):
        self.items = []
        self.groups = {}

    def add(
        self, kind, points, fill="#000000", tags=(), state="normal", width=1
    ):
        index = len(self.items)
        self.items.append([kind, tuple(points), fill, state, max(1, width)])
        for tag in tags if isinstance(tags, tuple) else (tags,):
            self.groups.setdefault(tag, []).append(index)
        return index

    def create_rectangle(self, *points, **options):
        return self.add("rect", points, **options)

    def create_oval(self, *points, **options):
        return self.add("ellipse", points, **options)

    def create_polygon(self, *points, **options):
        return self.add("polygon", points, **options)

    def create_line(self, *points, **options):
        return self.add("line", points, **options)

    def indices(self, item):
        return self.groups[item] if isinstance(item, str) else (item,)

    def configure(self, item, fill=None, state=None):
        for index in self.indices(item):
            shape = self.items[index]
            if fill is not None:
                shape[2] = fill
            if state is not None:
                shape[3] = state

    def coords(self, item, *points):
        for index in self.indices(item):
            self.items[index][1] = points

    def move(self, tag, dx, dy):
        for index in self.indices(tag):
            shape = self.items[index]
            points = iter(shape[1])
            shape[1] = tuple(
                v for x, y in zip(points, points) for v in (x + dx, y + dy)
            )

    def draw(self, surface):
        for kind, coords, color, state, width in self.items:
            if state == "hidden":
                continue
            points = tuple(zip(coords[::2], coords[1::2]))
            if kind == "line":
                pygame.draw.lines(surface, color, False, points, width)
            elif kind == "polygon":
                pygame.draw.polygon(surface, color, points)
            else:
                (left, top), (right, bottom) = points
                rect = (
                    round(left),
                    round(top),
                    max(1, round(right) - round(left)),
                    max(1, round(bottom) - round(top)),
                )
                draw = pygame.draw.rect if kind == "rect" else pygame.draw.ellipse
                draw(surface, color, rect)


class LisbonMenuScene:
    def __init__(self, size):
        self.shapes = SceneShapes()
        self.ready_at = -1
        self.backdrop = pygame.Surface(size)
        self.build(*size)

    def draw(self, surface, elapsed):
        frame = int(elapsed * 30)
        if self.ready_at != frame:
            self.animate(elapsed)
            self.shapes.draw(self.backdrop)
            self.ready_at = frame
        surface.blit(self.backdrop, (0, 0))

    # ----- Drawing helpers -----

    def shape(self, kind, coords, color, tint=True, tags=(), **options):
        """Create a scene item. Tinted items darken towards blue at night."""
        item = getattr(self.shapes, f"create_{kind}")(
            *coords, fill=color, tags=("scene", *tags), **options
        )
        if tint:
            self.tinted.append((item, color))
        return item

    def rect(self, x1, y1, x2, y2, color, **options):
        return self.shape("rectangle", (x1, y1, x2, y2), color, **options)

    def oval(self, x1, y1, x2, y2, color, **options):
        return self.shape("oval", (x1, y1, x2, y2), color, **options)

    def poly(self, points, color, **options):
        return self.shape("polygon", points, color, **options)

    def line(self, points, color, **options):
        return self.shape("line", points, color, **options)

    def light(self, x, y, radius, color="#ffe4a0", tags=()):
        """A lamp that only shows at night."""
        item = self.shapes.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill=color,
            width=0,
            state="hidden",
            tags=("scene", *tags),
        )
        self.lights.append(item)
        return item

    # ----- Scene -----

    def build(self, width, height):
        c = self.shapes
        self.size = (width, height)
        self.tinted, self.windows, self.lights, self.stars, self.movers = (
            [],
            [],
            [],
            [],
            [],
        )
        self.offsets = {}  # Current (x, y) shift of every moving tag
        self.last_dark = None
        # The fixed seed reproduces the desktop scenery.
        rng = random.Random(1974)  # nosec B311
        w, h = width, height
        self.water_y = water_y = h * 0.56
        self.deck_y = h * 0.395
        self.tower_top = h * 0.15
        self.span = (
            w * 0.05,
            w * 0.25,
            w * 0.67,
            w * 0.88,
        )  # anchorage, towers, anchorage

        # Sky, stars, sun and moon
        self.sky_bands = [
            c.create_rectangle(
                0,
                water_y * i / 24,
                w,
                water_y * (i + 1) / 24 + 1,
                width=0,
                tags="scene",
            )
            for i in range(24)
        ]
        for _ in range(70):
            x, y, size = (
                rng.uniform(0, w),
                rng.uniform(0, water_y * 0.75),
                rng.choice((1, 1, 1.5, 2)),
            )
            self.stars.append(
                c.create_oval(
                    x - size,
                    y - size,
                    x + size,
                    y + size,
                    fill="#f4f1dc",
                    width=0,
                    state="hidden",
                    tags="scene",
                )
            )
        sun = h * 0.045
        self.sun_glow = c.create_oval(
            -sun * 1.8, -sun * 1.8, sun * 1.8, sun * 1.8, width=0, tags="scene"
        )
        self.sun = c.create_oval(-sun, -sun, sun, sun, width=0, tags="scene")
        moon = h * 0.03
        self.moon = c.create_oval(
            -moon,
            -moon,
            moon,
            moon,
            fill="#f3efe0",
            width=0,
            state="hidden",
            tags="scene",
        )
        self.moon_shadow = c.create_oval(
            -moon * 0.3,
            -moon * 0.5,
            moon * 0.15,
            -moon * 0.05,
            fill="#dcd6c2",
            width=0,
            state="hidden",
            tags="scene",
        )
        # The river covers the sun as it sinks below the horizon.
        self.water_bands = [
            c.create_rectangle(
                0,
                water_y + (h - water_y) * i / 12,
                w,
                water_y + (h - water_y) * (i + 1) / 12 + 1,
                width=0,
                tags="scene",
            )
            for i in range(12)
        ]

        # Clouds and distant hills
        for index in range(6):
            x, y, size = (
                rng.uniform(0, w),
                rng.uniform(h * 0.12, h * 0.34),
                rng.uniform(0.7, 1.3) * h * 0.03,
            )
            tag = f"cloud{index}"
            for dx, dy, radius in (
                (0, 0, 1),
                (1.1, 0.25, 0.8),
                (-1.1, 0.3, 0.75),
                (0.5, -0.35, 0.7),
            ):
                self.oval(
                    x + dx * size - radius * size,
                    y + dy * size - radius * size * 0.7,
                    x + dx * size + radius * size,
                    y + dy * size + radius * size * 0.7,
                    "#fbf6ea",
                    tags=(tag,),
                )
            self.oval(
                x - size * 1.9,
                y - size * 0.05,
                x + size * 1.9,
                y + size * 0.6,
                "#fbf6ea",
                tags=(tag,),
            )
            self.movers.append(
                ("cloud", tag, x, rng.uniform(4, 10) * w / 1000, size * 4)
            )
        # Distant rolling hills, smoothed so they read as Monsanto's slopes rather than a plateau.
        ridge = (
            [(0, water_y)]
            + [
                (
                    w * i / 24,
                    water_y
                    - h
                    * (
                        0.045 + 0.02 * math.sin(i * 0.9 + 1) + 0.012 * math.sin(i * 2.3)
                    ),
                )
                for i in range(25)
            ]
            + [(w, water_y)]
        )
        self.poly([value for point in ridge for value in point], "#a7c2b6")

        self.draw_bridge(w, h, rng)
        self.draw_almada(w, h, rng)
        self.draw_lisbon(w, h, rng)
        self.draw_river(w, h, rng)
        self.draw_boats(w, h, rng)

        # Gulls
        for index in range(5):
            tag = f"gull{index}"
            x, y = rng.uniform(0, w), rng.uniform(h * 0.18, h * 0.36)
            self.line(
                (x - 8, y, x - 3, y - 4, x, y, x + 3, y - 4, x + 8, y),
                "#2f3d45",
                tags=(tag,),
                width=2,
            )
            self.movers.append(("gull", tag, x, rng.uniform(25, 45) * w / 1000, y))

    def draw_bridge(self, w, h, rng):
        anchor_left, tower_left, tower_right, anchor_right = self.span
        deck_y, top, water_y = self.deck_y, self.tower_top, self.water_y
        sag_y = deck_y - h * 0.012

        def cable_y(x):
            if x <= tower_left:
                amount = (x - anchor_left) / (tower_left - anchor_left)
                return (
                    deck_y
                    + (top - deck_y) * amount
                    - h * 0.025 * math.sin(math.pi * amount)
                )
            if x >= tower_right:
                amount = (anchor_right - x) / (anchor_right - tower_right)
                return (
                    deck_y
                    + (top - deck_y) * amount
                    - h * 0.025 * math.sin(math.pi * amount)
                )
            middle = (tower_left + tower_right) / 2
            amount = ((x - middle) / ((tower_right - tower_left) / 2)) ** 2
            return sag_y + (top - sag_y) * amount

        # Hangers, then the main cable over them
        step = w / 110
        x = anchor_left + step
        while x < anchor_right:
            if abs(x - tower_left) > step / 2 and abs(x - tower_right) > step / 2:
                self.line((x, cable_y(x), x, deck_y), "#b9483a", width=1)
            x += step
        points = []
        x = anchor_left
        while x <= anchor_right:
            points += [x, cable_y(x)]
            x += w / 200
        self.line(points, BRIDGE_DARK, width=3)

        # Deck: road on top, the red truss with the railway below
        truss_bottom = deck_y + h * 0.05
        self.rect(
            anchor_left, deck_y - h * 0.004, anchor_right, deck_y + h * 0.006, "#5e6b70"
        )
        self.rect(
            anchor_left, deck_y + h * 0.006, anchor_right, truss_bottom, BRIDGE_RED
        )
        self.rect(
            anchor_left,
            deck_y + h * 0.026,
            anchor_right,
            deck_y + h * 0.03,
            BRIDGE_DARK,
        )
        panel = h * 0.022
        x = anchor_left
        while x < anchor_right:
            self.line(
                (
                    x,
                    deck_y + h * 0.006,
                    x + panel / 2,
                    deck_y + h * 0.026,
                    x + panel,
                    deck_y + h * 0.006,
                ),
                BRIDGE_DARK,
                width=1,
            )
            self.line(
                (
                    x,
                    truss_bottom,
                    x + panel / 2,
                    deck_y + h * 0.03,
                    x + panel,
                    truss_bottom,
                ),
                BRIDGE_DARK,
                width=1,
            )
            x += panel
        self.train_y = (deck_y + h * 0.033, truss_bottom - h * 0.003)

        # Towers: two legs joined by cross beams, standing on concrete piers
        for x in (tower_left, tower_right):
            leg, gap = w * 0.0065, w * 0.011
            for left in (x - gap / 2 - leg, x + gap / 2):
                self.poly(
                    (
                        left,
                        top,
                        left + leg,
                        top,
                        left + leg * 1.2,
                        water_y,
                        left - leg * 0.2,
                        water_y,
                    ),
                    BRIDGE_RED,
                )
            for y in (
                top + h * 0.01,
                top + h * 0.07,
                top + h * 0.13,
                deck_y - h * 0.03,
                truss_bottom + h * 0.01,
            ):
                self.rect(x - gap / 2, y, x + gap / 2, y + h * 0.008, BRIDGE_RED)
            self.rect(
                x - gap / 2 - leg * 1.6,
                water_y - h * 0.008,
                x + gap / 2 + leg * 1.6,
                water_y + h * 0.012,
                "#bdb5a2",
            )
            self.light(x, top - h * 0.006, 3, "#ff6a5a")

        # Bridge lamps and the cars on the deck
        x = anchor_left + w * 0.02
        while x < anchor_right:
            self.light(x, deck_y - h * 0.012, 2)
            x += w * 0.03
        car_w, car_h = w * 0.014, h * 0.012
        for index in range(12):
            tag = f"car{index}"
            direction = 1 if index % 2 == 0 else -1
            color = CAR_COLORS[index % len(CAR_COLORS)]
            self.poly(
                (
                    0,
                    car_h * 0.45,
                    car_w * 0.18,
                    0,
                    car_w * 0.82,
                    0,
                    car_w,
                    car_h * 0.45,
                    car_w,
                    car_h,
                    0,
                    car_h,
                ),
                color,
                tags=(tag,),
            )
            self.rect(
                car_w * 0.25,
                car_h * 0.12,
                car_w * 0.75,
                car_h * 0.45,
                "#aac5c8",
                tags=(tag,),
            )
            lamp_x = car_w if direction > 0 else 0
            self.light(lamp_x, car_h * 0.6, 2, tags=(tag,))
            self.shapes.move(tag, 0, deck_y - h * 0.004 - car_h)
            offset = index / 12
            self.movers.append(
                ("car", tag, 0, direction, offset, rng.uniform(0.045, 0.07))
            )

        # A commuter train crosses on the lower deck now and then
        self.train_cars = []
        top_y, bottom_y = self.train_y
        for index in range(4):
            tag = f"train{index}"
            self.rect(0, top_y, w * 0.03, bottom_y, "#d9dfe2", tags=(tag, "train"))
            self.rect(
                w * 0.003,
                top_y + (bottom_y - top_y) * 0.2,
                w * 0.027,
                top_y + (bottom_y - top_y) * 0.55,
                "#2f4b5a",
                tags=(tag, "train"),
            )
            self.train_cars.append(tag)

    def draw_almada(self, w, h, rng):
        water_y = self.water_y
        hill = (
            (0, h * 0.30),
            (w * 0.04, h * 0.285),
            (w * 0.09, h * 0.30),
            (w * 0.14, h * 0.36),
            (w * 0.19, h * 0.46),
            (w * 0.23, h * 0.53),
            (w * 0.27, water_y),
        )
        self.poly(
            [value for point in ((0, water_y),) + hill for value in point], "#b7c08a"
        )
        self.poly(
            [
                0,
                h * 0.36,
                w * 0.05,
                h * 0.34,
                w * 0.12,
                h * 0.40,
                w * 0.2,
                h * 0.50,
                w * 0.24,
                water_y,
                0,
                water_y,
            ],
            "#a3b07a",
        )
        for index in range(14):
            x = rng.uniform(w * 0.01, w * 0.22)
            y = max(
                smooth_profile(hill, x) + h * 0.02,
                rng.uniform(h * 0.40, water_y - h * 0.01),
            )
            radius = h * 0.011
            self.oval(x - radius, y - radius, x + radius, y + radius, "#6f9f7a")
        for x in (w * 0.15, w * 0.18, w * 0.205):
            y = smooth_profile(hill, x) + h * 0.03
            self.house(x, y, w * 0.018, h * 0.03, rng)

        # Cristo Rei on its pedestal above the river
        x, base = w * 0.06, smooth_profile(hill, w * 0.06)
        stone, statue = "#e9e3d3", "#f1ece0"
        self.poly(
            (
                x - w * 0.018,
                base,
                x + w * 0.018,
                base,
                x + w * 0.011,
                base - h * 0.1,
                x - w * 0.011,
                base - h * 0.1,
            ),
            stone,
        )
        self.rect(x - w * 0.004, base - h * 0.075, x + w * 0.004, base, "#8f8a7c")
        self.rect(
            x - w * 0.014, base - h * 0.104, x + w * 0.014, base - h * 0.098, stone
        )
        self.rect(
            x - w * 0.0035, base - h * 0.155, x + w * 0.0035, base - h * 0.104, statue
        )
        self.rect(
            x - w * 0.016, base - h * 0.148, x + w * 0.016, base - h * 0.141, statue
        )
        self.oval(
            x - w * 0.003, base - h * 0.168, x + w * 0.003, base - h * 0.155, statue
        )
        self.light(x, base - h * 0.10, 3, "#fff0c4")

    def draw_lisbon(self, w, h, rng):
        water_y = self.water_y
        # The city starts just east of the bridge's north tower, which stands in the river.
        outline = (
            (w * 0.70, water_y),
            (w * 0.74, h * 0.50),
            (w * 0.79, h * 0.45),
            (w * 0.84, h * 0.41),
            (w * 0.88, h * 0.385),
            (w * 0.93, h * 0.30),
            (w * 0.97, h * 0.32),
            (w * 1.01, h * 0.35),
        )
        self.poly(
            [value for point in outline + ((w, water_y),) for value in point], "#d8cfa8"
        )

        # Castelo de São Jorge on the highest hill
        x, base = w * 0.93, h * 0.31
        stone, shade = "#d9c9a0", "#bfae86"
        self.rect(
            x - w * 0.045, base - h * 0.035, x + w * 0.045, base + h * 0.01, stone
        )
        for offset in range(-44, 45, 8):
            self.rect(
                x + w * offset / 1000,
                base - h * 0.043,
                x + w * (offset + 4) / 1000,
                base - h * 0.035,
                stone,
            )
        for offset, tall in ((-0.04, 0.06), (0, 0.075), (0.038, 0.055)):
            left = x + w * offset - w * 0.008
            self.rect(left, base - h * tall, left + w * 0.016, base, shade)
            for notch in range(3):
                self.rect(
                    left + notch * w * 0.006,
                    base - h * tall - h * 0.007,
                    left + notch * w * 0.006 + w * 0.004,
                    base - h * tall,
                    shade,
                )
        self.line(
            (x + w * 0.0, base - h * 0.082, x, base - h * 0.11), "#5b4b3a", width=2
        )
        self.rect(x, base - h * 0.11, x + w * 0.006, base - h * 0.098, "#2e8b57")
        self.rect(
            x + w * 0.006, base - h * 0.11, x + w * 0.014, base - h * 0.098, "#d33a35"
        )

        # Houses climbing the hills, farthest first
        houses = []
        x = w * 0.705
        while x < w:
            house_w = rng.uniform(0.02, 0.028) * w
            top = smooth_profile(outline, x + house_w / 2) + h * 0.012
            y = water_y - h * 0.014
            while y - h * 0.03 > top:
                house_h = rng.uniform(0.03, 0.042) * h
                houses.append((y, x, house_w, house_h))
                y -= house_h * 0.82
            x += house_w * 0.92
        for y, x, house_w, house_h in sorted(houses):
            self.house(x + house_w / 2, y, house_w, house_h, rng)

        # Waterfront promenade with trees and the yellow tram
        self.rect(w * 0.70, water_y - h * 0.014, w, water_y, "#e8dcc0")
        self.line(
            (w * 0.70, water_y - h * 0.004, w, water_y - h * 0.004), "#9c9483", width=1
        )
        for index in range(7):
            tx = w * 0.72 + index * w * 0.045
            self.oval(
                tx - h * 0.01,
                water_y - h * 0.032,
                tx + h * 0.01,
                water_y - h * 0.012,
                "#6f9f7a",
            )
            self.light(tx + w * 0.012, water_y - h * 0.02, 2)
        tram_w, tram_h = w * 0.035, h * 0.022
        top = water_y - h * 0.006 - tram_h
        self.rect(0, top, tram_w, top + tram_h, "#f2c230", tags=("tram",))
        self.rect(
            0, top + tram_h * 0.78, tram_w, top + tram_h, "#c9472f", tags=("tram",)
        )
        self.rect(
            tram_w * 0.08,
            top - tram_h * 0.12,
            tram_w * 0.92,
            top,
            "#f5efe2",
            tags=("tram",),
        )
        for index in range(4):
            left = tram_w * (0.1 + index * 0.21)
            window = self.rect(
                left,
                top + tram_h * 0.18,
                left + tram_w * 0.15,
                top + tram_h * 0.55,
                "#2f4b5a",
                tint=False,
                tags=("tram",),
            )
            self.windows.append((window, True))
        self.line(
            (tram_w * 0.5, top - tram_h * 0.12, tram_w * 0.62, top - tram_h * 0.6),
            "#3a3a3a",
            width=1,
            tags=("tram",),
        )
        self.movers.append(("tram", "tram", 0, w * 0.70, w - tram_w, w * 0.04))

    def house(self, center_x, bottom, width, height, rng):
        left, right, top = center_x - width / 2, center_x + width / 2, bottom - height
        self.rect(left, top, right, bottom, rng.choice(WALLS))
        roof = rng.choice(ROOFS)
        self.poly(
            (
                left - width * 0.06,
                top,
                center_x,
                top - height * 0.32,
                right + width * 0.06,
                top,
            ),
            roof,
        )
        for column in (0.22, 0.58) if width > 20 else (0.4,):
            window = self.rect(
                left + width * column,
                top + height * 0.22,
                left + width * (column + 0.2),
                top + height * 0.52,
                "#2f4b5a",
                tint=False,
            )
            self.windows.append((window, rng.random() < 0.65))

    def draw_river(self, w, h, rng):
        water_y = self.water_y
        # Light on the water drifts slowly with the current
        for index in range(46):
            depth = rng.random()
            y = water_y + h * 0.008 + (h - water_y) * depth**1.4
            length = w * (0.01 + 0.03 * depth)
            x = rng.uniform(0, w)
            tag = f"shimmer{index}"
            self.line(
                (x, y, x + length, y),
                "#d6ecef",
                tags=(tag,),
                width=1 if depth < 0.5 else 2,
            )
            self.movers.append(
                (
                    "shimmer",
                    tag,
                    x,
                    rng.uniform(4, 14) * w / 1000 * (1 if index % 3 else -1),
                    length,
                )
            )

    def draw_boats(self, w, h, rng):
        water_y = self.water_y
        boats = (
            ("sail", 0.03, 1),
            ("ferry", 0.09, -1),
            ("sail", 0.16, -1),
            ("ferry", 0.27, 1),
            ("sail", 0.36, 1),
        )
        for index, (kind, depth, direction) in enumerate(boats):
            y = water_y + (h - water_y) * depth
            scale = h * (0.0007 + depth * 0.004)
            tag = f"boat{index}"
            if kind == "sail":
                self.poly(
                    (
                        -14 * scale,
                        0,
                        14 * scale,
                        0,
                        10 * scale,
                        5 * scale,
                        -10 * scale,
                        5 * scale,
                    ),
                    "#f5efe2",
                    tags=(tag,),
                )
                self.line((0, 0, 0, -26 * scale), "#5b4b3a", tags=(tag,), width=1)
                self.poly(
                    (
                        1 * scale,
                        -25 * scale,
                        1 * scale,
                        -2 * scale,
                        13 * scale * direction,
                        -2 * scale,
                    ),
                    "#fbf6ea",
                    tags=(tag,),
                )
                self.light(0, -27 * scale, 2, "#ff6a5a", tags=(tag,))
            else:
                self.poly(
                    (
                        -22 * scale,
                        -2 * scale,
                        22 * scale,
                        -2 * scale,
                        18 * scale,
                        6 * scale,
                        -18 * scale,
                        6 * scale,
                    ),
                    "#e07a2e",
                    tags=(tag,),
                )
                self.rect(
                    -15 * scale,
                    -9 * scale,
                    13 * scale,
                    -2 * scale,
                    "#f5efe2",
                    tags=(tag,),
                )
                for window in range(5):
                    item = self.rect(
                        (-13 + window * 5.4) * scale,
                        -7 * scale,
                        (-10 + window * 5.4) * scale,
                        -4 * scale,
                        "#2f4b5a",
                        tint=False,
                        tags=(tag,),
                    )
                    self.windows.append((item, True))
                self.rect(
                    2 * scale,
                    -15 * scale,
                    6 * scale,
                    -9 * scale,
                    "#2f3d45",
                    tags=(tag,),
                )
            x = rng.uniform(0, w)
            self.shapes.move(tag, x, y)
            self.offsets[tag] = (x, y)
            speed = (8 + depth * 60) * w / 1000 * direction
            self.movers.append(("boat", tag, x, speed, 30 * scale, y))

    # ----- Animation -----

    def animate(self, elapsed):
        c = self.shapes
        w, h = self.size
        position = (START_POSITION + elapsed / CYCLE_SECONDS) % 1
        sky_top, sky_bottom, water_top, water_bottom, dark = sky_state(position)
        for index, band in enumerate(self.sky_bands):
            c.configure(
                band, fill=mix(sky_top, sky_bottom, index / (len(self.sky_bands) - 1))
            )
        for index, band in enumerate(self.water_bands):
            c.configure(
                band,
                fill=mix(water_top, water_bottom, index / (len(self.water_bands) - 1)),
            )

        # The sun sets behind the bridge; the moon rises over Alfama.
        sun_progress = min(1, position / 0.56)
        sun_x, sun_y = w * 0.46, h * 0.17 + (self.water_y - h * 0.15) * sun_progress**2
        radius = h * 0.045
        sun_color = mix("#ffe08a", "#ff8f52", sun_progress)
        c.coords(
            self.sun, sun_x - radius, sun_y - radius, sun_x + radius, sun_y + radius
        )
        c.coords(
            self.sun_glow,
            sun_x - radius * 1.8,
            sun_y - radius * 1.8,
            sun_x + radius * 1.8,
            sun_y + radius * 1.8,
        )
        c.configure(
            self.sun, fill=sun_color, state="normal" if position < 0.6 else "hidden"
        )
        c.configure(
            self.sun_glow,
            fill=mix(sky_bottom, sun_color, 0.35),
            state="normal" if position < 0.6 else "hidden",
        )
        moon_progress = (position - 0.58) / 0.36
        night_sky = 0 < moon_progress < 1
        moon_x, moon_y = (
            w * 0.78,
            self.water_y
            - (self.water_y - h * 0.2)
            * math.sin(math.pi * min(1, max(0, moon_progress))),
        )
        radius = h * 0.03
        c.coords(
            self.moon,
            moon_x - radius,
            moon_y - radius,
            moon_x + radius,
            moon_y + radius,
        )
        c.coords(
            self.moon_shadow,
            moon_x - radius * 0.3,
            moon_y - radius * 0.5,
            moon_x + radius * 0.15,
            moon_y - radius * 0.05,
        )
        for item in (self.moon, self.moon_shadow):
            c.configure(item, state="normal" if night_sky else "hidden")
        for item in self.stars:
            c.configure(item, state="normal" if dark > 0.6 else "hidden")

        if self.last_dark is None or abs(dark - self.last_dark) > 0.03:
            self.last_dark = dark
            for item, color in self.tinted:
                c.configure(item, fill=mix(color, NIGHT_TINT, dark * 0.6))
            for item, lit in self.windows:
                c.configure(
                    item,
                    fill="#ffd682"
                    if lit and dark > 0.5
                    else mix("#2f4b5a", NIGHT_TINT, dark * 0.6),
                )
            for item in self.lights:
                c.configure(item, state="normal" if dark > 0.5 else "hidden")

        self.move_actors(elapsed)

    def place(self, tag, x, y=None):
        """Move a tagged group so its own origin sits at (x, y)."""
        old_x, old_y = self.offsets.get(tag, (0, 0))
        y = old_y if y is None else y
        if x != old_x or y != old_y:
            self.shapes.move(tag, x - old_x, y - old_y)
            self.offsets[tag] = (x, y)

    def move_actors(self, elapsed):
        c = self.shapes
        w, h = self.size
        anchor_left, _, _, anchor_right = self.span
        span = anchor_right - anchor_left
        for index, mover in enumerate(self.movers):
            kind, tag = mover[0], mover[1]
            if kind in ("cloud", "shimmer"):
                _, _, x, speed, length = mover
                # Shapes were drawn at x, so their shift is measured from there.
                self.place(tag, (x + elapsed * speed) % (w + length * 2) - length - x)
            elif kind == "gull":
                _, _, x, speed, y = mover
                target = (x + elapsed * speed) % (w + 40) - 20
                flap = 4 * math.sin(elapsed * 9 + index)
                bob = 6 * math.sin(elapsed * 0.8 + index)
                c.coords(
                    tag,
                    target - 8,
                    y + bob,
                    target - 3,
                    y + bob - flap,
                    target,
                    y + bob,
                    target + 3,
                    y + bob - flap,
                    target + 8,
                    y + bob,
                )
            elif kind == "car":
                _, _, _, direction, offset, speed = mover
                progress = (offset + elapsed * speed) % 1
                self.place(
                    tag,
                    anchor_left + span * (progress if direction > 0 else 1 - progress),
                )
            elif kind == "boat":
                _, _, x, speed, half, y = mover
                target = (x + elapsed * speed) % (w + half * 4) - half * 2
                self.place(tag, target, y + math.sin(elapsed * 1.6 + index) * h * 0.002)
            elif kind == "tram":
                _, _, _, start, end, speed = mover
                distance = (elapsed * speed) % ((end - start) * 2)
                self.place(
                    tag,
                    start
                    + (
                        distance
                        if distance <= end - start
                        else (end - start) * 2 - distance
                    ),
                )
        # Train: crosses the lower deck, then waits out of sight.
        cycle = (elapsed % 16) / 16
        lead = anchor_left - w * 0.13 + (span + w * 0.26) * min(1, cycle / 0.7)
        for index, tag in enumerate(self.train_cars):
            x = lead - index * w * 0.032
            self.place(tag, x)
            visible = anchor_left <= x and x + w * 0.03 <= anchor_right
            c.configure(tag, state="normal" if visible else "hidden")
