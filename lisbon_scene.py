"""Retained vector scenery for a compact, playable interpretation of Lisbon."""
from contextlib import contextmanager
import math
import random
from lisbon_landmarks import draw_landmarks, light_landmarks

# The Tejo is wide enough that crossing takes a vehicle or the ferry. Everything on the
# south bank sits SOUTH_SHIFT lower than it did when the river ended at y=900.
OLD_RIVER_BOTTOM, SOUTH_SHIFT = 900, 180
RIVER_TOP, RIVER_BOTTOM = 718, OLD_RIVER_BOTTOM + SOUTH_SHIFT
MAP_BOTTOM = 1080
WORLD_WIDTH, WORLD_BOTTOM = 2400, 1600 + SOUTH_SHIFT


def north_avenue_outline(half_width, verge_width, bevel):
    """Perimeter of the avenue and its nine southbound approaches."""
    xs, y = NORTH_JUNCTIONS, NORTH_AVENUE_Y
    left, right = xs[0] - verge_width, xs[-1] + verge_width
    top, bottom = y - half_width, y + half_width
    points = [(left + bevel, top), (right - bevel, top), (right, top + bevel)]
    for x in reversed(xs):
        if x != xs[-1]:
            points.extend([(x + verge_width + bevel, bottom), (x + verge_width, bottom + bevel)])
        points.extend([(x + verge_width, y + 33), (x - verge_width, y + 33)])
        if x != xs[0]:
            points.extend([(x - verge_width, bottom + bevel), (x - verge_width - bevel, bottom)])
    points.append((left, top + bevel))
    return points


# Caparica beach polygons, relative to the south shoreline and west of Cristo Rei.
CAPARICA_ART = (
    # Sand ends at the kerbs and follows the western garden fence and tunnel portal.
    ("sand", (0, 0, 121, 0, 116, 24, 123, 55, 120, 88, 127, 115, 124, 141, 0, 141)),
    ("sand", (0, 175, 124, 175, 127, 188, 0, 188)),
    ("sand", (0, 232, 127, 232, 135, 260, 132, 286, 123, 309, 60, 309, 60, 440, 47, 440, 47, 448, 0, 448)),
    ("sand", (0, 492, 47, 492, 47, 500, 60, 500, 60, 631, 116, 631, 122, 648, 0, 648)),
    ("sand", (0, 692, 122, 692, 124, 700, 0, 700)),
    ("dune", (69, 258, 84, 253, 104, 254, 89, 256)),
    ("dune", (8, 412, 20, 406, 37, 405, 27, 409)),
    ("dune", (16, 584, 28, 580, 44, 578, 31, 583)),
    ("canopy", (38, 266, 41, 260, 48, 257, 54, 260, 56, 266, 48, 270)),
    ("stripe", (41, 260, 48, 257, 48, 270)),
    ("towel", (49, 273, 56, 272, 59, 286, 52, 287)),
    ("canopy", (18, 535, 20, 530, 26, 527, 32, 530, 34, 535, 26, 539)),
    ("stripe", (20, 530, 26, 527, 26, 539)),
    ("towel", (28, 541, 35, 540, 38, 553, 31, 554)),
    ("wet", (0, 0, 121, 0, 118, 7, 97, 11, 74, 10, 48, 15, 23, 12, 0, 17)),
    ("foam", (0, 0, 121, 0, 119, 2, 98, 5, 75, 4, 49, 8, 25, 5, 0, 9)),
    ("dune", (4, 111, 18, 105, 31, 104, 22, 108)),
    ("dune", (87, 34, 96, 29, 109, 28, 101, 32)),
    ("towel", (22, 41, 27, 39, 34, 53, 29, 55)),
    ("towel", (76, 72, 82, 73, 80, 88, 74, 87)),
    ("canopy", (13, 38, 15, 32, 21, 29, 27, 32, 29, 38, 21, 41)),
    ("stripe", (15, 32, 21, 29, 21, 41)),
    ("canopy", (66, 68, 68, 62, 74, 59, 80, 62, 82, 68, 74, 71)),
    ("stripe", (68, 62, 74, 59, 74, 71)),
)
CAPARICA_DAY = dict(sand="#ead6a4", wet="#d1be91", foam="#eef1d4", dune="#c5ad79",
                    towel="#588e98", canopy="#bd674a", stripe="#fff0bd")


def south(y):
    """Move a south-bank y coordinate from the old narrow-river layout to the current one."""
    return y + SOUTH_SHIFT if y > OLD_RIVER_BOTTOM else y


def shift_south(points):
    """Shift every (x, y) pair in a flat coordinate tuple that lies on the south bank."""
    return tuple(value if index % 2 == 0 else south(value) for index, value in enumerate(points))
VASCO_NORTH_X = 2035
NORTH_AVENUE_Y = 124
NORTH_JUNCTIONS = (238, 478, 718, 958, 1225, 1495, 1775, VASCO_NORTH_X, 2350)
NORTH_QUARTERS = ((115, "BELÉM"), (355, "ALCÂNTARA"),
                  (600, "BAIXA · CHIADO"), (835, "ALFAMA · GRAÇA"), (1090, "BEATO"),
                  (1370, "MARVILA"), (1900, "PARQUE DAS NAÇÕES"))
BRIDGE_TOLL = 3
# Plots without a business are apartment blocks, small parks or fountain squares,
# so they never look like a shop the player could use.
SCENERY_PLOTS = (
    ((1540, 160), "flats"), ((1280, 345), "fountain"), ((2080, 345), "flats"),
    ((700, south(1180)), "flats"), ((940, south(1180)), "park"), ((1280, south(1180)), "flats"),
    ((1800, south(1180)), "fountain"),
    ((1280, south(1430)), "park"), ((1540, south(1430)), "flats"), ((1800, south(1430)), "park"),
)
FOUNTAIN_BASIN = (58, 26, 118, 74)  # Inside the 176 x 104 plot
# Solid footprints: whole apartment blocks and fountain basins. Parks are walkable.
SOUTH_PARK_BOUNDS = (60, south(1210), 550, south(1530))
# A covered east-west roadway passes beneath the south-bank garden.
SOUTH_PARK_TUNNEL = (45, 565, south(1370), 17)
ORIENTE_PARK_BOUNDS = (1810, 520, 2010, 640)
PARK_BOUNDS = (SOUTH_PARK_BOUNDS, ORIENTE_PARK_BOUNDS) + tuple(
    (x, y, x+176, y+104) for (x, y), kind in SCENERY_PLOTS if kind == "park"
)
# A small low-tide foreshore meets the promenade beside the fixed tower.
SAND_WEST, SAND_EAST = 55, 235
SAND_BOTTOM = 855


def sand_edge(x):
    fraction = (x-SAND_WEST)/(SAND_EAST-SAND_WEST)
    if not 0 <= fraction <= 1:
        return RIVER_TOP
    curve = math.sin(math.pi*fraction)**.55
    scallops = 1 + .045*math.sin(fraction*math.tau*3)
    return RIVER_TOP + (SAND_BOTTOM-RIVER_TOP)*curve*scallops


def on_sand(x, y, radius=0):
    """Keep the walking footprint inside the same tidal edge used for drawing."""
    return (SAND_WEST+radius <= x <= SAND_EAST-radius and RIVER_TOP-3 <= y
            and y+radius <= min(sand_edge(x-radius), sand_edge(x), sand_edge(x+radius)))


