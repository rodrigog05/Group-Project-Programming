"""Map collision and time-based movement. The bridges carry vehicles only; walkers take the ferry."""

import math

from catalog import ROUTES

WIDTH, HEIGHT = 2400, 1780
RIVER_TOP, RIVER_BOTTOM = 718, 1080
RADIUS, SPEED = 10, 228

# Physical outlines for the other buildings, gardens and landmarks on the baked map.
SCENERY = (
    (1004, 342, 1180, 446),
    (988, 530, 1164, 634),
    (988, 160, 1164, 264),
    (28, 160, 204, 264),
    (380, 1115, 556, 1219),
    (1820, 345, 1996, 449),
    (2080, 530, 2256, 634),
    (2060, 1610, 2236, 1714),
    (1540, 1360, 1716, 1464),
    (2060, 1360, 2236, 1464),
    (508, 160, 684, 264),
    (28, 530, 204, 634),
    (650, 1115, 826, 1219),
    (1540, 160, 1716, 264),
    (1338, 371, 1398, 419),
    (2080, 345, 2256, 449),
    (700, 1360, 876, 1464),
    (1280, 1360, 1456, 1464),
    (1858, 1386, 1918, 1434),
    (1540, 1610, 1716, 1714),
    (28, 345, 204, 449),
    (748, 160, 924, 264),
    (508, 530, 532, 634),
    (660, 530, 684, 634),
    (532, 530, 660, 552),
    (1780, 190, 2030, 260),
)
WALLS = SCENERY + tuple(
    (s.x - 88, s.y - 104, s.x + 88, s.y)
    for r in ROUTES
    for s in (r.supplier, r.workshop, r.market)
)


# Paved lanes from the desktop map: (x1, y1, x2, y2, half width). Vehicles drive faster on them.
ROADS = (
    (238, 140, 238, 653, 15), (478, 140, 478, 653, 15), (718, 140, 718, 653, 15),
    (958, 140, 958, 653, 15), (0, 301, 2400, 301, 19.5), (0, 486, 2400, 486, 19.5),
    (0, 660, 2400, 660, 17.5), (1225, 140, 1225, 660, 14.5), (1495, 140, 1495, 660, 14.5),
    (1775, 140, 1775, 660, 14.5), (2035, 140, 2035, 660, 14.5), (2350, 140, 2350, 660, 14.5),
    (0, 1290, 2400, 1290, 17), (0, 1550, 2400, 1550, 17), (0, 1750, 2400, 1750, 17),
    (620, 1240, 620, 1760, 15), (1190, 1240, 1190, 1760, 15), (1495, 1240, 1495, 1760, 15),
    (1775, 1240, 1775, 1760, 15), (2035, 1240, 2035, 1760, 15), (2350, 1240, 2350, 1760, 15),
    (0, 1238, 2400, 1238, 12), (300, 1082, 300, 1238, 16), (1919, 1082, 2035, 1238, 16),
    (300, 695, 300, 1115, 27), (2041, 698, 1913, 1099, 22.5), (2035, 660, 2041, 698, 16),
)
# The Almada garden (only its tunnel lane at y=1550 is road) and a Parque das Nações plaza.
NO_ROAD = ((60, 1390, 550, 1710), (1810, 520, 2010, 640))


def on_bridge(x, y):
    east = 2035 - 0.32 * (y - RIVER_TOP)
    return abs(x - 300) <= 31 - RADIUS or abs(x - east) <= 27 - RADIUS


def on_road(x, y):
    if any(l < x < r and t < y < b and abs(y - 1550) > 17 for l, t, r, b in NO_ROAD):
        return False
    for x1, y1, x2, y2, half in ROADS:
        dx, dy = x2 - x1, y2 - y1
        f = min(1, max(0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
        if (x - x1 - f * dx) ** 2 + (y - y1 - f * dy) ** 2 <= half * half:
            return True
    return False


def walkable(x, y, driving=False):
    """Whether the player can stand here. Only vehicles may use the bridges."""
    if not (RADIUS <= x <= WIDTH - RADIUS and 104 + RADIUS <= y <= HEIGHT - RADIUS):
        return False
    if RIVER_TOP - RADIUS < y < RIVER_BOTTOM + RADIUS:
        if not driving or not on_bridge(x, y):
            return False
    return not any(
        l - RADIUS < x < r + RADIUS and top - RADIUS < y < b + RADIUS
        for l, top, r, b in WALLS
    )


def move(x, y, dx, dy, seconds, speed=SPEED, driving=False):
    length = math.hypot(dx, dy)
    if not length:
        return x, y
    distance = speed * min(max(seconds, 0), 0.25) / length
    steps = max(1, math.ceil(distance * length / 6))
    for _ in range(steps):
        nx = x + dx * distance / steps
        if walkable(nx, y, driving):
            x = nx
        ny = y + dy * distance / steps
        if walkable(x, ny, driving):
            y = ny
    return x, y
