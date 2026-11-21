"""Browser-specific navigation, simulation turns and optional local saves."""
from contextlib import closing
import json
import math
from pathlib import Path
import sqlite3

from exchange import advance_city
from ferry import FERRY_FARE, FERRY_PIERS, nearby_pier, ride_ferry
from tycoon import BRIDGE_TOLL, RIVER_BOTTOM, Town, pack_save, unpack_save


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


def advance_turn(town, seconds):
    """Advance active systems in the same order as play, settling each day once."""
    town.message = f"Advanced {seconds} seconds."
    for _ in range(seconds):
        advance_clock(town, 1)


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
    dx, dy, seconds, action = (event.get(key) for key in ("dx", "dy", "seconds", "action"))
    if (type(dx) is not int or dx not in (-1, 0, 1)
            or type(dy) is not int or dy not in (-1, 0, 1)
            or type(seconds) not in (int, float) or not 0 <= seconds <= 0.25
            or action not in (None, "interact", "bulk", "egg", "eggs")):
        return False

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
