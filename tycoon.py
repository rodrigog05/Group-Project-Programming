"""Foundry Town simulation, extracted from the desktop game."""
from copy import deepcopy
from dataclasses import asdict, dataclass
import math
import random
import time

from lisbon_scene import MAP_BOTTOM, WORLD_WIDTH, WORLD_BOTTOM, SCENERY_BLOCKS, RIVER_TOP, RIVER_BOTTOM, BRIDGE_TOLL, bridge_at, walkable_terrain, south
from journal_recipes import RECIPE_BY_KEY, infer_discoveries, normalize_discoveries, recipe_key_for_site
from lisbon_landmarks import LANDMARK_SOLIDS
from vehicles import VEHICLES, WALK_SPEED, on_road
from tourism import new_tourist_pools, tourism_bonus
from exchange import (initial_state as new_exchange_state, normalize_state as normalize_exchange_state,
                      record_trade, settle_exchange)
import innovation
import logistics
import contracts
import businesses


WIDTH = 1200

MAP_TOP = 104

HEIGHT = MAP_BOTTOM + 95

DAY_SECONDS = 2 * 60

DAYLIGHT_SECONDS = 60

NIGHT_SECONDS = 60

LEGACY_DAY_SECONDS = 24 * 60 * 60

START_CASH, CASH_GOAL, BAG_SIZE = 60, 500, 12

PLAYER_RADIUS, REACH = 10, 35

POWER_INTERVAL = 30

TARGET_FPS = 120

FRAME_SECONDS = 1 / TARGET_FPS

DAILY_TAX_PERCENT = 20

POWER_UPS = (
    ("Bag upgrade", "+", "#80e2b9", 315, 321),
    ("Speed boost", "»", "#86caff", 600, 1055),
    ("Cash bonus", "$", "#ffc66c", 812, 708),
)

WHITE, MUTED, INK = "#f8faf7", "#bdced0", "#18343f"

GOLD, MINT = "#f1c568", "#a5cbbb"

BODY_COLORS = {"Peach": "#f4bd93", "Amber": "#c78658", "Brown": "#89553c", "Mint": "#80dab9", "Lilac": "#bea0ec"}

HAIR_COLORS = {"Chestnut": "#673b2d", "Black": "#242027", "Blonde": "#f4cc73", "Silver": "#d3d8df", "Pink": "#e675af"}

COSTUMES = {
    "Builder": ("#457ca9", "#ffc66c"),
    "Chef": ("#e6e9df", "#ffffff"),
    "Explorer": ("#54876a", "#c2a271"),
    "Racer": ("#d65655", "#f5ede5"),
    "Astronaut": ("#b2bfd7", "#80dce4"),
    "Wizard": ("#885bbb", "#c6a0ff"),
}

@dataclass(frozen=True)
class Trade:
    supply: str
    product: str
    cost: int
    price: int
    seconds: int
    demand: int

TRADES = (
    Trade("Iron ore", "Tools", 5, 18, 5, 8),
    Trade("Timber", "Furniture", 7, 26, 7, 6),
    Trade("Clay", "Pottery", 6, 22, 6, 7),
    Trade("Wheat", "Bread", 4, 14, 4, 10),
)

EGG_COST = 2

MATERIAL_ROUTES = {"Iron ore": 0, "Timber": 1, "Wheat": 3}

@dataclass(frozen=True)
class LocalIndustry:
    product: str
    ingredients: tuple
    seconds: int
    price: int
    demand: int
    service: bool = False

INDUSTRIES = {
    "PASTELARIA": LocalIndustry("Pastéis", (("Wheat", 1), ("Eggs", 1)), 8, 24, 12),
    "SHIPYARD": LocalIndustry("Boat repair", (("Timber", 2), ("Iron ore", 2)), 20, 100, 3, True),
}

MARKET_EVENTS = (
    ("Builders' boom", 0, 1, 5, 4),
    ("Timber surplus", 1, -2, -4, 3),
    ("Pottery fair", 2, 1, 6, 5),
    ("Harvest festival", 3, -1, 4, 6),
)

ROULETTE_POCKETS = (
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10,
    5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26,
)

RED_NUMBERS = frozenset((1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36))

ROULETTE_PAYOUTS = {"red": 2, "black": 2, "green": 36}

CHIPS = (5, 10, 25, 50, 100)

SPIN_SECONDS = 4.5

