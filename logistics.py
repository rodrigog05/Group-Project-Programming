"""Paid, active-play supply routes and autonomous factory production.

Fleet cargo and factory stores are separate from the player's carried bag.
Every paid load, its exact travel clock and every factory order are saved as
ordinary JSON. No wall-clock or offline catch-up runs in this module.
"""
from dataclasses import dataclass
import math
from types import SimpleNamespace

import businesses
from exchange import record_bridge
from logistics_paths import bridge_used, path_length, point_on_path, road_path


SCHEMA_VERSION = 1
MAX_ROUTES = 8
BUFFER_LIMIT = 48
OUTPUT_LIMIT = 48
FACTORY_BATCH = 6
RETRY_SECONDS = 2.0
BRIDGE_TOLL = 3
EPSILON = 1e-8
RECIPE_KEYS = ("tools", "furniture", "pottery", "bread")


@dataclass(frozen=True)
class FleetVehicle:
    label: str
    price: int
    capacity: int
    speed: int
    running_cost: int


FLEET_VEHICLES = {
    "van": FleetVehicle("Delivery van", 320, 6, 300, 1),
    "drone": FleetVehicle("Cargo drone", 600, 3, 520, 2),
}


def _whole(value, default=0):
    return value if type(value) is int and value >= 0 else default