def vehicle_park_blocked(x, y, radius=10):
    left, right, center_y, half_width = SOUTH_PARK_TUNNEL
    if left <= x <= right and abs(y-center_y) <= half_width-radius:
        return False
    return any(left-radius < x < right+radius and top-radius < y < bottom+radius
               for left, top, right, bottom in PARK_BOUNDS)
SCENERY_BLOCKS = tuple(
    (x, y, x+176, y+104) if kind == "flats"
    else (x+FOUNTAIN_BASIN[0], y+FOUNTAIN_BASIN[1], x+FOUNTAIN_BASIN[2], y+FOUNTAIN_BASIN[3])
    for (x, y), kind in SCENERY_PLOTS if kind != "park"
)


def bridge_center(y, eastern=False):
    return VASCO_NORTH_X - 0.32 * (y - RIVER_TOP) if eastern else 300


def bridge_at(x, y, radius=10):
    for eastern, name in ((False, "25 de Abril"), (True, "Vasco da Gama")):
        if abs(x-bridge_center(y, eastern)) <= (27 if eastern else 31)-radius:
            return name
    return None


def walkable_terrain(x, y, radius=10, on_foot=False):
    """The river is only crossable on a bridge, and the bridges only carry vehicles."""
    if RIVER_TOP - radius < y < RIVER_BOTTOM + radius:
        if on_foot and on_sand(x, y, radius):
            # The tower stays in its original position and remains solid.
            if 90-radius < x < 190+radius and 735-radius < y < 850+radius:
                return False
            return True
        return not on_foot and bridge_at(x, y, radius) is not None
    return True


# These trees are rendered into the static day/night maps, outside doorways.
STREET_TREES = (
    tuple((x, 697, 12) for x in range(60, WORLD_WIDTH-40, 80)
          if all(abs(x-bridge_center(697, eastern)) > 85 for eastern in (False, True)) and abs(x-660) > 140)
    + tuple((x, south(952), 19) for x in range(1230, WORLD_WIDTH-40, 85)
            if abs(x-bridge_center(south(952), True)) > 90 and abs(x-1290) > 70)
    + tuple((x, y, 16) for x in (1260, 1740, 2300) for y in (205, 390, 575))
    + tuple((x, south(y), 19) for x in (690, 930, 1260, 1525, 1810, 2085, 2300) for y in (1150, 1405))
    + tuple((x, south(y), 22) for x, y in ((90, 1240), (175, 1235), (440, 1235), (515, 1240),
                                          (90, 1330), (515, 1330), (90, 1435), (515, 1435),
                                          (180, 1500), (270, 1500), (400, 1500), (490, 1500)))
    + ((1835, 595, 15), (1985, 605, 15))
)


