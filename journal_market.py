"""Read-only market observations for the journal.

The simulation tracks the player's inventory and orders, not all stock held
by the city. Ordinary demand is shared per product; tourist demand is local.
"""
from dataclasses import dataclass
import math
from typing import Optional

from innovation import TIER3_RECIPES, normalize_state as normalize_innovation
from tourism import tourism_bonus
import businesses


@dataclass(frozen=True)
class TouristShop:
    name: str
    product: str
    remaining: int
    maximum: int


@dataclass(frozen=True)
class MarketRow:
    key: str
    product: str
    raw_stock: str
    raw_cost: Optional[int]
    price: int
    stock: Optional[int]
    orders: int
    sold_today: int
    ordinary_buyers: int
    tourist_buyers: int
    revenue_today: int
    notes: str

    @property
    def remaining_buyers(self):
        return self.ordinary_buyers+self.tourist_buyers

    @property
    def stock_label(self):
        return "Service" if self.stock is None else str(self.stock)

    @property
    def demand_label(self):
        return "Jobs" if self.stock is None else "Buyers"


@dataclass(frozen=True)
class MarketSnapshot:
    day: int
    seconds_to_reset: int
    event_title: str
    event_detail: str
    rows: tuple
    tourist_shops: tuple
    notes: str


def _order_quantity(order):
    if isinstance(order, dict):
        return order.get("quantity", 0)
    return order.quantity if order is not None else 0


