"""Saved, active-play supply contracts and one-time Lisbon city projects.

Only carried products may be handed over, at the named collection point.
Deposits are final. Cash and reputation are awarded once, on full completion;
market buyer pools and automatic factory stores are deliberately independent.
"""
from dataclasses import dataclass
import math


SCHEMA_VERSION = 1
CYCLE_SECONDS = 300
ACTIVE_LIMIT = MAX_ACTIVE = 3
DELIVERY_REACH = 45
HISTORY_LIMIT = 40


@dataclass(frozen=True)
class Location:
    key: str
    name: str
    x: int
    y: int


@dataclass(frozen=True)
class Offer:
    key: str
    title: str
    kind: str
    product_key: str
    quantity: int
    seconds: int
    cash: int
    reputation: int
    description: str
    location: Location
    upgrade: str = None
    minimum_reputation: int = 0
    recipe_requirement: str = None


SQUARE = Location("square", "Praça do Comércio collection desk", 596, 650)
BRIDGE = Location("bridge", "Ponte 25 de Abril north works desk", 300, 700)
HOTEL = Location("hotel", "Hotel supply desk · Home Market", 1628, 467)
CAMPUS = Location("campus", "Nova SBE campus collection desk", 116, 652)
LOCATIONS = (SQUARE, BRIDGE, HOTEL, CAMPUS)
PRODUCT_NAMES = {"tools": "Tools", "furniture": "Furniture", "pottery": "Pottery",
                 "bread": "Bread", "pasteis": "Pastéis", "precision_machinery": "Precision Machinery"}
PRODUCT_ROUTES = {"tools": 0, "furniture": 1, "pottery": 2, "bread": 3}
UPGRADE_NAMES = {"cargo_expansion": "Festival cargo expansion",
                 "express_roads": "Express road permit",
                 "research_grant": "Nova SBE research grant"}
UPGRADE_DESCRIPTIONS = {
    "cargo_expansion": "+4 permanent personal cargo slots.",
    "express_roads": "+10% movement speed on paved roads, walking or driving.",
    "research_grant": "10% off future research payments; paid projects keep their existing cost.",
}
REPUTATION_RANKS = ((0, "Citizen"), (50, "Trusted Supplier"),
                    (150, "City Partner"), (300, "Lisbon Benefactor"))

PROJECTS = (
    Offer("festival_project", "Pastéis for the Lisbon Festival", "project", "pasteis", 40, 600,
          1400, 30, "Supply the festival's pastry stalls. Deliver in several trips before the deadline.",
          SQUARE, "cargo_expansion"),
    Offer("bridge_project", "Ponte 25 de Abril Maintenance", "project", "tools", 18, 360,
          450, 20, "Equip the north-bank maintenance crew with eighteen finished Tools.",
          BRIDGE, "express_roads"),
    Offer("hotel_project", "Riverside Hotel Fit-out", "project", "furniture", 16, 480,
          650, 25, "Furnish a new hotel through its Home Market supply desk. The client funds a research grant.",
          HOTEL, "research_grant"),
)
REGULAR_OFFERS = (
    Offer("bread_relief", "Bread for the Community Kitchen", "contract", "bread", 16, 180,
          320, 8, "Supply fresh bread to the waterfront community kitchen.", SQUARE),
    Offer("tools_workshop", "Tools for the Waterfront Crew", "contract", "tools", 12, 240,
          300, 8, "Deliver a replacement tool shipment to the bridge works desk.", BRIDGE),
    Offer("guesthouse_furniture", "Guesthouse Furniture Order", "contract", "furniture", 8, 300,
          280, 8, "Bring finished Furniture to the hotel supply desk.", HOTEL),
    Offer("gallery_pottery", "Pottery for the Riverside Gallery", "contract", "pottery", 12, 300,
          360, 10, "Provide a pottery collection for a temporary riverside exhibition.", SQUARE),
    Offer("tour_group_pasteis", "Pastéis for a Tour Group", "contract", "pasteis", 20, 360,
          650, 12, "A visiting tour group has booked a pastry reception at the square.", SQUARE),
    Offer("campus_machinery", "Nova SBE Equipment Order", "contract", "precision_machinery", 4, 420,
          440, 12, "Trusted suppliers may deliver Precision Machinery for the campus workshop.", CAMPUS,
          minimum_reputation=50, recipe_requirement="precision_machinery"),
)
CATALOG = PROJECTS + REGULAR_OFFERS
OFFER_BY_KEY = {offer.key: offer for offer in CATALOG}
PROJECT_BY_UPGRADE = {offer.upgrade: offer.key for offer in PROJECTS}