class LisbonScene:
    def __init__(self, game, sites, draw=True):
        self.game, self.c = game, game.canvas
        self.sites = sites
        self.tram_position = 0.0
        if draw:
            self.draw()

    @contextmanager
    def shifted(self, dy):
        """Draw the enclosed artwork dy lower. Used for south-bank art written in old coordinates."""
        previous = getattr(self.c, "shift_y", 0)
        self.c.shift_y = previous+dy
        try:
            yield
        finally:
            self.c.shift_y = previous

    def rect(self, x1, y1, x2, y2, color, **kwargs):
        return self.c.create_rectangle(x1, y1, x2, y2, fill=color, width=0, tags="city", **kwargs)

    def poly(self, points, color, **kwargs):
        return self.c.create_polygon(*points, fill=color, width=0, tags="city", **kwargs)

    def line(self, points, color, width=1, **kwargs):
        return self.c.create_line(*points, fill=color, width=width, tags="city", **kwargs)

    def text(self, x, y, value, size=10, color="#304b54", bold=False, anchor="w"):
        self.game.label(x, y, value, size, color, bold, anchor=anchor)

    def tree(self, x, y, size=12):
        self.c.create_oval(x-size, y-3, x+size+7, y+10, fill="#c1bc9c", outline="", tags="city")
        self.rect(x-2, y-8, x+2, y+7, "#8e7756")
        for dx, dy, radius, color in ((0, -9, size, "#55795e"), (-4, -14, size*.8, "#729271"),
                                      (4, -17, size*.65, "#8fa681")):
            self.c.create_oval(x+dx-radius, y+dy-radius, x+dx+radius, y+dy+radius,
                               fill=color, outline="", tags="city")

    def road(self, points, width=42):
        self.line(points, "#b4ac98", width+10, capstyle="round", joinstyle="round")
        self.line(points, "#747a77", width, capstyle="round", joinstyle="round")
        self.line(points, "#e4d8b9", 1, dash=(9, 14))

    @staticmethod
    def _cross_outline(x, y, vertical_half, horizontal_half, bevel):
        """A beveled plus-shaped road/curb outline for a clean four-way junction."""
        v, h, b = vertical_half, horizontal_half, bevel
        reach = h+b
        return (x-v, y-reach, x+v, y-reach,
                x+v+b, y-h,
                x+reach, y-h, x+reach, y+h,
                x+v+b, y+h, x+v, y+reach,
                x+v, y+reach, x-v, y+reach,
                x-v-b, y+h,
                x-reach, y+h, x-reach, y-h,
                x-v-b, y-h, x-v, y-reach)

    def road_junction(self, x, y, vertical_width, horizontal_width):
        """Unify the curb and asphalt where perpendicular streets meet."""
        outer_v, outer_h = vertical_width/2+5, horizontal_width/2+5
        inner_v, inner_h = vertical_width/2, horizontal_width/2
        self.poly(self._cross_outline(x, y, outer_v, outer_h, 4), "#b4ac98")
        self.poly(self._cross_outline(x, y, inner_v, inner_h, 3), "#747a77")

    def draw(self):
        self.rect(0, 104, WORLD_WIDTH, WORLD_BOTTOM, "#dfd5bd")
        self.expanded_north()
        # Subtle sunlit paving and green hills, rather than a square grass grid.
        for y in range(105, 716, 16):
            self.line((0, y, 1200, y), "#d9cfb7")
        self.poly((0, 105, 440, 105, 380, 151, 0, 167), "#c4c6a4", smooth=True)
        self.poly((680, 104, 1030, 104, 1120, 146, 720, 157), "#c0c4a4", smooth=True)
        for x in (238, 478, 718, 958):
            self.road((x, NORTH_AVENUE_Y, x, 653), 30)
        for y in (301, 486):
            self.road((0, y, WORLD_WIDTH, y), 39)
        self.road((0, 660, WORLD_WIDTH, 660), 35)
        verticals = tuple((x, 30 if x < 1200 else 29) for x in
                          (238, 478, 718, 958, 1225, 1495, 1775, VASCO_NORTH_X, 2350))
        for x, vertical_width in verticals:
            for y, horizontal_width in ((301, 39), (486, 39), (660, 35)):
                self.road_junction(x, y, vertical_width, horizontal_width)
        # Baixa's broad calçada waterfront, with wave patterns.
        self.rect(0, 697, 1200, RIVER_TOP, "#eee5cf")
        for x in range(-15, 1220, 52):
            self.line((x, 707, x+13, 701, x+26, 707, x+39, 713, x+52, 707), "#a5a294", 2, smooth=True)
        for half, side, bevel, color in ((18, 20, 7, "#b4ac98"), (13, 15, 5, "#747a77")):
            points = north_avenue_outline(half, side, bevel)
            self.poly(tuple(n for point in points for n in point), color)
        for left, right in zip(NORTH_JUNCTIONS, NORTH_JUNCTIONS[1:]):
            self.line((left+24, NORTH_AVENUE_Y, right-24, NORTH_AVENUE_Y), "#e4d8b9", 1, dash=(9, 14))
        for x, name in NORTH_QUARTERS:
            self.text(x, 96, name, 12, "#485b52", True, "center")
        for site in self.sites:
            if site.y < RIVER_TOP:
                self.building(site)
        for x, y in ((224, 171), (462, 168), (704, 164), (944, 167), (1180, 164),
                     (218, 366), (461, 365), (702, 367), (939, 365),
                     (221, 553), (460, 553), (702, 552), (941, 552)):
            self.tree(x, y, 11)
        self.river()
        with self.shifted(SOUTH_SHIFT):
            self.south_bank()
        self.south_garden()
        self.residential_blocks(north=False)
        for site in self.sites:
            if site.y >= RIVER_BOTTOM:
                self.building(site)
        self.suspension_bridge()
        self.cable_bridge()
        draw_landmarks(self)
        for x, y, size in STREET_TREES:
            self.tree(x, y, size)
        self.tramway()
        self.ferry_piers()
        self.text(18, 730, "RIBEIRA DAS NAUS", 7, "#3c5d61", True)
        middle = (RIVER_TOP+RIVER_BOTTOM)/2
        self.text(900, middle+30, "RIO TEJO", 23, "#d5edef", True, anchor="center")
        self.text(900, middle+54, "LISBOA  /  ALMADA", 8, "#587c81", anchor="center")
        self.text(350, 729, f"↑ LISBON · TOLL ${BRIDGE_TOLL}", 7, "#3c5d61", True)
        self.text(bridge_center(729, True)+35, 729, f"↑ LISBON · TOLL ${BRIDGE_TOLL}", 7, "#3c5d61", True)

    def expanded_north(self):
        self.rect(1200, 104, WORLD_WIDTH, RIVER_TOP, "#d9d7bf")
        for x in (1225, 1495, 1775, VASCO_NORTH_X, 2350):
            self.road((x, NORTH_AVENUE_Y, x, 660), 29)
        self.rect(*ORIENTE_PARK_BOUNDS, "#b7c5a0")
        self.line((1830, 610, 1910, 545, 1990, 610), "#ece3c7", 13, smooth=True)
        self.text(1910, 635, "GARDEN", 7, "#5f7650", True, "center")
        for x, y in ((1830, 550), (1985, 550), (1910, 615), (2300, 215),
                     (1260, 575), (1740, 555), (2300, 565), (2310, 390)):
            self.tree(x, y, 20)
        # Oriente-inspired station canopy, set back from the business streets.
        self.rect(1780, 190, 2030, 260, "#bdc6c0")
        for x in range(1788, 2020, 26):
            self.line((x, 250, x+10, 181, x+24, 250), "#eef0db", 4)
        self.text(1900, 277, "GARE DO ORIENTE", 9, "#617875", True, "center")
        self.residential_blocks(north=True)

    def residential_blocks(self, north):
        for index, ((x, y), kind) in enumerate(SCENERY_PLOTS):
            if (y < RIVER_TOP) != north:
                continue
            {"flats": self.flats, "park": self.park, "fountain": self.fountain_square}[kind](x, y, index)

    FLAT_COLORS = ("#e7d3a1", "#c9dfe0", "#eac2b3", "#d8e2c6", "#f1e9d8")

    def flat_windows(self, x, y):
        """Window rectangles of an apartment block: four floors of five."""
        return [(x+18+column*29, y-4+floor*24) for floor in range(4) for column in range(5)]

    def flats(self, x, y, index):
        """A four-storey apartment block: taller than the shops, flat roof, no shopfront."""
        right, bottom = x+176, y+104
        wall = self.FLAT_COLORS[index % len(self.FLAT_COLORS)]
        rng = random.Random(index)
        # The roofline stays below the street above, level with the other buildings' signs.
        self.poly((x+12, y-6, right+4, y-6, right+4, bottom+8, x+12, bottom+8), "#bfb69e")
        self.rect(x+8, y-14, right-8, bottom, wall)
        self.rect(right-17, y-11, right-8, bottom, "#afaa97")
        # Flat roof with a parapet, a water tank and a stairwell hut.
        self.rect(x+4, y-22, right-4, y-14, "#9a958a")
        self.rect(x+4, y-22, right-4, y-20, "#c9c2b0")
        self.rect(x+24, y-21, x+46, y-15, "#7d8a8c")
        self.rect(right-48, y-21, right-30, y-15, "#b3ab9a")
        for window_x, window_y in self.flat_windows(x, y):
            self.rect(window_x-2, window_y-2, window_x+20, window_y+15, "#efe6d2")
            self.rect(window_x, window_y, window_x+18, window_y+13, "#5f7d82")
            self.rect(window_x+2, window_y+2, window_x+8, window_y+8, "#a5c0bb")
            if (window_x-x) % 58 == 18:
                # Wrought-iron balcony rail.
                self.line((window_x-3, window_y+16, window_x+21, window_y+16), "#4e625e", 2)
        # Washing hung out to dry on one balcony.
        line_x, line_y = x+18+rng.randrange(0, 3)*58, y-4+rng.randrange(1, 3)*24+15
        self.line((line_x-3, line_y-6, line_x+21, line_y-6), "#7d7466")
        for offset, color in ((0, "#d65655"), (7, "#86caff"), (14, "#f5efe2")):
            self.rect(line_x+offset, line_y-6, line_x+offset+5, line_y, color)
        # Ground floor: a plain residents' entrance, no trading sign or coloured doorstep.
        self.rect(x+8, y+88, right-8, bottom, "#d8cfba")
        self.rect(x+80, y+86, x+96, bottom, "#6d5a45")
        self.rect(x+80, y+84, x+96, y+86, "#efe6d2")
        self.rect(x+3, bottom+13, x+173, bottom+32, "#ede4cf")

    def park(self, x, y, index):
        """A small neighbourhood garden with a path, benches and flower beds."""
        right, bottom = x+176, y+104

        # Every other park is mirrored so neighbouring gardens look different.
        mirrored = sum(kind == "park" for _, kind in SCENERY_PLOTS[:index]) % 2 == 1

        def across(offset):
            return right-offset if mirrored else x+offset

        self.rect(x, y, right, bottom, "#9db584")
        self.rect(x+4, y+4, right-4, bottom-4, "#b7c99a")
        self.line((across(4), bottom-22, across(60), y+50, across(120), y+58, across(172), y+20),
                  "#ece3c7", 11, smooth=True)
        for bed_x, bed_y, color in ((across(30), y+22, "#e8807a"), (across(132), y+76, "#f1cf6b"),
                                    (across(92), y+86, "#c69ae0")):
            self.c.create_oval(bed_x-14, bed_y-7, bed_x+14, bed_y+7, fill="#7f9a6a", outline="", tags="city")
            for dot in range(-9, 10, 6):
                self.c.create_oval(bed_x+dot-2, bed_y-3, bed_x+dot+2, bed_y+1, fill=color, outline="", tags="city")
        for bench_x, bench_y in ((across(64), y+36), (across(112), y+70)):
            self.rect(bench_x-11, bench_y-3, bench_x+11, bench_y+2, "#8e6d4e")
            self.rect(bench_x-11, bench_y-7, bench_x+11, bench_y-5, "#7a5c41")
        for tree_x, tree_y, size in ((across(26), y+70, 15), (across(150), y+36, 14), (across(92), y+30, 12)):
            self.tree(tree_x, tree_y, size)
        self.text(x+88, bottom-10, "GARDEN", 7, "#5f7650", True, "center")

    def fountain_square(self, x, y, index):
        """A paved praça with wavy calçada and a fountain in the middle."""
        right, bottom = x+176, y+104
        self.rect(x, y, right, bottom, "#ede5d1")
        for row in range(6):
            wave_y = y+10+row*17
            self.line([value for step in range(12) for value in (x+4+step*15.3, wave_y+4*math.sin(step*1.1+row))],
                      "#596566", 2, smooth=True)
        left, top, basin_right, basin_bottom = (x+FOUNTAIN_BASIN[0], y+FOUNTAIN_BASIN[1],
                                                x+FOUNTAIN_BASIN[2], y+FOUNTAIN_BASIN[3])
        self.c.create_oval(left-4, top-2, basin_right+4, basin_bottom+6, fill="#bfb69e", outline="", tags="city")
        self.c.create_oval(left, top, basin_right, basin_bottom, fill="#d8cfba", outline="", tags="city")
        self.c.create_oval(left+6, top+5, basin_right-6, basin_bottom-5, fill="#7fbac2", outline="", tags="city")
        self.c.create_oval(left+14, top+11, basin_right-14, basin_bottom-11, fill="#9fd0d4", outline="", tags="city")
        center_x, center_y = x+88, y+50
        self.rect(center_x-4, center_y-18, center_x+4, center_y+2, "#d8cfba")
        self.c.create_oval(center_x-9, center_y-24, center_x+9, center_y-16, fill="#cfc6b1", outline="", tags="city")
        for side in (-1, 1):
            self.line((center_x, center_y-22, center_x+side*10, center_y-34, center_x+side*20, center_y-14),
                      "#bfe4ea", 2, smooth=True)
        for bench_x, bench_y in ((x+22, y+20), (x+154, y+20), (x+22, y+86), (x+154, y+86)):
            self.rect(bench_x-11, bench_y-3, bench_x+11, bench_y+2, "#8e6d4e")
        for lamp_x in (x+8, right-8):
            self.line((lamp_x, bottom-6, lamp_x, y+12), "#4a5455", 2)
            self.c.create_oval(lamp_x-4, y+6, lamp_x+4, y+14, fill="#f1e6c2", outline="", tags="city")
        self.text(x+88, bottom-6, "SQUARE", 7, "#5f6a6a", True, "center")

    def light_scenery(self, glow):
        """Night pass for apartment windows, fountain lamps and lit water."""
        c = self.c
        for index, ((x, y), kind) in enumerate(SCENERY_PLOTS):
            if kind == "flats":
                rng = random.Random(index*7+1)
                for window_x, window_y in self.flat_windows(x, y):
                    if rng.random() < .6:
                        c.create_rectangle(window_x, window_y, window_x+18, window_y+13,
                                           fill=rng.choice(("#f3d49b", "#e7b96c", "#ffe5b7")),
                                           outline="", tags="night_lights")
                glow(x+88, y+92, 18)
            elif kind == "fountain":
                for lamp_x in (x+8, x+168):
                    glow(lamp_x, y+10, 16)
                glow(x+88, y+50, 26, "#bfe4ea")
            else:
                glow(x+88, y+52, 22, "#d8e8b0")

    def expanded_south(self):
        """South-bank streets in the old layout's coordinates. Drawn inside shifted()."""
        self.rect(0, 1085, WORLD_WIDTH, WORLD_BOTTOM-SOUTH_SHIFT, "#c5c9a6")
        for y in (1110, 1370, 1570):
            self.road((0, y, WORLD_WIDTH, y), 34)
        south_verticals = (620, 1190, 1495, 1775, VASCO_NORTH_X, 2350)
        for x in south_verticals:
            self.road((x, 1060, x, 1580), 30)
        for x in south_verticals:
            for y, horizontal_width in ((1110, 34), (1370, 34), (1570, 34)):
                self.road_junction(x, y, 30, horizontal_width)
        self.text(1290, 1010, "CACILHAS", 20, "#65795e", True)
        self.text(2070, 1010, "SEIXAL", 20, "#65795e", True)
        self.text(2090, 1335, "SOUTH BANK FARMS", 12, "#708461", True)
        for x in range(700, 1100, 35):
            self.line((x, 1430, x+12, 1520), "#aaab71", 7)
        for x, y in ((120, 1250), (250, 1400), (470, 1290), (90, 1510), (1470, 1420),
                     (1940, 1550), (2280, 1300), (2300, 1230), (1220, 1510), (570, 1450)):
            self.tree(x, y, 26)

    def night_lighting(self):
        c = self.c

        def glow(x, y, radius=18, color="#f4c878"):
            c.create_oval(x-radius, y-radius*.65, x+radius, y+radius*.65,
                          fill=color, stipple="gray25", outline="", tags="night_lights")
            c.create_oval(x-radius*.55, y-radius*.4, x+radius*.55, y+radius*.4,
                          fill=color, stipple="gray50", outline="", tags="night_lights")

        for site in self.sites:
            if site.role == "CASINO":
                from casino_art import window_bounds
                glow(site.x+88, site.y+51, 33, "#df58b1")
                self.game.label(site.x+88, site.y+51, "Lisbon Casino", 8, "#ffe2f5", True,
                                anchor="center", tag="night_lights")
                for left, top, right, bottom in window_bounds(site):
                    glow((left+right)/2, (top+bottom)/2, 6)
                    c.create_rectangle(left, top, right, bottom, fill="#ffd17a",
                                       outline="", tags="night_lights")
                door_x, door_y = site.door
                glow(door_x, door_y-8, 16)
                continue
            if site.role == "RESEARCH":
                self.light_research_building(site, glow)
                continue
            for index, x in enumerate((site.x+22, site.x+70, site.x+118)):
                color = ("#f3d49b", "#e7b96c", "#ffe5b7")[index]
                glow(x+12, site.y+44, 23)
                c.create_rectangle(x+1, site.y+32, x+23, site.y+56, fill=color, outline="", tags="night_lights")
                c.create_line(x+12, site.y+32, x+12, site.y+56, fill="#8b795a", width=1, tags="night_lights")
            door_x, door_y = site.door
            glow(door_x, door_y+8, 21)
            c.create_oval(door_x-2, door_y-16, door_x+2, door_y-12,
                          fill="#fff1be", outline="", tags="night_lights")
            if site.role == "EXCHANGE":
                from wayfinding import site_guide
                c.create_rectangle(site.x-1, site.y-22, site.x+177, site.y-4,
                                   fill="#243e50", outline="", tags="night_lights")
                c.create_line(site.x+2, site.y-20, site.x+174, site.y-20,
                              fill="#d6b264", width=2, tags="night_lights")
                self.game.label(site.x+88, site.y-12, site_guide(site).badge,
                                9, "#ffe4a3", True, anchor="center", tag="night_lights")
                self.game.label(site.x+88, site.y+81, "E  trade shares",
                                9, "#ffe4a3", True, anchor="center", tag="night_lights")
        # Warm suspension-bridge lights and reflections in the Tejo.
        # Bridge lights follow the river's edges, like the bridges themselves.
        top, bottom = RIVER_TOP-23, RIVER_BOTTOM+35
        for x in (267, 333):
            c.create_line(x, top+16, x, bottom-11, fill="#eaa06c", width=2, tags="night_lights")
            for y in range(int(top+29), int(bottom-15), 24):
                glow(x, y, 12)
                c.create_oval(x-2, y-2, x+2, y+2, fill="#ffe5a4", outline="", tags="night_lights")
        for y in self.across_river(.2, .78):
            c.create_line(263, y-31, 336, y-31, fill="#f5bd83", width=2, tags="night_lights")
        # The cable bridge has cool mast lighting and warm lamps along its deck.
        for y in range(RIVER_TOP+5, RIVER_BOTTOM+19, 27):
            x = bridge_center(y, True)
            for side in (-1, 1):
                lx = x+side*25
                glow(lx, y, 12, "#cce7e6")
                c.create_oval(lx-2, y-2, lx+2, y+2, fill="#eef4d9", outline="", tags="night_lights")
        for y in self.across_river(.236, .769):
            x = bridge_center(y, True)
            for side in (-1, 1):
                c.create_line(x+side*29, y+12, x+side*15, y-40,
                              fill="#d4edf0", width=3, tags="night_lights")
                glow(x+side*15, y-40, 17, "#bddfec")
        for x in (55, 372, 653, 920, 1144):
            glow(x, 674, 28)
            c.create_oval(x-2, 666, x+2, 670, fill="#fff0ba", outline="", tags="night_lights")
        for y in range(RIVER_TOP+29, RIVER_BOTTOM-4, 23):
            c.create_line(341, y, 360, y, fill="#d2ab69", stipple="gray25", width=2, tags="night_lights")
            x = bridge_center(y, True)-42
            c.create_line(x-14, y, x+8, y, fill="#b0d1d2", stipple="gray25", width=2, tags="night_lights")
        glow(149, south(930), 32, "#c5dde0")
        from ferry import FERRY_PIERS
        for pier in FERRY_PIERS:
            left, top, right, bottom = pier.kiosk
            glow(pier.x, (top+bottom)/2, 24)
            glow(pier.x, RIVER_TOP+66 if pier.north else RIVER_BOTTOM-66, 14, "#ffe5a4")
        self.light_scenery(glow)
        light_landmarks(self)

    def river(self):
        colors = ("#83b9bc", "#78afb6", "#6da7b0", "#629da8", "#5e98a4", "#619daa")
        for index, color in enumerate(colors):
            top = RIVER_TOP + index * (RIVER_BOTTOM-RIVER_TOP)/len(colors)
            self.rect(0, top, WORLD_WIDTH, top+(RIVER_BOTTOM-RIVER_TOP)/len(colors)+1, color)
        self.line((0, RIVER_TOP, WORLD_WIDTH, RIVER_TOP), "#faf0d8", 6)
        rng = random.Random(1528)
        for _ in range(round(160*(RIVER_BOTTOM-RIVER_TOP)/182)):
            x, y = rng.randrange(0, WORLD_WIDTH), rng.randrange(RIVER_TOP+12, RIVER_BOTTOM-8)
            self.line((x, y, x+rng.randrange(8, 30), y), "#91c1c4", 1)
        shoreline = [(x, sand_edge(x)) for x in range(SAND_WEST, SAND_EAST+1, 3)]
        coast = tuple(value for point in shoreline for value in point)
        # Broad pale sand backs onto the quay, with a damp, darker tidal fringe.
        sand_polygon = (SAND_WEST, RIVER_TOP-3, SAND_EAST, RIVER_TOP-3) + tuple(
            value for point in reversed(shoreline) for value in point)
        self.poly(sand_polygon, "#c9bc98")
        inner = [(x, max(RIVER_TOP, y-9)) for x, y in shoreline]
        wet_band = coast + tuple(value for point in reversed(inner) for value in point)
        self.poly(wet_band, "#9d9e83")
        self.line(coast, "#b5ccc0", 2)
        for x in range(SAND_WEST+10, SAND_EAST-10, 13):
            for y in range(RIVER_TOP+12, SAND_BOTTOM-8, 12):
                if on_sand(x, y, 8):
                    self.line((x, y, x+3, y+1), "#b5a887", 1)
        # Limestone quay and timber approach on the landward side of the tower.
        self.line((SAND_WEST, RIVER_TOP-2, SAND_EAST, RIVER_TOP-2), "#dcd6bf", 5)
        self.rect(133, RIVER_TOP-2, 145, 742, "#997e59")
        for y in range(RIVER_TOP, 741, 4):
            self.line((134, y, 144, y), "#c2a77f")
        self.line((133, RIVER_TOP-2, 133, 741), "#695c47", 1)
        self.line((145, RIVER_TOP-2, 145, 741), "#695c47", 1)
        # A small traditional sailing boat and a commuter ferry.
        self.poly((519, 807, 566, 807, 556, 818, 529, 818), "#f2e6c9")
        self.line((541, 770, 541, 807), "#735b46", 2)
        self.poly((538, 774, 518, 802, 538, 802), "#fff5dc")
        self.poly((545, 780, 563, 802, 545, 802), "#dfbc90")
        self.poly((1110, 822, 1170, 822, 1158, 836, 1118, 836), "#e8e8dd")
        self.rect(1122, 809, 1156, 822, "#e8e8dd")
        self.rect(1128, 813, 1151, 818, "#416372")
        self.line((1110, 838, 1089, 841), "#b2d2d0", 2)

    def south_bank(self):
        """South-bank art in the old layout's coordinates. Drawn inside shifted()."""
        self.rect(0, OLD_RIVER_BOTTOM+2, WORLD_WIDTH, WORLD_BOTTOM-SOUTH_SHIFT, "#cfceb0")
        self.expanded_south()
        self.rect(0, OLD_RIVER_BOTTOM+2, WORLD_WIDTH, OLD_RIVER_BOTTOM+9, "#f1e8ce")
        self.road((0, 1058, WORLD_WIDTH, 1058), 24)
        self.road((300, 902, 300, 1058), 32)
        self.road((bridge_center(south(902), True), 902, VASCO_NORTH_X, 1058), 32)
        self.road_junction(300, 1058, 32, 24)
        self.road_junction(VASCO_NORTH_X, 1058, 32, 24)
        self.text(144, 1021, "ALMADA", 20, "#65795e", True)
        if any(site.role == "SHIPYARD" for site in self.sites):
            self.rect(458, 868, 478, 912, "#aa8b63")
            for y in range(870, 910, 7):
                self.line((459, y, 477, y), "#d2b98d", 2)
            self.poly((483, 866, 545, 866, 533, 890, 493, 890), "#9b6051")
            self.rect(495, 851, 532, 866, "#e9dfc8")
            self.rect(501, 854, 525, 861, "#5d858c")
            self.line((470, 882, 486, 875), "#d9c69d", 2)
            self.line((424, 925, 424, 856, 483, 845), "#747d72", 4)
            self.line((483, 845, 483, 864), "#747d72", 1)
            self.text(425, 904, "DOCA DE REPARAÇÕES", 6, "#657e78")
        # Cristo Rei silhouette on the south bank.
        self.rect(130, 971, 167, 982, "#b5af97")
        self.poly((137, 971, 142, 936, 156, 936, 161, 971), "#e4dbc1")
        self.rect(146, 917, 152, 944, "#f5edd6")
        self.rect(133, 923, 165, 928, "#f5edd6")
        self.c.create_oval(145, 910, 153, 919, fill="#f5edd6", outline="", tags="city")
        self.text(149, 998, "CRISTO REI", 7, "#7b826a", anchor="center")
        for x, y in ((415, 1014), (466, 978), (1146, 960), (1112, 1025)):
            self.tree(x, y, 15)
        for material, coords in CAPARICA_ART:
            points = tuple(v if i % 2 == 0 else OLD_RIVER_BOTTOM+v for i, v in enumerate(coords))
            self.poly(points, CAPARICA_DAY[material])
        self.text(52, 995, "COSTA DA", 8, "#645c43", True, "center")
        self.text(52, 1006, "CAPARICA", 10, "#645c43", True, "center")

    def south_garden(self):
        """The Almada garden and its road tunnel, in current coordinates."""
        self.rect(*SOUTH_PARK_BOUNDS, "#abbc8b")
        self.line(shift_south((100, 1480, 300, 1250, 495, 1480)), "#e1d7b6", 22, smooth=True)
        for x, y in ((120, 1250), (250, 1400), (470, 1290), (90, 1510), (570, 1450)):
            self.tree(x, south(y), 26)
        self.south_park_tunnel()

    def south_park_tunnel(self):
        """Mark the covered road portals at either edge of the central garden."""
        left, right, center_y, _ = SOUTH_PARK_TUNNEL
        for x in (SOUTH_PARK_BOUNDS[0], SOUTH_PARK_BOUNDS[2]):
            self.rect(x-12, center_y-25, x+12, center_y+25, "#777d73")
            self.rect(x-9, center_y-21, x+9, center_y+21, "#202a2b")
            self.rect(x-6, center_y-15, x+6, center_y+15, "#59615f")
            self.line((x-5, center_y, x+5, center_y), "#dfd0aa", 1, dash=(3, 3))
            self.rect(x-11, center_y-28, x+11, center_y-24, "#d7c59e")
            self.rect(x-11, center_y+24, x+11, center_y+28, "#d7c59e")
        self.text((left+right)/2, SOUTH_PARK_BOUNDS[1]+18, "GARDEN · TUNNEL", 7, "#5e6c54", True, "center")

    @staticmethod
    def across_river(*fractions):
        """Points spaced across the river, as fractions of its width from the north bank."""
        return [RIVER_TOP+fraction*(RIVER_BOTTOM-RIVER_TOP) for fraction in fractions]

    def suspension_bridge(self):
        top, bottom = RIVER_TOP-23, RIVER_BOTTOM+35
        self.line((308, top+9, 308, bottom-11), "#638b8a", 72)
        self.line((300, top+2, 300, bottom-1), "#9e5147", 69)
        self.line((300, top, 300, bottom), "#555d61", 54)
        self.line((300, top, 300, bottom), "#d8c5a6", 1, dash=(6, 8))
        towers = self.across_river(.2, .78)
        for side in (267, 333):
            self.line((side, top+9, side, bottom-10), "#b05c4d", 3)
            self.line((side, top+18, side, bottom-14), "#cf8b73", 3)
            for y in range(int(top+30), int(bottom-17), 14):
                self.line((side, y, side-5 if side < 300 else side+5, y-10), "#d99a81", 1)
        for y in towers:
            for x in (263, 326):
                self.rect(x, y-34, x+10, y+14, "#9d493f")
                self.rect(x+2, y-34, x+5, y+14, "#d18c74")
            self.rect(263, y-33, 336, y-27, "#a95547")
            self.line((273, y-24, 326, y+6, 273, y+6, 326, y-24), "#bc7460", 2)
        self.text(250, (RIVER_TOP+RIVER_BOTTOM)/2, "25 DE ABRIL", 8, "#f5dfc5", True, anchor="e")

    def cable_bridge(self):
        start_y, end_y = RIVER_TOP-20, RIVER_BOTTOM+19
        start, end = (bridge_center(start_y, True), start_y), (bridge_center(end_y, True), end_y)
        self.road((VASCO_NORTH_X, 660, *start), 32)
        self.line((start[0]+7, start[1]+7, end[0]+7, end[1]+7), "#638d8f", 59)
        self.line((*start, *end), "#c3c9c1", 58)
        self.line((*start, *end), "#747e7e", 45)
        self.line((*start, *end), "#eee3c5", 1, dash=(6, 9))
        for y in self.across_river(.236, .769):
            x = bridge_center(y, True)
            for side in (-1, 1):
                self.line((x+side*29, y+12, x+side*15, y-40), "#e0e3d5", 5)
                for spread in (-37, -22, 0, 23, 38):
                    target_y = y+spread
                    target_x = bridge_center(target_y, True)+side*26
                    self.line((x+side*15, y-39, target_x, target_y), "#d8e0d6", 1)
        label_y = self.across_river(.31)[0]
        self.text(bridge_center(label_y, True)+55, label_y, "VASCO", 8, "#e0efdf", True)
        self.text(bridge_center(label_y, True)+55, label_y+14, "DA GAMA", 8, "#e0efdf", True)

    def ferry_piers(self):
        """Wooden jetties with a ticket kiosk for the cacilheiro between Cais do Sodré and Cacilhas."""
        from ferry import FERRY_FARE, FERRY_PIERS
        for pier in FERRY_PIERS:
            north = pier.north
            edge = RIVER_TOP if north else RIVER_BOTTOM
            reach = 70 if north else -70
            self.rect(pier.x-11, min(edge, edge+reach), pier.x+11, max(edge, edge+reach), "#9b7651")
            for plank in range(0, abs(reach), 8):
                y = edge+plank*(1 if north else -1)
                self.line((pier.x-11, y, pier.x+11, y), "#7e5d3e")
            for post_y in (edge+reach*.6, edge+reach):
                for side in (-14, 14):
                    self.c.create_oval(pier.x+side-3, post_y-3, pier.x+side+3, post_y+3,
                                       fill="#5e4630", outline="", tags="city")
            # Ticket kiosk on a wider landing at the jetty's land end; its window faces the quay.
            left, top, right, bottom = pier.kiosk
            self.rect(left-4, top-2, right+4, bottom+2, "#8a6a48")
            self.rect(left+3, top+5, right+3, bottom+3, "#7f9fa6")
            self.rect(left, top, right, bottom, "#f4e3b4")
            # The striped awning and service window face the quay, where the player stands.
            stripes = top if north else bottom-9
            for index, x in enumerate(range(int(left), int(right), 8)):
                self.rect(x, stripes, min(right, x+8), stripes+9, "#c9472f" if index % 2 == 0 else "#f8f1e2")
            window_y = top+11 if north else bottom-22
            self.rect(left+8, window_y, right-8, window_y+10, "#2f4b5a")
            counter_y = window_y-3 if north else window_y+10
            self.rect(left+8, counter_y, right-8, counter_y+3, "#a37b52")
            sign_y = bottom-8 if north else top+8
            self.text(pier.x, sign_y, f"FERRY TICKETS €{FERRY_FARE}", 6, "#3f4c4c", True, "center")
            if north:
                self.text(pier.x+30, pier.y-1, pier.name.upper(), 7, "#3c5d61", True, "w")

    def exchange_building(self, site, guide):
        """Stone banking hall, drawn once into the day/night background caches."""
        x, y, right, bottom = site.bounds
        navy, gold = "#243e50", "#d6b264"
        # A limestone pediment and four fluted columns distinguish the exchange.
        self.rect(x, y+22, right, bottom, "#c8bfa9")
        self.rect(x+5, y+26, right-5, bottom-6, "#e3d9c1")
        self.poly((x, y+22, x+88, y, right, y+22), "#eee3ca")
        self.poly((x+16, y+20, x+88, y+5, right-16, y+20), "#b7aa90")
        self.line((x+4, y+24, right-4, y+24), gold, 3)
        self.text(x+88, y+17, site.name.upper(), 7, navy, True, "center")
        for window_x in (x+22, x+70, x+118):
            self.rect(window_x-2, y+30, window_x+26, y+62, "#ac9f85")
            self.rect(window_x, y+32, window_x+24, y+59, navy)
            self.line((window_x+3, y+54, window_x+8, y+47,
                       window_x+13, y+50, window_x+21, y+38), "#b2d0b6", 2)
            self.line((window_x+2, y+58, window_x+22, y+58), gold)
        for column_x in (x+9, x+58, x+108, x+157):
            self.rect(column_x-3, y+28, column_x+12, y+33, "#f3e9d3")
            self.rect(column_x, y+33, column_x+9, y+66, "#f0e5cc")
            self.line((column_x+3, y+34, column_x+3, y+65), "#cec2a7")
            self.rect(column_x-3, y+66, column_x+12, y+71, "#b6aa91")
        self.rect(x+6, y+72, right-6, y+89, navy)
        self.text(x+88, y+81, "E  trade shares", 9, "#fff1cf", True, "center")
        self.rect(x+8, y+91, right-8, bottom-3, "#d6ccb5")
        door_x, _ = site.door
        self.rect(door_x-11, y+90, door_x+11, bottom, navy)
        self.line((door_x, y+91, door_x, bottom), gold)
        self.rect(door_x-16, bottom, door_x+16, bottom+8, guide.color)
        self.rect(x+3, bottom+13, right-3, bottom+32, "#ede4cf")
        # Keep the purpose legible at normal gameplay zoom and in night mode.
        self.rect(x-1, y-22, right+1, y-4, navy)
        self.rect(x+2, y-21, right-2, y-19, gold)
        self.text(x+88, y-12, guide.badge, 9, "#ffe4a3", True, "center")

    def research_building(self, site, guide):
        """Modern coastal campus, baked into the static map like other scenery."""
        x, y, right, bottom = site.bounds
        navy, glass = "#244b5b", "#759fa9"
        self.poly((x+6, y+17, right+8, y+17, right+8, bottom+7, x+6, bottom+7), "#b8b8a7")
        self.rect(x, y+10, right, bottom, "#ecede3")
        self.rect(right-8, y+11, right, bottom, "#bac9c6")
        # Flat white roofs, a planted terrace and solar arrays distinguish the lab.
        self.rect(x-2, y+4, right+2, y+13, "#faf9ec")
        self.rect(x+10, y, x+66, y+5, "#76957b")
        for panel_x in (x+93, x+115, x+137):
            self.poly((panel_x, y+1, panel_x+17, y+1, panel_x+20, y+7, panel_x+3, y+7), "#436b7f")
            self.line((panel_x+9, y+2, panel_x+12, y+6), "#a0bac3")
        self.text(x+11, y+23, "NOVA SBE", 11, navy, True)
        self.text(right-13, y+23, "CARCAVELOS", 7, "#47767a", True, "e")
        self.rect(x+10, y+31, right-16, y+62, glass)
        self.rect(x+10, y+31, right-16, y+35, "#c2dbdc")
        for column_x in range(x+10, right-15, 25):
            self.line((column_x, y+31, column_x, y+62), "#eaf0e6", 3)
            self.line((column_x+5, y+38, column_x+16, y+50), "#a8cbd0")
        self.line((x+10, y+61, right-16, y+61), "#f5f4e7", 4)
        self.rect(x+8, y+70, right-12, y+88, navy)
        self.text(x+88, y+79, "E  Present Foundry Town", 8, "#f1f8eb", True, "center")
        door_x, _ = site.door
        self.rect(door_x-13, y+90, door_x+13, bottom, "#537d84")
        self.line((door_x, y+91, door_x, bottom), "#d9ebe6", 2)
        self.rect(door_x-16, bottom+1, door_x+16, bottom+8, guide.color)
        self.rect(x+3, bottom+13, right-3, bottom+32, "#ede4cf")
        self.rect(x-1, y-22, right+1, y-4, guide.color)
        self.rect(x+2, y-20, right-2, y-18, "#a4d6d4")
        self.text(x+88, y-12, "PRESENTATION", 9, "#ffffff", True, "center")

    def light_research_building(self, site, glow):
        """Cool glazing and lit campus signs use the same cached night pass."""
        x, y = site.x, site.y
        c = self.c
        for window_x in range(x+12, x+160, 25):
            glow(window_x+9, y+47, 20, "#b8e0dc")
            c.create_rectangle(window_x+1, y+36, window_x+21, y+58,
                               fill="#c3e4dc", outline="", tags="night_lights")
            c.create_line(window_x+4, y+40, window_x+17, y+51,
                          fill="#a3c9ca", width=1, tags="night_lights")
        c.create_rectangle(x-1, y-22, x+177, y-4,
                           fill="#246b80", outline="", tags="night_lights")
        self.game.label(x+88, y-12, "PRESENTATION", 9, "#d9fff1", True,
                        anchor="center", tag="night_lights")
        self.game.label(x+11, y+23, "NOVA SBE", 11, "#e2fff3", True,
                        anchor="w", tag="night_lights")
        self.game.label(x+163, y+23, "CARCAVELOS", 7, "#dcf4e6", True,
                        anchor="e", tag="night_lights")
        self.game.label(x+88, y+79, "E  Present Foundry Town", 8, "#e2fff3", True,
                        anchor="center", tag="night_lights")
        door_x, door_y = site.door
        glow(door_x, door_y+7, 22, "#c6e4da")

    def building(self, site):
        if site.role == "CASINO":
            from casino_art import draw_casino
            draw_casino(self, site)
            return
        from wayfinding import site_guide
        guide = site_guide(site)
        if site.role == "EXCHANGE":
            self.exchange_building(site, guide)
            return
        if site.role == "RESEARCH":
            self.research_building(site, guide)
            return
        x, y, right, bottom = site.bounds
        palettes = (("#dec4a0", "#bc785b"), ("#e3c4b5", "#b87356"), ("#c7d3d0", "#ac7058"),
                    ("#e4ce95", "#b97552"))
        wall, roof = palettes[max(0, site.trade) % len(palettes)]
        if site.role == "CASINO":
            wall, roof = "#d3cabd", "#796f68"
        elif site.role == "TIER2":
            wall, roof = "#b98b73", "#5a6c71"
        elif site.role == "WAREHOUSE":
            wall, roof = "#bdd0cd", "#8b8f84"
        elif site.role == "PASTELARIA":
            wall, roof = "#f0dca6", "#b77955"
        elif site.role == "SHIPYARD":
            wall, roof = "#b8c8c5", "#5a747c"
        # Soft offset shadows, stone side wall, tiled pitched roof.
        self.poly((x+6, y+21, right+11, y+21, right+11, bottom+8, x+7, bottom+8), "#bfb69e")
        self.rect(x, y+12, right, bottom, wall)
        self.rect(right-8, y+15, right, bottom, "#afaa97")
        self.poly((x-4, y+14, x+14, y-2, right-13, y-2, right+4, y+14), roof)
        self.line((x+2, y+15, right-2, y+15), "#e9d1b0", 3)
        for tile_x in range(x+10, right-8, 13):
            self.line((tile_x, y+1, tile_x-4, y+11), "#cb9571")
        self.rect(x+10, y+20, right-14, y+24, "#eee2c8")
        # Tall shuttered windows and wrought-iron balconies.
        for window_x in (x+22, x+70, x+118):
            self.rect(window_x-3, y+29, window_x+27, y+63, "#eddfc9")
            self.rect(window_x, y+31, window_x+24, y+60, "#5f7d82")
            self.rect(window_x+2, y+33, window_x+10, y+46, "#a5c0bb")
            self.line((window_x+12, y+32, window_x+12, y+60), "#e8ddbf", 2)
            self.rect(window_x-6, y+57, window_x+30, y+61, "#777c70")
            self.line((window_x-4, y+50, window_x-4, y+59, window_x+28, y+59, window_x+28, y+50), "#4e625e")
            for bar in range(0, 28, 5):
                self.line((window_x+bar, y+51, window_x+bar, y+59), "#4e625e")
        # Azulejo band and an inviting ground-floor shopfront.
        self.rect(x+7, y+64, right-10, y+70, "#e9e3ce")
        for tile_x in range(x+10, right-12, 10):
            self.poly((tile_x, y+67, tile_x+3, y+64, tile_x+6, y+67, tile_x+3, y+70), "#628b9b")
        self.rect(x+8, y+72, right-11, bottom-4, "#314c55")
        self.text(x+15, y+81, site.name, 8, "#fff5df", True)
        if site.role != "RESIDENTIAL":
            # Colored signs name each building's role in the trading loop.
            self.rect(x-1, y-22, right+1, y-4, guide.color)
            self.rect(x+2, y-19, right-2, y-17, "#f6e7bf")
            self.text(x+88, y-12, guide.badge, 9, "#ffffff", True, anchor="center")
            self.rect(x+8, y+72, x+12, bottom-4, guide.color)
            self.rect(right-15, y+72, right-11, bottom-4, guide.color)
            self.text(x+15, y+95, guide.detail, 7, "#f2e7cb")
        else:
            self.text(x+15, y+96, guide.detail, 6, "#d1c9a8")
        door_x, _ = site.door
        self.rect(door_x-12, bottom-13, door_x+12, bottom+1, "#98754e")
        self.rect(door_x-16, bottom+2, door_x+16, bottom+8,
                  guide.color if site.role != "RESIDENTIAL" else "#d4a45c")
        self.rect(x+3, bottom+13, right-3, bottom+32, "#ede4cf")

    def tramway(self):
        """Tram tracks along the waterfront. The tram is scenery; there are no stops to board."""
        for y in (681, 691):
            self.line((25, y, WORLD_WIDTH-25, y), "#7f8580", 2)
            self.line((25, y+1, WORLD_WIDTH-25, y+1), "#f0e6d0")
        self.line((45, 665, WORLD_WIDTH-45, 665), "#8c9387", 1)
        for x in range(55, WORLD_WIDTH-30, 280):
            self.line((x, 668, x, 698), "#737e77", 2)
            self.line((x-8, 666, x+8, 666), "#737e77", 2)
        self.create_tram()

    def create_tram(self):
        # One retained group, moved each frame instead of rebuilding the tram.
        c = self.c
        c.create_oval(-34, 692, 38, 703, fill="#b4ac92", outline="", tags="tram")
        c.create_polygon(-34, 664, -28, 655, 28, 655, 34, 664, 34, 690, 28, 696, -28, 696, -34, 690,
                         fill="#d8a32f", outline="#a47931", smooth=True, tags="tram")
        c.create_rectangle(-30, 660, 30, 665, fill="#f7e8c3", outline="", tags="tram")
        self.tram_windows = []
        for x in (-25, -10, 5, 20):
            self.tram_windows.append(c.create_rectangle(x, 668, x+10, 681, fill="#55777c", outline="#f4e7bd", tags="tram"))
        c.create_line(-30, 684, 30, 684, fill="#f4e4b4", width=2, tags="tram")
        c.create_line(-8, 655, 2, 645, 12, 655, fill="#4a5d5e", width=2, tags="tram")
        c.create_oval(-25, 690, -16, 699, fill="#3c4c4f", outline="", tags="tram")
        c.create_oval(16, 690, 25, 699, fill="#3c4c4f", outline="", tags="tram")
        self.game.label(0, 687, "TEJO", 6, "#fff5dc", True, anchor="center", tag="tram")

    def set_night(self, enabled):
        for item in self.tram_windows:
            self.c.itemconfigure(item, fill="#f2d69a" if enabled else "#55777c")

    def animate(self, elapsed):
        phase = elapsed % 40
        fraction = min(1, phase/17) if phase < 20 else max(0, 1-(phase-20)/17)
        x = 80+(WORLD_WIDTH-180)*fraction
        self.c.move("tram", (x-self.tram_position)*self.game.scale_x, 0)
        self.tram_position = x