def market_snapshot(town, trades=None, industries=None, sites=None, *, day_seconds=300, egg_cost=2):
    """Return current observations without advancing time or changing a market."""
    # Main-script callers supply models, avoiding a second import as 'tycoon'.
    # The convenience form is useful to tools/tests that imported Town normally.
    if trades is None or industries is None or sites is None:
        import tycoon
        trades = tycoon.TRADES if trades is None else trades
        industries = tycoon.INDUSTRIES if industries is None else industries
        sites = tycoon.SITES if sites is None else sites
    material_routes = {trade.supply: index for index, trade in enumerate(trades)}
    sites = tuple(businesses.effective_site(town, site) for site in sites)

    tourists = []
    seen_shops = set()
    for site in sites:
        maximum = tourism_bonus(site)
        if maximum and site.name not in seen_shops:
            product = industries[site.role].product if site.role in industries else trades[site.trade].product
            tourists.append(TouristShop(site.name, product, town.tourism_for(site), maximum))
            seen_shops.add(site.name)
    tourists = tuple(sorted(tourists, key=lambda row: row.name.casefold()))

    def visitors(product):
        return sum(shop.remaining for shop in tourists if shop.product == product)

    rows = []
    for index, trade in enumerate(trades):
        shops = ", ".join(site.name for site in sites if site.role == "PUBLIC SHOP" and site.trade == index)
        note = (f"Ordinary buyers share one pool across {shops}; that pool is counted once. "
                "Tourist buyers remain local to their listed shop. The stock and orders shown are yours.")
        owned_orders = 0
        for site in sites:
            if site.trade != index or not businesses.is_owned(town, site):
                continue
            owned = businesses.record_for(town, site)
            if site.role == "FACTORY" and owned["manual_order"]:
                owned_orders += owned["manual_order"]["quantity"]
            elif site.role == "PUBLIC SHOP":
                note += (f" Owned shop {site.name}: {owned['stock']} stored for customers, "
                         f"quote ${businesses.sale_price(town, site)} each. Shop stock is separate from carried stock; "
                         "the row's quote is the base market price.")
        for site in sites:
            if site.role != "FACTORY" or site.trade != index:
                continue
            factory = getattr(town, "logistics", {}).get("factories", {}).get(site.name, {})
            if factory and (factory.get("input") or factory.get("order") or factory.get("output")):
                order = factory.get("order")
                processing = order["quantity"] if order else 0
                note += (f" Automated storage at {site.name}: {factory['input']} raw materials, "
                         f"{processing} in production, {factory['output']} finished. "
                         "These stocks are separate from the carried stock and manual orders above. "
                         "Visit this factory to collect its finished products; L opens delivery routes.")
        rows.append(MarketRow(
            f"trade:{index}", trade.product, f"{trade.supply}: {town.supplies[index]}",
            town.costs[index], town.prices[index], town.goods[index], _order_quantity(town.orders[index])+owned_orders,
            town.sales_today[index], town.demand[index], visitors(trade.product), town.revenue_today[index], note))

    rows.append(MarketRow(
        "tier2", "Precision Machinery", f"Tools: {town.goods[0]} · Furniture: {town.goods[1]}",
        None, town.tier2_price, town.tier2_goods, _order_quantity(town.tier2_order),
        town.tier2_sales_today, town.tier2_demand, 0, town.tier2_revenue_today,
        "One Tool + one Furniture makes one Machinery. These finished inputs are made at earlier factories, "
        "so there is no direct input purchase quote. Input counts refer to the same inventory shown in their product rows."))

    for role, recipe in industries.items():
        materials, cost = [], 0
        for name, amount in recipe.ingredients:
            if name == "Eggs":
                stock, unit_cost = town.eggs, egg_cost
            else:
                index = material_routes[name]
                stock, unit_cost = town.supplies[index], town.costs[index]
            materials.append(f"{name}: {stock}")
            cost += amount*unit_cost
        if recipe.service:
            note = ("Boat repairs are service contracts, not stored goods. Remaining jobs exclude a contract "
                    "already reserved by your active order; orders and completed jobs are shown separately.")
            if town.industry_orders[role] is not None:
                note += f" Your active repair pays its saved quote of ${town.shipyard_quote} per job."
        else:
            note = ("One Wheat + one Egg makes one Pastel. Ordinary and tourist buyers are shown separately; "
                    "tourist buyers are local to Pastéis de Belém. Sell the collected pastries at the same business.")
        rows.append(MarketRow(
            f"industry:{role}", recipe.product, " · ".join(materials), cost, town.industry_prices[role],
            None if recipe.service else town.industry_goods[role], _order_quantity(town.industry_orders[role]),
            town.industry_sales_today[role], town.industry_demand[role], visitors(recipe.product),
            town.industry_revenue_today[role], note))

    # Normalize a copy rather than changing a save while the journal is read.
    innovation = normalize_innovation(getattr(town, "innovation", None))
    for recipe in TIER3_RECIPES:
        materials = []
        for item in recipe.ingredients:
            if item.source == "innovation":
                count = innovation["goods"][item.index]
            elif item.source == "tier2_goods":
                count = town.tier2_goods
            else:
                count = getattr(town, item.source)[item.index]
            materials.append(f"{item.label}: {count}")
        unlocked = innovation["levels"]["metallurgy"] >= recipe.level
        note = (f"Tier-3 workshop at Nova SBE in Carcavelos. Requires Advanced Metallurgy level {recipe.level}. "
                "Finished inputs are made through earlier recipes, so there is no direct input purchase quote. "
                "These counts refer to the same inventory shown in the other product rows. "
                "Craft, collect and sell through the campus Advanced Workshop; ordinary buyers are local to this workshop.")
        if not unlocked:
            note = "Locked: complete the required research before making or selling this product. " + note
        order = innovation["orders"][recipe.key]
        rows.append(MarketRow(
            f"innovation:{recipe.key}", recipe.product, " · ".join(materials), None,
            innovation["prices"][recipe.key], innovation["goods"][recipe.key], _order_quantity(order),
            innovation["sales_today"][recipe.key], innovation["demand"][recipe.key] if unlocked else 0,
            0, innovation["revenue_today"][recipe.key], note))

    event = town.market_event
    return MarketSnapshot(
        town.day, max(0, math.ceil(day_seconds-town.market_elapsed % day_seconds)),
        event[0] if event else "No special market event", event[1] if event else "Prices and buyers refresh with the next day.",
        tuple(rows), tourists,
        "Your stock and Your orders describe your own supply, not all stock in the city. Orders include "
        "both work in progress and finished output waiting for pickup. Ordinary buyers are shared per product "
        "and counted once; tourists can only be served at their listed shop. Materials used by several recipes "
        "refer to the same inventory. Sales and revenue are today's totals, including tourist sales.")
