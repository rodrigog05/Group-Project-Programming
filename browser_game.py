"""Browser-specific navigation, simulation turns and optional local saves."""
from contextlib import closing
import json
import math
from pathlib import Path
import random
import sqlite3

from exchange import advance_city
from ferry import FERRY_FARE, FERRY_PIERS, nearby_pier, ride_ferry
import lisbon_scene as scene
from vehicles import CAR_SPEED_RANGE, ROAD_EXCLUSIONS, tunnel_covers_y
from tycoon import (BRIDGE_TOLL, COLLISION_BOUNDS, MAP_TOP, PLAYER_RADIUS, RIVER_BOTTOM, Town, pack_save,
                    unpack_save)

# The browser predicts movement with the same walls as Town.can_walk. Python still checks every step.
COLLISION_MAP = {
    "radius": PLAYER_RADIUS,
    "world": [scene.WORLD_WIDTH, MAP_TOP, scene.WORLD_BOTTOM],
    "boxes": [list(box) for box in COLLISION_BOUNDS],
    "parks": [list(box) for box in scene.PARK_BOUNDS],
    "tunnel": list(scene.SOUTH_PARK_TUNNEL),
    "river": [scene.RIVER_TOP, scene.RIVER_BOTTOM],
    "vasco": scene.VASCO_NORTH_X,
    "sand": [scene.SAND_WEST, scene.SAND_EAST, scene.SAND_BOTTOM],
    "tower": [90, 735, 190, 850],  # Belém Tower on the beach (left, top, right, bottom), as in walkable_terrain
    "toll": BRIDGE_TOLL,
}


def street_life():
    """Decorative pedestrians, cars and the waterfront tram, with the desktop game's routes."""
    rng = random.Random(2815)
    south = scene.south
    walks = (((32, 280), (1160, 280)), ((40, 465), (1160, 465)), ((50, 647), (1150, 647)),
             ((1260, 280), (scene.WORLD_WIDTH-70, 280)), ((1260, 465), (scene.WORLD_WIDTH-90, 465)),
             ((1270, 645), (scene.WORLD_WIDTH-80, 645)), ((90, south(1090)), (scene.WORLD_WIDTH-120, south(1090))),
             ((85, south(1395)), (scene.WORLD_WIDTH-130, south(1395))),
             ((65, scene.WORLD_BOTTOM-55), (scene.WORLD_WIDTH-110, scene.WORLD_BOTTOM-55)))
    people = []
    for index in range(45):
        (x1, y1), (x2, y2) = walks[index % len(walks)]
        people.append([x1, y1, x2, y2, rng.uniform(20, 34), rng.random()*2,
                       rng.choice(("#b37262", "#547d8b", "#81926f", "#ba9d61", "#8a7195"))])
    cars = []
    lanes = (291, 308, 476, 493, 650, 666, south(1101), south(1119), south(1362), south(1378),
             scene.WORLD_BOTTOM-38, scene.WORLD_BOTTOM-22)
    for index, y in enumerate(lanes):
        # Lanes that would cross a park start beside it; the tunnel lane runs under the Almada park.
        start = max([15] + [right+20 for left, top, right, bottom in ROAD_EXCLUSIONS
                            if top < y < bottom and not (left == scene.SOUTH_PARK_BOUNDS[0] and tunnel_covers_y(y))])
        # Paired lanes carry traffic in opposite directions.
        phase = rng.random()
        for extra in (0, .5):  # Two cars per lane, half a lap apart
            cars.append([start, y, scene.WORLD_WIDTH-20, rng.uniform(*CAR_SPEED_RANGE), (phase+extra) % 1,
                         -1 if index % 2 else 1,
                         rng.choice(("#9b584e", "#c6c5b5", "#759ca5", "#b89b62", "#e8455a", "#86caff"))])
    left, _, right, _ = scene.SOUTH_PARK_BOUNDS
    _, _, tunnel_y, tunnel_half = scene.SOUTH_PARK_TUNNEL
    return {"people": people, "cars": cars, "tunnel": [left, right, tunnel_y, tunnel_half],
            "tram": [80, scene.WORLD_WIDTH-100, 40]}  # From x, to x, seconds for a round trip


STREET_LIFE = street_life()


def entrance(site):
    """Return the walkable approach within interaction range of the door."""
    x, y = site.door
    return x, y + 15


