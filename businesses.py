"""Saved ownership, factory equipment and stocked retail businesses.

Business stock lives outside the player's bag. Factories keep per-building
manual orders; automated factory buffers remain in the delivery ledger.
"""
from dataclasses import dataclass, is_dataclass, replace
import math
from types import SimpleNamespace


SCHEMA_VERSION = 1
SUPPORTED_ROLES = ("FACTORY", "PUBLIC SHOP")
PRODUCT_NAMES = ("Tools", "Furniture", "Pottery", "Bread")
MATERIAL_NAMES = ("Iron ore", "Timber", "Clay", "Wheat")
BASE_SECONDS = (5, 7, 6, 4)
PURCHASE_PRICES = {"FACTORY": 600, "PUBLIC SHOP": 450}
STORAGE_COSTS = (200, 400, 800)
EQUIPMENT_COSTS = (250, 500, 1000)
MAX_LEVEL = 3
BASE_STORAGE = 48
STORAGE_STEP = 24
RETAIL_INTERVAL = 10
PRODUCTION_PERCENT = (100, 85, 70, 55)


@dataclass(frozen=True)
class SaleEvent:
    site: object
    quantity: int
    revenue: int


def initial_state():
    return {"version": SCHEMA_VERSION, "owned": {}, "retail_elapsed": 0.0}


def _whole(value, default=0):
    return value if type(value) is int and value >= 0 else default


