"""Vehicle costs, reusable trunk capacity and the town's painted road network."""
from dataclasses import dataclass

from lisbon_scene import (WORLD_WIDTH, VASCO_NORTH_X, RIVER_TOP, RIVER_BOTTOM, bridge_center, south,
                          SOUTH_PARK_BOUNDS, SOUTH_PARK_TUNNEL, NORTH_AVENUE_Y, NORTH_JUNCTIONS)


@dataclass(frozen=True)
class Vehicle:
    label: str
    price: int
    trunk: int
    offroad_speed: int
    road_speed: int


# Every ride can be purchased before the $500 victory threshold.
VEHICLES = {
    "motorcycle": Vehicle("Motorcycle", 120, 6, 294, 364),
    "car": Vehicle("Car", 240, 48, 357, 483),
    "van": Vehicle("Delivery van", 360, 108, 301, 434),
    "f1": Vehicle("F1 car", 480, 0, 245, 630),
}
WALK_SPEED = 228
# City traffic outpaces a walking player, even one with the 1.5x speed power-up.
CAR_SPEED_RANGE = (360, 440)
ROAD_EXCLUSIONS = (SOUTH_PARK_BOUNDS, (1810, 520, 2010, 640))


def tunnel_covers_y(y):
    """Whether a lane center runs inside the covered south-bank underpass."""
    _, _, center_y, half_width = SOUTH_PARK_TUNNEL
    return abs(y-center_y) <= half_width


def in_tunnel(x, y):
    """Whether a point is on the playable tunnel road below the central park."""
    left, right, center_y, half_width = SOUTH_PARK_TUNNEL
    return left <= x <= right and abs(y-center_y) <= half_width

# Center lines and half-widths match LisbonScene's paved lanes. Pavements,
# parks and the waterfront promenade do not grant the driving speed bonus.
ROAD_SEGMENTS = (
    ((NORTH_JUNCTIONS[0], NORTH_AVENUE_Y, NORTH_JUNCTIONS[-1], NORTH_AVENUE_Y, 13),)
    + tuple((x, NORTH_AVENUE_Y, x, 653, 15) for x in NORTH_JUNCTIONS[:4])
    + tuple((0, y, WORLD_WIDTH, y, 19.5) for y in (301, 486))
    + ((0, 660, WORLD_WIDTH, 660, 17.5),)
    + tuple((x, NORTH_AVENUE_Y, x, 660, 14.5) for x in NORTH_JUNCTIONS[4:])
    + tuple((0, south(y), WORLD_WIDTH, south(y), 17) for y in (1110, 1370, 1570))
    + tuple((x, south(1060), x, south(1580), 15) for x in (620, 1190, 1495, 1775, VASCO_NORTH_X, 2350))
    + ((0, south(1058), WORLD_WIDTH, south(1058), 12), (300, RIVER_BOTTOM+2, 300, south(1058), 16),
       (bridge_center(RIVER_BOTTOM+19, True), RIVER_BOTTOM+19, VASCO_NORTH_X, south(1058), 16),
       # Bridge decks span the river from quay to quay.
       (300, RIVER_TOP-23, 300, RIVER_BOTTOM+35, 27),
       (bridge_center(RIVER_TOP-20, True), RIVER_TOP-20, bridge_center(RIVER_BOTTOM+19, True), RIVER_BOTTOM+19, 22.5),
       (VASCO_NORTH_X, 660, bridge_center(RIVER_TOP-20, True), RIVER_TOP-20, 16))
)


def road_projection(x, y, segment):
    x1, y1, x2, y2, _ = segment
    dx, dy = x2-x1, y2-y1
    fraction = min(1, max(0, ((x-x1)*dx+(y-y1)*dy)/(dx*dx+dy*dy)))
    return x1 + fraction*dx, y1 + fraction*dy


def on_road(x, y, blocked=()):
    """Test actual lane width; collision footprints take priority over paint."""
    if any(left < x < right and top < y < bottom and not in_tunnel(x, y)
           for left, top, right, bottom in ROAD_EXCLUSIONS):
        return False
    if any(left < x < right and top < y < bottom for left, top, right, bottom in blocked):
        return False
    for segment in ROAD_SEGMENTS:
        center_x, center_y = road_projection(x, y, segment)
        if (x-center_x)**2+(y-center_y)**2 <= segment[-1]**2:
            return True
    return False