def visit(town, position, label):
    south = town.y >= RIVER_BOTTOM
    destination_south = position[1] >= RIVER_BOTTOM
    charge = ""
    if south != destination_south:
        if town.vehicle:
            if south and town.cash < BRIDGE_TOLL:
                town.message = f"The portagem toward Lisboa costs ${BRIDGE_TOLL}. You need more cash."
                return
            town.bridge_journey = {"origin": "south" if south else "north", "bridge": "25 de Abril"}
            old_y = town.y
            town.y = position[1]
            town.check_bridge_crossing(old_y)
            if south:
                charge = f" · Bridge toll ${BRIDGE_TOLL}"
        else:
            if town.cash < FERRY_FARE:
                town.message = f"Crossing costs ${FERRY_FARE}. You need more cash."
                return
            old_position = town.x, town.y
            town.x, town.y = FERRY_PIERS[int(south)].position
            if ride_ferry(town) is None:
                town.x, town.y = old_position
                return
            charge = f" · Ferry fare ${FERRY_FARE}"

    town.x, town.y = position
    town.message = f"Arrived at {label}{charge}."


def advance_clock(town, seconds):
    town.advance(seconds)
    advance_city(town, seconds)
    town.advance_research(seconds)
    town.advance_deliveries(seconds)
    town.advance_contracts(seconds)
    town.advance_businesses(seconds)
    town.sync_market(town.market_elapsed + seconds)


def street_input(town, event):
    """Apply a small, validated movement batch using the desktop collision rules."""
    if not isinstance(event, dict):
        return False
    action = event.get("action")
    segments = event.get("segments", [event])
    if (not isinstance(segments, list) or not 1 <= len(segments) <= 120
            or action not in (None, "interact", "bulk", "egg", "eggs")):
        return False
    total = 0
    for segment in segments:
        if not isinstance(segment, dict):
            return False
        dx, dy, seconds = (segment.get(key) for key in ("dx", "dy", "seconds"))
        if (type(dx) is not int or dx not in (-1, 0, 1)
                or type(dy) is not int or dy not in (-1, 0, 1)
                or type(seconds) not in (int, float) or not 0 <= seconds <= 0.25):
            return False
        total += seconds
    if total > 2.000001:
        return False
    for segment in segments:
        dx, dy, seconds = (segment[key] for key in ("dx", "dy", "seconds"))
        steps = max(1, math.ceil(seconds * 60))
        for _ in range(steps):
            if dx or dy:
                town.move(dx, dy, seconds / steps)
            if seconds:
                advance_clock(town, seconds / steps)
    if action == "interact" and nearby_pier(town.x, town.y):
        ride_ferry(town)
    elif action in ("interact", "bulk"):
        if action == "bulk" and (town.nearby() is None or town.nearby().role != "SUPPLIER"):
            town.message = "Walk up to a supplier to buy materials in bulk."
        else:
            town.interact(bulk=action == "bulk")
    elif action in ("egg", "eggs"):
        town.buy_eggs(bulk=action == "eggs")
    return True


class SaveConflict(Exception):
    """The save was updated in another browser session."""


class LocalSave:
    """One SQLite slot for a private, loopback-only instance."""

    def __init__(self, path):
        self.path = Path(path)

    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.path, timeout=2)

    def load(self):
        with closing(self.connect()) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS game (id INTEGER PRIMARY KEY CHECK (id = 1), "
                "revision INTEGER NOT NULL, snapshot TEXT NOT NULL)"
            )
            row = connection.execute("SELECT revision, snapshot FROM game WHERE id = 1").fetchone()
        if row is None:
            return Town(), 0
        revision, snapshot = row
        town, _ = unpack_save(json.loads(snapshot))
        return town, revision

    def save(self, town, revision):
        snapshot = json.dumps(pack_save(town, 0), allow_nan=False)
        with closing(self.connect()) as connection, connection:
            if revision == 0:
                result = connection.execute(
                    "INSERT INTO game VALUES (1, 1, ?) ON CONFLICT (id) DO NOTHING", (snapshot,)
                )
            else:
                result = connection.execute(
                    "UPDATE game SET snapshot = ?, revision = revision + 1 "
                    "WHERE id = 1 AND revision = ?", (snapshot, revision)
                )
            if result.rowcount != 1:
                raise SaveConflict
        return revision + 1
