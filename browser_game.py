"""Browser-specific navigation, simulation turns and optional local saves."""
from contextlib import closing
import json
import math
from pathlib import Path
import random
import sqlite3

from exchange import advance_city
from ferry import FERRY_FARE, FERRY_PIERS, nearby_pier, ride_ferry
import businesses
import lisbon_scene as scene
from lisbon_landmarks import LANDMARKS
from vehicles import (
    VEHICLES, CAR_SPEED_RANGE, ROAD_EXCLUSIONS, ROAD_SEGMENTS, in_tunnel, on_road,
    road_projection, tunnel_covers_y,
)
from tycoon import (BRIDGE_TOLL, COLLISION_BOUNDS, MAP_TOP, PLAYER_RADIUS, RIVER_BOTTOM, SITES, TRADES, Town,
                    pack_save, unpack_save)

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
    "roads": ROAD_SEGMENTS,
    "road_exclusions": ROAD_EXCLUSIONS,
}


PEDESTRIAN_BODY = (-13, 0, 8)  # Head, body and feet relative to a walker's position in street.js


def off_road(x, y):
    """A pedestrian here stands on dry land with their whole body clear of every traffic lane.
    Their head may overlap a shop front behind them, as on the desktop game's pavements."""
    return scene.walkable_terrain(x, y, 0, on_foot=True) and not any(
        on_road(x+dx, y+dy) for dx in (-5, 5) for dy in PEDESTRIAN_BODY)


def pavement_walks():
    """Pavement stretches beside each street, split at crossings so nobody walks into traffic."""
    south = scene.south
    walks = []
    for base in (280, 465, 647, south(1090), south(1395), scene.WORLD_BOTTOM-55):
        # The desktop routes ran on the kerb; move each one onto the nearest clear pavement.
        y = min((y for y in range(base-40, base+41)
                 if sum(off_road(x, y) for x in range(40, scene.WORLD_WIDTH, 40)) > 30),
                key=lambda y: abs(y-base))
        start = None
        for x in range(0, scene.WORLD_WIDTH+4, 4):
            clear = x < scene.WORLD_WIDTH and off_road(x, y)
            if clear and start is None:
                start = x
            elif not clear and start is not None:
                if x-start >= 80:
                    walks.append((start+6, x-10, y))
                start = None
    return walks