def initial_state():
    return {"version": SCHEMA_VERSION, "elapsed": 0.0, "next_id": 1,
            "reputation": 0, "active": [], "history": [], "taken": [],
            "completed_projects": [], "upgrades": [], "completed": 0, "failed": 0,
            "abandoned": 0, "cash_earned": 0, "revenue_today": 0,
            "delivered": {key: 0 for key in PRODUCT_NAMES}}


def _whole(value, default=0):
    return value if type(value) is int and value >= 0 else default


def _finite(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _clock(value):
    return float(value) if _finite(value) and 0 <= value <= 1e12 else 0.0


def _cycle(state):
    return int(state["elapsed"] // CYCLE_SECONDS)


def _token(cycle, key):
    return f"{cycle}:{key}"


def normalize_state(value):
    """Restore deposits, deadlines and claims without paying or applying upgrades.

    Either a completed-project marker or its saved upgrade prevents the same
    unique project being claimed again. Cargo capacity already belongs to Town;
    loading this ledger never adds it a second time.
    """
    result = initial_state()
    if (not isinstance(value, dict) or type(value.get("version", SCHEMA_VERSION)) is not int
            or value.get("version", SCHEMA_VERSION) != SCHEMA_VERSION):
        return result
    result["elapsed"] = _clock(value.get("elapsed", 0))
    for key in ("reputation", "completed", "failed", "abandoned", "cash_earned", "revenue_today"):
        result[key] = _whole(value.get(key))
    delivered = value.get("delivered")
    if isinstance(delivered, dict):
        result["delivered"] = {key: _whole(delivered.get(key)) for key in PRODUCT_NAMES}
    project_keys = {offer.key for offer in PROJECTS}
    completed = value.get("completed_projects", [])
    completed = {key for key in completed if isinstance(key, str) and key in project_keys} if isinstance(completed, list) else set()
    upgrades = value.get("upgrades", [])
    upgrades = {key for key in upgrades if isinstance(key, str) and key in UPGRADE_NAMES} if isinstance(upgrades, list) else set()
    history, closed_ids = value.get("history", []), set()
    if isinstance(history, list):
        for record in history[-HISTORY_LIMIT:]:
            if not isinstance(record, dict):
                continue
            identifier, key, status = record.get("id"), record.get("key"), record.get("status")
            offer = OFFER_BY_KEY.get(key) if isinstance(key, str) else None
            if (type(identifier) is not int or identifier < 1 or identifier in closed_ids or offer is None
                    or status not in ("completed", "failed", "abandoned")):
                continue
            required = _whole(record.get("required"), offer.quantity)
            if not required:
                continue
            amount = min(required, _whole(record.get("delivered")))
            result["history"].append({"id": identifier, "key": key, "status": status,
                "required": required, "delivered": amount,
                "cash": _whole(record.get("cash")) if status == "completed" else 0,
                "reputation": _whole(record.get("reputation")) if status == "completed" else 0,
                "ended_at": _clock(record.get("ended_at", result["elapsed"]))})
            closed_ids.add(identifier)
            if status == "completed" and offer.kind == "project":
                completed.add(key)
    completed.update(PROJECT_BY_UPGRADE[key] for key in upgrades)
    upgrades.update(offer.upgrade for offer in PROJECTS if offer.key in completed)
    result["completed_projects"] = [offer.key for offer in PROJECTS if offer.key in completed]
    result["upgrades"] = [offer.upgrade for offer in PROJECTS if offer.upgrade in upgrades]
    current, tokens = _cycle(result), value.get("taken", [])
    if isinstance(tokens, list):
        for token in tokens:
            if not isinstance(token, str) or len(token) > 80 or ":" not in token:
                continue
            cycle_text, key = token.split(":", 1)
            if not cycle_text.isascii() or not cycle_text.isdecimal() or key not in OFFER_BY_KEY:
                continue
            cycle = int(cycle_text)
            if max(0, current-2) <= cycle <= current:
                canonical = _token(cycle, key)
                if canonical not in result["taken"]:
                    result["taken"].append(canonical)
    active, used_ids, used_keys = value.get("active", []), set(closed_ids), set()
    if isinstance(active, list):
        for record in active:
            if len(result["active"]) >= ACTIVE_LIMIT:
                break
            if not isinstance(record, dict):
                continue
            identifier, key = record.get("id"), record.get("key")
            offer = OFFER_BY_KEY.get(key) if isinstance(key, str) else None
            required, amount, deadline = record.get("required"), record.get("delivered"), record.get("deadline")
            if (type(identifier) is not int or identifier < 1 or identifier in used_ids or offer is None
                    or key in used_keys or key in completed or type(required) is not int or required <= 0
                    or type(amount) is not int or not 0 <= amount < required or not _finite(deadline)
                    or not 0 <= deadline <= result["elapsed"]+offer.seconds):
                continue
            cash, reputation, upgrade = record.get("cash"), record.get("reputation"), record.get("upgrade")
            if type(cash) is not int or cash < 0 or type(reputation) is not int or reputation < 0 or upgrade != offer.upgrade:
                continue
            result["active"].append({"id": identifier, "key": key, "required": required,
                "delivered": amount, "deadline": float(deadline), "cash": cash,
                "reputation": reputation, "upgrade": upgrade})
            used_ids.add(identifier)
            used_keys.add(key)
    result["next_id"] = max(1, _whole(value.get("next_id"), 1), max(used_ids, default=0)+1)
    return result


def _state(town):
    state = getattr(town, "contracts", None)
    if not isinstance(state, dict) or state.get("version") != SCHEMA_VERSION:
        state = town.contracts = initial_state()
    return state


def active_offer(record):
    return OFFER_BY_KEY.get(record.get("key")) if isinstance(record, dict) else None


def rank_name(town):
    reputation = _state(town)["reputation"]
    return next(name for minimum, name in reversed(REPUTATION_RANKS) if reputation >= minimum)


def remaining_seconds(town, record):
    return max(0.0, record["deadline"]-_state(town)["elapsed"])


def inventory_amount(town, product_key):
    if not isinstance(product_key, str):
        return 0
    if product_key in PRODUCT_ROUTES:
        return town.goods[PRODUCT_ROUTES[product_key]]
    if product_key == "pasteis":
        return town.industry_goods["PASTELARIA"]
    return town.tier2_goods if product_key == "precision_machinery" else 0


def near_destination(town, offer):
    return offer is not None and math.hypot(town.x-offer.location.x, town.y-offer.location.y) <= DELIVERY_REACH


def research_cost(town, base_cost):
    return max(1, (base_cost*9+9)//10) if "research_grant" in _state(town)["upgrades"] else base_cost


def road_multiplier(town):
    return 1.1 if "express_roads" in _state(town)["upgrades"] else 1.0


def available_offers(town):
    """Read the deterministic board; inspection never advances or rerolls time."""
    state, cycle = _state(town), _cycle(_state(town))
    active = {record["key"] for record in state["active"]}
    discoveries = getattr(town, "discovered_recipes", ())
    eligible = tuple(offer for offer in REGULAR_OFFERS if state["reputation"] >= offer.minimum_reputation
                     and (offer.recipe_requirement is None or offer.recipe_requirement in discoveries))
    start = cycle*3 % len(eligible)
    rotating = tuple(eligible[(start+index) % len(eligible)] for index in range(min(3, len(eligible))))
    return tuple(offer for offer in PROJECTS+rotating
                 if offer.key not in active and offer.key not in state["completed_projects"]
                 and _token(cycle, offer.key) not in state["taken"])


def _archive(state, record, status):
    state["active"].remove(record)
    state[status] += 1
    state["history"].append({"id": record["id"], "key": record["key"], "status": status,
        "required": record["required"], "delivered": record["delivered"],
        "cash": record["cash"] if status == "completed" else 0,
        "reputation": record["reputation"] if status == "completed" else 0,
        "ended_at": record["deadline"] if status == "failed" else state["elapsed"]})
    del state["history"][:-HISTORY_LIMIT]
    ended_at = record["deadline"] if status == "failed" else state["elapsed"]
    token = _token(int(ended_at // CYCLE_SECONDS), record["key"])
    if token not in state["taken"]:
        state["taken"].append(token)


def _expire(state):
    expired = []
    for record in tuple(state["active"]):
        if record["deadline"] <= state["elapsed"]:
            expired.append(dict(record))
            _archive(state, record, "failed")
    return tuple(expired)


def advance_contracts(town, focused_seconds):
    """Return expired record copies once; no offline clock or inventory is read."""
    if not _finite(focused_seconds) or focused_seconds <= 0:
        return ()
    state = _state(town)
    if state["elapsed"]+focused_seconds > 1e12:
        return ()
    previous_cycle = _cycle(state)
    state["elapsed"] += focused_seconds
    expired = _expire(state)
    if _cycle(state) != previous_cycle:
        oldest = max(0, _cycle(state)-2)
        state["taken"] = [token for token in state["taken"] if int(token.split(":", 1)[0]) >= oldest]
    if expired:
        titles = ", ".join(OFFER_BY_KEY[record["key"]].title for record in expired)
        town.message = f"Contract deadline missed: {titles}. Deposited products are not returned."
    return expired


def accept_contract(town, key):
    state = _state(town)
    _expire(state)
    offer = OFFER_BY_KEY.get(key) if isinstance(key, str) else None
    if offer is None:
        town.message = "Choose an available contract or city project."
        return False
    if len(state["active"]) >= ACTIVE_LIMIT:
        town.message = f"You can hold at most {ACTIVE_LIMIT} active contracts and projects."
        return False
    if offer not in available_offers(town):
        town.message = "This offer is unavailable. Active, completed and already taken offers cannot be accepted again."
        return False
    state["active"].append({"id": state["next_id"], "key": key, "required": offer.quantity,
        "delivered": 0, "deadline": state["elapsed"]+offer.seconds,
        "cash": offer.cash, "reputation": offer.reputation, "upgrade": offer.upgrade})
    state["next_id"] += 1
    state["taken"].append(_token(_cycle(state), key))
    town.message = f"Accepted {offer.title} · deliver {offer.quantity} {PRODUCT_NAMES[offer.product_key]} in {offer.seconds}s of active play."
    return True


def _record(town, identifier):
    if type(identifier) is not int:
        return None
    return next((record for record in _state(town)["active"] if record["id"] == identifier), None)


def _consume(town, product_key, quantity):
    if product_key in PRODUCT_ROUTES:
        town.goods[PRODUCT_ROUTES[product_key]] -= quantity
    elif product_key == "pasteis":
        town.industry_goods["PASTELARIA"] -= quantity
    else:
        town.tier2_goods -= quantity


def deliver_contract(town, identifier, quantity=None):
    state = _state(town)
    _expire(state)
    record = _record(town, identifier)
    if record is None or (quantity is not None and (type(quantity) is not int or quantity <= 0)):
        town.message = "Choose an active contract and a positive whole delivery quantity."
        return 0
    offer = active_offer(record)
    if not near_destination(town, offer):
        town.message = f"Visit {offer.location.name} to deliver this order. Use Guide to client."
        return 0
    if offer.kind == "project" and offer.key in state["completed_projects"]:
        town.message = "This city project has already been completed and rewarded."
        return 0
    remaining = record["required"]-record["delivered"]
    count = min(remaining, inventory_amount(town, offer.product_key), remaining if quantity is None else quantity)
    if count <= 0:
        town.message = f"Carry finished {PRODUCT_NAMES[offer.product_key]} to this client. Factory storage and orders must be collected first."
        return 0
    _consume(town, offer.product_key, count)
    record["delivered"] += count
    state["delivered"][offer.product_key] += count
    if record["delivered"] < record["required"]:
        town.message = f"Delivered {count} {PRODUCT_NAMES[offer.product_key]} · {record['delivered']}/{record['required']} for {offer.title}."
        return count
    _archive(state, record, "completed")
    state["reputation"] += record["reputation"]
    state["cash_earned"] += record["cash"]
    state["revenue_today"] += record["cash"]
    if offer.kind == "project":
        state["completed_projects"].append(offer.key)
        if offer.upgrade not in state["upgrades"]:
            state["upgrades"].append(offer.upgrade)
            if offer.upgrade == "cargo_expansion":
                town.bag_size += 4
    town.add_cash(record["cash"], business=True)
    town.message = f"Completed {offer.title}! Earned ${record['cash']:,} and {record['reputation']} reputation."
    if offer.upgrade:
        town.message += f" Unlocked {UPGRADE_NAMES[offer.upgrade]}."
    return count


def abandon_contract(town, identifier):
    state = _state(town)
    _expire(state)
    record = _record(town, identifier)
    if record is None:
        town.message = "Choose an active contract to abandon."
        return False
    _archive(state, record, "abandoned")
    town.message = "Contract abandoned. Deposited products are not returned. Retry eligible offers after the next board refresh."
    return True


def reset_day(town):
    """Called after the existing P&L settlement; contracts and deadlines remain."""
    _state(town)["revenue_today"] = 0
