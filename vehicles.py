"""Vehicle costs, reusable trunk capacity and the town's painted road network."""
from dataclasses import dataclass

from lisbon_scene import WORLD_WIDTH, VASCO_NORTH_X, bridge_center


@dataclass(frozen=True)
class Vehicle:
    label: str
    price: int
    trunk: int
    offroad_speed: int
    road_speed: int


# Every ride can be purchased before the $500 victory threshold.
VEHICLES = {
    "motorcycle": Vehicle("Motorcycle", 120, 6, 420, 520),
    "car": Vehicle("Car", 240, 48, 510, 690),
    "van": Vehicle("Delivery van", 360, 108, 430, 620),
}
WALK_SPEED = 228
ROAD_EXCLUSIONS = ((60, 1210, 550, 1530), (1810, 520, 2010, 640))

# Center lines and half-widths match LisbonScene's paved lanes. Pavements,
# parks and the tram promenade do not grant the driving speed bonus.
ROAD_SEGMENTS = (
    tuple((x, 140, x, 653, 15) for x in (238, 478, 718, 958))
    + tuple((0, y, WORLD_WIDTH, y, 19.5) for y in (301, 486))
    + ((0, 660, WORLD_WIDTH, 660, 17.5),)
    + tuple((x, 140, x, 660, 14.5) for x in (1225, 1495, 1775, VASCO_NORTH_X, 2350))
    + tuple((0, y, WORLD_WIDTH, y, 17) for y in (1110, 1370, 1570))
    + tuple((x, 1060, x, 1580, 15) for x in (620, 1190, 1495, 1775, VASCO_NORTH_X, 2350))
    + ((0, 1058, WORLD_WIDTH, 1058, 12), (300, 902, 300, 1058, 16),
       (bridge_center(902, True), 902, VASCO_NORTH_X, 1058, 16),
       (300, 695, 300, 935, 27),
       (bridge_center(698, True), 698, bridge_center(919, True), 919, 22.5),
       (VASCO_NORTH_X, 660, bridge_center(698, True), 698, 16))
)


def on_road(x, y, blocked=()):
    """Test actual lane width; collision footprints take priority over paint."""
    if any(left < x < right and top < y < bottom for left, top, right, bottom in ROAD_EXCLUSIONS):
        return False
    if any(left < x < right and top < y < bottom for left, top, right, bottom in blocked):
        return False
    for x1, y1, x2, y2, half_width in ROAD_SEGMENTS:
        dx, dy = x2-x1, y2-y1
        fraction = min(1, max(0, ((x-x1)*dx+(y-y1)*dy)/(dx*dx+dy*dy)))
        if (x-x1-fraction*dx)**2+(y-y1-fraction*dy)**2 <= half_width**2:
            return True
    return False