def street_life():
    """Decorative pedestrians, cars and the waterfront tram, with the desktop game's routes."""
    rng = random.Random(2815)
    south = scene.south
    people = []
    walks = pavement_walks()
    for index in range(45):
        x1, x2, y = walks[index % len(walks)]
        people.append([x1, y, x2, y, rng.uniform(20, 34), rng.random()*2,
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
    north_pier, south_pier = FERRY_PIERS
    # The cacilheiro shuttles between the two piers, as on the desktop map.
    shuttle = [north_pier.x+30, scene.RIVER_TOP+80, south_pier.x-30, scene.RIVER_BOTTOM-80, 45]
    return {"people": people, "cars": cars, "tunnel": [left, right, tunnel_y, tunnel_half], "ferry": shuttle,
            "tram": [80, scene.WORLD_WIDTH-100, 40]}  # From x, to x, seconds for a round trip


STREET_LIFE = street_life()


# ----- Buildings: what is at the door, which illustrated scene to show and what the vendor says -----

MONASTERY = "Mosteiro dos Jerónimos"
DRIVE_IN = 110  # How far below its door a driver can still enter the dealership (forecourt + road lane)
# Closed to keep the game simple: the only car dealership is in Cacilhas (so the first vehicle needs a ferry
# ride), one warehouse is enough, and the eggs / pastéis side chain is gone. The engine keeps them for
# old saves; on the map their plots show apartment blocks.
CLOSED_SITES = frozenset({"Motorworks Garage", "Armazém do Seixal", "Pastéis de Belém"})
OPEN_SITES = tuple(site for site in SITES if site.name not in CLOSED_SITES)
INTERIOR_ROLES = ("SUPPLIER", "FACTORY", "PUBLIC SHOP", "PASTELARIA", "SHIPYARD", "TIER2")
# Scenes from the desktop game, as drawn in street/scenes. Boxes are in each scene's own pixels.
SCENES = {
    "interior": {"size": (640, 400), "bubble": (250, 20, 470, 130), "board": (336, 318, 500, 384)},
    "garage": {"size": (800, 400), "bubble": (460, 10, 790, 80), "board": None},
    "monastery": {"size": (640, 400), "bubble": None, "board": None},
    "casino": {"size": (1200, 700), "bubble": None, "board": None},
}


def building_at(town):
    """The building or monastery whose door the player stands at, by name. Ferry piers come first."""
    if nearby_pier(town.x, town.y):
        return None
    site = town.nearby()
    if site:
        return None if site.name in CLOSED_SITES else site.name
    if town.vehicle:
        # Drivers stay on the road, so the dealership's door reaches across its forecourt to the
        # road in front of it.
        for dealer in OPEN_SITES:
            door_x, door_y = dealer.door
            if dealer.role == "GARAGE" and abs(town.x - door_x) <= 60 and door_y < town.y <= door_y + DRIVE_IN:
                return dealer.name
    left, _, right, bottom = LANDMARKS[0].bounds
    if math.hypot(town.x-(left+right)/2, town.y-(bottom+16)) <= 40:
        return MONASTERY
    return None


BUILDING_HINTS = {
    "CASINO": "Pick a chip with ← →, then press 1 (red), 2 (black) or 3 (green 0) to spin the wheel.",
    "GARAGE": "Press 1–4 to buy a vehicle. Vehicles are faster and their trunk carries more.",
    "WAREHOUSE": "Press E to add 12 storage slots, so you can carry bigger batches.",
    "EXCHANGE": "Buy and sell shares with the controls below the game view.",
    "RESEARCH": "Start research below the game view to unlock new products.",
    MONASTERY: "Each visit adds 5 points of casino luck, up to +20.",
}


def bag_full(town):
    """No free slot left: materials, products and slots reserved by orders in production all count."""
    return town.cargo + town.reserved >= town.carry_capacity


def next_move(town, inside=None):
    """The next step to suggest, as {"text", "target"}, or None when the player needs no hint.

    Where the player is matters: away from a store the hint says where to go, at its door it says
    to go in, and inside it names the key to press. Route steps are shown only for routes the player
    has not completed yet (sold at least once, from the saved total_sold).
    """
    def place(role, trade):
        return next(site.name for site in OPEN_SITES if site.role == role and site.trade == trade)

    def named(name):
        return next((site for site in OPEN_SITES if site.name == name), None)

    door = None if inside else building_at(town)  # Standing at a door, still outside
    room = named(inside) if inside else None      # The building the player is inside
    if inside == MONASTERY:
        return {"text": BUILDING_HINTS[MONASTERY], "target": None}
    if room and room.role in BUILDING_HINTS:
        return {"text": BUILDING_HINTS[room.role], "target": None}
    if room and room.role == "FACTORY":
        trade = town.business_site(room).trade
        if town.orders[trade] is not None:
            return {"text": f"Press E to collect your {TRADES[trade].product}.", "target": room.name}
    learned = [bool(sold) for sold in town.total_sold]
    new = [index for index in range(len(TRADES)) if not learned[index]]

    def step(target, key_text, go_text):
        if inside == target:
            return {"text": key_text, "target": target}
        if door == target:
            return {"text": f"Press E to go into {target}.", "target": target}
        return {"text": go_text, "target": target}

    # 0. A full bag blocks buying on every route, learned or not: say how to make room.
    if bag_full(town):
        used = f"({town.cargo + town.reserved}/{town.carry_capacity})"
        for index, trade in enumerate(TRADES):
            if town.goods[index]:
                market = place("PUBLIC SHOP", index)
                return step(market, f"Press E to sell your {trade.product}.",
                            f"Your bag is full {used}. Sell your {town.goods[index]} {trade.product} at {market}.")
        for index, trade in enumerate(TRADES):
            order = town.orders[index]
            if order is not None and town.elapsed >= order.ready_at:
                factory = place("FACTORY", index)
                return step(factory, f"Press E to collect your {trade.product}.",
                            f"Your bag is full {used}. Collect your {trade.product} at {factory}, then sell it.")
        for index, trade in enumerate(TRADES):
            if town.supplies[index]:
                factory = place("FACTORY", index)
                order = town.orders[index]
                if order is not None:  # The workshop is still busy with this product
                    return step(factory, f"Press E to collect your {trade.product}.",
                                f"Your bag is full {used}. Collect your {trade.product} at {factory}, "
                                f"then drop off your {trade.supply}.")
                return step(factory, f"Press E to drop off your {trade.supply} and make {trade.product}.",
                            f"Your bag is full {used}. Take your {trade.supply} to {factory} to make {trade.product}.")
        for index, trade in enumerate(TRADES):
            order = town.orders[index]
            if order is not None:
                factory = place("FACTORY", index)
                return step(factory, f"Press E to collect your {trade.product}.",
                            f"Your bag is full {used}. Collect your {trade.product} at {factory}, then sell it.")

    # 1. Steps on a route the player has started but not completed yet.
    for index in new:  # Finished products first
        if town.goods[index]:
            trade, market = TRADES[index], place("PUBLIC SHOP", index)
            return step(market, f"Press E to sell your {trade.product}.",
                        f"Sell your {town.goods[index]} {trade.product} at {market}.")
    for index in new:  # Then batches ready to collect
        order = town.orders[index]
        if order is not None and town.elapsed >= order.ready_at:
            trade, factory = TRADES[index], place("FACTORY", index)
            return step(factory, f"Press E to collect your {trade.product}.",
                        f"Collect your {trade.product} at {factory}.")
    for index in new:  # Then materials to process
        if town.supplies[index]:
            trade, factory = TRADES[index], place("FACTORY", index)
            return step(factory, f"Press E to drop off your {trade.supply} and make {trade.product}.",
                        f"Now go to {factory} to turn your {trade.supply} into {trade.product}.")
    for index in new:  # Then batches still being made
        order = town.orders[index]
        if order is not None:
            trade, factory = TRADES[index], place("FACTORY", index)
            return step(factory, f"Press E to collect your {trade.product}.",
                        f"Collect your {trade.product} at {factory}.")

    # 2. The first route: the bread route the Basics teach.
    if not any(learned):
        supplier = place("SUPPLIER", 3)
        return step(supplier, "Press Q to buy up to 4 Wheat (E buys one).",
                    f"Go to {supplier} and buy Wheat (${town.costs[3]} each).")

    # 3. A store on a route the player hasn't done yet: explain it, even while busy with a known route.
    here = room or named(door)
    if here and here.role in ("SUPPLIER", "FACTORY", "PUBLIC SHOP") and here.trade in new:
        trade = TRADES[here.trade]
        supplier = place("SUPPLIER", here.trade)
        if here.role == "SUPPLIER":
            return step(here.name, f"Press Q to buy up to 4 {trade.supply} (${town.costs[here.trade]} each).",
                        here.name)
        what = "makes" if here.role == "FACTORY" else "buys"
        detail = (f"{trade.product} from {trade.supply}" if here.role == "FACTORY"
                  else f"{trade.product} for ${town.prices[here.trade]} each")
        return {"text": f"{here.name} {what} {detail}. Start by buying {trade.supply} at {supplier}.",
                "target": supplier}

    # 4. Working a route the player already knows: no need to explain it again.
    if any(town.supplies[i] or town.goods[i] or town.orders[i] is not None for i in range(len(TRADES))):
        return None
    # 5. Hands empty with routes left to try: invite the player to explore.
    if new:
        return {"text": "Nice work! Now explore the other buildings: each coloured sign is a new way to earn.",
                "target": None}
    return None  # Every route learned: no more hints needed


def scene_for(town, site):
    """(image name, layout) for a building, or None when it has no illustrated scene."""
    if site == MONASTERY:
        return "monastery", SCENES["monastery"]
    if site.role in INTERIOR_ROLES:
        trade = town.business_site(site).trade if site.role in ("FACTORY", "PUBLIC SHOP") else max(site.trade, 0)
        return f"{site.role.replace(' ', '_').lower()}_{trade}", SCENES["interior"]
    if site.role in ("GARAGE", "CASINO"):
        return site.role.lower(), SCENES[site.role.lower()]
    if site.role == "WAREHOUSE":
        return "warehouse", SCENES["interior"]
    return None


def greeting(town, site):
    """What the person behind the counter says when you walk in, as in the desktop game."""
    if site == MONASTERY:
        return "Peace be with you. Each visit adds 5 percentage points of casino luck, up to 20."
    role = site.role
    if role == "SUPPLIER":
        trade = TRADES[site.trade]
        opener = ("Freshly mined", "Cut this morning", "Dug from the pit today", "Harvested at dawn")[site.trade]
        return f"{opener}! {trade.supply} for ${town.costs[site.trade]} each."
    if role == "PUBLIC SHOP":
        trade = town.business_site(site).trade
        if businesses.is_owned(town, site):
            return f"Welcome back, boss! Shall I put your {TRADES[trade].product} on the shelves?"
        return f"I buy your {TRADES[trade].product} for ${town.prices[trade]} each!"
    if role == "FACTORY":
        trade = TRADES[town.business_site(site).trade]
        return f"Bring me {trade.supply} and I'll turn it into {trade.product}."
    if role == "PASTELARIA":
        return "Pastéis de nata, fresh from the oven! 1 Wheat + 1 Egg makes one."
    if role == "SHIPYARD":
        return "This boat won't fix itself! Bring 2 Timber + 2 Iron ore and the job is yours."
    if role == "TIER2":
        return "Precision work only! 1 Tools + 1 Furniture makes one Precision Machinery."
    if role == "GARAGE":
        ride = VEHICLES.get(town.vehicle)
        if ride is None:
            if town.owned_vehicles:
                return "Welcome back! Your owned vehicles are ready to collect for free. Pick a ride."
            return "Tired of walking? The bridges are for vehicles only. Pick a ride and I'll hand you the keys!"
        return f"How's the {ride.label.lower()} running? Trade up for a bigger trunk any time."
    if role == "CASINO":
        return "Welcome to the casino. Pick a chip, then bet on a colour."
    if role == "WAREHOUSE":
        return f"Need more room? Each expansion adds 12 slots for ${300 + town.warehouse_level * 250:,}."
    return f"Welcome to {site.name}."


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


def place_vehicle_on_road(town):
    """Return an active vehicle to the road when leaving a building or loading an old save."""
    if not town.vehicle or town.can_walk(town.x, town.y, roads_only=True):
        return
    x, y = town.x, town.y

    def same_bank(py):
        if y < scene.RIVER_TOP:
            return py < scene.RIVER_TOP
        if y >= RIVER_BOTTOM:
            return py >= RIVER_BOTTOM
        return scene.RIVER_TOP <= py < RIVER_BOTTOM

    closest = None
    for segment in ROAD_SEGMENTS:
        px, py = road_projection(x, y, segment)
        if same_bank(py) and town.can_walk(px, py, roads_only=True):
            distance = math.hypot(x - px, y - py)
            if closest is None or distance < closest[0]:
                closest = distance, px, py
    if closest is not None:
        _, town.x, town.y = closest


def toggle_vehicle(town):
    if town.vehicle:
        town.leave_vehicle()
    elif town.stowed_vehicle:
        if not on_road(town.x, town.y) or scene.vehicle_park_blocked(town.x, town.y, PLAYER_RADIUS) or not scene.walkable_terrain(
            town.x, town.y, PLAYER_RADIUS
        ):
            town.message = "Move to a street before bringing your vehicle back."
        else:
            if town.stowed_vehicle not in town.owned_vehicles:
                town.owned_vehicles.append(town.stowed_vehicle)
            town.vehicle, town.stowed_vehicle = town.stowed_vehicle, None
            town.message = "You’re back in your vehicle."


def street_input(town, event):
    """Apply a small, validated movement batch using the desktop collision rules."""
    if not isinstance(event, dict):
        return False
    action = event.get("action")
    segments = event.get("segments", [event])
    if (not isinstance(segments, list) or not 1 <= len(segments) <= 120
            or action not in (None, "interact", "bulk", "egg", "eggs", "dismount", "vehicle")):
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
    place_vehicle_on_road(town)
    for segment in segments:
        dx, dy, seconds = (segment[key] for key in ("dx", "dy", "seconds"))
        steps = max(1, math.ceil(seconds * 60))
        for _ in range(steps):
            if dx or dy:
                town.move(dx, dy, seconds / steps, roads_only=True)
            if seconds:
                advance_clock(town, seconds / steps)
    if action == "dismount":
        town.leave_vehicle()
    elif action == "interact" and nearby_pier(town.x, town.y):
        ride_ferry(town)
    elif action in ("interact", "bulk"):
        if action == "bulk" and (town.nearby() is None or town.nearby().role != "SUPPLIER"):
            town.message = "Walk up to a supplier to buy materials in bulk."
        else:
            town.interact(bulk=action == "bulk")
    elif action in ("egg", "eggs"):
        town.buy_eggs(bulk=action == "eggs")
    elif action == "vehicle":
        toggle_vehicle(town)
    return True


def street_event(town, event):
    """Apply one map event. E at a building's door walks there and returns the building to open
    (trading happens inside); every other event is applied by street_input as usual."""
    if isinstance(event, dict) and event.get("action") == "interact":
        moved = street_input(town, {**event, "action": None})
        name = building_at(town) if moved else None
        if name:
            if name == MONASTERY:
                town.visit_monastery()
            return name
        if not moved:
            return None
        if town.nearby() and town.nearby().name in CLOSED_SITES:
            town.message = "These are apartments. Follow a coloured shop sign to trade."
            return None
        event = {"segments": [{"dx": 0, "dy": 0, "seconds": 0}], "action": "interact"}
    street_input(town, event)
    return None


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
