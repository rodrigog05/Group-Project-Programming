"""Street directions only: never move the player or change game state."""
from functools import lru_cache
import heapq
import math

from ferry import FERRY_PIERS
from lisbon_scene import RIVER_BOTTOM
from tycoon import Town
from vehicles import on_road

STEP = 20


@lru_cache(maxsize=2)
def navigator(driving):
    town = Town()
    town.vehicle = "car" if driving else None
    return town


@lru_cache(maxsize=40000)
def valid(point, driving):
    return navigator(driving).can_walk(*point, roads_only=driving)


def clear_line(a, b, driving):
    steps = max(1, math.ceil(math.dist(a, b) / 5))
    return all(valid((a[0] + (b[0]-a[0])*i/steps, a[1] + (b[1]-a[1])*i/steps), driving)
               for i in range(steps+1))


def anchor(point, driving, access=False):
    x, y = (round(value/STEP)*STEP for value in point)
    candidates = [(x+dx*STEP, y+dy*STEP) for dx in range(-8, 9) for dy in range(-8, 9)]
    candidates.sort(key=lambda candidate: math.dist(point, candidate))
    for candidate in candidates:
        if (candidate[1] >= RIVER_BOTTOM) != (point[1] >= RIVER_BOTTOM):
            continue
        if valid(candidate, driving) and (access or clear_line(point, candidate, driving)):
            return candidate
    return None


@lru_cache(maxsize=256)
def grid_route(start, end, driving):
    queue = [(math.dist(start, end), 0, start)]
    costs, previous = {start: 0}, {}
    while queue:
        _, cost, point = heapq.heappop(queue)
        if cost != costs[point]:
            continue
        if point == end:
            route = [end]
            while route[-1] != start:
                route.append(previous[route[-1]])
            route.reverse()
            # Keep turns, omit redundant points along straight streets.
            result = route[:1]
            for i in range(1, len(route)-1):
                a, b, c = route[i-1:i+2]
                if (b[0]-a[0], b[1]-a[1]) != (c[0]-b[0], c[1]-b[1]):
                    result.append(b)
            return tuple(result + route[-1:])
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)):
            neighbor = point[0]+dx*STEP, point[1]+dy*STEP
            if not valid(neighbor, driving) or not clear_line(point, neighbor, driving):
                continue
            distance = math.dist(point, neighbor)
            weight = 1 if driving or on_road(*neighbor) else 2.8
            next_cost = cost + distance * weight
            if next_cost < costs.get(neighbor, math.inf):
                costs[neighbor], previous[neighbor] = next_cost, point
                heapq.heappush(queue, (next_cost+math.dist(neighbor, end), next_cost, neighbor))
    return ()


def directions(town, destination):
    if destination is None:
        return {"points": [], "instruction": "Choose a destination to show directions."}
    start = town.x, town.y
    end = tuple(destination)
    driving = bool(town.vehicle)
    instruction = "Follow the blue line. Press E at the entrance."
    if not driving and (town.y >= RIVER_BOTTOM) != (end[1] >= RIVER_BOTTOM):
        pier = FERRY_PIERS[int(town.y >= RIVER_BOTTOM)]
        end = pier.position
        instruction = f"Follow the blue line to {pier.name}. Press E to take the ferry ($2)."
    if math.dist(start, end) <= 28:
        return {"points": [], "instruction": "You have arrived. Press E to interact." if end == tuple(destination) else instruction}
    first, last = anchor(start, driving), anchor(end, driving, access=driving)
    if first is None or last is None:
        return {"points": [], "instruction": "Walk onto a nearby street to start directions."}
    path = grid_route(first, last, driving)
    if not path:
        return {"points": [], "instruction": "No safe street route from here. Walk onto a nearby street."}
    points = [start, *path]
    if clear_line(last, end, driving):
        points.append(end)
    elif driving:
        instruction = "Follow the blue line, then leave your vehicle and walk to the entrance."
    return {"points": points, "instruction": instruction}