CASINO_CENTER = (WIDTH // 2, 380)

CASINO_TRACK_RADIUS = 172

CASINO_POCKET_RADIUS = 122

PROFILE_X = WIDTH - 80

POCKET_COLORS = {"red": "#c8313c", "black": "#1b1d22", "green": "#1f8a4c"}

def roulette_color(number):
    if number == 0:
        return "green"
    return "red" if number in RED_NUMBERS else "black"

@dataclass(frozen=True)
class Site:
    name: str
    role: str
    trade: int
    x: int
    y: int
    color: str

    @property
    def bounds(self):
        return self.x, self.y, self.x + 176, self.y + 104

    @property
    def solid_bounds(self):
        """Building footprint; the rest of a compact trading plot is walkable paving."""
        from city_layout import building_bounds
        return building_bounds(self.x,self.y,self.role,self.name)

    @property
    def door(self):
        left,_,right,bottom = self.solid_bounds
        return (left+right)/2,bottom

SITES = (
    Site("Iron Hill Mine", "SUPPLIER", 0, 1010, south(935), "#d6a46e"),
    Site("Ironworks", "FACTORY", 0, 268, 345, "#ef8f76"),
    Site("Tool Market", "PUBLIC SHOP", 0, 508, 345, "#72d8bc"),
    Site("Pine Mill", "SUPPLIER", 1, 1280, 160, "#d6a46e"),
    Site("Oak Workshop", "FACTORY", 1, 268, 160, "#ef8f76"),
    Site("Home Market", "PUBLIC SHOP", 1, 1540, 345, "#72d8bc"),
    Site("Redbank Clay Pit", "SUPPLIER", 2, 2080, 160, "#e6a17f"),
    Site("Ember Kiln", "FACTORY", 2, 748, 345, "#f3a376"),
    Site("The Pottery Shop", "PUBLIC SHOP", 2, 748, 530, "#d2a7e5"),
    Site("Goldenfield Farm", "SUPPLIER", 3, 1280, 530, "#e3c77e"),
    Site("Sunrise Bakery", "FACTORY", 3, 1540, 530, "#ebbe83"),
    Site("Daily Bread Market", "PUBLIC SHOP", 3, 268, 530, "#f3ca85"),
    # The casino has no trade route, so its trade index is unused.
    Site("Foundry Casino", "CASINO", -1, 1004, 342, "#e8455a"),
    Site("Motorworks Garage", "GARAGE", -1, 988, 530, "#86caff"),
    Site("Foundry Warehouse", "WAREHOUSE", -1, 988, 160, "#d2a7e5"),
    Site("Pastéis de Belém", "PASTELARIA", -1, 28, 160, "#f1d69b"),
    Site("Estaleiro do Tejo", "SHIPYARD", -1, 380, south(935), "#94bdc9"),
    Site("Oriente Tool Market", "PUBLIC SHOP", 0, 1820, 345, "#72d8bc"),
    Site("Mercado das Nações", "PUBLIC SHOP", 2, 2080, 530, "#d2a7e5"),
    Site("Quinta de Palmela", "SUPPLIER", 3, 2060, south(1430), "#e3c77e"),
    Site("Cacilhas Dealership", "GARAGE", -1, 1540, south(1180), "#86caff"),
    Site("Armazém do Seixal", "WAREHOUSE", -1, 2060, south(1180), "#d2a7e5"),
    Site("Bolsa de Lisboa", "EXCHANGE", -1, 508, 160, "#d7bb6e"),
    Site("Nova SBE · Carcavelos", "RESEARCH", -1, 28, 530, "#83bac9"),
    Site("Foundry Precision Works", "TIER2", -1, 650, south(935), "#ffc66c"),
)

COLLISION_BOUNDS = tuple(site.solid_bounds for site in SITES)+SCENERY_BLOCKS+LANDMARK_SOLIDS+((1780, 190, 2030, 260),)

@dataclass
class Order:
    quantity: int
    ready_at: float

class Town:
    def __init__(self):
        self.cash = START_CASH
        self.supplies = [0] * len(TRADES)
        self.goods = [0] * len(TRADES)
        self.orders = [None] * len(TRADES)
        self.discovered_recipes = []
        self.exchange = new_exchange_state()
        self.innovation = innovation.initial_state()
        self.logistics = logistics.initial_state(SITES)
        self.businesses = businesses.initial_state()
        self.contracts = contracts.initial_state()
        self.demand = [trade.demand for trade in TRADES]
        self.tourist_buyers = new_tourist_pools(SITES)
        self.market_elapsed = 0
        self.costs = [trade.cost for trade in TRADES]
        self.prices = [trade.price for trade in TRADES]
        self.sales_today = [0] * len(TRADES)
        self.revenue_today = [0] * len(TRADES)
        self.expenses_today = [0] * len(TRADES)
        self.total_sold = [0] * len(TRADES)
        self.tier2_order = None
        self.tier2_goods = 0
        self.tier2_demand = 5
        self.tier2_price = 80
        self.tier2_sales_today = 0
        self.tier2_revenue_today = 0
        self.tier2_total_sold = 0
        self.eggs = 0
        self.egg_expenses_today = 0
        self.industry_orders = {role: None for role in INDUSTRIES}
        self.industry_goods = {role: 0 for role in INDUSTRIES}
        self.industry_demand = {role: recipe.demand for role, recipe in INDUSTRIES.items()}
        self.industry_prices = {role: recipe.price for role, recipe in INDUSTRIES.items()}
        self.industry_sales_today = {role: 0 for role in INDUSTRIES}
        self.industry_revenue_today = {role: 0 for role in INDUSTRIES}
        self.industry_total_sold = {role: 0 for role in INDUSTRIES}
        self.shipyard_quote = 0
        self.other_income_today = 0
        self.other_expenses_today = 0
        self.tolls_today = 0
        self.toll_count_today = 0
        self.tolls_paid_total = 0
        self.taxes_paid_total = 0
        self.last_tax_day = 0
        self.last_day_summary = None
        self.bridge_journey = None
        self.vehicle = None
        self.owned_vehicles = []
        self.stowed_vehicle = None
        self.market_event = None
        self.elapsed = 0.0
        self.x, self.y = 480.0, 321.0
        self.facing = 1
        self.won = False
        self.milestone_acknowledged = False
        self.level_notices = 0
        self.final_goal_reached = False
        self.bag_size = BAG_SIZE
        self.warehouse_level = 0
        self.speed_until = 0
        self.power_up = None
        self.profile = {"name": "Player", "body": "Peach", "hair": "Chestnut", "costume": "Builder"}
        self.notice = ""
        self.notice_until = 0
        self.monastery_visits = 0
        self.message = "Open Places (P): 1 Buy raw materials → 2 Make products → 3 Sell products."

    def set_profile(self, values):
        name = values.get("name")
        if isinstance(name, str):
            self.profile["name"] = " ".join(name.split())[:24] or "Player"
        for key, choices in (("body", BODY_COLORS), ("hair", HAIR_COLORS), ("costume", COSTUMES)):
            value = values.get(key)
            if isinstance(value, str) and value in choices:
                self.profile[key] = value

    def discover_recipe(self, key):
        if key not in RECIPE_BY_KEY or key in self.discovered_recipes:
            return False
        self.discovered_recipes.append(key)
        self.notice = f"Recipe recorded: {RECIPE_BY_KEY[key].title} · J opens your journal"
        self.notice_until = self.elapsed+4
        return True

    def congratulate(self, quantity, item, action="collected"):
        self.notice = f"Congratulations {self.profile['name']}, you just {action} {quantity} {item}"
        self.notice_until = self.elapsed + 4

    def start_research(self, branch):
        return innovation.start_research(self, branch)

    def advance_research(self, seconds):
        completions = innovation.advance_innovation(self, seconds)
        for completion in completions:
            for key in completion.unlocked_recipes:
                self.discover_recipe(key)
            branch = innovation.BRANCH_BY_KEY[completion.branch]
            self.notice = f"Research complete: {branch.name} {completion.level} · Nova SBE"
            self.notice_until = self.elapsed+6
        return completions

    def start_fabrication(self, recipe, quantity):
        return innovation.start_fabrication(self, recipe, quantity)

    def collect_research_products(self, recipe, quantity=None):
        return innovation.collect_products(self, recipe, quantity)

    def sell_research_products(self, recipe, quantity=None):
        sold = innovation.sell_products(self, recipe, quantity)
        if sold:
            record_trade(self, next(site for site in SITES if site.role == "RESEARCH"), sold)
        return sold

    @property
    def first_product_sold(self):
        return (sum(self.total_sold) + self.tier2_total_sold
                + self.industry_total_sold["PASTELARIA"]
                + sum(self.innovation["total_sold"].values())) > 0

    @property
    def pending_level(self):
        goals = (self.first_product_sold, self.won, self.final_goal_reached)
        level = self.level_notices
        return level + 1 if level < 3 and goals[level] else None

    def acknowledge_level(self):
        level = self.pending_level
        if level is None:
            return
        self.level_notices = level
        if level == 2:
            self.continue_after_milestone()

    def level_progress(self):
        if self.level_notices == 3:
            return "ALL 3 LEVELS COMPLETE", 1
        level = self.level_notices + 1
        if level == 1:
            sold = int(self.first_product_sold)
            return f"LEVEL 1/3 · Sell a product {sold}/1", sold
        goal = CASH_GOAL if level == 2 else 2000
        reached = self.won if level == 2 else self.final_goal_reached
        amount = goal if reached else max(0, min(self.cash, goal))
        return f"LEVEL {level}/3 · ${amount:,} / ${goal:,}", amount / goal

    def continue_after_milestone(self):
        if not self.won:
            return False
        self.milestone_acknowledged = True
        self.message = "Cash milestone complete! Visit Nova SBE in Carcavelos for our Foundry Town presentation."
        return True

    def create_delivery_route(self, kind, source, destination):
        return logistics.create_route(self, kind, source, destination, SITES, TRADES)

    def reassign_delivery_route(self, identifier, source, destination):
        return logistics.reassign_route(self, identifier, source, destination, SITES, TRADES)

    def set_delivery_enabled(self, route_id, enabled):
        return logistics.set_route_enabled(self, route_id, enabled)

    def remove_delivery_route(self, route_id):
        return logistics.remove_route(self, route_id)

    def advance_deliveries(self, seconds):
        for key in logistics.advance_logistics(self, seconds, SITES, TRADES):
            self.discover_recipe(key)

    def collect_delivery_products(self, factory, quantity=None):
        site = self.nearby()
        if site is None or site.role != "FACTORY" or site.name != factory:
            self.message = f"Visit {factory} to collect its automated production. Use L for delivery routes."
            return 0
        return logistics.collect_output(self, factory, quantity)

    def accept_contract(self, key):
        return contracts.accept_contract(self, key)

    def deliver_contract(self, identifier, quantity=None):
        record = next((item for item in self.contracts["active"] if item["id"] == identifier), None)
        delivered = contracts.deliver_contract(self, identifier, quantity)
        if delivered and record is not None:
            offer = contracts.active_offer(record)
            record_trade(self, offer.location, delivered)
            if record["delivered"] == record["required"]:
                self.notice = f"Contract complete: {offer.title} · +{record['reputation']} reputation"
                self.notice_until = self.elapsed+6
        return delivered

    def abandon_contract(self, identifier):
        return contracts.abandon_contract(self, identifier)

    def advance_contracts(self, seconds):
        expired = contracts.advance_contracts(self, seconds)
        if expired:
            titles = ", ".join(contracts.active_offer(record).title for record in expired)
            self.notice = f"Deadline missed: {titles} · C opens contracts"
            self.notice_until = self.elapsed+6
        return expired

    def business_site(self, site):
        return businesses.effective_site(self, site)

    def purchase_business(self, name):
        return businesses.purchase_business(self, name, SITES)

    def upgrade_business(self, name, kind):
        return businesses.upgrade_business(self, name, kind, SITES)

    def specialize_business(self, name, trade):
        changed = businesses.specialize_business(self, name, trade, SITES)
        if changed and name in self.logistics["factories"]:
            self.logistics["factories"][name]["trade"] = trade
        return changed

    def _owned_shop(self, name):
        site = self.nearby()
        if site is None or site.name != name or site.role != "PUBLIC SHOP" or not businesses.is_owned(self, site):
            self.message = f"Visit your shop at {name} to manage its stock. Use B for businesses."
            return None
        return site

    def stock_business(self, name, quantity=None):
        site = self._owned_shop(name)
        return businesses.deposit_shop(self, site, quantity) if site else 0

    def withdraw_business(self, name, quantity=None):
        site = self._owned_shop(name)
        return businesses.withdraw_shop(self, site, quantity) if site else 0

    def sell_business_carried(self, name, quantity=None):
        site = self._owned_shop(name)
        if site is None:
            return 0
        sold = businesses.sell_shop(self, site, source="carried", quantity=quantity)
        if sold:
            record_trade(self, self.business_site(site), sold)
        return sold

    def advance_businesses(self, seconds):
        events = businesses.advance_businesses(self, seconds, SITES, TRADES)
        for event in events:
            record_trade(self, event.site, event.quantity)
        return events

    @property
    def day(self):
        return int(self.market_elapsed // DAY_SECONDS) + 1

    @property
    def daily_revenue(self):
        return (sum(self.revenue_today)+self.tier2_revenue_today+sum(self.industry_revenue_today.values())
                +sum(self.innovation["revenue_today"].values())+self.other_income_today+self.contracts["revenue_today"])

    @property
    def daily_expenses(self):
        return sum(self.expenses_today)+self.egg_expenses_today+self.other_expenses_today+self.tolls_today

    @property
    def daily_net_profit(self):
        return self.daily_revenue-self.daily_expenses

    def settle_day(self, day, *, pay_daily_dividends=True):
        if day <= self.last_tax_day:
            return
        dividends = settle_exchange(self, day, pay_daily_dividends=pay_daily_dividends)
        profit = self.daily_net_profit
        rate = innovation.tax_rate(self, DAILY_TAX_PERCENT)
        tax = (max(0, profit)*rate+50)//100
        self.last_day_summary = {
            "day": day, "revenue": self.daily_revenue, "expenses": self.daily_expenses,
            "profit": profit, "tax": tax, "net_profit": profit-tax,
            "tolls": self.tolls_today, "crossings": self.toll_count_today,
            "dividends": dividends,
            "tax_rate": rate,
        }
        self.cash -= tax
        self.taxes_paid_total += tax
        self.last_tax_day = day
        self.notice = f"Dia {day} fechado · Lucro ${profit} · Imposto ({rate}%) ${tax}"
        if dividends:
            self.notice += f" · Dividendos ${dividends}"
        self.notice_until = self.elapsed+6

    def sync_market(self, elapsed):
        previous_day = self.day
        self.market_elapsed = max(self.market_elapsed, elapsed)
        if self.day == previous_day:
            return
        self.settle_day(previous_day, pay_daily_dividends=self.day == previous_day + 1)
        businesses.reset_day(self)
        contracts.reset_day(self)
        innovation.reset_day(self)
        self.tourist_buyers = new_tourist_pools(SITES)
        self.costs = [trade.cost for trade in TRADES]
        self.prices = [trade.price for trade in TRADES]
        self.demand = [trade.demand for trade in TRADES]
        # Daily demand fluctuates, with occasional spikes. Unsold inventory weighs
        # on prices while unusually strong demand pushes them up sharply.
        for index, trade in enumerate(TRADES):
            demand_factor = 2.5 if random.random() < 0.12 else random.uniform(0.85, 1.15)
            today_demand = max(1, round(trade.demand * demand_factor))
            factory_stock = sum(factory["output"] for factory in self.logistics["factories"].values()
                                if factory["trade"] == index)
            shop_stock = sum(record["stock"] for record in self.businesses["owned"].values()
                             if record["role"] == "PUBLIC SHOP" and record["trade"] == index)
            available_supply = self.sales_today[index]+self.goods[index]+factory_stock+shop_stock
            price_factor = 1 + 0.6 * (today_demand / trade.demand - 1) - 0.5 * (available_supply / trade.demand)
            self.prices[index] = max(1, round(trade.price * max(0.4, min(2.5, price_factor))))
            self.demand[index] = today_demand
        tier2_demand = max(1, round(5 * (2.5 if random.random() < 0.12 else random.uniform(0.85, 1.15))))
        tier2_supply = self.tier2_sales_today + self.tier2_goods
        tier2_factor = 1 + 0.6 * (tier2_demand / 5 - 1) - 0.5 * (tier2_supply / 5)
        self.tier2_price = max(32, round(80 * max(0.4, min(2.5, tier2_factor))))
        self.tier2_demand = tier2_demand
        for role, recipe in INDUSTRIES.items():
            factor = 2.5 if random.random() < 0.12 else random.uniform(0.85, 1.15)
            demand = max(1, round(recipe.demand*factor))
            supply = self.industry_sales_today[role]+self.industry_goods[role]
            price_factor = 1+0.6*(demand/recipe.demand-1)-0.5*supply/recipe.demand
            self.industry_prices[role] = max(1, round(recipe.price*max(0.4, min(2.5, price_factor))))
            self.industry_demand[role] = demand
        self.industry_sales_today = {role: 0 for role in INDUSTRIES}
        self.industry_revenue_today = {role: 0 for role in INDUSTRIES}
        self.egg_expenses_today = 0
        self.sales_today = [0] * len(TRADES)
        self.revenue_today = [0] * len(TRADES)
        self.expenses_today = [0] * len(TRADES)
        self.tier2_sales_today = 0
        self.tier2_revenue_today = 0
        self.other_income_today = 0
        self.other_expenses_today = 0
        self.tolls_today = 0
        self.toll_count_today = 0
        self.market_event = None
        self.message = f"Day {self.day}. New customers have arrived at the markets."
        if self.day % 3 == 0:
            name, index, cost_change, price_change, demand_change = MARKET_EVENTS[
                (self.day // 3 - 1) % len(MARKET_EVENTS)
            ]
            self.costs[index] += cost_change
            self.prices[index] += price_change
            self.demand[index] += demand_change
            trade = TRADES[index]
            self.market_event = (
                name,
                f"{trade.supply} ${trade.cost} → ${self.costs[index]}   ·   "
                f"{trade.product} ${trade.price} → ${self.prices[index]}   ·   "
                f"Daily demand {trade.demand} → {self.demand[index]}",
            )
            self.message = f"Market event today. {name}."

    def tourism_for(self, site):
        return min(tourism_bonus(site), max(0, self.tourist_buyers.get(site.name, 0)))

    def buyers_for(self, site):
        site = self.business_site(site)
        if site.role == "PUBLIC SHOP":
            base = self.demand[site.trade]
        elif site.role == "PASTELARIA":
            base = self.industry_demand[site.role]
        else:
            return 0
        return base+self.tourism_for(site)

    def buyer_status(self, site):
        status = f"{self.buyers_for(site)} buyers"
        if tourism_bonus(site):
            status += f" (+{self.tourism_for(site)} tourists)"
        return status

    def _consume_buyers(self, site, quantity):
        site = self.business_site(site)
        if not 0 <= quantity <= self.buyers_for(site):
            raise ValueError("Sale exceeds remaining buyers")
        base = self.demand[site.trade] if site.role == "PUBLIC SHOP" else self.industry_demand[site.role]
        ordinary = min(base, quantity)
        if site.role == "PUBLIC SHOP":
            self.demand[site.trade] -= ordinary
        else:
            self.industry_demand[site.role] -= ordinary
        if quantity > ordinary:
            self.tourist_buyers[site.name] -= quantity-ordinary

    @property
    def cargo(self):
        return (sum(self.supplies)+sum(self.goods)+self.tier2_goods+self.eggs
                +sum(self.industry_goods.values())+innovation.cargo(self))

    @property
    def reserved(self):
        return sum(order.quantity for order in self.orders if order is not None) + (
            self.tier2_order.quantity if self.tier2_order is not None else 0
        ) + sum(order.quantity for role, order in self.industry_orders.items()
                if order is not None and not INDUSTRIES[role].service) + innovation.reserved(self) + businesses.reserved(self)

    @property
    def carry_capacity(self):
        vehicle = VEHICLES.get(self.vehicle)
        return self.bag_size+(vehicle.trunk if vehicle else 0)

    @property
    def road_bonus_active(self):
        return self.vehicle in VEHICLES and on_road(self.x, self.y, COLLISION_BOUNDS)

    @property
    def movement_speed(self):
        vehicle = VEHICLES.get(self.vehicle)
        paved = self.road_bonus_active if vehicle else False
        speed = WALK_SPEED if vehicle is None else (vehicle.road_speed if paved else vehicle.offroad_speed)
        road_bonus = contracts.road_multiplier(self)
        if road_bonus > 1 and (paved or vehicle is None and on_road(self.x, self.y, COLLISION_BOUNDS)):
            speed *= road_bonus
        return speed*(1.5 if self.elapsed < self.speed_until else 1)

    def purchase_vehicle(self, vehicle):
        ride = VEHICLES.get(vehicle)
        if ride is None:
            self.message = "Choose a motorcycle, car, delivery van or F1 car at the garage."
            return False
        if self.vehicle == vehicle:
            self.message = f"You already own this {ride.label.lower()}."
            return False
        capacity = self.bag_size+ride.trunk
        if self.cargo+self.reserved > capacity:
            self.message = f"This ride carries {capacity} items. Unload cargo or finish reserved orders before switching."
            return False
        owned = vehicle in self.owned_vehicles or vehicle == self.stowed_vehicle
        if not owned and self.cash < ride.price:
            self.message = f"You need ${ride.price:,} for the {ride.label.lower()}."
            return False
        if self.vehicle and self.vehicle not in self.owned_vehicles:
            self.owned_vehicles.append(self.vehicle)
        if self.stowed_vehicle and self.stowed_vehicle not in self.owned_vehicles:
            self.owned_vehicles.append(self.stowed_vehicle)
        if not owned:
            self.cash -= ride.price
            self.other_expenses_today += ride.price
            self.owned_vehicles.append(vehicle)
        self.vehicle = vehicle
        self.stowed_vehicle = None
        outcome = "Retrieved" if owned else "Bought"
        cost = "for free" if owned else f"for ${ride.price:,}"
        self.message = f"{outcome} {ride.label.lower()} {cost} · {self.carry_capacity} cargo slots · {ride.road_speed} road speed."
        return True

    def leave_vehicle(self):
        """Store the ride for free collection at a garage without discarding cargo."""
        if self.vehicle is None:
            self.message = "You are already walking."
            return False
        if self.cargo + self.reserved > self.bag_size:
            self.message = f"Unload cargo or finish reserved orders first. Your walking bag holds {self.bag_size} items."
            return False
        from vehicles import in_tunnel
        if in_tunnel(self.x, self.y) or self.bridge_journey:
            self.message = "Leave the bridge or tunnel before getting out."
            return False
        vehicle = self.vehicle
        self.vehicle = None
        if not self.can_walk(self.x, self.y):
            self.vehicle = vehicle
            self.message = "You cannot walk here. Drive off the bridge before leaving your vehicle."
            return False
        if vehicle not in self.owned_vehicles:
            self.owned_vehicles.append(vehicle)
        self.stowed_vehicle = vehicle
        self.bridge_journey = None
        self.message = "You are now walking. Collect your owned vehicle for free at any garage."
        return True

    def advance(self, seconds):
        previous_spawn = int(self.elapsed // POWER_INTERVAL)
        self.elapsed += seconds
        spawn = int(self.elapsed // POWER_INTERVAL)
        if spawn != previous_spawn:
            self.power_up = (spawn - 1) % len(POWER_UPS)
        self.collect_power_up()

    def collect_power_up(self):
        if self.power_up is None:
            return
        _, _, _, x, y = POWER_UPS[self.power_up]
        if math.hypot(self.x - x, self.y - y) > 23:
            return
        if self.power_up == 0:
            self.bag_size += 4
            self.message = f"Bag upgrade collected · Personal storage {self.bag_size} · Total cargo {self.carry_capacity}."
        elif self.power_up == 1:
            self.speed_until = self.elapsed + 15
            self.message = "Speed boost collected. Move 50% faster for 15 seconds."
        else:
            self.message = "Cash bonus collected. You earned $30."
            self.add_cash(30)
        self.power_up = None

    def add_cash(self, amount, business=False):
        self.cash += amount
        if self.cash >= 2000:
            self.final_goal_reached = True
        if not business:
            self.other_income_today += amount
        if self.cash >= CASH_GOAL and not self.won:
            self.won = True
            self.message = f"Goal reached on Day {self.day}! Keep trading to grow your business."

    def move(self, dx, dy, seconds, *, roads_only=False):
        old_y = self.y
        length = math.hypot(dx, dy)
        if not length:
            return
        if dx:
            self.facing = 1 if dx > 0 else -1
        speed = self.movement_speed
        distance = speed * seconds / length
        next_x = min(WORLD_WIDTH - 17, max(17, self.x + dx * distance))
        next_y = min(WORLD_BOTTOM - 15, max(MAP_TOP + 15, self.y + dy * distance))
        if self.can_walk(next_x, self.y, roads_only=roads_only):
            self.x = next_x
        if self.toll_blocks(next_y):
            self.message = (f"The portagem toward Lisboa costs ${BRIDGE_TOLL}. "
                            "You need more cash to cross the bridge.")
        elif self.can_walk(self.x, next_y, roads_only=roads_only):
            self.y = next_y
        elif (self.vehicle is None and RIVER_TOP-PLAYER_RADIUS < next_y < RIVER_BOTTOM+PLAYER_RADIUS
              and bridge_at(self.x, next_y, PLAYER_RADIUS)):
            # The bridges only carry vehicles; walkers take the ferry.
            from ferry import FERRY_FARE
            self.message = (f"The bridges are for vehicles only. On foot, take the ferry at Cais do Sodré "
                            f"or Cacilhas (${FERRY_FARE}), or buy a vehicle at a garage.")
        self.check_bridge_crossing(old_y)
        self.collect_power_up()

    def toll_blocks(self, next_y):
        """Driving onto a bridge from Almada needs the toll in cash before you start."""
        south = RIVER_BOTTOM+PLAYER_RADIUS
        return (self.vehicle is not None and self.bridge_journey is None and self.cash < BRIDGE_TOLL
                and self.y >= south > next_y and bridge_at(self.x, next_y, PLAYER_RADIUS) is not None)

    def check_bridge_crossing(self, old_y):
        north, south = RIVER_TOP-PLAYER_RADIUS, RIVER_BOTTOM+PLAYER_RADIUS
        if self.bridge_journey is None:
            origin = "south" if old_y >= south and self.y < south else (
                "north" if old_y <= north and self.y > north else None
            )
            bridge = bridge_at(self.x, self.y, PLAYER_RADIUS)
            if origin and bridge:
                self.bridge_journey = {"origin": origin, "bridge": bridge}
        if self.bridge_journey is None:
            return
        if self.y <= north:
            if self.bridge_journey["origin"] == "south":
                name = self.bridge_journey["bridge"]
                self.cash -= BRIDGE_TOLL
                self.tolls_today += BRIDGE_TOLL
                self.tolls_paid_total += BRIDGE_TOLL
                self.toll_count_today += 1
                self.message = f"Portagem · Ponte {name} → Lisboa: -${BRIDGE_TOLL}."
                self.notice = self.message
                self.notice_until = self.elapsed+4
            self.bridge_journey = None
        elif self.y >= south:
            self.bridge_journey = None

    def can_walk(self, x, y, *, roads_only=False):
        from lisbon_scene import vehicle_park_blocked
        if self.vehicle and (
            vehicle_park_blocked(x, y, PLAYER_RADIUS)
            or roads_only and not on_road(x, y)
        ):
            return False
        return (PLAYER_RADIUS <= x <= WORLD_WIDTH-PLAYER_RADIUS and MAP_TOP+PLAYER_RADIUS <= y <= WORLD_BOTTOM-PLAYER_RADIUS
                and walkable_terrain(x, y, PLAYER_RADIUS, on_foot=self.vehicle is None)) and not any(
            left - PLAYER_RADIUS < x < right + PLAYER_RADIUS
            and top - PLAYER_RADIUS < y < bottom + PLAYER_RADIUS
            for left, top, right, bottom in COLLISION_BOUNDS
        )

    def nearby(self):
        for site in SITES:
            x, y = site.door
            if math.hypot(self.x - x, self.y - y) <= REACH:
                return site
        return None

    def interact(self, bulk=False):
        site = self.nearby()
        if site is None:
            self.message = "Walk up to a marked entrance to trade."
            return
        site = self.business_site(site)
        self.discover_recipe(recipe_key_for_site(site))
        if site.role == "PUBLIC SHOP" and businesses.is_owned(self, site):
            self.stock_business(site.name)
            return
        if site.role == "FACTORY" and businesses.is_owned(self, site):
            record = businesses.record_for(self, site)
            order = record["manual_order"]
            automated = self.logistics["factories"][site.name]
            if automated["output"] and (
                    order is None and not self.supplies[site.trade]
                    or order is not None and self.elapsed < order["ready_at"]):
                self.collect_delivery_products(site.name)
            else:
                businesses.operate_factory(self, site, TRADES[site.trade].seconds)
            return
        if site.role == "CASINO":
            self.message = "Welcome to the Foundry Casino. Place your bets!"
            return
        if site.role == "GARAGE":
            self.message = "Motorworks Garage · E to browse motorcycles, cars, vans and F1 cars."
            return
        if site.role == "WAREHOUSE":
            self.message = "Foundry Warehouse · E to expand your carrying capacity."
            return
        if site.role == "EXCHANGE":
            self.message = "Bolsa de Lisboa · E to buy or sell district and infrastructure shares."
            return
        if site.role == "RESEARCH":
            self.message = "Nova SBE · Carcavelos · Foundry Town presentation."
            return
        if site.role in INDUSTRIES:
            self.interact_industry(site.role)
            return
        if site.role == "TIER2":
            order = self.tier2_order
            if order is not None:
                if self.elapsed < order.ready_at:
                    self.message = "Precision Works production is still running."
                    return
                space = max(0, self.carry_capacity-self.cargo)
                if not space:
                    self.message = "Free up space in your bag before collecting your order."
                    return
                quantity = min(space, order.quantity)
                self.tier2_goods += quantity
                order.quantity -= quantity
                if not order.quantity:
                    self.tier2_order = None
                self.message = f"Collected {quantity} × Precision Machinery. Sell it here."
                self.congratulate(quantity, "precision machinery")
                return
            if self.tier2_goods:
                quantity = min(self.tier2_goods, self.tier2_demand)
                if not quantity:
                    self.message = "Today's customers are served. Come back tomorrow."
                    return
                revenue = quantity * self.tier2_price
                self.tier2_goods -= quantity
                self.tier2_demand -= quantity
                self.tier2_sales_today += quantity
                self.tier2_total_sold += quantity
                self.tier2_revenue_today += revenue
                self.message = f"Sold {quantity} × Precision Machinery for ${revenue}."
                self.congratulate(quantity, "precision machinery", action="sold")
                record_trade(self, site, quantity)
                self.add_cash(revenue, business=True)
                return
            quantity = min(self.goods[0], self.goods[1])
            if not quantity:
                self.message = "Bring Tools and Furniture to craft Precision Machinery."
                return
            self.goods[0] -= quantity
            self.goods[1] -= quantity
            self.tier2_order = Order(quantity, self.elapsed + 12)
            self.message = f"Crafting {quantity} × Precision Machinery. Ready in 12s."
            return
        index = site.trade
        trade = TRADES[index]
        space = max(0, self.carry_capacity-self.cargo)
        if site.role == "SUPPLIER":
            space = max(0, space-self.reserved)
            quantity = max(0, min(4 if bulk else 1, space, self.cash // self.costs[index]))
            if not quantity:
                if not space and self.reserved:
                    self.message = "Bag space is reserved for your factory orders."
                else:
                    self.message = "Your bag is full." if not space else "You need more cash for supplies."
                return
            cost = quantity * self.costs[index]
            self.cash -= cost
            self.expenses_today[index] += cost
            self.supplies[index] += quantity
            self.message = (f"You now carry {self.supplies[index]} × {trade.supply}. "
                            f"Bought {quantity} for ${cost}.")
            self.congratulate(quantity, trade.supply.lower())
        elif site.role == "FACTORY":
            order = self.orders[index]
            automated = self.logistics["factories"].get(site.name, {})
            if automated.get("output", 0) and (
                    (order is None and not self.supplies[index])
                    or (order is not None and self.elapsed < order.ready_at)):
                self.collect_delivery_products(site.name)
                return
            if order is None:
                quantity = self.supplies[index]
                if not quantity:
                    self.message = f"Bring {trade.supply.lower()} to start production."
                    return
                self.supplies[index] = 0
                self.orders[index] = Order(quantity, self.elapsed + trade.seconds)
                self.message = f"Dropped off {quantity} × {trade.supply}. Ready in {trade.seconds}s."
            elif self.elapsed < order.ready_at:
                self.message = "Production is still running. Come back when the order is ready."
            elif not space:
                self.message = "Free up space in your bag before collecting your order."
            else:
                quantity = min(space, order.quantity)
                self.goods[index] += quantity
                order.quantity -= quantity
                if not order.quantity:
                    self.orders[index] = None
                self.message = f"Collected {quantity} × {trade.product}. Take them to the public shop."
                self.congratulate(quantity, trade.product.lower())
        else:
            quantity = min(self.goods[index], self.buyers_for(site))
            if not quantity:
                self.message = (
                    f"Bring {trade.product.lower()} to sell." if not self.goods[index]
                    else "Today's customers are served. Come back tomorrow."
                )
                return
            revenue = quantity * self.prices[index]
            self.goods[index] -= quantity
            self._consume_buyers(site, quantity)
            self.sales_today[index] += quantity
            self.total_sold[index] += quantity
            self.revenue_today[index] += revenue
            self.message = f"Sold {quantity} × {trade.product} to customers for ${revenue}."
            self.congratulate(quantity, trade.product.lower(), action="sold")
            record_trade(self, site, quantity)
            self.add_cash(revenue, business=True)

    def buy_eggs(self, bulk=False):
        site = self.nearby()
        if site is None or site.role != "SUPPLIER" or site.trade != 3:
            self.message = "Buy eggs at Goldenfield Farm in Marvila or Quinta de Palmela."
            return
        space = max(0, self.carry_capacity-self.cargo-self.reserved)
        quantity = max(0, min(4 if bulk else 1, space, self.cash//EGG_COST))
        if not quantity:
            self.message = "Your bag is full or reserved for orders." if not space else "You need more cash for eggs."
            return
        cost = quantity*EGG_COST
        self.cash -= cost
        self.eggs += quantity
        self.egg_expenses_today += cost
        self.message = f"Bought {quantity} × Eggs for ${cost}. Take eggs and wheat to Pastéis de Belém."

    def material_amount(self, name):
        return self.eggs if name == "Eggs" else self.supplies[MATERIAL_ROUTES[name]]

    def interact_industry(self, role):
        self.discover_recipe(next((recipe.key for recipe in RECIPE_BY_KEY.values() if recipe.role == role), None))
        recipe = INDUSTRIES[role]
        order = self.industry_orders[role]
        if order is not None:
            if self.elapsed < order.ready_at:
                self.message = f"{recipe.product}: work in progress. Ready in {math.ceil(order.ready_at-self.elapsed)}s."
                return
            if recipe.service:
                revenue = order.quantity*self.shipyard_quote
                self.industry_sales_today[role] += order.quantity
                self.industry_total_sold[role] += order.quantity
                self.industry_revenue_today[role] += revenue
                self.industry_orders[role] = None
                self.shipyard_quote = 0
                self.message = f"Boat repaired and returned to its owner. You received ${revenue}."
                record_trade(self, next(site for site in SITES if site.role == role), order.quantity)
                self.add_cash(revenue, business=True)
                return
            space = max(0, self.carry_capacity-self.cargo)
            if not space:
                self.message = "Free bag space before collecting your pastéis."
                return
            quantity = min(space, order.quantity)
            self.industry_goods[role] += quantity
            order.quantity -= quantity
            if not order.quantity:
                self.industry_orders[role] = None
            self.message = f"Collected {quantity} × Pastéis. Press E again here to sell them."
            self.congratulate(quantity, "pastéis")
            return
        if not recipe.service and self.industry_goods[role]:
            nearby = self.nearby()
            shop = nearby if nearby is not None and nearby.role == role else next(site for site in SITES if site.role == role)
            quantity = min(self.industry_goods[role], self.buyers_for(shop))
            if not quantity:
                self.message = "Today's pastry customers are served. Come back tomorrow."
                return
            revenue = quantity*self.industry_prices[role]
            self.industry_goods[role] -= quantity
            self._consume_buyers(shop, quantity)
            self.industry_sales_today[role] += quantity
            self.industry_total_sold[role] += quantity
            self.industry_revenue_today[role] += revenue
            self.message = f"Sold {quantity} × Pastéis for ${revenue}."
            record_trade(self, shop, quantity)
            self.add_cash(revenue, business=True)
            return
        if recipe.service and not self.industry_demand[role]:
            self.message = "No boat repair contracts remain today. Come back tomorrow."
            return
        quantity = min(self.material_amount(name)//amount for name, amount in recipe.ingredients)
        if not quantity:
            ingredients = " + ".join(f"{amount} {name}" for name, amount in recipe.ingredients)
            self.message = f"Bring {ingredients} to start {recipe.product.lower()}."
            return
        if recipe.service:
            quantity = 1
            self.industry_demand[role] -= 1
            self.shipyard_quote = self.industry_prices[role]
        for name, amount in recipe.ingredients:
            if name == "Eggs":
                self.eggs -= quantity*amount
            else:
                self.supplies[MATERIAL_ROUTES[name]] -= quantity*amount
        self.industry_orders[role] = Order(quantity, self.elapsed+recipe.seconds)
        if recipe.service:
            self.message = f"Repair started with 2 Timber + 2 Iron ore. Ready in {recipe.seconds}s · Payment ${self.shipyard_quote}."
        else:
            self.message = f"Baking {quantity} × Pastéis with Wheat + Eggs. Ready in {recipe.seconds}s."

    @property
    def casino_luck(self):
        return min(self.monastery_visits, 4) * 5

    def visit_monastery(self):
        self.monastery_visits = min(self.monastery_visits + 1, 4)
        self.message = f"Monastery visited · Casino odds +{self.casino_luck}%."

    def roulette_pocket(self, choice):
        winners = [index for index, number in enumerate(ROULETTE_POCKETS)
                   if roulette_color(number) == choice]
        losers = [index for index, number in enumerate(ROULETTE_POCKETS)
                  if roulette_color(number) != choice]
        # Luck scales each bet's own chance (+20 luck: red 48.6% -> 58.4%, green 2.7% -> 3.2%), so the
        # 36x green bet stays a long shot instead of becoming a sure profit.
        chance = len(winners) / len(ROULETTE_POCKETS) * (1 + self.casino_luck / 100)
        return random.choice(winners if random.random() < chance else losers)

    def bet_roulette(self, choice, stake, number):
        """Take a stake on red, black, or green and return the payout for `number`.

        The stake leaves the player's cash now. The caller adds the payout once the
        ball has landed, so the cash display does not give the result away early.
        """
        if choice not in ROULETTE_PAYOUTS:
            raise ValueError(f"Unknown roulette bet: {choice}")
        if not 0 < stake <= self.cash:
            return None
        self.cash -= stake
        self.other_expenses_today += stake
        return stake * ROULETTE_PAYOUTS[choice] if roulette_color(number) == choice else 0

    def site_status(self, site):
        if businesses.is_owned(self, site):
            site = self.business_site(site)
            record = businesses.record_for(self, site)
            product = TRADES[site.trade].product
            if site.role == "PUBLIC SHOP":
                return f"Owned · {product} ${businesses.sale_price(self, site)} · Stock {record['stock']}/{businesses.storage_capacity(self, site)} · B Manage"
            order = record["manual_order"]
            if order:
                progress = "E Collect" if order["ready_at"] <= self.elapsed else f"{math.ceil(order['ready_at']-self.elapsed)}s"
                return f"Owned · {product} × {order['quantity']} · {progress} · B Manage"
            factory = self.logistics["factories"][site.name]
            return f"Owned · {TRADES[site.trade].supply} → {product} · {factory['output']} stored · B Manage"
        if site.role == "FACTORY" and self.orders[site.trade] is None and not self.supplies[site.trade]:
            factory = self.logistics["factories"].get(site.name, {})
            if factory.get("output", 0):
                return f"Auto: {factory['output']} ready · E Collect · L Deliveries"
            if factory.get("order"):
                order = factory["order"]
                return f"Auto: {order['quantity']} crafting · {math.ceil(order['remaining'])}s · L Deliveries"
            if factory.get("input", 0):
                return f"Auto: {factory['input']} raw materials stored · L Deliveries"
        if site.role == "RESEARCH":
            return "Foundry Town · Team presentation"
        if site.role == "EXCHANGE":
            shares = sum(self.exchange["holdings"].values())
            paid = sum(self.exchange["total_dividends"].values())
            return f"{shares} shares · Dividends ${paid}"
        if site.role in INDUSTRIES:
            role, recipe = site.role, INDUSTRIES[site.role]
            order = self.industry_orders[role]
            if order is not None:
                if self.elapsed >= order.ready_at:
                    return f"E · Claim ${self.shipyard_quote}" if recipe.service else f"E · Collect {order.quantity} pastéis"
                return f"{'Repairing boat' if recipe.service else 'Baking'} · {math.ceil(order.ready_at-self.elapsed)}s"
            if recipe.service:
                return f"2 Wood + 2 Ore · ${self.industry_prices[role]} · {self.industry_demand[role]} jobs"
            return f"Pastéis ${self.industry_prices[role]} · {self.buyer_status(site)}"
        if site.role == "CASINO":
            return "Roulette  ·  Win up to 36×"
        if site.role == "GARAGE":
            ride = VEHICLES.get(self.vehicle)
            return f"{ride.label} · {self.carry_capacity} cargo slots" if ride else "Cars & vans: bigger trunks + road speed"
        if site.role == "WAREHOUSE":
            return f"Personal storage {self.bag_size} · Total cargo {self.carry_capacity}"
        if site.role == "TIER2":
            if self.tier2_order:
                status = "Ready to collect" if self.tier2_order.ready_at <= self.elapsed else f"Crafting · {math.ceil(self.tier2_order.ready_at-self.elapsed)}s"
                return f"Tools + Furniture → Precision Machinery · {status}"
            if self.tier2_goods:
                return f"Precision Machinery · ${self.tier2_price} · {self.tier2_demand} buyers"
            return "Tools + Furniture → Precision Machinery"
        index = site.trade
        trade = TRADES[index]
        if site.role == "SUPPLIER":
            if site.trade == 3:
                return f"Wheat ${self.costs[index]} · Eggs ${EGG_COST} (F / R)"
            return f"${self.costs[index]} / {trade.supply.lower()}"
        if site.role == "PUBLIC SHOP":
            return f"${self.prices[index]} each  ·  {self.buyer_status(site)}"
        order = self.orders[index]
        if order is None:
            return f"{trade.supply} → {trade.product}"
        if order.ready_at <= self.elapsed:
            return f"Ready for pickup  ·  {order.quantity}"
        return f"In production  ·  {math.ceil(order.ready_at - self.elapsed)}s"

    def action_hint(self, site):
        if businesses.is_owned(self, site):
            if site.role == "PUBLIC SHOP":
                return "E  Stock your shop for customer sales    B  Manage / withdraw / sell carried goods"
            return "E  Drop off materials / collect factory products    B  Upgrade / specialize business"
        if site.role == "FACTORY" and self.logistics["factories"].get(site.name, {}).get("output", 0):
            return "E  Collect automatic output / process personal supplies    L  Manage deliveries"
        if site.role == "RESEARCH":
            return "E  Nova SBE · Watch the team present Foundry Town"
        if site.role == "EXCHANGE":
            return "E  Trade district / infrastructure shares and view dividends"
        if site.role == "PASTELARIA":
            return "E  Bake, collect or sell · 1 Wheat + 1 Egg = 1 Pastel"
        if site.role == "SHIPYARD":
            return "E  Start repair or collect payment · 2 Timber + 2 Iron ore"
        if site.role == "CASINO":
            return "E  Play roulette"
        if site.role == "GARAGE":
            return "E  Browse vehicles"
        if site.role == "WAREHOUSE":
            return "E  Buy more storage"
        if site.role == "TIER2":
            return "E  Craft, collect, or sell"
        if site.role == "SUPPLIER":
            if site.trade == 3:
                return "E / Q  Buy Wheat (1 / 4)    F / R  Buy Eggs (1 / 4)"
            return "E  Buy one    •    Q  Buy up to four"
        if site.role == "PUBLIC SHOP":
            return "E  Sell to today's customers"
        order = self.orders[site.trade]
        if order is None:
            return "E  Drop off matching supplies"
        if order.ready_at <= self.elapsed:
            return "E  Collect finished goods"
        return "Production running"

def pack_save(town, market_started_at):
    state = deepcopy(vars(town))
    state["orders"] = [asdict(order) if order else None for order in town.orders]
    state["tier2_order"] = asdict(town.tier2_order) if town.tier2_order else None
    state["industry_orders"] = {role: asdict(order) if order else None for role, order in town.industry_orders.items()}
    return {"version": 1, "dayLength": DAY_SECONDS, "marketStart": market_started_at, "state": state}

def unpack_save(data):
    town = Town()
    state = dict(data["state"])
    previous_day_length = data.get("dayLength", LEGACY_DAY_SECONDS)
    old_market_elapsed = state.get("market_elapsed", 0)
    if previous_day_length != DAY_SECONDS:
        completed_days, day_progress = divmod(old_market_elapsed, previous_day_length)
        state["market_elapsed"] = completed_days * DAY_SECONDS + day_progress * DAY_SECONDS / previous_day_length
        data = dict(data)
        data["marketStart"] = time.time() - state["market_elapsed"]
    for name in ("sales_today", "revenue_today", "expenses_today", "total_sold"):
        state.setdefault(name, [0] * len(TRADES))
    state.setdefault("vehicle", None)
    state.setdefault("owned_vehicles", [])
    owned = state["owned_vehicles"]
    if (not isinstance(owned, list) or any(not isinstance(key, str) or key not in VEHICLES for key in owned)
            or len(set(owned)) != len(owned)
            or state["vehicle"] is not None and (not isinstance(state["vehicle"], str) or state["vehicle"] not in VEHICLES)):
        raise ValueError("Invalid owned vehicles in save")
    if state["vehicle"] and state["vehicle"] not in owned:
        state["owned_vehicles"] = [*owned, state["vehicle"]]
    state.setdefault("stowed_vehicle", None)
    stowed = state["stowed_vehicle"]
    if stowed is not None and (not isinstance(stowed, str) or stowed not in VEHICLES or state["vehicle"] is not None):
        raise ValueError("Invalid stowed vehicle in save")
    if stowed and stowed not in state["owned_vehicles"]:
        state["owned_vehicles"] = [*state["owned_vehicles"], stowed]
    state.setdefault("warehouse_level", 0)
    state.setdefault("tier2_order", None)
    state.setdefault("tier2_goods", 0)
    state.setdefault("tier2_demand", 5)
    state.setdefault("tier2_price", 80)
    state.setdefault("tier2_sales_today", 0)
    state.setdefault("tier2_revenue_today", 0)
    state.setdefault("tier2_total_sold", 0)
    for name in ("eggs", "egg_expenses_today", "industry_orders", "industry_goods", "industry_demand",
                 "industry_prices", "industry_sales_today", "industry_revenue_today", "industry_total_sold", "shipyard_quote",
                 "other_income_today", "other_expenses_today", "tolls_today", "toll_count_today", "tolls_paid_total",
                 "taxes_paid_total", "last_tax_day", "last_day_summary", "bridge_journey", "tourist_buyers"):
        state.setdefault(name, deepcopy(getattr(town, name)))
    if "discovered_recipes" not in state:
        state["discovered_recipes"] = infer_discoveries(state)
    state["discovered_recipes"] = normalize_discoveries(state["discovered_recipes"])
    state["exchange"] = normalize_exchange_state(state.get("exchange"))
    state["innovation"] = innovation.normalize_state(state.get("innovation"))
    state["businesses"] = businesses.normalize_state(state.get("businesses"), SITES)
    state["logistics"] = logistics.normalize_state(state.get("logistics"), SITES, businesses_state=state["businesses"])
    state["contracts"] = contracts.normalize_state(state.get("contracts"))
    state.setdefault("milestone_acknowledged", False)
    state.setdefault("level_notices", 2 if state["milestone_acknowledged"] else 0)
    state.setdefault("final_goal_reached", state["cash"] >= 2000)
    if type(state["level_notices"]) is not int or not 0 <= state["level_notices"] <= 3:
        raise ValueError("Invalid level progress in save")
    if type(state["final_goal_reached"]) is not bool:
        raise ValueError("Invalid final level state in save")
    state.setdefault("monastery_visits", 0)
    if type(state["monastery_visits"]) is not int or not 0 <= state["monastery_visits"] <= 4:
        raise ValueError("Invalid monastery visit bonus in save")
    if type(state["milestone_acknowledged"]) is not bool:
        raise ValueError("Invalid cash milestone state in save")
    if data["version"] != 1 or state.keys() != vars(town).keys():
        raise ValueError("Unsupported Foundry Town save")
    pools = state["tourist_buyers"]
    if not isinstance(pools, dict):
        raise ValueError("Invalid tourist buyers in save")
    normalized_pools = {}
    for name, maximum in town.tourist_buyers.items():
        remaining = pools.get(name, maximum)
        if type(remaining) is not int or not 0 <= remaining <= maximum:
            raise ValueError("Invalid tourist buyer count in save")
        normalized_pools[name] = remaining
    state["tourist_buyers"] = normalized_pools
    for name in ("supplies", "goods", "orders", "demand", "costs", "prices"):
        if len(state[name]) != len(TRADES):
            raise ValueError("Invalid trade data in save")
    state["orders"] = [Order(**order) if order is not None else None for order in state["orders"]]
    if state["tier2_order"] is not None:
        state["tier2_order"] = Order(**state["tier2_order"])
    for name in ("industry_orders", "industry_goods", "industry_demand", "industry_prices",
                 "industry_sales_today", "industry_revenue_today", "industry_total_sold"):
        if state[name].keys() != INDUSTRIES.keys():
            raise ValueError("Invalid local industry data in save")
    state["industry_orders"] = {role: Order(**order) if order is not None else None for role, order in state["industry_orders"].items()}
    vars(town).update(state)
    if not town.can_walk(town.x, town.y):
        town.x, town.y = 480.0, 321.0
        town.bridge_journey = None
    return town, float(data["marketStart"])