def _finite(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _trade(value):
    return type(value) is int and 0 <= value < len(PRODUCT_NAMES)


def _new_record(site):
    return {"role": site.role, "trade": site.trade, "storage_level": 0,
            "equipment_level": 0, "manual_order": None, "stock": 0,
            "sales_today": 0, "revenue_today": 0, "total_sold": 0,
            "total_revenue": 0, "invested": 0}


def _manual_order(order, trade):
    if isinstance(order, dict):
        quantity, ready_at = order.get("quantity"), order.get("ready_at")
        product = order.get("trade", trade)
    else:
        quantity, ready_at, product = getattr(order, "quantity", None), getattr(order, "ready_at", None), trade
    if type(quantity) is int and quantity > 0 and _finite(ready_at) and ready_at >= 0 and _trade(product):
        return {"quantity": quantity, "ready_at": float(ready_at), "trade": product}
    return None


def normalize_state(value, sites):
    """Restore owned property and paid inventory without charging or producing."""
    result = initial_state()
    if (not isinstance(value, dict) or type(value.get("version", SCHEMA_VERSION)) is not int
            or value.get("version", SCHEMA_VERSION) != SCHEMA_VERSION):
        return result
    elapsed = value.get("retail_elapsed", 0)
    if _finite(elapsed) and 0 <= elapsed < RETAIL_INTERVAL:
        result["retail_elapsed"] = float(elapsed)
    owned = value.get("owned")
    if not isinstance(owned, dict):
        return result
    for site in sites:
        saved = owned.get(site.name)
        if (site.role not in SUPPORTED_ROLES or not isinstance(saved, dict)
                or saved.get("role") != site.role):
            continue
        record = _new_record(site)
        record["trade"] = saved["trade"] if _trade(saved.get("trade")) else site.trade
        for field in ("storage_level", "equipment_level"):
            record[field] = min(MAX_LEVEL, _whole(saved.get(field)))
        for field in ("sales_today", "revenue_today", "total_sold", "total_revenue", "invested"):
            record[field] = _whole(saved.get(field))
        if site.role == "PUBLIC SHOP":
            record["stock"] = min(BASE_STORAGE+STORAGE_STEP*record["storage_level"], _whole(saved.get("stock")))
        else:
            record["manual_order"] = _manual_order(saved.get("manual_order"), record["trade"])
        result["owned"][site.name] = record
    return result


def _state(town):
    state = getattr(town, "businesses", None)
    if (not isinstance(state, dict) or type(state.get("version")) is not int
            or state.get("version") != SCHEMA_VERSION or not isinstance(state.get("owned"), dict)):
        state = town.businesses = initial_state()
    return state


def record_for(town, site):
    name = site if isinstance(site, str) else getattr(site, "name", None)
    state = getattr(town, "businesses", None)
    owned = state.get("owned", {}) if isinstance(state, dict) else {}
    return owned.get(name) if isinstance(owned, dict) and isinstance(name, str) else None


def is_owned(town, site):
    return record_for(town, site) is not None


def trade_for_state(state, site):
    owned = state.get("owned", {}) if isinstance(state, dict) else {}
    record = owned.get(site.name) if isinstance(owned, dict) else None
    return record["trade"] if isinstance(record, dict) and _trade(record.get("trade")) else site.trade


def trade_for(town, site):
    return trade_for_state(getattr(town, "businesses", None), site)


def capacity_for_state(state, site):
    owned = state.get("owned", {}) if isinstance(state, dict) else {}
    record = owned.get(site.name) if isinstance(owned, dict) else None
    level = min(MAX_LEVEL, _whole(record.get("storage_level"))) if isinstance(record, dict) else 0
    return BASE_STORAGE+STORAGE_STEP*level


def storage_capacity(town, site):
    return capacity_for_state(getattr(town, "businesses", None), site)


def _equipment(town, site):
    record = record_for(town, site)
    return min(MAX_LEVEL, _whole(record.get("equipment_level"))) if record else 0


def production_seconds(town, site, base_seconds):
    return base_seconds*PRODUCTION_PERCENT[_equipment(town, site)]/100


def batch_size(town, site):
    return 6+2*_equipment(town, site)


def sale_price(town, site):
    base = town.prices[trade_for(town, site)]
    level = _equipment(town, site) if site.role == "PUBLIC SHOP" else 0
    return max(1, (base*(100+5*level)+50)//100)


def effective_site(town, site):
    trade = trade_for(town, site)
    if trade == site.trade:
        return site
    if is_dataclass(site):
        return replace(site, trade=trade)
    values = dict(vars(site))
    for field in ("name", "role", "x", "y", "door", "bounds", "color"):
        if hasattr(site, field):
            values[field] = getattr(site, field)
    values["trade"] = trade
    return SimpleNamespace(**values)


def upgrade_cost(town, site, kind):
    record = record_for(town, site)
    prices = STORAGE_COSTS if kind == "storage" else EQUIPMENT_COSTS if kind == "equipment" else None
    if record is None or prices is None:
        return None
    level = record[f"{kind}_level"]
    return prices[level] if level < MAX_LEVEL else None


def _site(name, sites):
    return next((site for site in sites if site.name == name and site.role in SUPPORTED_ROLES), None)


def purchase_business(town, name, sites):
    site = _site(name, sites) if isinstance(name, str) else None
    if site is None:
        town.message = "Choose a standard factory or public shop to buy."
        return False
    if is_owned(town, site):
        town.message = "You already own this business."
        return False
    price = PURCHASE_PRICES[site.role]
    if town.cash < price:
        town.message = f"You need ${price:,} to buy {site.name}."
        return False
    record = _new_record(site)
    if site.role == "FACTORY":
        old_order = town.orders[site.trade]
        if old_order is not None:
            record["manual_order"] = _manual_order(old_order, site.trade)
            if record["manual_order"] is None:
                town.message = "Finish the existing production order before buying this factory."
                return False
    town.cash -= price
    town.other_expenses_today += price
    record["invested"] = price
    _state(town)["owned"][site.name] = record
    if site.role == "FACTORY" and record["manual_order"] is not None:
        town.orders[site.trade] = None
    town.message = f"Bought {site.name} for ${price:,}. B opens business management."
    return True


def upgrade_business(town, name, kind, sites):
    site = _site(name, sites) if isinstance(name, str) else None
    cost = upgrade_cost(town, site, kind) if site is not None else None
    if cost is None:
        town.message = "Own this business and choose an available storage or equipment upgrade."
        return False
    if town.cash < cost:
        town.message = f"You need ${cost:,} for this {kind} upgrade."
        return False
    record = record_for(town, site)
    town.cash -= cost
    town.other_expenses_today += cost
    record[f"{kind}_level"] += 1
    record["invested"] += cost
    town.message = f"{site.name}: {kind} level {record[f'{kind}_level']} purchased for ${cost:,}."
    return True


def specialization_block_reason(town, site):
    record = record_for(town, site)
    if record is None:
        return "Buy this business before choosing its product."
    if site.role == "PUBLIC SHOP":
        return "Sell or withdraw all shop stock before changing product." if record["stock"] else None
    if record["manual_order"] is not None:
        return "Collect the current manual order before changing product."
    logistics = getattr(town, "logistics", {})
    factory = logistics.get("factories", {}).get(site.name, {})
    if factory.get("input") or factory.get("order") or factory.get("output"):
        return "Empty this factory's delivered materials, production and finished output before changing product."
    if any(route.get("destination") == site.name for route in logistics.get("routes", ())):
        return "Pause and reassign all delivery routes from this factory before changing its product."
    return None


def specialize_business(town, name, trade, sites):
    site = _site(name, sites) if isinstance(name, str) else None
    if site is None or not _trade(trade) or not is_owned(town, site):
        town.message = "Choose an owned business and one of its four standard products."
        return False
    if trade_for(town, site) == trade:
        town.message = "This business already specializes in that product."
        return False
    reason = specialization_block_reason(town, site)
    if reason:
        town.message = reason
        return False
    record_for(town, site)["trade"] = trade
    factory = getattr(town, "logistics", {}).get("factories", {}).get(site.name)
    if site.role == "FACTORY" and isinstance(factory, dict):
        factory["trade"] = trade
    town.message = f"{site.name} now specializes in {PRODUCT_NAMES[trade]}."
    return True


def reserved(town):
    state = getattr(town, "businesses", None)
    owned = state.get("owned", {}) if isinstance(state, dict) else {}
    return sum(record["manual_order"]["quantity"] for record in owned.values()
               if record.get("manual_order") is not None)


def operate_factory(town, site, base_seconds=None):
    """Start or collect this factory's manual batch; return collected units."""
    record = record_for(town, site)
    if record is None or site.role != "FACTORY":
        town.message = "Choose an owned production factory."
        return 0
    order = record["manual_order"]
    if order is not None:
        if town.elapsed < order["ready_at"]:
            town.message = f"{site.name} production is still running."
            return 0
        other_reserved = max(0, town.reserved-order["quantity"])
        quantity = min(order["quantity"], max(0, town.carry_capacity-town.cargo-other_reserved))
        if not quantity:
            town.message = "Free cargo space before collecting this factory order."
            return 0
        town.goods[order["trade"]] += quantity
        order["quantity"] -= quantity
        if not order["quantity"]:
            record["manual_order"] = None
        town.message = f"Collected {quantity} × {PRODUCT_NAMES[order['trade']]} from {site.name}."
        return quantity
    trade = record["trade"]
    quantity = town.supplies[trade]
    if not quantity:
        town.message = f"Bring {MATERIAL_NAMES[trade]} to make {PRODUCT_NAMES[trade]}. B opens business management."
        return 0
    base = BASE_SECONDS[trade] if base_seconds is None else base_seconds
    if not _finite(base) or base <= 0:
        town.message = "Choose a valid positive production time."
        return 0
    seconds = production_seconds(town, site, base)
    town.supplies[trade] -= quantity
    record["manual_order"] = {"quantity": quantity, "ready_at": town.elapsed+seconds, "trade": trade}
    town.message = f"Making {quantity} × {PRODUCT_NAMES[trade]} at {site.name} · {seconds:g}s."
    return 0


def near_business(town, site):
    method = getattr(town, "nearby", None)
    nearby = method() if callable(method) else None
    return nearby is not None and nearby.name == site.name and nearby.role == site.role


def _shop_record(town, site):
    record = record_for(town, site)
    return record if getattr(site, "role", None) == "PUBLIC SHOP" and record is not None else None


def _quantity(value):
    return value is None or type(value) is int and value > 0


def deposit_shop(town, site, quantity=None):
    record = _shop_record(town, site)
    if record is None or not _quantity(quantity) or not near_business(town, site):
        town.message = "Visit your shop with a positive whole stock quantity."
        return 0
    trade = record["trade"]
    count = min(town.goods[trade], storage_capacity(town, site)-record["stock"],
                town.goods[trade] if quantity is None else quantity)
    if count <= 0:
        town.message = "Shop storage is full." if record["stock"] >= storage_capacity(town, site) else f"Carry {PRODUCT_NAMES[trade]} to stock this shop."
        return 0
    town.goods[trade] -= count
    record["stock"] += count
    town.message = f"Stocked {count} × {PRODUCT_NAMES[trade]} at {site.name}. Customers buy automatically."
    return count


def withdraw_shop(town, site, quantity=None):
    record = _shop_record(town, site)
    if record is None or not _quantity(quantity) or not near_business(town, site):
        town.message = "Visit your shop to collect a positive whole quantity of stored goods."
        return 0
    space = max(0, town.carry_capacity-town.cargo-town.reserved)
    count = min(record["stock"], space, record["stock"] if quantity is None else quantity)
    if not count:
        town.message = "Free cargo space before withdrawing shop stock." if not space else "This shop has no stock to withdraw."
        return 0
    record["stock"] -= count
    town.goods[record["trade"]] += count
    town.message = f"Withdrew {count} × {PRODUCT_NAMES[record['trade']]} from {site.name}."
    return count


def sell_shop(town, site, source="stock", quantity=None):
    """Sell stored stock, or carried goods when physically at this owned shop."""
    record = _shop_record(town, site)
    if record is None or source not in ("stock", "carried") or not _quantity(quantity):
        town.message = "Choose an owned shop and a positive whole sale quantity."
        return 0
    if source == "carried" and not near_business(town, site):
        town.message = "Visit this shop to sell carried goods immediately."
        return 0
    effective = effective_site(town, site)
    available = record["stock"] if source == "stock" else town.goods[record["trade"]]
    count = min(available, town.buyers_for(effective), available if quantity is None else quantity)
    if not count:
        town.message = "No stock or remaining buyers are available at this shop."
        return 0
    revenue = count*sale_price(town, site)
    if source == "stock":
        record["stock"] -= count
    else:
        town.goods[record["trade"]] -= count
    town._consume_buyers(effective, count)
    trade = record["trade"]
    for field, amount in (("sales_today", count), ("total_sold", count), ("revenue_today", revenue)):
        getattr(town, field)[trade] += amount
    record["sales_today"] += count
    record["revenue_today"] += revenue
    record["total_sold"] += count
    record["total_revenue"] += revenue
    town.add_cash(revenue, business=True)
    town.message = f"{site.name} sold {count} × {PRODUCT_NAMES[trade]} for ${revenue:,}."
    return count


def advance_businesses(town, seconds, sites, trades=None):
    """Serve shops on active ten-second boundaries; return actual sales only."""
    if not _finite(seconds) or seconds <= 0:
        return ()
    state = _state(town)
    if not any(record["role"] == "PUBLIC SHOP" for record in state["owned"].values()):
        return ()
    total = state["retail_elapsed"]+seconds
    periods = int((total+1e-9)//RETAIL_INTERVAL)
    state["retail_elapsed"] = max(0.0, total-periods*RETAIL_INTERVAL)
    if not periods:
        return ()
    shops = tuple(site for site in sites if site.role == "PUBLIC SHOP" and is_owned(town, site))
    events = []
    for _ in range(periods):
        sold_any = False
        for site in shops:
            record = record_for(town, site)
            effective = effective_site(town, site)
            if not record["stock"] or not town.buyers_for(effective):
                continue
            price = sale_price(town, site)
            quantity = sell_shop(town, site, quantity=2+_equipment(town, site))
            if quantity:
                events.append(SaleEvent(effective_site(town, site), quantity, quantity*price))
                sold_any = True
        if not sold_any:
            break
    return tuple(events)


def reset_day(town):
    state = getattr(town, "businesses", None)
    if not isinstance(state, dict):
        return
    for record in state.get("owned", {}).values():
        record["sales_today"] = record["revenue_today"] = 0