def draw_character(canvas, profile, body_colors, hair_colors, costumes, x, y,
                   elapsed=0, moving=False, facing=1, tag="live"):
    """Smooth, shaded figure, shared by the character editor and game."""
    outfit, accessory = costumes[profile["costume"]]
    stride = math.sin(elapsed*13)*3 if moving else 0
    canvas.create_oval(x-11, y+8, x+12, y+16, fill="#7e8474", outline="", tags=tag)
    for side in (-1, 1):
        foot_y = y+10+side*stride
        canvas.create_line(x+side*4, y+2, x+side*5, foot_y, fill="#3c4d56", width=5, capstyle="round", tags=tag)
        canvas.create_oval(x+side*5-3, foot_y-1, x+side*5+4, foot_y+3, fill="#28363e", outline="", tags=tag)
    canvas.create_oval(x-10, y-10, x+10, y+8, fill=outfit, outline="#5d6f70", width=1, tags=tag)
    canvas.create_line(x-10, y-4, x-13, y+3-stride*.4, fill=outfit, width=5, capstyle="round", tags=tag)
    canvas.create_line(x+10, y-4, x+13, y+3+stride*.4, fill=outfit, width=5, capstyle="round", tags=tag)
    canvas.create_oval(x-7, y-24, x+7, y-9, fill=body_colors[profile["body"]], outline="#aa8a71", width=1, tags=tag)
    canvas.create_arc(x-8, y-26, x+8, y-8, start=0, extent=180, fill=hair_colors[profile["hair"]], outline="", tags=tag)
    canvas.create_oval(x+facing*3-1, y-17, x+facing*3+1, y-15, fill="#3b4544", outline="", tags=tag)
    canvas.create_line(x-5, y-9, x+5, y-8, fill=accessory, width=3, capstyle="round", tags=tag)
    if profile["costume"] == "Builder":
        canvas.create_arc(x-9, y-30, x+9, y-17, start=0, extent=180, fill=accessory, outline="", tags=tag)
        canvas.create_line(x-10, y-23, x+10, y-23, fill=accessory, width=3, tags=tag)
    elif profile["costume"] == "Wizard":
        canvas.create_polygon(x-9, y-24, x+2, y-42, x+8, y-24, fill=accessory, smooth=True, outline="", tags=tag)
    elif profile["costume"] in ("Explorer", "Chef"):
        canvas.create_oval(x-10, y-29, x+10, y-22, fill=accessory, outline="", tags=tag)
