"""Cheap walking directions with explicit, usable river crossings."""
import math

from lisbon_scene import RIVER_TOP, RIVER_BOTTOM, bridge_at, bridge_center


def next_step(x, y, target_x, target_y):
    north, south = RIVER_TOP-14, RIVER_BOTTOM+14
    target_north = target_y < RIVER_TOP
    if RIVER_TOP-10 < y < RIVER_BOTTOM+10:
        name = bridge_at(x, y)
        if name:
            exit_y = north if target_north else south
            return (bridge_center(exit_y, name == "Vasco da Gama"), exit_y), f"Cross Ponte {name}"
    if (y < RIVER_TOP) == target_north:
        return (target_x, target_y), ""
    entries = []
    for eastern, name in ((False, "25 de Abril"), (True, "Vasco da Gama")):
        entry_y, exit_y = (south, north) if target_north else (north, south)
        entry, exit = (bridge_center(entry_y, eastern), entry_y), (bridge_center(exit_y, eastern), exit_y)
        length = math.dist((x, y), entry)+math.dist(entry, exit)+math.dist(exit, (target_x, target_y))
        entries.append((length, entry, exit, name))
    _, entry, exit, name = min(entries)
    return (exit if math.dist((x, y), entry) < 18 else entry), f"Via Ponte {name}"


def compass(dx, dy):
    if abs(dx)+abs(dy) < 1:
        return "HERE"
    directions = ("E →", "SE ↘", "S ↓", "SW ↙", "W ←", "NW ↖", "N ↑", "NE ↗")
    return directions[round(math.atan2(dy, dx)/(math.pi/4)) % 8]
