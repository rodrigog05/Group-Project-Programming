"""Cached delivery routes on the painted roads of the compact Lisbon map.

Road search happens when a route is first used, never for each animation frame.
This module is independent of the game and renderer to avoid import cycles.
"""
from functools import lru_cache
import heapq
import math


NORTH_ROWS = (301, 486, 660)
NORTH_COLUMNS = (238, 478, 718, 958, 1225, 1495, 1775, 2035, 2350)
SOUTH_ROWS = (1058, 1110, 1370, 1570)
SOUTH_COLUMNS = (620, 1190, 1495, 1775, 2035, 2350)
RIVER_TOP, RIVER_BOTTOM = 718, 900


def _bridge_x(y):
    return 2035 - .32 * (y - RIVER_TOP)


def _anchor(point):
    x, y = point
    rows = NORTH_ROWS if y < RIVER_TOP else SOUTH_ROWS
    return x, min(rows, key=lambda row: abs(y-row))


@lru_cache(maxsize=256)
def road_path(start, end):
    """Return a shortest paved path, with short doorstep access at both ends."""
    start, end = tuple(start), tuple(end)
    if start == end:
        return (start,)
    first, last = _anchor(start), _anchor(end)
    graph = {}

    def connect(a, b):
        if a == b:
            return
        distance = math.dist(a, b)
        graph.setdefault(a, {})[b] = distance
        graph.setdefault(b, {})[a] = distance

    for rows, columns in ((NORTH_ROWS, NORTH_COLUMNS), (SOUTH_ROWS, SOUTH_COLUMNS)):
        xs = set(columns) | {300}
        for point in (first, last):
            if point[1] in rows:
                xs.add(point[0])
        xs = sorted(xs)
        for y in rows:
            for left, right in zip(xs, xs[1:]):
                connect((left, y), (right, y))
        for x in columns:
            for top, bottom in zip(rows, rows[1:]):
                connect((x, top), (x, bottom))

    connect((300, 660), (300, 1058))
    east = ((2035, 660), (_bridge_x(698), 698), (_bridge_x(919), 919), (2035, 1058))
    for a, b in zip(east, east[1:]):
        connect(a, b)
    connect(start, first)
    connect(last, end)
    graph.setdefault(start, {})
    graph.setdefault(end, {})
    queue, costs, previous = [(0, start)], {start: 0}, {}
    while queue:
        distance, node = heapq.heappop(queue)
        if distance != costs[node]:
            continue
        if node == end:
            result = [end]
            while result[-1] != start:
                result.append(previous[result[-1]])
            return tuple(reversed(result))
        for neighbor, length in graph[node].items():
            cost = distance+length
            if cost < costs.get(neighbor, math.inf):
                costs[neighbor], previous[neighbor] = cost, node
                heapq.heappush(queue, (cost, neighbor))
    raise ValueError("No delivery road connects those entrances")


@lru_cache(maxsize=512)
def path_length(points):
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def point_on_path(points, fraction):
    """Sample a saved route without changing clocks, inventory or accounts."""
    if len(points) < 2:
        return points[0]
    distance = min(1, max(0, fraction))*path_length(points)
    for a, b in zip(points, points[1:]):
        length = math.dist(a, b)
        if distance <= length:
            amount = distance/length if length else 0
            return a[0]+(b[0]-a[0])*amount, a[1]+(b[1]-a[1])*amount
        distance -= length
    return points[-1]


def bridge_used(points):
    """Identify the actual bridge of a cross-bank van route."""
    if (points[0][1] < RIVER_TOP) == (points[-1][1] < RIVER_TOP):
        return None
    return "25 de Abril" if (300, 660) in points and (300, 1058) in points else "Vasco da Gama"
