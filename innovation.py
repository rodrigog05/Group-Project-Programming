"""Active-play research and tier-three manufacturing at Nova SBE, Carcavelos.

The entire ledger is JSON serializable. Timers advance only by the focused game
seconds passed to ``advance_innovation``; saving or loading grants no time.
Town supplies the shared cargo/reservation totals and whole-dollar accounting.
"""
from dataclasses import dataclass
import math
import random

from contracts import research_cost


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ResearchLevel:
    level: int
    cost: int
    seconds: int
    tax_discount: int = 0
    unlocks: tuple = ()


@dataclass(frozen=True)
class ResearchBranch:
    key: str
    name: str
    description: str
    levels: tuple


@dataclass(frozen=True)
class Ingredient:
    source: str
    index: object
    quantity: int
    label: str


@dataclass(frozen=True)
class Tier3Recipe:
    key: str
    product: str
    level: int
    ingredients: tuple
    seconds: int
    base_price: int
    buyers: int


@dataclass(frozen=True)
class ResearchCompletion:
    branch: str
    level: int
    unlocked_recipes: tuple


TIER3_RECIPES = (
    Tier3Recipe("alloy_components", "Alloy Components", 1,
                (Ingredient("supplies", 0, 2, "Iron ore"),
                 Ingredient("goods", 0, 1, "Tools")), 14, 75, 8),
    Tier3Recipe("precision_turbines", "Precision Turbines", 2,
                (Ingredient("tier2_goods", None, 1, "Precision Machinery"),
                 Ingredient("innovation", "alloy_components", 2, "Alloy Components")),
                25, 360, 4),
    Tier3Recipe("tram_assemblies", "Smart Tram Assemblies", 3,
                (Ingredient("innovation", "precision_turbines", 2, "Precision Turbines"),
                 Ingredient("goods", 0, 2, "Tools")), 40, 1200, 2),
)
RECIPE_BY_KEY = {recipe.key: recipe for recipe in TIER3_RECIPES}
RESEARCH_BRANCHES = (
    ResearchBranch("green_energy", "Green Energy",
                   "Cleaner operating methods reduce the daily tax on net profit.",
                   (ResearchLevel(1, 200, 45, tax_discount=2),
                    ResearchLevel(2, 450, 75, tax_discount=5),
                    ResearchLevel(3, 900, 120, tax_discount=10))),
    ResearchBranch("metallurgy", "Advanced Metallurgy",
                   "Unlock increasingly valuable tier-three products to make and sell at the lab.",
                   (ResearchLevel(1, 350, 60, unlocks=("alloy_components",)),
                    ResearchLevel(2, 800, 90, unlocks=("precision_turbines",)),
                    ResearchLevel(3, 1600, 120, unlocks=("tram_assemblies",)))),
)
BRANCH_BY_KEY = {branch.key: branch for branch in RESEARCH_BRANCHES}