def _finite(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _factory(site):
    return {"trade": site.trade, "input": 0, "order": None, "output": 0,
            "produced": 0, "collected": 0}


def initial_state(sites=()):
    return {"version": SCHEMA_VERSION, "next_id": 1, "routes": [],
            "factories": {site.name: _factory(site) for site in sites if site.role == "FACTORY"}}


def _site_map(sites):
    return {site.name: site for site in sites}


def _pair(source, destination, sites, trades=None, town=None, businesses_state=None,
          physical_only=False):
    if not isinstance(source, str) or not isinstance(destination, str):
        return None
    table = sites if isinstance(sites, dict) else _site_map(sites)
    first, last = table.get(source), table.get(destination)
    if (first is None or last is None or first.role != "SUPPLIER" or last.role != "FACTORY"
            or type(first.trade) is not int or not 0 <= first.trade < len(RECIPE_KEYS)
            or trades is not None and first.trade >= len(trades)):
        return None
    selected = businesses.trade_for(town, last) if town is not None else businesses.trade_for_state(businesses_state, last)
    if not physical_only and first.trade != selected:
        return None
    return first, last


def _entrance(site):
    x, y = site.door
    return x, y+18


def route_path(route, sites):
    table = sites if isinstance(sites, dict) else _site_map(sites)
    pair = _pair(route.get("source"), route.get("destination"), table, physical_only=True)
    if pair is None:
        return ((0, 0),)
    first, last = (_entrance(site) for site in pair)
    return road_path(first, last) if route.get("kind") == "van" else (first, last)


def _duration(kind, pair):
    first, last = (_entrance(site) for site in pair)
    path = road_path(first, last) if kind == "van" else (first, last)
    return max(.1, path_length(path)/FLEET_VEHICLES[kind].speed)


def normalize_state(value, sites, businesses_state=None):
    """Restore valid paid cargo without buying again or granting elapsed time."""
    sites = tuple(sites)
    result, table = initial_state(sites), _site_map(sites)
    owner = SimpleNamespace(businesses=businesses_state)
    for name, factory in result["factories"].items():
        factory["trade"] = businesses.trade_for_state(businesses_state, table[name])
    if (not isinstance(value, dict) or type(value.get("version", SCHEMA_VERSION)) is not int
            or value.get("version", SCHEMA_VERSION) != SCHEMA_VERSION):
        return result
    stored_factories = value.get("factories", {})
    if isinstance(stored_factories, dict):
        for name, factory in result["factories"].items():
            capacity = businesses.capacity_for_state(businesses_state, table[name])
            saved = stored_factories.get(name)
            if not isinstance(saved, dict):
                continue
            for field, limit in (("input", capacity), ("output", capacity)):
                factory[field] = min(limit, _whole(saved.get(field)))
            for field in ("produced", "collected"):
                factory[field] = _whole(saved.get(field))
            order = saved.get("order")
            if isinstance(order, dict):
                quantity, remaining = order.get("quantity"), order.get("remaining")
                if (type(quantity) is int and 0 < quantity <= businesses.batch_size(owner, table[name])
                        and quantity+factory["output"] <= capacity
                        and _finite(remaining) and remaining >= 0):
                    factory["order"] = {"quantity": quantity, "remaining": float(remaining)}
    routes = value.get("routes", ())
    if not isinstance(routes, list):
        routes = ()
    used = set()
    for saved in routes:
        if not isinstance(saved, dict) or len(result["routes"]) >= MAX_ROUTES:
            continue
        identifier, kind = saved.get("id"), saved.get("kind")
        if (type(identifier) is not int or identifier < 1 or identifier in used
                or not isinstance(kind, str) or kind not in FLEET_VEHICLES):
            continue
        pair = _pair(saved.get("source"), saved.get("destination"), table,
                     businesses_state=businesses_state)
        phase, elapsed = saved.get("phase"), saved.get("elapsed", 0)
        if pair is None or phase not in ("idle", "outbound", "returning") or not _finite(elapsed):
            continue
        duration = _duration(kind, pair)
        load = _whole(saved.get("load"))
        if load > FLEET_VEHICLES[kind].capacity or (phase != "outbound" and load):
            continue
        if phase == "outbound" and not load:
            continue
        route = {"id": identifier, "kind": kind, "source": pair[0].name,
                 "destination": pair[1].name, "trade": pair[0].trade,
                 "enabled": saved.get("enabled") if type(saved.get("enabled")) is bool else False,
                 "phase": phase, "elapsed": min(duration, max(0, elapsed)) if phase != "idle" else 0.0,
                 "duration": duration, "load": load,
                 "retry": min(RETRY_SECONDS, max(0, saved.get("retry", 0)))
                    if _finite(saved.get("retry", 0)) else 0.0,
                 "status": saved.get("status") if isinstance(saved.get("status"), str) else "Ready at depot"}
        for field in ("delivered", "trips", "materials_spent", "running_spent", "tolls_spent"):
            route[field] = _whole(saved.get(field))
        result["routes"].append(route)
        used.add(identifier)
    result["next_id"] = max(_whole(value.get("next_id"), 1), max(used, default=0)+1, 1)
    return result


def _state(town, sites=()):
    state = getattr(town, "logistics", None)
    if (not isinstance(state, dict) or state.get("version") != SCHEMA_VERSION
            or not isinstance(state.get("routes"), list) or not isinstance(state.get("factories"), dict)):
        state = town.logistics = normalize_state(state, sites, getattr(town, "businesses", None))
    if sites:
        for site in sites:
            if site.role == "FACTORY" and site.name not in state["factories"]:
                state["factories"][site.name] = _factory(site)
            if site.role == "FACTORY":
                factory = state["factories"][site.name]
                if not factory["input"] and not factory["order"] and not factory["output"]:
                    factory["trade"] = businesses.trade_for(town, site)
    return state


def create_route(town, kind, source, destination, sites, trades):
    if not isinstance(kind, str) or kind not in FLEET_VEHICLES:
        town.message = "Choose a delivery van or cargo drone."
        return False
    pair = _pair(source, destination, sites, trades, town=town)
    if pair is None:
        town.message = "Choose a raw-material depot and a factory that uses the same material."
        return False
    state, vehicle = _state(town, sites), FLEET_VEHICLES[kind]
    if len(state["routes"]) >= MAX_ROUTES:
        town.message = f"Your fleet already has the maximum {MAX_ROUTES} routes."
        return False
    if town.cash < vehicle.price:
        town.message = f"You need ${vehicle.price:,} to buy this fleet {vehicle.label.lower()}."
        return False
    route = {"id": state["next_id"], "kind": kind, "source": source, "destination": destination,
             "trade": pair[0].trade, "enabled": True, "phase": "idle", "elapsed": 0.0,
             "duration": _duration(kind, pair), "load": 0, "retry": 0.0,
             "status": "Ready at depot", "delivered": 0, "trips": 0,
             "materials_spent": 0, "running_spent": 0, "tolls_spent": 0}
    town.cash -= vehicle.price
    town.other_expenses_today += vehicle.price
    state["routes"].append(route)
    state["next_id"] += 1
    town.message = f"Bought fleet {vehicle.label.lower()} · {source} → {destination}. Automatic supply is enabled."
    return True


def _route(town, identifier):
    return next((route for route in _state(town)["routes"]
                 if type(identifier) is int and route["id"] == identifier), None)


def set_route_enabled(town, identifier, enabled):
    route = _route(town, identifier)
    if route is None or type(enabled) is not bool:
        town.message = "Choose an existing delivery route."
        return False
    route["enabled"], route["retry"] = enabled, 0.0
    if route["phase"] == "idle":
        route["status"] = "Ready at depot" if enabled else "Paused at depot"
    town.message = ("Route resumed. New deliveries will run automatically." if enabled else
                    "Route paused. Its paid delivery and return will finish before parking.")
    return True


def remove_route(town, identifier):
    route = _route(town, identifier)
    if route is None:
        town.message = "Choose an existing delivery route."
        return False
    if route["phase"] != "idle":
        town.message = "Pause this route and wait for its vehicle to return empty before removing it."
        return False
    _state(town)["routes"].remove(route)
    town.message = "Delivery route retired. Factory materials and goods remain available; used fleet purchases are not refunded."
    return True


def reassign_route(town, identifier, source, destination, sites, trades):
    """Redeploy an existing empty fleet vehicle without paying for it again."""
    route = _route(town, identifier)
    if route is None:
        town.message = "Choose an existing delivery route to reassign."
        return False
    if route["phase"] != "idle" or route["load"]:
        town.message = "Pause the route and wait for its empty vehicle to return before reassigning it."
        return False
    pair = _pair(source, destination, sites, trades, town=town)
    if pair is None:
        town.message = "Choose a raw-material depot and a factory currently specialized in that material."
        return False
    _state(town, sites)
    route.update(source=source, destination=destination, trade=pair[0].trade,
                 duration=_duration(route["kind"], pair), elapsed=0.0, retry=0.0,
                 status="Ready at new depot" if route["enabled"] else "Paused at new depot")
    town.message = "Empty fleet vehicle reassigned at no purchase cost. Its operating history is preserved."
    return True


def route_status(route):
    if route["phase"] == "outbound":
        return f"Delivering {route['load']} · {math.ceil(max(0, route['duration']-route['elapsed']))}s"
    if route["phase"] == "returning":
        return f"Returning empty · {math.ceil(max(0, route['duration']-route['elapsed']))}s"
    return route["status"] if route["enabled"] else "Paused at depot"


def route_position(route, sites):
    points = route_path(route, sites)
    if route.get("phase") == "idle":
        return points[0]
    duration = route.get("duration", 0)
    fraction = route.get("elapsed", 0)/duration if duration > 0 else 0
    if route.get("phase") == "returning":
        fraction = 1-fraction
    return point_on_path(points, fraction)


def _charge_northbound_toll(town, route, table, phase):
    if route["kind"] != "van":
        return
    source, destination = table[route["source"]], table[route["destination"]]
    first, last = (source, destination) if phase == "outbound" else (destination, source)
    if first.y < 718 or last.y >= 718:
        return
    town.cash -= BRIDGE_TOLL
    town.tolls_today += BRIDGE_TOLL
    town.toll_count_today += 1
    town.tolls_paid_total += BRIDGE_TOLL
    route["tolls_spent"] += BRIDGE_TOLL
    record_bridge(town, bridge_used(route_path(route, table)))


def _dispatch(town, state, route, table):
    vehicle, factory = FLEET_VEHICLES[route["kind"]], state["factories"][route["destination"]]
    site = table[route["destination"]]
    if route["trade"] != businesses.trade_for(town, site) or route["trade"] != factory["trade"]:
        route["retry"], route["status"] = RETRY_SECONDS, "Waiting: factory specialization changed; reassign this route"
        return
    capacity = businesses.storage_capacity(town, site)
    incoming = sum(item["load"] for item in state["routes"]
                   if item["phase"] == "outbound" and item["destination"] == route["destination"])
    space = max(0, capacity-factory["input"]-incoming)
    in_production = factory["order"]["quantity"] if factory["order"] else 0
    if not space or factory["output"]+in_production >= capacity:
        route["retry"], route["status"] = RETRY_SECONDS, "Waiting: factory storage full"
        return
    unit_cost = max(1, _whole(town.costs[route["trade"]], 1))
    quantity = min(vehicle.capacity, space, max(0, (town.cash-vehicle.running_cost)//unit_cost))
    if not quantity:
        route["retry"], route["status"] = RETRY_SECONDS, "Waiting: insufficient operating cash"
        return
    materials = quantity*unit_cost
    town.cash -= materials+vehicle.running_cost
    town.expenses_today[route["trade"]] += materials
    town.other_expenses_today += vehicle.running_cost
    route["materials_spent"] += materials
    route["running_spent"] += vehicle.running_cost
    route.update(phase="outbound", elapsed=0.0, load=quantity, retry=0.0, status="Delivering materials")


def _events(town, state, table, trades):
    discoveries = []
    for name, factory in state["factories"].items():
        order = factory["order"]
        if order is not None and order["remaining"] <= EPSILON:
            factory["output"] += order["quantity"]
            factory["produced"] += order["quantity"]
            factory["order"] = None
            discoveries.append(RECIPE_KEYS[factory["trade"]])
    for route in state["routes"]:
        phase = route["phase"]
        if phase == "idle" or route["elapsed"]+EPSILON < route["duration"]:
            continue
        _charge_northbound_toll(town, route, table, phase)
        route["elapsed"] = 0.0
        if phase == "outbound":
            factory = state["factories"][route["destination"]]
            factory["input"] += route["load"]
            route["delivered"] += route["load"]
            route["trips"] += 1
            route.update(phase="returning", load=0, status="Returning empty")
        else:
            route.update(phase="idle", retry=RETRY_SECONDS, status="Loading at depot" if route["enabled"] else "Paused at depot")
    for name, factory in state["factories"].items():
        site = table[name]
        capacity = businesses.storage_capacity(town, site)
        if factory["order"] is None and factory["input"] and factory["output"] < capacity:
            quantity = min(businesses.batch_size(town, site), factory["input"], capacity-factory["output"])
            factory["input"] -= quantity
            factory["order"] = {"quantity": quantity, "remaining": businesses.production_seconds(town, site, trades[factory["trade"]].seconds)}
    for route in state["routes"]:
        if route["phase"] == "idle" and route["enabled"] and route["retry"] <= EPSILON:
            _dispatch(town, state, route, table)
    return discoveries


def advance_logistics(town, seconds, sites, trades):
    """Advance only the active seconds supplied by the focused game loop.

    Event boundaries preserve exact travel/production time, whether a caller
    advances a full trip in one test step or supplies individual render frames.
    Existing paid trips finish while a route is disabled; no new load departs.
    """
    if not _finite(seconds) or seconds <= 0:
        return ()
    state = _state(town, sites)
    if not state["routes"] and not any(factory["input"] or factory["order"] for factory in state["factories"].values()):
        return ()
    table, remaining, discoveries = _site_map(sites), seconds, []
    while True:
        discoveries.extend(_events(town, state, table, trades))
        if remaining <= EPSILON:
            break
        boundaries = [remaining]
        for route in state["routes"]:
            if route["phase"] != "idle":
                boundaries.append(max(EPSILON, route["duration"]-route["elapsed"]))
            elif route["enabled"] and route["retry"] > EPSILON:
                boundaries.append(route["retry"])
        boundaries.extend(factory["order"]["remaining"] for factory in state["factories"].values()
                          if factory["order"] is not None)
        step = min(boundaries)
        for route in state["routes"]:
            if route["phase"] != "idle":
                route["elapsed"] = min(route["duration"], route["elapsed"]+step)
            elif route["enabled"]:
                route["retry"] = max(0.0, route["retry"]-step)
        for factory in state["factories"].values():
            if factory["order"] is not None:
                factory["order"]["remaining"] = max(0.0, factory["order"]["remaining"]-step)
        remaining -= step
    return tuple(dict.fromkeys(discoveries))


def collect_output(town, factory_name, quantity=None):
    if quantity is not None and (type(quantity) is not int or quantity <= 0):
        town.message = "Choose a positive whole collection quantity."
        return 0
    factory = _state(town)["factories"].get(factory_name)
    if factory is None:
        town.message = "Choose a production factory."
        return 0
    space = max(0, town.carry_capacity-town.cargo-town.reserved)
    collected = min(factory["output"], space, factory["output"] if quantity is None else quantity)
    if not collected:
        town.message = "Free bag space before collecting factory stock." if not space else "No automated goods are ready to collect."
        return 0
    factory["output"] -= collected
    factory["collected"] += collected
    town.goods[factory["trade"]] += collected
    town.message = f"Collected {collected} automated goods from {factory_name}. Take them to the matching market."
    return collected