def initial_state():
    """Create an independent empty lab, with no research, production or income."""
    def zeros():
        return {recipe.key: 0 for recipe in TIER3_RECIPES}

    return {
        "version": SCHEMA_VERSION,
        "levels": {branch.key: 0 for branch in RESEARCH_BRANCHES},
        "project": None,
        "goods": zeros(),
        "orders": {recipe.key: None for recipe in TIER3_RECIPES},
        "demand": zeros(),
        "prices": {recipe.key: recipe.base_price for recipe in TIER3_RECIPES},
        "sales_today": zeros(),
        "revenue_today": zeros(),
        "total_sold": zeros(),
        "total_revenue": zeros(),
        "research_spent": 0,
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


def normalize_state(value):
    """Sanitize saved data without inferring progress, elapsed time or revenue.

    Paid valid projects resume their saved remaining time, without charging
    again. Missing buyer counts use the completed level and recorded sales;
    missing revenue and lifetime totals always stay zero. Unlocked goods are
    never inferred from research. Existing valid stock is preserved even when
    its research metadata is missing, so loading cannot discard carried goods.
    """
    result = initial_state()
    if not isinstance(value, dict):
        return result
    version = value.get("version", SCHEMA_VERSION)
    if type(version) is not int or version != SCHEMA_VERSION:
        return result

    def mapping(key):
        found = value.get(key)
        return found if isinstance(found, dict) else {}

    levels = mapping("levels")
    for branch in RESEARCH_BRANCHES:
        level = levels.get(branch.key)
        if type(level) is int and 0 <= level <= len(branch.levels):
            result["levels"][branch.key] = level
    result["research_spent"] = _whole(value.get("research_spent"))
    project = value.get("project")
    if isinstance(project, dict):
        branch = BRANCH_BY_KEY.get(project.get("branch")) if isinstance(project.get("branch"), str) else None
        level, remaining = project.get("level"), project.get("remaining")
        if (branch is not None and type(level) is int
                and level == result["levels"][branch.key] + 1
                and level <= len(branch.levels) and _finite(remaining)
                and 0 <= remaining <= branch.levels[level - 1].seconds):
            base_cost = branch.levels[level-1].cost
            paid_cost = project.get("paid_cost", base_cost)
            if type(paid_cost) is not int or not 1 <= paid_cost <= base_cost:
                paid_cost = base_cost
            result["project"] = {"branch": branch.key, "level": level,
                                 "remaining": float(remaining), "paid_cost": paid_cost}

    fields = {key: mapping(key) for key in (
        "goods", "orders", "demand", "prices", "sales_today", "revenue_today", "total_sold", "total_revenue")}
    for recipe in TIER3_RECIPES:
        key = recipe.key
        unlocked = result["levels"]["metallurgy"] >= recipe.level
        for field in ("goods", "revenue_today", "total_sold", "total_revenue"):
            result[field][key] = _whole(fields[field].get(key))
        # Ordinary days use the base buyer count; demand spikes reach 2.5x.
        # Allow a little rounding headroom without permitting unbounded markets.
        capacity = 3 * recipe.buyers
        sales = min(capacity, _whole(fields["sales_today"].get(key)))
        result["sales_today"][key] = sales
        default_demand = max(0, recipe.buyers - sales)
        result["demand"][key] = (min(capacity - sales,
            _whole(fields["demand"].get(key), default_demand)) if unlocked else 0)
        result["prices"][key] = max(1, _whole(fields["prices"].get(key), recipe.base_price))
        order = fields["orders"].get(key)
        if unlocked and isinstance(order, dict):
            quantity, remaining = order.get("quantity"), order.get("remaining")
            if (_whole(quantity) > 0 and _finite(remaining)
                    and 0 <= remaining <= recipe.seconds):
                result["orders"][key] = {"quantity": quantity, "remaining": float(remaining)}
    return result


def _state(town):
    """Cheap fast path: save loading is responsible for full normalization."""
    state = getattr(town, "innovation", None)
    if (not isinstance(state, dict) or type(state.get("version")) is not int
            or state.get("version") != SCHEMA_VERSION
            or any(not isinstance(state.get(key), dict) for key in (
                "levels", "goods", "orders", "demand", "prices", "sales_today",
                "revenue_today", "total_sold", "total_revenue"))):
        state = town.innovation = normalize_state(state)
    return state


def _branch(key):
    return BRANCH_BY_KEY.get(key) if isinstance(key, str) else None


def _recipe(key):
    return RECIPE_BY_KEY.get(key) if isinstance(key, str) else None


def research_level(town, branch):
    return _state(town)["levels"].get(branch, 0) if isinstance(branch, str) else 0


def next_research(town, branch):
    info = _branch(branch)
    if info is None:
        return None
    level = research_level(town, branch)
    return info.levels[level] if level < len(info.levels) else None


def research_quote(town, branch):
    """Quote a new payment; paid projects retain the price saved at their start."""
    node = next_research(town, branch)
    return research_cost(town, node.cost) if node is not None else None


def unlocked_recipes(town):
    level = research_level(town, "metallurgy")
    return tuple(recipe for recipe in TIER3_RECIPES if recipe.level <= level)


def tax_rate(town, base=20):
    """Whole percentage rate; each Green Energy level supplies a total discount."""
    level = research_level(town, "green_energy")
    discount = BRANCH_BY_KEY["green_energy"].levels[level - 1].tax_discount if level else 0
    return max(0, base - discount)


def start_research(town, branch):
    """Pay once for the next level in one branch; failures change no accounting."""
    info = _branch(branch)
    if info is None:
        town.message = "Choose a research branch at Nova SBE."
        return False
    state = _state(town)
    if state["project"] is not None:
        town.message = "The lab is already researching a project. Finish it before starting another."
        return False
    node = next_research(town, branch)
    if node is None:
        town.message = f"{info.name} is fully researched."
        return False
    cost = research_quote(town, branch)
    if town.cash < cost:
        town.message = f"You need ${cost:,} to research {info.name} level {node.level}."
        return False
    town.cash -= cost
    town.other_expenses_today += cost
    state["research_spent"] += cost
    state["project"] = {"branch": branch, "level": node.level,
                        "remaining": float(node.seconds), "paid_cost": cost}
    town.message = f"Researching {info.name} level {node.level} · ${cost:,} paid · {node.seconds}s active play."
    return True


def advance_innovation(town, focused_seconds):
    """Advance active timers; return completed research records exactly once.

    Fabrication orders run in parallel and remain reserved after reaching zero.
    No goods or sale income is granted automatically. A subsequent research
    level requires another explicit payment and cannot use surplus frame time.
    """
    if not _finite(focused_seconds) or focused_seconds <= 0:
        return ()
    state = _state(town)
    for order in state["orders"].values():
        if order is not None:
            order["remaining"] = max(0.0, order["remaining"] - focused_seconds)
    project = state["project"]
    if project is None:
        return ()
    project["remaining"] = max(0.0, project["remaining"] - focused_seconds)
    if project["remaining"] > 1e-9:
        return ()
    branch, level = project["branch"], project["level"]
    node = BRANCH_BY_KEY[branch].levels[level - 1]
    state["levels"][branch] = level
    state["project"] = None
    for key in node.unlocks:
        state["demand"][key] = max(0, RECIPE_BY_KEY[key].buyers - state["sales_today"][key])
    town.message = f"Research complete: {BRANCH_BY_KEY[branch].name} level {level}."
    return (ResearchCompletion(branch, level, node.unlocks),)


def cargo(town):
    """Include this count in Town.cargo."""
    return sum(_state(town)["goods"].values())


def reserved(town):
    """Include this count in Town.reserved, including ready uncollected orders."""
    return sum(order["quantity"] for order in _state(town)["orders"].values()
               if order is not None)


def ingredient_stock(town, ingredient):
    if ingredient.source == "innovation":
        return _state(town)["goods"][ingredient.index]
    if ingredient.source == "tier2_goods":
        return town.tier2_goods
    return getattr(town, ingredient.source)[ingredient.index]


ingredient_owned = ingredient_stock


def _consume(town, ingredient, quantity):
    count = ingredient.quantity * quantity
    if ingredient.source == "innovation":
        _state(town)["goods"][ingredient.index] -= count
    elif ingredient.source == "tier2_goods":
        town.tier2_goods -= count
    else:
        getattr(town, ingredient.source)[ingredient.index] -= count


def _quantity(value):
    return type(value) is int and value > 0


def max_fabrication(town, key):
    recipe = _recipe(key)
    if recipe is None or research_level(town, "metallurgy") < recipe.level:
        return 0
    if _state(town)["orders"][key] is not None:
        return 0
    quantity = min(ingredient_stock(town, item) // item.quantity for item in recipe.ingredients)
    consumed = quantity * sum(item.quantity for item in recipe.ingredients)
    return quantity if town.cargo - consumed + town.reserved + quantity <= town.carry_capacity else 0


def start_fabrication(town, key, quantity=1):
    """Consume an exact batch atomically and reserve its eventual carried output."""
    recipe = _recipe(key)
    if recipe is None or not _quantity(quantity):
        town.message = "Choose a product and a positive whole batch quantity."
        return False
    state = _state(town)
    if research_level(town, "metallurgy") < recipe.level:
        town.message = f"Research Advanced Metallurgy level {recipe.level} to unlock {recipe.product}."
        return False
    if state["orders"][key] is not None:
        town.message = f"Collect the existing {recipe.product} order before starting another."
        return False
    if any(ingredient_stock(town, item) < item.quantity * quantity for item in recipe.ingredients):
        ingredients = " + ".join(f"{item.quantity * quantity} {item.label}" for item in recipe.ingredients)
        town.message = f"Bring {ingredients} to make {quantity} × {recipe.product}."
        return False
    consumed = sum(item.quantity for item in recipe.ingredients) * quantity
    if town.cargo - consumed + town.reserved + quantity > town.carry_capacity:
        town.message = "Free cargo space before reserving another lab order."
        return False
    for item in recipe.ingredients:
        _consume(town, item, quantity)
    state["orders"][key] = {"quantity": quantity, "remaining": float(recipe.seconds)}
    town.message = f"Making {quantity} × {recipe.product} · ready in {recipe.seconds}s active play."
    return True


def collect_products(town, key, quantity=None):
    """Collect as much of a ready order as requested space permits; return units."""
    recipe = _recipe(key)
    if recipe is None or (quantity is not None and not _quantity(quantity)):
        town.message = "Choose a product and a positive whole collection quantity."
        return 0
    state = _state(town)
    if research_level(town, "metallurgy") < recipe.level:
        town.message = f"Research Advanced Metallurgy level {recipe.level} to collect {recipe.product}."
        return 0
    order = state["orders"][key]
    if order is None:
        town.message = f"There is no {recipe.product} order to collect."
        return 0
    if order["remaining"] > 1e-9:
        town.message = f"{recipe.product} is still in production."
        return 0
    # This order releases its own reservation; every other order keeps its slots.
    other_reserved = max(0, town.reserved - order["quantity"])
    space = max(0, town.carry_capacity - town.cargo - other_reserved)
    count = min(order["quantity"], space, quantity if quantity is not None else order["quantity"])
    if not count:
        town.message = "Free cargo space before collecting your lab order."
        return 0
    state["goods"][key] += count
    order["quantity"] -= count
    if not order["quantity"]:
        state["orders"][key] = None
    town.message = f"Collected {count} × {recipe.product}. Sell them at Nova SBE or use them in another recipe."
    return count


def sell_products(town, key, quantity=None):
    """Sell carried output up to today's remaining buyers; return units sold."""
    recipe = _recipe(key)
    if recipe is None or (quantity is not None and not _quantity(quantity)):
        town.message = "Choose a product and a positive whole sale quantity."
        return 0
    state = _state(town)
    if research_level(town, "metallurgy") < recipe.level:
        town.message = f"Research Advanced Metallurgy level {recipe.level} to trade {recipe.product}."
        return 0
    count = min(state["goods"][key], state["demand"][key],
                quantity if quantity is not None else state["goods"][key])
    if not count:
        town.message = ("Today's lab customers are served. Come back tomorrow."
                        if not state["demand"][key] else f"Bring {recipe.product} to sell at Nova SBE.")
        return 0
    revenue = count * state["prices"][key]
    state["goods"][key] -= count
    state["demand"][key] -= count
    state["sales_today"][key] += count
    state["revenue_today"][key] += revenue
    state["total_sold"][key] += count
    state["total_revenue"][key] += revenue
    town.add_cash(revenue, business=True)
    town.message = f"Sold {count} × {recipe.product} for ${revenue:,}."
    return count


def reset_day(town):
    """Price a new market after settlement; retain research, orders and stock.

    Supply sold yesterday plus carried inventory depresses quotes. Unexpected
    demand spikes can sharply increase both prices and today's buyer pool.
    """
    state = _state(town)
    level = research_level(town, "metallurgy")
    for recipe in TIER3_RECIPES:
        key = recipe.key
        if level >= recipe.level:
            demand_factor = 2.5 if random.random() < 0.12 else random.uniform(0.85, 1.15)
            demand = max(1, round(recipe.buyers * demand_factor))
            supply = state["sales_today"][key] + state["goods"][key]
            price_factor = (1 + 0.6 * (demand / recipe.buyers - 1)
                            - 0.5 * (supply / recipe.buyers))
            state["prices"][key] = max(1, round(recipe.base_price * max(0.4, min(2.5, price_factor))))
            state["demand"][key] = demand
        else:
            state["demand"][key] = 0
            state["prices"][key] = recipe.base_price
        state["sales_today"][key] = 0
        state["revenue_today"][key] = 0
