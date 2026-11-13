"""Foundry Town, a small business tycoon built with Tkinter."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import asdict, dataclass
import math
from pathlib import Path
import random
import sys
import time
import tkinter as tk
from tkinter import messagebox

from saves import RemoteSaves, SaveConflict, desktop_storage
from lisbon_scene import LisbonScene, MAP_BOTTOM, WORLD_WIDTH, WORLD_BOTTOM, SCENERY_BLOCKS, RIVER_TOP, RIVER_BOTTOM, BRIDGE_TOLL, bridge_at, draw_character, walkable_terrain
from soundtrack import music_for
from living_world import LivingWorld
from journal_recipes import RECIPE_BY_KEY, infer_discoveries, normalize_discoveries, recipe_key_for_site
from lisbon_landmarks import LANDMARK_SOLIDS
from vehicles import VEHICLES, WALK_SPEED, on_road
from tourism import new_tourist_pools, tourism_bonus
from exchange import (initial_state as new_exchange_state, normalize_state as normalize_exchange_state,
                      advance_city, record_trade, record_bridge, settle_exchange)
import innovation
import logistics
import contracts
import businesses


WIDTH = 1200
MAP_TOP = 104
HEIGHT = MAP_BOTTOM + 95
DAY_SECONDS = 5 * 60
DAYLIGHT_SECONDS = 3 * 60
NIGHT_SECONDS = 2 * 60
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
IS_MAC = sys.platform == "darwin"
FONT = "Helvetica Neue" if IS_MAC else "Segoe UI"
# Tk on macOS draws 1 pixel per point, while Windows draws 96/72 pixels per point.
# Sizing text in pixels on macOS keeps the layout the same as on Windows.
FONT_PIXELS_PER_POINT = 96 / 72
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
RULES_TEXT = (
    "MOVE  ·  WASD or arrow keys\n"
    "INTERACT  ·  Walk to a colored entrance and press E\n"
    "BULK BUY  ·  Press Q at a supplier to buy up to four supplies\n\n"
    "PRODUCTION\n"
    "Buy Iron ore, Timber, Clay, or Wheat from a supplier. Drop it off at its matching factory, "
    "wait for production, and return to collect the finished goods. Sell goods at the matching public market.\n\n"
    "TIER 2 FACTORY\n"
    "Foundry Precision Works combines 1 Tool and 1 Furniture into 1 Precision Machinery. "
    "Wait 12 seconds, collect it, then interact again to sell it at the factory. It is in Almada, across either bridge.\n\n"
    "BELÉM & THE SHIPYARD\n"
    "At Goldenfield Farm, E/Q buys Wheat (1/4) and F/R buys Eggs (1/4), at $2 per egg. "
    "Pastéis de Belém combines 1 Wheat + 1 Egg into 1 Pastel in 8 seconds. Collect and sell it there (base price $24). "
    "Estaleiro do Tejo in Almada uses 2 Timber + 2 Iron ore for a 20-second boat repair (base payment $100). "
    "Return to claim the agreed payment. Iron Hill Mine is now on the Almada bank.\n\n"
    "LISBOA\n"
    "Cross the Tejo using Ponte 25 de Abril or Ponte Vasco da Gama. The yellow elétrico travels along the north bank. "
    "Visit Mosteiro dos Jerónimos, Castelo de São Jorge, Torre de Belém and Praça do Comércio. "
    "Building signs follow 1 BUY RAW MATERIALS → 2 MAKE PRODUCTS → 3 SELL PRODUCTS. "
    "Open Places (P) to see recipes and locations, then choose Guide me here for a destination marker. "
    "Press J or click Journal to track recipes you have discovered, read landmark and Tejo history, "
    "and check current market stock, orders, prices and buyers. Talk to a production building with E to record its recipe. "
    "Click the gold Settings button or press F1 for fullscreen, music, and help.\n\n"
    "LIVING WORLD\n"
    "Explore Marvila, Parque das Nações, Cacilhas and Seixal in a 2400 × 1600 world. The camera follows you. "
    "M toggles the minimap; Settings offers three camera zoom levels and ambient animation controls. "
    "New markets, depots, a farm, a garage and a warehouse share the town's existing prices, demand and upgrades.\n\n"
    "TOURISM & TRANSPORT\n"
    "Monuments attract extra local shoppers each day: Jerónimos and Torre de Belém help Pastéis, "
    "Praça do Comércio helps bread, pottery and tools, and Castelo adds pottery buyers. "
    "Their remaining tourist buyers save and reset with each new day. "
    "At a garage, motorcycles cost $120 (+6 trunk slots), cars $240 (+48) and vans $360 (+108). "
    "Trunks combine with personal and warehouse storage, and vehicles get a speed bonus on paved roads. "
    "Walk to a yellow TRAM stop, press E and pay $3 for express travel to another Lisbon district. "
    "Your cargo and vehicle remain available after the trip.\n\n"
    "STOCK EXCHANGE\n"
    "Visit Bolsa de Lisboa in Baixa-Chiado and press E to buy or sell district and infrastructure shares. "
    "City trade, paid 25 de Abril returns and tram journeys earn dividend credits for shares you already hold. "
    "The wider city also records simulated activity every 10 active seconds, including while the exchange is open. "
    "Whole-dollar dividends are paid per investment at day close and included in taxable profit; fractional credits carry over. "
    "Share capital is separate from operating expenses; only realized gains or losses affect profit. "
    "Sale quotes include a 10% spread. Offline time creates no new city activity.\n\n"
    "NOVA SBE · CARCAVELOS · INOVAÇÃO\n"
    "Find the waterfront university in Places → Services and press E at its entrance. "
    "Spend cash and active play time on one research project at a time. Green Energy has three levels, "
    "reducing profit tax from 20% to 18%, 15% and 10%. Advanced Metallurgy unlocks Alloy Components, "
    "Precision Turbines and Smart Tram Assemblies in order. The campus workshop shows each recipe's "
    "inputs, production time and current buyers; fabricate, collect and sell there. Research and workshop "
    "timers continue while focused menus are open, save between sessions, and do not advance offline.\n\n"
    "AUTOMATED DELIVERIES\n"
    "Click Deliveries or press L to buy and assign a delivery van ($320, 6 items) or drone ($600, 3 items). "
    "Choose a raw-material supplier and a factory that uses that material: Goldenfield Farm → Sunrise Bakery "
    "for Wheat, Pine Mill or Marvila Timber Depot → Oak Workshop for Timber. Each departure buys materials "
    "at current prices and charges a $1 van / $2 drone operating fee. Vans follow roads and pay normal "
    "northbound bridge tolls; drones fly directly. Factories automatically process deliveries into their own "
    "storage, separate from your bag. Visit the factory and press E to collect output, then sell at a market. "
    "Personal supplies and finished manual orders take priority when interacting. Routes wait when funds "
    "or storage run out. Pausing stops new departures; paid loads finish their trip. "
    "Fleet, cargo and factory timers save and run only during focused play.\n\n"
    "CONTRACTS & CITY PROJECTS\n"
    "Click Contracts or press C to accept timed orders. Up to three orders can be active, including city projects. "
    "Choose Guide to client, carry the required finished products to the marked desk, then open C and deliver "
    "a quantity. Partial deliveries count toward the order; payment and reputation arrive when it is complete. "
    "Deadlines use focused play time, including open menus, and pause while closed or unfocused. "
    "Failed or abandoned orders keep deposited goods and pay no reward. Recurring offers rotate every five active minutes. "
    "Complete the festival, bridge and hotel projects for permanent extra cargo, faster road movement and cheaper research. "
    "Project upgrades can be earned once. Contracts, reputation, deliveries and deadlines save automatically.\n\n"
    "BUSINESS OWNERSHIP\n"
    "Click Businesses or press B to buy a standard factory ($600) or public shop ($450). Existing unowned "
    "businesses remain available for normal trading. Owned businesses can specialize in Tools, Furniture, Pottery "
    "or Bread. Three storage expansions raise building storage from 48 to 72, 96 and 120 items, separate from your bag. "
    "Factory equipment shortens new production times and increases automated batch size. Shop equipment improves "
    "checkout speed and selling prices. At your shop, E deposits goods; customers buy stocked goods every ten active "
    "seconds while buyers remain. B also offers withdrawals and immediate sales of carried goods when you visit. "
    "Collect or empty stock and orders before changing product. Use L to reassign idle, empty delivery vehicles for free "
    "before retooling a supplied factory. Paid loads cannot be reassigned. Ownership, equipment, specializations, "
    "shop stock and production save automatically; closed or unfocused games generate no retail sales.\n\n"
    "NIGHT, TAX & TOLLS\n"
    "Buildings and both bridges light up at night. At the end of each full day, tax starts at 20% of positive net profit "
    "(all income received minus purchases, upgrades, casino stakes and tolls). Loss-making days pay no tax. "
    "Each completed Almada-to-Lisbon bridge crossing costs $3, on foot or in a vehicle. Outbound crossings and halfway turnarounds are free.\n\n"
    "TOWN & GOAL\n"
    "Each day lasts 5 minutes: 3 minutes of daylight and 2 minutes of night. Prices and customer demand "
    "change daily. Reach $500 for the first milestone, then choose Continue building & researching to keep playing. "
    "Your progress saves automatically."
)


def configure_display_dpi():
    """Let Windows report physical monitor pixels before Tk creates a window."""
    if sys.platform != "win32":
        return
    import ctypes
    try:
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def show_rules(parent):
    panel = tk.Toplevel(parent)
    panel.title("Foundry Town · How to Play")
    panel.transient(parent)
    panel.resizable(False, False)
    frame = tk.Frame(panel, padx=24, pady=18)
    frame.pack(fill="both", expand=True)
    tk.Label(frame, text="RULES & HOW TO PLAY", font=(FONT, 17, "bold")).pack(anchor="w", pady=(0, 12))
    body = tk.Frame(frame)
    body.pack(fill="both", expand=True)
    scrollbar = tk.Scrollbar(body)
    scrollbar.pack(side="right", fill="y")
    rules = tk.Text(body, width=66, height=22, wrap="word", font=(FONT, 10),
                    relief="flat", padx=6, pady=6, yscrollcommand=scrollbar.set)
    rules.insert("1.0", RULES_TEXT)
    rules.configure(state="disabled")
    rules.pack(side="left", fill="both", expand=True)
    scrollbar.configure(command=rules.yview)
    close = tk.Button(frame, text="Close", command=panel.destroy)
    close.pack(anchor="e", pady=(16, 0))
    panel.bind("<Escape>", lambda event: panel.destroy())
    panel.protocol("WM_DELETE_WINDOW", panel.destroy)
    panel.grab_set()
    return panel


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

# Name, trade index, and changes to material cost, sale price, and daily demand.
MARKET_EVENTS = (
    ("Builders' boom", 0, 1, 5, 4),
    ("Timber surplus", 1, -2, -4, 3),
    ("Pottery fair", 2, 1, 6, 5),
    ("Harvest festival", 3, -1, 4, 6),
)

# A European roulette wheel: the 37 pockets in their real order, clockwise from 0.
ROULETTE_POCKETS = (
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10,
    5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26,
)
RED_NUMBERS = frozenset((1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36))
# Money returned for each $1 staked, including the stake, when the bet wins.
ROULETTE_PAYOUTS = {"red": 2, "black": 2, "green": 36}
CHIPS = (5, 10, 25, 50, 100)
SPIN_SECONDS = 4.5
# Casino screen layout, in map pixels. The ball circles the rim, then drops into a pocket.
CASINO_CENTER = (WIDTH // 2, 380)
CASINO_TRACK_RADIUS = 172
CASINO_POCKET_RADIUS = 122
PROFILE_X = WIDTH - 80
POCKET_COLORS = {"red": "#c8313c", "black": "#1b1d22", "green": "#1f8a4c"}


def roulette_color(number):
    if number == 0:
        return "green"
    return "red" if number in RED_NUMBERS else "black"


def market_start():
    marker = Path(__file__).with_name(".foundry-market-start")
    try:
        if not marker.exists():
            try:
                marker.touch(exist_ok=False)
            except FileExistsError:
                pass
        return marker.stat().st_mtime
    except OSError:
        return time.time()


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
    def door(self):
        return self.x + 88, self.y + 104


SITES = (
    Site("Iron Hill Mine", "SUPPLIER", 0, 1010, 935, "#d6a46e"),
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
    Site("Foundry Casino", "CASINO", -1, 988, 345, "#e8455a"),
    Site("Motorworks Garage", "GARAGE", -1, 988, 530, "#86caff"),
    Site("Foundry Warehouse", "WAREHOUSE", -1, 988, 160, "#d2a7e5"),
    Site("Pastéis de Belém", "PASTELARIA", -1, 28, 160, "#f1d69b"),
    Site("Estaleiro do Tejo", "SHIPYARD", -1, 380, 935, "#94bdc9"),
    Site("Marvila Timber Depot", "SUPPLIER", 1, 1280, 345, "#d6a46e"),
    Site("Oriente Tool Market", "PUBLIC SHOP", 0, 1820, 345, "#72d8bc"),
    Site("Mercado das Nações", "PUBLIC SHOP", 2, 2080, 530, "#d2a7e5"),
    Site("Quinta de Palmela", "SUPPLIER", 3, 2060, 1430, "#e3c77e"),
    Site("Cacilhas Garage", "GARAGE", -1, 1540, 1180, "#86caff"),
    Site("Armazém do Seixal", "WAREHOUSE", -1, 2060, 1180, "#d2a7e5"),
    Site("Bolsa de Lisboa", "EXCHANGE", -1, 508, 160, "#d7bb6e"),
    Site("Nova SBE · Carcavelos", "RESEARCH", -1, 28, 530, "#83bac9"),
    Site("Foundry Precision Works", "TIER2", -1, 650, 935, "#ffc66c"),
)
COLLISION_BOUNDS = tuple(site.bounds for site in SITES)+SCENERY_BLOCKS+LANDMARK_SOLIDS+((1780, 190, 2030, 260),)


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
        self.market_event = None
        self.elapsed = 0.0
        self.x, self.y = 480.0, 321.0
        self.facing = 1
        self.won = False
        self.milestone_acknowledged = False
        self.bag_size = BAG_SIZE
        self.warehouse_level = 0
        self.speed_until = 0
        self.power_up = None
        self.profile = {"name": "Player", "body": "Peach", "hair": "Chestnut", "costume": "Builder"}
        self.notice = ""
        self.notice_until = 0
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

    def congratulate(self, quantity, item):
        self.notice = f"Congratulations {self.profile['name']}, you just collect {quantity} {item}"
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

    def continue_after_milestone(self):
        if not self.won:
            return False
        self.milestone_acknowledged = True
        self.message = "Cash milestone complete! Visit Nova SBE in Carcavelos for research and tier-3 crafting."
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

    def settle_day(self, day):
        if day <= self.last_tax_day:
            return
        dividends = settle_exchange(self, day)
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
        self.settle_day(previous_day)
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
            self.message = "Choose a motorcycle, car or delivery van at the garage."
            return False
        if self.vehicle == vehicle:
            self.message = f"You already own this {ride.label.lower()}."
            return False
        capacity = self.bag_size+ride.trunk
        if self.cargo+self.reserved > capacity:
            self.message = f"This ride carries {capacity} items. Unload cargo or finish reserved orders before switching."
            return False
        if self.cash < ride.price:
            self.message = f"You need ${ride.price:,} for the {ride.label.lower()}."
            return False
        self.cash -= ride.price
        self.other_expenses_today += ride.price
        self.vehicle = vehicle
        self.message = f"Bought {ride.label.lower()} for ${ride.price:,} · {self.carry_capacity} cargo slots · {ride.road_speed} road speed."
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
        if not business:
            self.other_income_today += amount
        if self.cash >= CASH_GOAL and not self.won:
            self.won = True
            self.message = f"Goal reached on Day {self.day}! Keep trading to grow your business."

    def move(self, dx, dy, seconds):
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
        if self.can_walk(next_x, self.y):
            self.x = next_x
        if self.can_walk(self.x, next_y):
            self.y = next_y
        self.check_bridge_crossing(old_y)
        self.collect_power_up()

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
                record_bridge(self, name)
                self.message = f"Portagem · Ponte {name} → Lisboa: -${BRIDGE_TOLL}."
                self.notice = self.message
                self.notice_until = self.elapsed+4
            self.bridge_journey = None
        elif self.y >= south:
            self.bridge_journey = None

    def can_walk(self, x, y):
        return (PLAYER_RADIUS <= x <= WORLD_WIDTH-PLAYER_RADIUS and MAP_TOP+PLAYER_RADIUS <= y <= WORLD_BOTTOM-PLAYER_RADIUS
                and walkable_terrain(x, y, PLAYER_RADIUS)) and not any(
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
            self.message = "Motorworks Garage · E to browse motorcycles, cars and delivery vans."
            return
        if site.role == "WAREHOUSE":
            self.message = "Foundry Warehouse · E to expand your carrying capacity."
            return
        if site.role == "EXCHANGE":
            self.message = "Bolsa de Lisboa · E to buy or sell district and infrastructure shares."
            return
        if site.role == "RESEARCH":
            self.message = "Nova SBE · Carcavelos · E for research and the advanced workshop."
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
                self.congratulate(quantity, "precision machinery")
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
            self.message = f"Picked up {quantity} × {trade.supply} for ${cost}."
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
            self.congratulate(quantity, trade.product.lower())
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
            project = self.innovation["project"]
            if project:
                branch = innovation.BRANCH_BY_KEY[project["branch"]]
                return f"{branch.name} {project['level']} · {math.ceil(project['remaining'])}s"
            return f"Inovação · Green {innovation.research_level(self, 'green_energy')}/3 · Metal {innovation.research_level(self, 'metallurgy')}/3"
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
            return "E  Nova SBE · Research upgrades / craft and sell tier-3 products"
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


class Game:
    display_scale = 1
    power_up_definitions = POWER_UPS

    def __init__(self, root, session=None, initial_profile=None):
        self.root = root
        self.music = music_for(root)
        self.town = Town()
        self.market_started_at = market_start()
        if session is None:
            self.storage, self.player = desktop_storage()
            self.revision, saved = self.storage.load(self.player)
        else:
            self.storage, self.player, self.revision, saved = session
            if saved is None:
                self.market_started_at = time.time()
        if saved is not None:
            self.town, self.market_started_at = unpack_save(saved)
        if initial_profile is not None:
            self.town.set_profile(initial_profile)
        self.writer = ThreadPoolExecutor(max_workers=1)
        self.pending_save = None
        self.save_conflict = False
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.autosave_timer = root.after(10000, self.autosave)
        self.keys = set()
        self.profile_window = None
        self.winner_window = None
        # Casino state lives only in this session, so old saves still load.
        self.casino_open = False
        self.chip_index = 1
        self.wheel_angle = 0.0
        self.ball_pocket = None
        self.spin = None
        self.roulette_history = []
        self.casino_result = ("Pick a chip, then bet on a color.", WHITE)
        self.casino_buttons = []
        self.casino_bulbs = []
        self.casino_light_frame = -1
        self.traffic_enabled = True
        self.hud_label_items = {}
        self.world_view = None
        self.resize_timer = None
        self.traffic = [(offset, lane, speed, color) for offset, lane, speed, color in (
            (0.05, 287, 150, "#e8455a"), (0.48, 298, -112, "#ffc66c"),
            (0.76, 480, 124, "#86caff"), (0.28, 491, -95, "#e6e9df"),
            (0.67, 673, 138, "#80dab9"), (0.15, 684, -105, "#bea0ec"),
        )]
        self.last_tick = time.perf_counter()
        self.next_frame_time = self.last_tick
        root.title("Foundry Town | Lisboa")
        root.configure(bg=INK)
        root.attributes("-fullscreen", True)
        if IS_MAC:
            # Tk 9 on macOS keeps a window at 200x200 if it is locked before it
            # appears, so lock the size once the window is on screen.
            def lock_size(event):
                root.unbind("<Map>")
                root.after(50, lambda: root.resizable(False, False))
            root.bind("<Map>", lock_size)
        else:
            root.resizable(False, False)
        self.viewport_width, self.viewport_height = root.winfo_screenwidth(), root.winfo_screenheight()
        self.scale_x = self.viewport_width/WIDTH
        self.scale_y = self.viewport_height/HEIGHT
        self.display_scale = min(self.scale_x, self.scale_y)
        self.canvas = tk.Canvas(root, width=self.viewport_width, height=self.viewport_height,
                                highlightthickness=0, borderwidth=0, bg=INK)
        self.canvas.pack(fill="both", expand=True)
        self.settings_button = tk.Button(
            self.canvas, text="⚙ Settings", command=self.open_settings,
            bg=GOLD, fg=INK, activebackground="#ffe0a0", activeforeground=INK,
            font=(FONT, 11, "bold"), relief="flat", borderwidth=0, cursor="hand2", takefocus=True,
        )
        self.places_button = tk.Button(
            self.canvas, text="Places · P", command=self.open_places,
            bg="#365563", fg=WHITE, activebackground="#496b7a", activeforeground=WHITE,
            font=(FONT, 10, "bold"), relief="flat", borderwidth=0, cursor="hand2", takefocus=True,
        )
        self.journal_button = tk.Button(
            self.canvas, text="Journal · J", command=self.open_journal,
            bg="#365563", fg=WHITE, activebackground="#496b7a", activeforeground=WHITE,
            font=(FONT, 10, "bold"), relief="flat", borderwidth=0, cursor="hand2", takefocus=True,
        )
        self.deliveries_button = tk.Button(
            self.canvas, text="Deliveries · L", command=self.open_deliveries,
            bg="#365563", fg=WHITE, activebackground="#496b7a", activeforeground=WHITE,
            font=(FONT, 10, "bold"), relief="flat", borderwidth=0, cursor="hand2", takefocus=True,
        )
        self.contracts_button = tk.Button(
            self.canvas, text="Contracts · C", command=self.open_contracts,
            bg="#365563", fg=WHITE, activebackground="#496b7a", activeforeground=WHITE,
            font=(FONT, 10, "bold"), relief="flat", borderwidth=0, cursor="hand2", takefocus=True,
        )
        self.businesses_button = tk.Button(
            self.canvas, text="Businesses · B", command=self.open_businesses,
            bg="#365563", fg=WHITE, activebackground="#496b7a", activeforeground=WHITE,
            font=(FONT, 10, "bold"), relief="flat", borderwidth=0, cursor="hand2", takefocus=True,
        )
        self.minimize_button = tk.Button(root, text="—", font=(FONT, 12, "bold"),
                                         command=root.iconify, takefocus=False)
        self.minimize_button.place(relx=1, x=-12, y=12, anchor="ne")
        self.menu_button = tk.Button(root, text="Save and return to menu", command=self.return_to_menu)
        root.bind("<KeyPress>", self.key_down)
        root.bind("<Control-m>", lambda event: root.iconify())
        root.bind("<KeyRelease>", self.key_up)
        root.bind("<FocusOut>", lambda event: self.keys.clear())
        self.canvas.bind("<Button-1>", self.click)
        self.draw_city()
        self.canvas.scale("all", 0, 0, self.scale_x, self.scale_y)
        self.canvas.bind("<Configure>", self.on_canvas_resize)
        if IS_MAC:
            # Apps started from Terminal open behind other windows on macOS, and the
            # game clock only runs while its window has focus.
            root.lift()
            root.attributes("-topmost", True)
            root.after(300, lambda: root.attributes("-topmost", False))
            root.focus_force()
        self.tick()

    def write_save(self):
        snapshot = pack_save(self.town, self.market_started_at)
        return self.writer.submit(self.storage.save, self.player, self.revision, snapshot)

    def autosave(self):
        if self.pending_save is not None:
            if not self.pending_save.done():
                self.autosave_timer = self.root.after(200, self.autosave)
                return
            try:
                self.revision = self.pending_save.result()
                self.root.title("Foundry Town | Saved")
            except SaveConflict as exc:
                self.save_conflict = True
                messagebox.showwarning("Save conflict", str(exc), parent=self.root)
                return
            except Exception as exc:
                self.root.title(f"Foundry Town | Save failed: {exc}")
            finally:
                self.pending_save = None
            self.autosave_timer = self.root.after(10000, self.autosave)
        else:
            self.pending_save = self.write_save()
            self.autosave_timer = self.root.after(200, self.autosave)

    def return_to_menu(self):
        self.close(to_menu=True)

    def save_and_close(self):
        self.close(require_save=True)

    def close(self, to_menu=False, require_save=False):
        # Pay out a spin that is still running so quitting never loses a win.
        self.settle_spin()
        try:
            if self.pending_save is not None:
                pending, self.pending_save = self.pending_save, None
                self.revision = pending.result()
            if self.save_conflict:
                raise SaveConflict("A newer save exists on the server.")
            self.revision = self.write_save().result()
        except Exception as exc:
            if isinstance(exc, SaveConflict):
                self.save_conflict = True
            if require_save:
                messagebox.showerror("Save failed", f"{exc}\n\nYour game is still open. Try saving again.", parent=self.root)
                return
            if not messagebox.askyesno("Save failed", f"{exc}\n\nQuit without saving this session?",
                                       parent=self.root):
                return
        self.writer.shutdown()
        if self.resize_timer is not None:
            self.root.after_cancel(self.resize_timer)
            self.resize_timer = None
        self.root.after_cancel(self.tick_timer)
        self.root.after_cancel(self.autosave_timer)
        if to_menu:
            for event in ("<KeyPress>", "<KeyRelease>", "<FocusOut>", "<Control-m>"):
                self.root.unbind(event)
            self.canvas.destroy()
            self.minimize_button.destroy()
            self.menu_button.destroy()
            StartMenu(self.root, (self.storage, self.player))
        else:
            self.music.stop()
            self.root.destroy()

    def key_down(self, event):
        if self.profile_window is not None:
            return
        key = event.keysym.lower()
        if key == "f1":
            self.open_settings()
            return
        if key == "j":
            self.open_journal()
            return
        if key == "l":
            self.open_deliveries()
            return
        if key == "c":
            self.open_contracts()
            return
        if key == "b" and not self.casino_open:
            self.open_businesses()
            return
        if self.casino_open:
            # Ignore key repeats, so holding E does not close the casino straight away.
            if key not in self.keys:
                self.casino_key(key)
            self.keys.add(key)
            return
        if key == "m" and key not in self.keys:
            self.world_view.toggle_map()
            self.keys.add(key)
            return
        if key == "p":
            self.open_places()
            return
        if key not in self.keys and key in ("f", "r"):
            self.town.buy_eggs(bulk=(key == "r"))
            self.keys.add(key)
            return
        if key not in self.keys and key in ("e", "q"):
            nearby = self.town.nearby()
            if key == "e" and nearby is not None and nearby.role == "CASINO":
                self.open_casino()
                return
            if key == "e" and nearby is not None and nearby.role == "GARAGE":
                self.open_vehicle_shop()
                self.keys.add(key)
                return
            if key == "e" and nearby is not None and nearby.role == "WAREHOUSE":
                self.open_warehouse_shop()
                self.keys.add(key)
                return
            if key == "e" and nearby is not None and nearby.role == "EXCHANGE":
                self.open_exchange()
                self.keys.add(key)
                return
            if key == "e" and nearby is not None and nearby.role == "RESEARCH":
                self.open_research()
                self.keys.add(key)
                return
            if key == "e" and nearby is None:
                from tram import nearby_stop
                if nearby_stop(self.town.x, self.town.y) is not None:
                    from tram_menu import open_tram
                    open_tram(self)
                    return
            if key == "e" or (nearby and nearby.role == "SUPPLIER"):
                self.town.interact(bulk=(key == "q"))
        self.keys.add(key)

    def key_up(self, event):
        self.keys.discard(event.keysym.lower())

    def open_places(self):
        from places_menu import open_places
        open_places(self, SITES)

    def open_journal(self):
        from journal_panel import open_journal
        open_journal(self, TRADES, INDUSTRIES, tuple(self.town.business_site(site) for site in SITES))

    def open_exchange(self):
        from exchange_panel import open_exchange
        open_exchange(self)

    def open_research(self):
        from research_panel import open_research
        open_research(self)

    def open_deliveries(self):
        from logistics_panel import open_logistics
        open_logistics(self, SITES, TRADES)

    def open_contracts(self):
        from contracts_panel import open_contracts
        open_contracts(self)

    def open_businesses(self):
        from businesses_panel import open_businesses
        open_businesses(self, SITES, TRADES)

    def tick(self):
        now = time.perf_counter()
        dt = now - self.last_tick
        self.last_tick = now
        self.town.sync_market(time.time() - self.market_started_at)
        if self.spin is not None and now - self.spin["start"] >= SPIN_SECONDS:
            self.settle_spin()
        paused = self.profile_window is not None or self.casino_open
        focused = self.root.focus_displayof() is not None
        if focused and (not self.town.won or self.town.milestone_acknowledged):
            active_seconds = min(.25, max(0, dt))
            advance_city(self.town, active_seconds)
            self.town.advance_research(active_seconds)
            self.town.advance_deliveries(active_seconds)
            self.town.advance_contracts(active_seconds)
            self.town.advance_businesses(active_seconds)
        if not paused and focused:
            self.town.advance(dt)
        if self.town.won and not self.town.milestone_acknowledged and self.winner_window is None:
            self.show_winner()
        if not self.casino_open:
            dx = int("d" in self.keys or "right" in self.keys) - int("a" in self.keys or "left" in self.keys)
            dy = int("s" in self.keys or "down" in self.keys) - int("w" in self.keys or "up" in self.keys)
            move_time = min(dt, 0.25)
            move_steps = max(1, math.ceil(move_time / 0.05))
            for _ in range(move_steps):
                self.town.move(dx, dy, move_time / move_steps)
        self.draw_live()
        self.canvas.scale("live", 0, 0, self.scale_x, self.scale_y)
        # Pace against an absolute clock so timer jitter does not accumulate.
        self.next_frame_time += FRAME_SECONDS
        if now-self.next_frame_time > FRAME_SECONDS*4:
            self.next_frame_time = now+FRAME_SECONDS
        remaining = self.next_frame_time-time.perf_counter()
        self.tick_timer = self.root.after(max(1, int(remaining*1000)), self.tick)

    # ----- Casino -----

    def open_casino(self):
        # E is still held down. Recording it stops its key repeats from closing the casino.
        self.keys = {"e"}
        self.casino_open = True
        self.town.interact()

    def show_winner(self):
        self.keys.clear()
        if self.profile_window is not None:
            previous, self.profile_window = self.profile_window, None
            previous.destroy()
        panel = self.winner_window = tk.Toplevel(self.root)
        self.profile_window = panel
        panel.title("Foundry Town Champion")
        panel.transient(self.root)
        panel.resizable(False, False)
        panel.grab_set()
        frame = tk.Frame(panel, padx=40, pady=32, bg=INK)
        frame.pack()
        tk.Label(frame, text="YOU ARE THE WINNER!", font=(FONT, 24, "bold"),
                 bg=INK, fg=GOLD).pack(pady=(0, 12))
        tk.Label(frame, text=f"Your business reached ${CASH_GOAL:,} on Day {self.town.day}.",
                 font=(FONT, 13), bg=INK, fg=WHITE).pack(pady=(0, 18))
        tk.Label(frame, text="Continue growing: research at Nova SBE in Carcavelos\nand unlock advanced products.",
                 font=(FONT, 11), bg=INK, fg=MUTED).pack(pady=(0, 18))

        def continue_playing():
            self.town.continue_after_milestone()
            self.winner_window = None
            if self.profile_window is panel:
                self.profile_window = None
            panel.grab_release()
            panel.destroy()
            self.keys.clear()
            self.root.focus_set()

        tk.Button(frame, text="Continue building & researching", command=continue_playing,
                  bg=GOLD, fg=INK).pack(fill="x", pady=(0, 10))
        tk.Button(frame, text="Save and exit game", command=self.close).pack(fill="x")

        def finish():
            self.winner_window = None
            self.close()

        panel.protocol("WM_DELETE_WINDOW", finish)

    def close_casino(self):
        # Held keys stay recorded until released, so a held E does not reopen the casino.
        self.settle_spin()
        self.casino_open = False
        self.town.message = "Thanks for visiting the Foundry Casino."

    def open_vehicle_shop(self):
        if self.profile_window is not None:
            return
        self.keys.clear()
        panel = self.profile_window = tk.Toplevel(self.root)
        panel.title("Motorworks Garage")
        panel.transient(self.root)
        panel.resizable(False, False)
        frame = tk.Frame(panel, padx=22, pady=18)
        frame.pack()
        def summary():
            ride = VEHICLES.get(self.town.vehicle)
            label = ride.label if ride else "On foot"
            trunk = ride.trunk if ride else 0
            return (f"Cash ${self.town.cash:,} · {label}\n"
                    f"Personal storage {self.town.bag_size} + trunk {trunk} = {self.town.carry_capacity} cargo slots")

        status = tk.StringVar(value=summary())
        tk.Label(frame, text="CHOOSE YOUR RIDE & TRUNK", font=(FONT, 16, "bold")).pack(pady=(0, 10))
        tk.Label(frame, text="Vehicles add reusable cargo space and drive faster on paved roads.\n"
                            "Warehouse and bag upgrades still add to your total capacity.",
                 justify="center", font=(FONT, 10)).pack(pady=(0, 10))
        tk.Label(frame, textvariable=status).pack(pady=(0, 10))

        def buy(vehicle):
            self.town.purchase_vehicle(vehicle)
            status.set(self.town.message+"\n"+summary())

        for key, ride in VEHICLES.items():
            capacity = self.town.bag_size+ride.trunk
            text = (f"{ride.label} · ${ride.price:,} · {capacity} total cargo slots\n"
                    f"Road speed {ride.road_speed} · Off-road speed {ride.offroad_speed} · +{ride.trunk} trunk slots")
            tk.Button(frame, text=text, command=lambda value=key: buy(value),
                       font=(FONT, 10), padx=12, pady=6).pack(fill="x", pady=4)

        def clear_pause(event=None):
            if event is None or event.widget is panel:
                if self.profile_window is panel:
                    self.profile_window = None
                self.keys.clear()

        def close(event=None):
            clear_pause()
            try:
                panel.grab_release()
                panel.destroy()
                self.root.focus_set()
            except tk.TclError:
                pass
            self.keys.clear()
            return "break"

        tk.Button(frame, text="Automated delivery fleet · Manage routes",
                  command=lambda: (close(), self.open_deliveries())).pack(fill="x", pady=(10, 0))
        tk.Button(frame, text="Close garage", command=close).pack(pady=(10, 0))
        panel.bind("<Escape>", close)
        panel.bind("<Destroy>", clear_pause)
        panel.protocol("WM_DELETE_WINDOW", close)
        panel.grab_set()

    def open_warehouse_shop(self):
        panel = self.profile_window = tk.Toplevel(self.root)
        panel.title("Foundry Warehouse")
        panel.transient(self.root)
        panel.resizable(False, False)
        panel.grab_set()
        frame = tk.Frame(panel, padx=22, pady=18)
        frame.pack()
        tk.Label(frame, text="EXPAND YOUR STORAGE", font=(FONT, 16, "bold")).pack(pady=(0, 10))
        status = tk.StringVar()
        tk.Label(frame, textvariable=status).pack(pady=(0, 10))
        button = tk.Button(frame)
        button.pack(fill="x", pady=4)

        def refresh():
            level = self.town.warehouse_level
            price = 300 + level * 250
            status.set(f"Personal storage {self.town.bag_size} · Total cargo {self.town.carry_capacity} · Cash ${self.town.cash:,}")
            button.configure(text=f"Buy 12 more slots · ${price:,}", command=lambda: buy(price))

        def buy(price):
            if self.town.cash < price:
                status.set(f"You need ${price:,} for this warehouse expansion.")
                return
            self.town.cash -= price
            self.town.other_expenses_today += price
            self.town.bag_size += 12
            self.town.warehouse_level += 1
            self.town.message = f"Warehouse expanded · Personal storage {self.town.bag_size} · Total cargo {self.town.carry_capacity}."
            refresh()

        def close():
            panel.destroy()
            self.profile_window = None
            self.keys.clear()
            self.root.focus_set()

        refresh()
        tk.Button(frame, text="Close warehouse", command=close).pack(pady=(10, 0))
        panel.protocol("WM_DELETE_WINDOW", close)

    def casino_key(self, key):
        if key in ("escape", "e"):
            self.close_casino()
        elif key in ("r", "b", "g"):
            self.spin_wheel({"r": "red", "b": "black", "g": "green"}[key])
        elif key in ("left", "a"):
            self.chip_index = max(0, self.chip_index - 1)
        elif key in ("right", "d"):
            self.chip_index = min(len(CHIPS) - 1, self.chip_index + 1)
        elif key in ("1", "2", "3", "4", "5"):
            self.chip_index = int(key) - 1

    def spin_wheel(self, choice):
        if self.spin is not None:
            return
        stake = CHIPS[self.chip_index]
        pocket = random.randrange(len(ROULETTE_POCKETS))
        number = ROULETTE_POCKETS[pocket]
        payout = self.town.bet_roulette(choice, stake, number)
        if payout is None:
            self.casino_result = (f"You need ${stake} in cash for that chip.", GOLD)
            return
        self.spin = {
            "start": time.perf_counter(), "choice": choice, "stake": stake,
            "pocket": pocket, "number": number, "payout": payout,
            "wheel_from": self.wheel_angle,
            "wheel_to": self.wheel_angle + math.tau * (2.5 + random.random()),
        }
        self.casino_result = (f"${stake} on {choice.upper()}  ·  No more bets!", WHITE)

    def settle_spin(self):
        spin, self.spin = self.spin, None
        if spin is None:
            return
        self.wheel_angle = spin["wheel_to"] % math.tau
        self.ball_pocket = spin["pocket"]
        number, color = spin["number"], roulette_color(spin["number"])
        self.roulette_history = ([number] + self.roulette_history)[:12]
        landed = f"{number} {color.upper()}"
        if spin["payout"]:
            self.town.add_cash(spin["payout"])
            profit = spin["payout"] - spin["stake"]
            self.casino_result = (f"{landed}  ·  You win ${profit}!", MINT)
            self.town.message = f"Roulette: {landed}. You won ${profit}."
        else:
            self.casino_result = (f"{landed}  ·  You lose ${spin['stake']}.", "#ff8a8a")
            self.town.message = f"Roulette: {landed}. You lost ${spin['stake']}."

    def wheel_state(self):
        """Wheel angle, ball angle, and ball radius right now, in wheel units."""
        seg = math.tau / len(ROULETTE_POCKETS)
        spin = self.spin
        if spin is None:
            ball = None
            if self.ball_pocket is not None:
                ball = (self.wheel_angle + self.ball_pocket * seg, CASINO_POCKET_RADIUS)
            return self.wheel_angle, ball
        progress = min(1, (time.perf_counter() - spin["start"]) / SPIN_SECONDS)
        # The wheel slows down evenly and stops when the spin ends.
        wheel = spin["wheel_from"] + (spin["wheel_to"] - spin["wheel_from"]) * (1 - (1 - progress) ** 2)
        # The ball runs the other way and slows down to finish in its pocket.
        ball_angle = spin["wheel_to"] + spin["pocket"] * seg + math.tau * 6 * (1 - progress) ** 2
        drop = min(1, max(0, (progress - .6) / .3))
        drop = drop * drop * (3 - 2 * drop)
        bounce = 6 * abs(math.sin(progress * 38)) * (1 - progress) if .6 < progress < .95 else 0
        radius = CASINO_TRACK_RADIUS - (CASINO_TRACK_RADIUS - CASINO_POCKET_RADIUS) * drop + bounce
        return wheel, (ball_angle, radius)

    def click(self, event):
        x, y = event.x/self.scale_x, event.y/self.scale_y
        if self.casino_open:
            for left, top, right, bottom, action in self.casino_buttons:
                if left <= x <= right and top <= y <= bottom:
                    action()
                    return
            return
        if 1005 <= x <= 1105 and 19 <= y <= 77:
            self.open_settings()
            return
        self.click_profile(x, y)

    def open_settings(self):
        if self.profile_window is not None:
            return
        self.keys.clear()
        panel = self.profile_window = tk.Toplevel(self.root)
        panel.title("Foundry Town · Settings")
        panel.transient(self.root)
        panel.resizable(False, False)
        frame = tk.Frame(panel, padx=22, pady=18)
        frame.pack(fill="both", expand=True)

        def close():
            panel.destroy()
            self.profile_window = None
            self.root.focus_set()

        traffic = tk.BooleanVar(value=self.traffic_enabled)
        music_enabled = tk.BooleanVar(value=self.music.enabled)
        ambient_enabled = tk.BooleanVar(value=self.world_view.actors_enabled)

        def toggle_fullscreen():
            enabled = not self.fullscreen_active()
            self.set_fullscreen(enabled)
            fullscreen_button.configure(text="Exit Fullscreen" if enabled else "Enter Fullscreen")

        def set_traffic():
            self.traffic_enabled = traffic.get()
            state = "normal" if self.traffic_enabled else "hidden"
            for body, window, *_ in self.traffic_items:
                self.canvas.itemconfigure(body, state=state)
                self.canvas.itemconfigure(window, state=state)

        tk.Label(frame, text="SETTINGS", font=(FONT, 17, "bold")).pack(anchor="w", pady=(0, 10))
        self.resolution_text = tk.StringVar(value=f"Display: {self.viewport_width} × {self.viewport_height}")
        tk.Label(frame, textvariable=self.resolution_text, fg="#52636b").pack(anchor="w", pady=(0, 8))
        fps_text = f"{self.world_view.fps:.0f} FPS" if self.world_view.fps else "Measuring FPS..."
        tk.Label(frame, text=f"Renderer: {fps_text} · target {TARGET_FPS}", fg="#52636b").pack(anchor="w", pady=(0, 8))
        fullscreen_button = tk.Button(
            frame,
            text="Exit Fullscreen" if self.fullscreen_active() else "Enter Fullscreen",
            command=toggle_fullscreen,
        )
        fullscreen_button.pack(anchor="w", pady=3)
        tk.Checkbutton(frame, text="Show moving town traffic", variable=traffic, command=set_traffic).pack(anchor="w", pady=3)
        tk.Checkbutton(frame, text="Pedestrians, boats and water movement", variable=ambient_enabled,
                       command=lambda: setattr(self.world_view, "actors_enabled", ambient_enabled.get())).pack(anchor="w", pady=3)
        zoom_choices = {"Wide · 1.0×": 1.0, "Standard · 1.25×": 1.25, "Close · 1.5×": 1.5}
        zoom_value = tk.StringVar(value=next(name for name, value in zoom_choices.items() if value == self.world_view.zoom))
        tk.Label(frame, text="Following camera · Zoom (M toggles minimap)").pack(anchor="w", pady=(8, 0))
        tk.OptionMenu(frame, zoom_value, *zoom_choices, command=lambda name: self.world_view.set_zoom(zoom_choices[name])).pack(fill="x", pady=3)
        tk.Checkbutton(frame, text="Fado guitar background music", variable=music_enabled,
                       command=lambda: self.music.set_enabled(music_enabled.get())).pack(anchor="w", pady=3)
        tk.Label(frame, text="Saudade do Tejo · original instrumental", fg="#52636b").pack(anchor="w", pady=(2, 8))
        tk.Label(frame, text="Daylight 3 minutes  ·  Night 2 minutes", fg="#52636b").pack(anchor="w", pady=(8, 14))
        buttons = tk.Frame(frame)
        buttons.pack(fill="x")
        tk.Button(buttons, text="Rules & How to Play", command=lambda: (close(), show_rules(self.root))).pack(side="left")
        tk.Button(buttons, text="Close", command=close).pack(side="right")
        tk.Button(frame, text="Automated deliveries · L",
                  command=lambda: (close(), self.open_deliveries())).pack(fill="x", pady=(8, 0))
        tk.Button(frame, text="Contracts & city projects · C",
                  command=lambda: (close(), self.open_contracts())).pack(fill="x", pady=(6, 0))
        tk.Button(frame, text="Business ownership · B",
                  command=lambda: (close(), self.open_businesses())).pack(fill="x", pady=(6, 0))
        tk.Button(frame, text="Save and return to main menu", command=lambda: (close(), self.return_to_menu())).pack(fill="x", pady=(14, 0))
        tk.Button(frame, text="Save and Close Game", command=lambda: (close(), self.save_and_close()),
                  bg=INK, fg=WHITE, activebackground="#2c5360", activeforeground=WHITE,
                  font=(FONT, 10, "bold"), pady=6).pack(fill="x", pady=(6, 0))
        panel.bind("<Escape>", lambda event: close())
        panel.protocol("WM_DELETE_WINDOW", close)
        panel.grab_set()

    def fullscreen_active(self):
        value = self.root.attributes("-fullscreen")
        return str(value).lower() in ("1", "true", "yes")

    def set_fullscreen(self, enabled):
        self.root.attributes("-fullscreen", enabled)
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        if enabled:
            self.root.resizable(False, False)
            width, height = screen_width, screen_height
        else:
            self.root.resizable(True, True)
            width, height = round(screen_width*.85), round(screen_height*.85)
            left = max(0, (screen_width - width) // 2)
            top = max(0, (screen_height - height) // 2)
            self.root.state("normal")
            self.root.geometry(f"{width}x{height}+{left}+{top}")
            self.root.update_idletasks()
        self.resize_canvas(width, height)
        if self.profile_window is not None and self.profile_window.winfo_exists():
            self.root.after(100, self.center_settings_window)
        self.next_frame_time = time.perf_counter()

    def on_canvas_resize(self, event):
        if self.resize_timer is not None:
            self.root.after_cancel(self.resize_timer)
            self.resize_timer = None
        if event.width < 320 or event.height < 240:
            return
        if (event.width, event.height) != (self.viewport_width, self.viewport_height):
            self.resize_timer = self.root.after(120, lambda: self.resize_canvas(event.width, event.height))

    def resize_canvas(self, width, height):
        if self.resize_timer is not None:
            self.root.after_cancel(self.resize_timer)
            self.resize_timer = None
        self.viewport_width, self.viewport_height = width, height
        if hasattr(self, "resolution_text"):
            self.resolution_text.set(f"Display: {width} × {height}")
        self.scale_x, self.scale_y = width/WIDTH, height/HEIGHT
        self.display_scale = min(self.scale_x, self.scale_y)
        self.canvas.delete("all")
        self.hud_label_items = {}
        self.draw_city()
        self.canvas.scale("all", 0, 0, self.scale_x, self.scale_y)
        self.draw_live()
        self.canvas.scale("live", 0, 0, self.scale_x, self.scale_y)

    def center_settings_window(self):
        panel = self.profile_window
        if panel is None or not panel.winfo_exists():
            return
        panel.update_idletasks()
        width, height = panel.winfo_width(), panel.winfo_height()
        screen_width, screen_height = panel.winfo_screenwidth(), panel.winfo_screenheight()
        left = self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2
        top = self.root.winfo_rooty() + (self.root.winfo_height() - height) // 2
        left = min(max(0, left), max(0, screen_width - width))
        top = min(max(0, top), max(0, screen_height - height))
        panel.geometry(f"+{left}+{top}")
        panel.lift()

    def click_profile(self, x, y):
        if not (PROFILE_X <= x <= PROFILE_X + 56 and 19 <= y <= 77) or self.profile_window is not None:
            return
        self.keys.clear()
        panel = self.profile_window = tk.Toplevel(self.root)
        panel.title("Town financial analytics")
        panel.transient(self.root)
        panel.resizable(False, False)
        panel.grab_set()
        frame = tk.Frame(panel, padx=18, pady=14)
        frame.pack()
        def close():
            panel.destroy()
            self.profile_window = None
            self.root.focus_set()

        town = self.town
        frame.columnconfigure(1, weight=1)
        tk.Label(frame, text="PROFIT & LOSS", font=(FONT, 16, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        tk.Label(frame, text=f"Day {town.day} revenue  ${town.daily_revenue:,}").grid(row=1, column=0, columnspan=2, sticky="w")
        tk.Label(frame, text=f"Day {town.day} expenses  ${town.daily_expenses:,}").grid(row=2, column=0, columnspan=2, sticky="w")
        tk.Label(frame, text="District sales today").grid(row=3, column=0, columnspan=2, sticky="w", pady=(10, 3))
        districts = ("Metal", "Timber", "Clay", "Farm")
        for index, trade in enumerate(TRADES):
            tk.Label(frame, text=f"{districts[index]} · {trade.product} · {town.sales_today[index]} sold").grid(row=4 + index, column=0, sticky="w")
            costs = town.expenses_today[index]+(town.egg_expenses_today if index == 3 else 0)
            tk.Label(frame, text=f"Revenue ${town.revenue_today[index]:,} · Purchases ${costs:,}").grid(row=4 + index, column=1, sticky="e")
        totals = (town.total_sold+[town.tier2_total_sold]+list(town.industry_total_sold.values())
                  +[town.innovation["total_sold"][recipe.key] for recipe in innovation.TIER3_RECIPES])
        products = ([trade.product for trade in TRADES]+["Precision Machinery"]+[recipe.product for recipe in INDUSTRIES.values()]
                    +[recipe.product for recipe in innovation.TIER3_RECIPES])
        best = max(range(len(totals)), key=lambda index: totals[index])
        tk.Label(frame, text=f"Precision Works · {town.tier2_sales_today} sold · Revenue ${town.tier2_revenue_today:,}").grid(row=8, column=0, columnspan=2, sticky="w")
        for row, (role, district) in enumerate((("PASTELARIA", "Belém · Pastéis"), ("SHIPYARD", "Tejo · Boat repairs")), start=9):
            tk.Label(frame, text=f"{district} · {town.industry_sales_today[role]} completed").grid(row=row, column=0, sticky="w")
            tk.Label(frame, text=f"Revenue ${town.industry_revenue_today[role]:,}").grid(row=row, column=1, sticky="e")
        for row, recipe in enumerate(innovation.TIER3_RECIPES, start=11):
            tk.Label(frame, text=f"Carcavelos · {recipe.product} · {town.innovation['sales_today'][recipe.key]} sold").grid(row=row, column=0, sticky="w")
            tk.Label(frame, text=f"Revenue ${town.innovation['revenue_today'][recipe.key]:,}").grid(row=row, column=1, sticky="e")
        rate = innovation.tax_rate(town, DAILY_TAX_PERCENT)
        estimated_tax = (max(0, town.daily_net_profit)*rate+50)//100
        summary = [
            f"Lucro antes de imposto: ${town.daily_net_profit:,} · Imposto estimado ({rate}%): ${estimated_tax:,}",
            f"Portagens hoje: ${town.tolls_today} · {town.toll_count_today} regressos a Lisboa",
            f"Outras receitas: ${town.other_income_today:,} · Outras despesas: ${town.other_expenses_today:,}",
            f"Total pago · Impostos: ${town.taxes_paid_total:,} · Portagens: ${town.tolls_paid_total:,}",
            f"Bolsa · {sum(town.exchange['holdings'].values())} ações · Dividendos recebidos ${sum(town.exchange['total_dividends'].values())}",
            f"Logística · {len(town.logistics['routes'])} rotas · {sum(factory['output'] for factory in town.logistics['factories'].values())} produtos nas fábricas",
            f"Contracts · Revenue ${town.contracts['revenue_today']:,} · {town.contracts['completed']} completed · Reputation {town.contracts['reputation']}",
            f"Owned businesses · {len(town.businesses['owned'])} properties · Sales today ${sum(record['revenue_today'] for record in town.businesses['owned'].values()):,}",
        ]
        if town.last_day_summary:
            last = town.last_day_summary
            summary.append(f"Fecho do dia {last['day']}: lucro ${last['profit']} · imposto ${last['tax']} · líquido ${last['net_profit']}")
        for row, line in enumerate(summary, start=14):
            tk.Label(frame, text=line).grid(row=row, column=0, columnspan=2, sticky="w", pady=2)
        row = 14+len(summary)
        tk.Label(frame, text=f"Top seller overall  {products[best]} · {totals[best]} sold").grid(row=row, column=0, columnspan=2, sticky="w", pady=(8, 4))
        tk.Button(frame, text="Edit player profile", command=lambda: self.open_profile_editor(close)).grid(row=row+1, column=0, sticky="w", pady=(8, 0))
        tk.Button(frame, text="Close", command=close).grid(row=row+1, column=1, sticky="e", pady=(8, 0))
        panel.protocol("WM_DELETE_WINDOW", close)

    def open_profile_editor(self, close_analytics):
        close_analytics()
        panel = self.profile_window = tk.Toplevel(self.root)
        panel.title("Player profile")
        panel.transient(self.root)
        panel.resizable(False, False)
        panel.grab_set()
        frame = tk.Frame(panel, padx=18, pady=14)
        frame.pack()
        values = {key: tk.StringVar(panel, value) for key, value in self.town.profile.items()}

        def close():
            panel.destroy()
            self.profile_window = None
            self.root.focus_set()

        def save():
            self.town.set_profile({key: value.get() for key, value in values.items()})
            close()

        for row, (key, title, choices) in enumerate((
            ("name", "Name", None), ("body", "Character color", BODY_COLORS),
            ("hair", "Hair color", HAIR_COLORS), ("costume", "Costume", COSTUMES),
        )):
            tk.Label(frame, text=title).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
            control = tk.OptionMenu(frame, values[key], *choices) if choices else tk.Entry(frame, textvariable=values[key])
            control.grid(row=row, column=1, sticky="ew")
            if key == "name":
                control.focus_set()
        tk.Button(frame, text="Cancel", command=close).grid(row=4, column=0, pady=(10, 0))
        tk.Button(frame, text="Save profile", command=save).grid(row=4, column=1, pady=(10, 0))
        panel.bind("<Return>", lambda event: save())
        panel.bind("<Escape>", lambda event: close())
        panel.protocol("WM_DELETE_WINDOW", close)

    def label(self, x, y, value, size=11, color=WHITE, bold=False, anchor="w", tag="city"):
        if IS_MAC:
            # A negative size is in pixels rather than points.
            font_size = -max(1, round(size * FONT_PIXELS_PER_POINT * self.display_scale))
        else:
            font_size = max(1, round(size * self.display_scale))
        self.canvas.create_text(
            x, y, text=value, fill=color, anchor=anchor,
            font=(FONT, font_size, "bold" if bold else "normal"), tags=tag,
        )

    def hud_label(self, key, x, y, value, size=11, color=WHITE, bold=False, anchor="w", visible=True):
        item = self.hud_label_items.get(key)
        state = "normal" if visible else "hidden"
        style = (size, color, bold, anchor)
        if item is None:
            if IS_MAC:
                font_size = -max(1, round(size * FONT_PIXELS_PER_POINT * self.display_scale))
            else:
                font_size = max(1, round(size * self.display_scale))
            item = self.canvas.create_text(
                x*self.scale_x, y*self.scale_y, text=value, fill=color, anchor=anchor,
                font=(FONT, font_size, "bold" if bold else "normal"), state=state, tags="hud_cache",
            )
            self.hud_label_items[key] = (item, value, x, y, visible, style)
        else:
            item_id, old_value, old_x, old_y, old_visible, old_style = item
            if old_value != value:
                self.canvas.itemconfigure(item_id, text=value)
            if (old_x, old_y) != (x, y):
                self.canvas.coords(item_id, x*self.scale_x, y*self.scale_y)
            if old_visible != visible:
                self.canvas.itemconfigure(item_id, state=state)
            if old_style != style:
                font_size = (-max(1, round(size*FONT_PIXELS_PER_POINT*self.display_scale)) if IS_MAC
                             else max(1, round(size*self.display_scale)))
                self.canvas.itemconfigure(item_id, fill=color, anchor=anchor,
                                          font=(FONT, font_size, "bold" if bold else "normal"))
            self.hud_label_items[key] = (item_id, value, x, y, visible, style)

    def box(self, x1, y1, x2, y2, color, tag="city"):
        self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, width=0, tags=tag)

    def draw_mesh(self, origin_x, origin_y, vertices, faces, *, skew=0.38, tag="city"):
        """Project local 3D coordinates into the town's fixed camera."""
        def depth(face):
            indices, _ = face
            return sum(vertices[index][1] + 0.55 * vertices[index][2] for index in indices) / len(indices)

        for indices, color in sorted(faces, key=depth):
            points = []
            for index in indices:
                x, y, z = vertices[index]
                points.extend((origin_x + x + skew * y, origin_y + 0.46 * y - z))
            self.canvas.create_polygon(*points, fill=color, tags=tag)

    def draw_pine(self, x, y, scale):
        self.box(x-2*scale, y-12*scale, x+2*scale, y, "#8d6545")
        for tier in range(5):
            base = 5 + tier * 6
            radius = 12 - tier * 1.9
            vertices = [
                (scale * radius * (1 if angle % 2 == 0 else .68) * math.cos(angle * math.tau / 10 + tier),
                 scale * radius * (1 if angle % 2 == 0 else .68) * math.sin(angle * math.tau / 10 + tier),
                 scale * (base + (2 if angle % 2 else 0)))
                for angle in range(10)
            ]
            vertices.append((0, 0, scale * (base + 13)))
            palette = ("#253f32", "#3b6040", "#55764a", "#77905a", "#95a56a")
            faces = [((index, (index + 1) % 10, 10), palette[(index + tier) % 5]) for index in range(10)]
            self.draw_mesh(x, y, vertices, faces)

    def draw_city(self):
        if self.world_view is None:
            self.world_view = LivingWorld(self, SITES)
        self.world_view.resize(self.viewport_width, round((MAP_BOTTOM-MAP_TOP)*self.scale_y), round(MAP_TOP*self.scale_y))
        self.scene = self.world_view.scene
        self.background_image = self.world_view.day_image
        self.night_image = self.world_view.night_image
        self.box(0, 0, WIDTH, HEIGHT, INK)
        self.label(24, 30, "FOUNDRY TOWN", 19, WHITE, True)
        self.label(25, 62, "L I S B O A   /   LIVING WORLD", 8, GOLD, True)
        self.box(0, 101, WIDTH, MAP_TOP, "#bfae86")
        help_text = ("WASD / Arrows  Move     E  Interact     Q  Buy four     P  Places     M  Map     F1  Settings"
                     if self.viewport_width >= 1250 else "WASD Move · E Interact")
        self.label(24, MAP_BOTTOM+73, help_text, 9, MUTED)
        self.canvas.create_rectangle(308, 52, 412, 59, fill="#304851", width=0, tags="city")
        self.day_progress = self.canvas.create_rectangle(308, 52, 308, 59, fill=MINT, width=0, tags="city")
        self.canvas.create_rectangle(451, 52, 631, 59, fill="#304851", width=0, tags="city")
        self.cash_progress = self.canvas.create_rectangle(451, 52, 451, 59, fill=GOLD, width=0, tags="city")
        self.canvas.create_rectangle(PROFILE_X, 19, PROFILE_X+56, 77, fill="#304851", width=0, tags="city")
        self.canvas.create_oval(PROFILE_X+19, 28, PROFILE_X+37, 46, fill=GOLD, width=0, tags="city")
        self.canvas.create_oval(PROFILE_X+12, 46, PROFILE_X+44, 65, fill=GOLD, width=0, tags="city")
        self.last_progress = None
        self.traffic_items = []
        for button, y in ((self.settings_button, 29), (self.places_button, 76)):
            button.configure(font=(FONT, max(9, round(10*self.display_scale)), "bold"))
            self.canvas.create_window(1055, y, window=button, width=max(90, 112*self.display_scale),
                                      height=max(28, 32*self.display_scale), tags="controls")
        footer_width = max(102, 140*self.display_scale)
        for button, margin in ((self.journal_button, 3*footer_width+48),
                               (self.contracts_button, 2*footer_width+36),
                               (self.businesses_button, footer_width+24), (self.deliveries_button, 12)):
            button.configure(font=(FONT, max(9, round(10*self.display_scale)), "bold"))
            self.canvas.create_window(WIDTH-margin/self.scale_x, MAP_BOTTOM+73, window=button, anchor="e",
                                      width=footer_width, height=max(24, 28*self.display_scale), tags="controls")

    def draw_legacy_city(self):
        self.box(0, MAP_TOP, WIDTH, MAP_BOTTOM, "#2a4b43")
        for left, right in ((262, 365), (595, 698)):
            self.box(left, MAP_TOP, right, MAP_BOTTOM, "#586768")
            self.box(left + 8, MAP_TOP, right - 8, MAP_BOTTOM, "#35454b")
            for y in range(110, MAP_BOTTOM - 12, 29):
                self.box((left + right) // 2 - 1, y, (left + right) // 2 + 1, y + 12, "#657273")
        for y in (287, 480, 673, 866):
            self.box(0, y, WIDTH, y + 63, "#586768")
            self.box(0, y + 7, WIDTH, y + 56, "#35454b")
            for x in range(14, WIDTH, 32):
                self.box(x, y + 30, x + 15, y + 32, "#657273")
        for y in (137, 375, 568, 761, 929):
            for x in (23, 249, 378, 580, 708, 934, 1180):
                self.canvas.create_oval(x-10, y-7, x+12, y+10, fill="#203a34", width=0)
                self.canvas.create_oval(x-10, y-12, x+9, y+6, fill="#41775b", width=0)
                self.canvas.create_oval(x-6, y-11, x+5, y, fill="#53956d", width=0)
        for name, x, y in (("01   METAL DISTRICT", 60, 131), ("02   TIMBER DISTRICT", 60, 352),
                           ("03   CLAY DISTRICT", 60, 545), ("04   FARM DISTRICT", 60, 738),
                           ("05   CASINO DISTRICT", 992, 352)):
            self.label(x, y, name, 10, "#bee2c4", True)
        self.draw_casino_district()
        for site in SITES:
            self.draw_site(site)
        self.draw_wheat_field(tag="city")
        self.box(0, 0, WIDTH, MAP_TOP, INK)
        self.label(24, 31, "FOUNDRY TOWN", 21, WHITE, True)
        self.label(25, 66, "BUSINESS TYCOON", 10, MINT, True)
        self.box(0, 102, WIDTH, 104, "#385159")
        self.box(0, MAP_BOTTOM, WIDTH, HEIGHT, INK)
        self.box(0, MAP_BOTTOM, WIDTH, MAP_BOTTOM + 2, "#385159")
        self.label(24, MAP_BOTTOM + 73, "W A S D   Move       E   Interact       Q   Buy four at suppliers", 10, MUTED)
        self.night_overlay = self.canvas.create_rectangle(
            0, MAP_TOP, WIDTH, MAP_BOTTOM, fill="#15213d", stipple="gray50", outline="", state="hidden", tags="city"
        )
        self.traffic_items = []
        for offset, lane, speed, color in self.traffic:
            body = self.canvas.create_rectangle(0, lane, 23, lane + 10, fill=color, outline=INK, width=1, tags="traffic")
            window = self.canvas.create_rectangle(4, lane + 2, 10, lane + 5, fill="#b9d7d7", width=0, tags="traffic")
            self.traffic_items.append((body, window, offset, lane, speed))

    def draw_casino_district(self):
        """Pine groves and a car park around the casino."""
        for top in (170, 765):
            for offset_x, offset_y, scale in ((22, 40, 1.0), (60, 30, .85), (98, 44, 1.05),
                                              (138, 32, .9), (166, 48, .8), (42, 70, .95),
                                              (84, 76, 1.0), (126, 72, .9), (160, 84, 1.0)):
                self.draw_pine(992 + offset_x, top + offset_y, scale)

    def draw_casino(self, site):
        x, y, right, bottom = site.bounds
        door_x, _ = site.door
        self.box(x + 5, y + 7, right + 5, bottom + 6, "#1a322d")
        self.canvas.create_polygon(x, y+24, x+24, y+2, right-24, y+2, right, y+24, fill="#2b1427")
        self.box(x, y + 24, right, bottom, "#4a2340")
        self.box(x, y + 24, right, y + 27, GOLD)
        # The sign on the roof, with marquee bulbs that blink in draw_live.
        self.box(x + 46, y + 3, right - 46, y + 21, "#120a12")
        self.label(door_x, y + 12, "CASINO", 10, GOLD, True, anchor="center")
        self.casino_bulbs = []
        self.casino_light_frame = -1
        for index, (bulb_x, bulb_y) in enumerate(
            (position for bulb_x in range(x + 48, right - 45, 6)
             for position in ((bulb_x, y + 1), (bulb_x, y + 23)))
        ):
            item = self.canvas.create_oval(bulb_x - 1.6, bulb_y - 1.6, bulb_x + 1.6, bulb_y + 1.6,
                                           fill="#7a5520", width=0, tags="city")
            self.casino_bulbs.append((item, index))
        self.box(x + 8, y + 30, right - 8, y + 81, "#1d0f1c")
        self.box(x + 8, y + 30, right - 8, y + 33, site.color)
        for left in (x + 14, right - 52):
            self.box(left, bottom - 20, left + 38, bottom - 4, "#2b1427")
            self.box(left + 3, bottom - 17, left + 35, bottom - 7, "#e8b04a")
            self.box(left + 3, bottom - 17, left + 9, bottom - 7, "#8e1f2e")
            self.box(left + 29, bottom - 17, left + 35, bottom - 7, "#8e1f2e")
        self.box(door_x - 15, bottom - 17, door_x + 15, bottom, "#7a1424")
        self.box(door_x - 1, bottom - 17, door_x + 1, bottom, "#4a0c16")
        self.box(door_x - 6, bottom - 9, door_x - 3, bottom - 7, GOLD)
        self.box(door_x + 3, bottom - 9, door_x + 6, bottom - 7, GOLD)
        self.box(door_x - 15, bottom, door_x + 15, bottom + 6, site.color)
        self.box(door_x - 10, bottom + 9, door_x + 10, bottom + 11, "#b3c7bd")
        self.label(x + 13, y + 42, site.role, 8, site.color, True)
        self.label(x + 13, y + 57, site.name, 12, WHITE, True)

    def draw_site(self, site):
        x, y, right, bottom = site.bounds
        door_x, _ = site.door
        if site.role == "CASINO":
            self.draw_casino(site)
            return
        if site.role == "GARAGE":
            self.box(x + 5, y + 7, right + 5, bottom + 6, "#1a322d")
            self.box(x, y + 22, right, bottom, "#344e5b")
            self.box(x + 8, y + 7, right - 8, y + 24, "#182832")
            self.box(x + 20, y + 34, right - 20, bottom - 5, "#203b49")
            self.box(door_x - 24, bottom - 36, door_x + 24, bottom, "#111c23")
            self.box(door_x - 22, bottom - 34, door_x - 1, bottom - 2, "#86caff")
            self.box(door_x + 2, bottom - 34, door_x + 22, bottom - 2, "#86caff")
            self.box(door_x - 15, bottom, door_x + 15, bottom + 6, site.color)
            self.label(x + 13, y + 39, "VEHICLE SHOP", 8, site.color, True)
            self.label(x + 13, y + 57, site.name, 12, WHITE, True)
            return
        if site.role == "WAREHOUSE":
            self.box(x + 5, y + 7, right + 5, bottom + 6, "#1a322d")
            self.box(x, y + 24, right, bottom, "#493e57")
            self.box(x + 14, y + 3, right - 14, y + 28, "#30283b")
            for crate_x in (x + 25, x + 67, x + 109, x + 143):
                self.box(crate_x, y + 61, crate_x + 24, y + 88, "#b48762")
                self.box(crate_x + 3, y + 65, crate_x + 21, y + 68, "#e2c49c")
            self.box(door_x - 16, bottom - 26, door_x + 16, bottom, "#18252d")
            self.box(door_x - 15, bottom, door_x + 15, bottom + 6, site.color)
            self.label(x + 13, y + 39, "STORAGE", 8, site.color, True)
            self.label(x + 13, y + 53, site.name, 11, WHITE, True)
            return
        if site.role == "TIER2":
            self.box(x + 5, y + 7, right + 5, bottom + 6, "#1a322d")
            self.canvas.create_polygon(x, y+24, x+22, y+2, right-22, y+2, right, y+24, fill="#6b4c31")
            self.box(x, y + 24, right, bottom, "#55432e")
            self.box(x + 8, y + 27, right - 8, y + 31, site.color)
            for furnace_x in (x + 24, x + 76, x + 128):
                self.box(furnace_x, y + 48, furnace_x + 24, y + 79, "#282a2a")
                self.box(furnace_x + 5, y + 56, furnace_x + 19, y + 73, "#e08143")
                self.box(furnace_x + 8, y + 60, furnace_x + 16, y + 72, "#ffc66c")
            self.box(door_x - 17, bottom - 25, door_x + 17, bottom, "#302a21")
            self.box(door_x - 15, bottom, door_x + 15, bottom + 6, site.color)
            self.label(x + 13, y + 39, "TIER 2 FACTORY", 8, site.color, True)
            self.label(x + 13, y + 54, site.name, 11, WHITE, True)
            return
        if site.role == "SUPPLIER":
            self.draw_supplier(site)
            self.box(door_x - 15, bottom, door_x + 15, bottom + 6, site.color)
            self.box(door_x - 10, bottom + 9, door_x + 10, bottom + 11, "#b3c7bd")
            return
        self.box(x + 5, y + 7, right + 5, bottom + 6, "#1a322d")
        if site.role == "FACTORY":
            wall, roof = (("#875949", "#4d4c4d"), ("#806451", "#524237"),
                          ("#a25d4b", "#63453d"), ("#b18259", "#684b40"))[site.trade]
            self.box(right-35, y-13, right-21, y+22, wall)
            self.box(right-38, y-15, right-18, y-10, roof)
            if site.trade == 0:
                self.box(right-59, y-7, right-48, y+22, wall)
                self.box(right-62, y-9, right-45, y-5, roof)
        else:
            wall, roof = (("#727e72", "#435b56"), ("#97785b", "#614b45"),
                          ("#846e89", "#59445f"), ("#ad8d56", "#6c5432"))[site.trade]
            self.canvas.create_polygon(x, y+24, x+24, y+2, right-24, y+2, right, y+24, fill=roof)
        self.box(x, y + 24, right, bottom, wall)
        for offset in (29, 39, 49, 59, 69, 79, 89, 99):
            self.box(x, y+offset, right, y+offset+1, roof)
        self.box(x + 7, y + 15, right - 7, y + 25, roof)
        self.box(x + 8, y + 27, right - 8, y + 81, "#253842")
        self.box(x + 8, y + 27, right - 8, y + 30, site.color)
        for left in (x+14, right-52):
            self.box(left, bottom-20, left+38, bottom-4, roof)
            self.box(left+3, bottom-17, left+35, bottom-7, "#71969a")
            self.box(left+18, bottom-17, left+21, bottom-7, roof)
        if site.role == "PUBLIC SHOP":
            for offset in range(8, 168, 16):
                self.box(x+offset, bottom-24, x+offset+16, bottom-19,
                         site.color if offset % 32 == 8 else "#eee0c6")
        self.box(door_x - 15, bottom - 15, door_x + 15, bottom, "#14252f")
        self.box(door_x + 7, bottom - 9, door_x + 10, bottom - 7, GOLD)
        self.box(door_x - 15, bottom, door_x + 15, bottom + 6, site.color)
        self.box(door_x - 10, bottom + 9, door_x + 10, bottom + 11, "#b3c7bd")
        self.label(x + 13, y + 39, site.role, 8, site.color, True)
        self.label(x + 13, y + 54, site.name, 12, WHITE, True)

    def draw_supplier(self, site):
        x, y, right, bottom = site.bounds
        canvas = self.canvas
        ground = ("#786650", "#355940", "#784a40", "#586038")[site.trade]
        self.box(x, y+44, right, bottom, ground)
        sign_right = x+97 if site.trade == 0 else right-2
        self.box(x+2, y, sign_right, y+(48 if site.trade == 0 else 41), "#253842")
        self.box(x+2, y, sign_right, y+3, site.color)
        self.label(x+9, y+16, site.name, 10 if site.trade == 0 else 12, WHITE, True)
        if site.trade == 0:
            self.draw_mine(site)
        elif site.trade == 1:
            for tree_x, tree_y, scale in ((20, 87, 1.05), (45, 79, .86), (126, 81, .95), (154, 85, 1.02)):
                self.draw_pine(x+tree_x, y+tree_y, scale)
            self.draw_mill_cabin(x+65, y+88)
            self.draw_pine(x+29, y+100, .91)
            for offset, height in ((135, 94), (151, 94), (143, 83), (158, 83), (150, 72)):
                log_x, log_y = x + offset, y + height
                self.box(log_x-14, log_y-5, log_x, log_y+5, "#72472d")
                canvas.create_oval(log_x-5, log_y-5, log_x+5, log_y+5, fill="#cd9b65", outline="#62432f", width=1)
                canvas.create_oval(log_x-2, log_y-2, log_x+2, log_y+2, fill="#9a663e", width=0)
        elif site.trade == 2:
            self.draw_clay_pit(x+88, y+70)
        else:
            canvas.create_oval(x+21, y+57, right-21, bottom-3, fill="#5b4a2b", width=0)

    def draw_clay_pit(self, x, y):
        rings = []
        for width, depth, level in ((68, 42, 0), (58, 35, 0), (46, 27, -5),
                                    (37, 22, -5), (28, 16, -11), (17, 9, -16)):
            rings.append(tuple((px*width, py*depth, level) for px, py in
                               ((-.8, -1), (.8, -1), (1, -.58), (1, .58),
                                (.8, 1), (-.8, 1), (-1, .58), (-1, -.58))))
        palettes = (
            ("#d9946c", "#e2a77e", "#c17958", "#a86149"),
            ("#ab644b", "#bb7254", "#824837", "#693e33"),
            ("#e2a078", "#ce8962", "#a76047", "#94533d"),
            ("#97543e", "#a45c44", "#6d3e32", "#58332c"),
            ("#784336", "#94513b", "#63392e", "#4c2c27"),
        )
        self.draw_mesh(x, y, rings[0], ((tuple(range(8)), "#613a34"),), skew=.16)
        for outer, inner, colors in zip(rings, rings[1:], palettes):
            faces = [((index, (index+1) % 8, (index+1) % 8+8, index+8), colors[index//2])
                     for index in range(8)]
            self.draw_mesh(x, y, outer+inner, faces, skew=.16)
        self.draw_mesh(x, y, rings[-1], ((tuple(range(8)), "#402823"),), skew=.16)

    def draw_wheat_field(self, tag="live"):
        """Draw the detailed wheat field as static scenery to keep frames light."""
        farm = SITES[9]
        canvas = self.canvas
        center_x, center_y = farm.x + 88, farm.y + 79
        wind = self.town.elapsed * math.tau / 4
        # Back rows are drawn first so the front rows overlap them.
        for row_y, height in ((-9, 15), (-1, 17), (7, 18), (15, 19)):
            # Keep each row inside the oval field, which is 134 by 44 pixels.
            half_width = 67 * math.sqrt(1 - (row_y / 22) ** 2) - 9
            count = max(2, int(half_width * 2 // 9))
            for index in range(count + 1):
                base_x = center_x - half_width + index * 2 * half_width / count
                base_y = center_y + row_y
                sway = 3 * math.sin(wind - base_x * .12)
                top_x, top_y = base_x + sway, base_y - height
                # Unit vectors along the stalk and across it, for the ear of grain.
                along_x, along_y = sway / height, -1
                length = math.hypot(along_x, along_y)
                along_x, along_y = along_x / length, along_y / length
                across_x, across_y = -along_y, along_x
                canvas.create_line(base_x, base_y, top_x, top_y, fill="#a8913f", tags=tag)
                tip_x, tip_y = top_x + along_x * 3, top_y + along_y * 3
                mid_x, mid_y = top_x - along_x * 2.5, top_y - along_y * 2.5
                canvas.create_polygon(
                    tip_x, tip_y,
                    mid_x + across_x * 1.8, mid_y + across_y * 1.8,
                    top_x - along_x * 8, top_y - along_y * 8,
                    mid_x - across_x * 1.8, mid_y - across_y * 1.8,
                    fill="#f2cc63" if index % 2 else "#e0b44a", outline="#a87b2c", tags=tag,
                )
                canvas.create_line(tip_x, tip_y, tip_x + along_x * 4 + across_x * 1.5,
                                   tip_y + along_y * 4 + across_y * 1.5, fill="#e8c66a", tags=tag)

    def mine_mesh(self, site, vertices, faces, tag="city"):
        self.draw_mesh(site.x+109, site.y+83, vertices, faces, skew=-0.65, tag=tag)

    def draw_block(self, project, x, y, z, width, depth, height, colors):
        vertices = [(x+dx, y+dy, z+dz)
                    for dz in (0, height)
                    for dx, dy in ((0, 0), (width, 0), (width, depth), (0, depth))]
        side, front, top = colors
        project(vertices, (
            ((1, 2, 6, 5), side), ((2, 3, 7, 6), front), ((4, 5, 6, 7), top),
        ))

    def draw_mill_cabin(self, origin_x, origin_y):
        def project(vertices, faces):
            self.draw_mesh(origin_x, origin_y, vertices, faces, skew=-0.55)

        timber = ("#6e4430", "#9b6543", "#d8a571")
        dark_wood = ("#4e3428", "#724b35", "#a5724e")
        self.draw_block(project, 0, -17, 0, 48, 42, 4, dark_wood)
        for height in range(4, 25, 4):
            self.draw_block(project, -1, -18, height, 50, 28, 4, timber)

        # The door and windows sit on the visible front and right walls.
        self.draw_block(project, 30, 10, 4, 12, 1, 19, dark_wood)
        for offset in (7, 13):
            self.draw_block(project, offset, 10, 14, 5, 1, 7, ("#426165", "#94aeb0", "#c0cfbd"))
        for offset in (-11, -4):
            self.draw_block(project, 49, offset, 13, 1, 6, 9, ("#456163", "#456163", "#b69771"))
        self.draw_block(project, 39, 11, 11, 1, 1, 1, ("#ecd696", "#ecd696", "#ecd696"))
        for post in (0, 46):
            self.draw_block(project, post, 22, 4, 2, 2, 19, timber)
        for post in range(3, 26, 5):
            self.draw_block(project, post, 22, 4, 1.5, 1.5, 6, timber)
        self.draw_block(project, 0, 22, 10, 27, 2, 2, timber)
        for depth, height in ((24, 3), (28, 1)):
            self.draw_block(project, 29, depth, 0, 15, 5, height, timber)

        project(((49, -18, 28), (49, -6, 41), (49, 10, 28)),
                (((0, 1, 2), "#79523a"),))
        roof = ("#a75d3e", "#ba714b", "#cb8156", "#d69464")
        for column, left in enumerate(range(-4, 52, 7)):
            for row, (back, front, ridge, eave) in enumerate((
                (-21, -6, 27, 42), (-6, 3, 42, 34), (3, 12, 34, 26), (12, 26, 26, 22),
            )):
                vertices = ((left, back, ridge), (left+7, back, ridge),
                            (left+7, front, eave), (left, front, eave))
                project(vertices, (((0, 1, 2, 3), roof[(column + row) % 4]),))
        self.draw_block(project, 6, -12, 35, 7, 7, 12, ("#625a50", "#80766b", "#a49985"))

    def draw_mine(self, site):
        rock = ("#3e4b4b", "#546461", "#687572", "#7f8c85", "#3d5750")
        wood = ("#71482f", "#a06a42", "#c78a53")

        def block(*dimensions):
            self.draw_block(lambda vertices, faces: self.mine_mesh(site, vertices, faces), *dimensions)

        def boulder(x, y, width, depth, height):
            vertices = [(x, y, 0), (x+width, y, 0), (x+width, y+depth, 0), (x, y+depth, 0),
                        (x+width*.22, y+depth*.1, height*.84), (x+width*.81, y+depth*.15, height),
                        (x+width*.91, y+depth*.73, height*.7), (x+width*.15, y+depth*.89, height*.56)]
            self.mine_mesh(site, vertices, (
                ((1, 2, 6, 5), rock[0]), ((2, 3, 7, 6), rock[1]),
                ((4, 5, 7), rock[3]), ((5, 6, 7), rock[2]), ((0, 3, 7, 4), rock[4]),
            ))

        boulder(-19, -15, 34, 22, 50)
        boulder(4, -9, 37, 23, 43)
        boulder(-34, -4, 22, 24, 19)
        boulder(17, 3, 26, 22, 34)
        self.mine_mesh(site, ((-14, 4, 0), (15, 4, 0), (15, 4, 24), (-14, 4, 24)),
                       (((0, 1, 2, 3), "#101718"),))
        for depth in range(5, 39, 6):
            block(-14, depth, 0, 28, 3, 2, wood)
        for rail in (-9, 8):
            block(rail, 3, 2, 2, 38, 1, ("#536268", "#627077", "#a4b1b3"))
        for post in (-15, 13):
            block(post, 3, 0, 4, 13, 22, wood)
        for plank in range(-16, 18, 5):
            block(plank, -2, 22, 5, 20, 3, wood)

        for z in (29, 33, 37):
            block(-11, 2, z, 25, 2, 3, wood)
        for direction in (-1, 1):
            self.mine_mesh(site, ((2+direction*2, 5, 30), (2+direction*8, 5, 39),
                                  (2+direction*9, 5, 38), (2+direction*3, 5, 29),
                                  (2+direction*3, 5, 37), (2+direction*8, 5, 40),
                                  (2+direction*12, 5, 37), (2+direction*8, 5, 38)),
                           (((0, 1, 2, 3), "#5c3928"), ((4, 5, 6, 7), "#c3c7bd")))
        for rung in range(4, 28, 5):
            depth = 32 - rung * 0.48
            block(31, depth, rung, 9, 2, 1.5, wood)
        for x in (30, 39):
            self.mine_mesh(site, ((x, 32, 0), (x+2, 32, 0), (x+2, 18, 29), (x, 18, 29)),
                           (((0, 1, 2, 3), wood[2]),))
        boulder(18, 24, 9, 8, 7)

    def draw_mine_cart(self):
        site = SITES[0]
        phase = self.town.elapsed % 8
        depth = -8 + 40 * (1 - math.cos(phase * math.tau / 8)) / 2
        rear, front = max(depth-5, 15), depth+5
        if front <= rear:
            return
        vertices = [(-8, rear, 6), (8, rear, 6), (8, front, 6), (-8, front, 6),
                    (-11, rear, 14), (11, rear, 14), (11, front, 14), (-11, front, 14)]
        for rail in (-8, 8):
            wheel_x = site.x+109 + rail - .65*front
            wheel_y = site.y+83 + .46*front - 4
            self.canvas.create_oval(wheel_x-2.5, wheel_y-2.5, wheel_x+2.5, wheel_y+2.5,
                                    fill="#20272b", width=0, tags="live")
        self.mine_mesh(site, vertices, (
            ((0, 3, 7, 4), "#535c60"), ((2, 3, 7, 6), "#8b9698"),
            ((4, 5, 6, 7), "#2b3739"),
        ), "live")
        if phase <= 4:
            for x, z in ((-6, 16), (1, 19), (6, 16)):
                self.mine_mesh(site, ((x-3, rear, 14), (x, (front+rear)/2, z),
                                      (x+3, front, 14), (x-1, front, 14)),
                               (((0, 1, 3), "#a79a67"), ((1, 2, 3), "#c3b17e")), "live")

    def draw_casino_lights(self):
        frame = int(time.perf_counter() * 5)
        if frame == self.casino_light_frame:
            return
        self.casino_light_frame = frame
        for item, index in self.casino_bulbs:
            color = GOLD if (index // 2 + frame) % 3 == 0 else "#7a5520"
            self.canvas.itemconfigure(item, fill=color)

    def draw_casino_screen(self):
        canvas, town = self.canvas, self.town
        center_x, center_y = CASINO_CENTER
        buttons = self.casino_buttons = []
        spinning = self.spin is not None

        def ring(radius, color, outline="", width=0):
            canvas.create_oval(center_x - radius, center_y - radius, center_x + radius, center_y + radius,
                               fill=color, outline=outline, width=width, tags="live")

        def point(angle, radius):
            return center_x + radius * math.sin(angle), center_y - radius * math.cos(angle)

        # Table
        self.box(center_x - 300, 116, center_x + 300, 930, "#123b2c", "live")
        self.box(center_x - 300, 116, center_x + 300, 119, GOLD, "live")
        self.box(center_x - 292, 124, center_x + 292, 922, "#15452f", "live")
        self.label(center_x, 146, "FOUNDRY CASINO", 18, GOLD, True, anchor="center", tag="live")
        self.label(center_x, 170, "EUROPEAN ROULETTE  ·  37 POCKETS", 8, MINT, True, anchor="center", tag="live")
        self.box(center_x + 252, 130, center_x + 284, 162, "#0d2d21", "live")
        self.label(center_x + 268, 146, "✕", 13, WHITE, True, anchor="center", tag="live")
        buttons.append((center_x + 252, 130, center_x + 284, 162, self.close_casino))

        # Wheel
        wheel, ball = self.wheel_state()
        seg = math.tau / len(ROULETTE_POCKETS)
        ring(194, "#4a2614")
        ring(186, "#7a4424")
        ring(182, "#2a1a10")
        ring(163, GOLD)
        dark = {"red": "#8e1f2a", "black": "#0c0d10", "green": "#13633a"}
        for index, number in enumerate(ROULETTE_POCKETS):
            color = roulette_color(number)
            start, end = wheel + (index - .5) * seg, wheel + (index + .5) * seg
            winner = not spinning and index == self.ball_pocket
            canvas.create_polygon(*point(start, 161), *point(end, 161), *point(end, 133), *point(start, 133),
                                  fill=POCKET_COLORS[color], outline=GOLD if winner else "",
                                  width=2 if winner else 0, tags="live")
            canvas.create_polygon(*point(start, 133), *point(end, 133), *point(end, 111), *point(start, 111),
                                  fill=dark[color], tags="live")
            canvas.create_line(*point(start, 111), *point(start, 161), fill="#c9a24a", tags="live")
            self.label(*point(wheel + index * seg, 147), str(number), 8, WHITE, True,
                       anchor="center", tag="live")
        ring(111, "#6b3d22", "#c9a24a", 1)
        ring(84, "#8a5a33")
        ring(46, "#b07a45")
        for arm in range(4):
            angle = wheel + arm * math.tau / 4 + seg / 2
            canvas.create_line(*point(angle, 8), *point(angle, 58), fill=GOLD, width=3, tags="live")
            knob_x, knob_y = point(angle, 60)
            canvas.create_oval(knob_x - 5, knob_y - 5, knob_x + 5, knob_y + 5, fill=GOLD, width=0, tags="live")
        ring(13, GOLD)
        if ball is not None:
            ball_x, ball_y = point(*ball)
            canvas.create_oval(ball_x - 6, ball_y - 6, ball_x + 6, ball_y + 6,
                               fill="#f7f7f2", outline="#9aa3a6", tags="live")

        # Result
        text, color = self.casino_result
        self.label(center_x, 604, text, 13, color, True, anchor="center", tag="live")

        # Chips
        self.label(center_x, 634, "CHIP", 8, MUTED, True, anchor="center", tag="live")
        chip_colors = ("#e6e9df", "#d65655", "#3f8fd2", "#2f9e5e", "#1b1d22")
        for index, value in enumerate(CHIPS):
            chip_x, chip_y = center_x + (index - 2) * 64, 670
            affordable = value <= town.cash
            if index == self.chip_index:
                canvas.create_oval(chip_x - 28, chip_y - 28, chip_x + 28, chip_y + 28,
                                   outline=GOLD, width=3, tags="live")
            fill = chip_colors[index] if affordable else "#4a5559"
            canvas.create_oval(chip_x - 22, chip_y - 22, chip_x + 22, chip_y + 22,
                               fill=fill, outline="#f2f7f6", width=2, tags="live")
            canvas.create_oval(chip_x - 15, chip_y - 15, chip_x + 15, chip_y + 15,
                               outline="#f2f7f6" if index else INK, width=1, tags="live")
            text_color = INK if index == 0 and affordable else (WHITE if affordable else MUTED)
            self.label(chip_x, chip_y, f"${value}", 10, text_color, True, anchor="center", tag="live")
            buttons.append((chip_x - 24, chip_y - 24, chip_x + 24, chip_y + 24,
                            lambda index=index: setattr(self, "chip_index", index)))

        # Bets
        for offset, choice, title, detail in ((-190, "red", "RED  (R)", "Pays 2×  ·  18 numbers"),
                                              (0, "black", "BLACK  (B)", "Pays 2×  ·  18 numbers"),
                                              (190, "green", "GREEN 0  (G)", "Pays 36×  ·  1 number")):
            left, right = center_x + offset - 85, center_x + offset + 85
            fill = "#3a4044" if spinning else POCKET_COLORS[choice]
            canvas.create_rectangle(left, 712, right, 772, fill=fill, outline=GOLD, width=2, tags="live")
            self.label(center_x + offset, 734, title, 13, WHITE, True, anchor="center", tag="live")
            self.label(center_x + offset, 756, detail, 8, "#e9dccb", anchor="center", tag="live")
            buttons.append((left, 712, right, 772, lambda choice=choice: self.spin_wheel(choice)))

        # Recent results
        self.label(center_x - 270, 812, "LAST SPINS", 8, MUTED, True, tag="live")
        if not self.roulette_history:
            self.label(center_x - 170, 812, "No spins yet", 9, MUTED, tag="live")
        for index, number in enumerate(self.roulette_history):
            spot_x = center_x - 160 + index * 34
            canvas.create_oval(spot_x - 13, 799, spot_x + 13, 825,
                               fill=POCKET_COLORS[roulette_color(number)], outline=GOLD if index == 0 else "",
                               width=2, tags="live")
            self.label(spot_x, 812, str(number), 9, WHITE, True, anchor="center", tag="live")

        self.label(center_x, 862, "Click a color or press R, B or G   ·   ← →  change chip   ·   Esc or E  leave",
                   9, MUTED, anchor="center", tag="live")
        self.label(center_x, 894, f"CASH  ${town.cash:,}", 13, GOLD, True, anchor="center", tag="live")

    def draw_live(self):
        canvas, town = self.canvas, self.town
        canvas.delete("live")
        phase = town.market_elapsed % DAY_SECONDS
        is_daytime = phase < DAYLIGHT_SECONDS
        duration = DAYLIGHT_SECONDS if is_daytime else NIGHT_SECONDS
        phase_elapsed = phase if is_daytime else phase-DAYLIGHT_SECONDS
        fraction = phase_elapsed/duration
        self.world_view.set_night(not is_daytime)
        self.world_view.set_visible(not self.casino_open)
        if not self.casino_open:
            self.world_view.render(BODY_COLORS, HAIR_COLORS, COSTUMES)
        self.hud_label("day", 308, 30, f"DAY {town.day:02}", 14, WHITE, True)
        progress = round(104*self.scale_x*fraction), town.cash, is_daytime
        if progress != self.last_progress:
            self.canvas.coords(self.day_progress, 308*self.scale_x, 52*self.scale_y,
                               308*self.scale_x+progress[0], 59*self.scale_y)
            self.canvas.itemconfigure(self.day_progress, fill=MINT if is_daytime else GOLD)
            self.canvas.coords(self.cash_progress, 451*self.scale_x, 52*self.scale_y,
                               (451+180*(1 if town.won else max(0, min(town.cash/CASH_GOAL, 1))))*self.scale_x, 59*self.scale_y)
            self.last_progress = progress
        minutes, seconds = divmod(max(0, math.ceil(duration-phase_elapsed)), 60)
        phase_name = "DAY" if is_daytime else "NIGHT"
        self.hud_label("phase", 308, 77, f"{phase_name} · {minutes}:{seconds:02} left", 9, MUTED)
        self.hud_label("cash", 451, 30, f"CASH  ${town.cash:,}", 14, GOLD, True)
        self.hud_label("goal", 451, 77, "MILESTONE COMPLETE" if town.won else f"${CASH_GOAL} GOAL", 9, MUTED)
        reserved = f"   +{town.reserved} at factory" if town.reserved else ""
        cargo_label = "BAG + TRUNK" if town.vehicle else "BAG"
        self.hud_label("bag", 673, 25, f"{cargo_label}  {town.cargo}/{town.carry_capacity}{reserved}", 12, WHITE, True)
        supplies = "  ".join(f"{name} {quantity}" for name, quantity in zip(("Ore", "Wood", "Clay", "Wheat"), town.supplies))
        goods = "  ".join(f"{name} {quantity}" for name, quantity in zip(("Tools", "Furn.", "Pots", "Bread"), town.goods))
        self.hud_label("supplies", 673, 51, supplies+f"  Eggs {town.eggs}", 9, MUTED)
        self.hud_label("goods", 673, 74, goods+f"  Mach. {town.tier2_goods}  Pastéis {town.industry_goods['PASTELARIA']}", 9, MUTED)
        near = town.nearby()
        self.hud_label("message", 24, MAP_BOTTOM+23, town.message, 11, WHITE, True)
        hint = f"{near.name}   ·   {town.action_hint(near)}" if near else "P · Find suppliers, factories, markets and landmarks     M · Map     F1 · Settings"
        if near is None:
            from tram import TRAM_FARE, nearby_stop
            stop = nearby_stop(town.x, town.y)
            if stop is not None:
                hint = f"{stop.name} · E  Board the yellow tram · ${TRAM_FARE} per trip"
        self.hud_label("hint", 24, MAP_BOTTOM+46, hint, 10, GOLD if near else MUTED)
        if town.elapsed < town.speed_until:
            power_status = f"Speed boost · {math.ceil(town.speed_until-town.elapsed)}s"
        elif town.power_up is not None:
            power_status = "Power-up on the map"
        else:
            power_status = f"Next power-up in {math.ceil(POWER_INTERVAL-town.elapsed % POWER_INTERVAL)}s"
        if town.vehicle in VEHICLES:
            surface = "ROAD" if town.road_bonus_active else "OFF-ROAD"
            power_status = f"{VEHICLES[town.vehicle].label} · {surface} {town.movement_speed:g} · {power_status}"
        self.hud_label("power-status", WIDTH-24, MAP_BOTTOM+73, power_status, 9, MINT, anchor="e")
        if self.casino_open:
            self.draw_casino_screen()

class StartMenu:
    """Load player progress without blocking Tk while the API responds."""

    def __init__(self, root, connection=None):
        self.root = root
        self.connection = connection
        self.session = None
        self.worker = ThreadPoolExecutor(max_workers=1)
        self.music = music_for(root)
        root.title("Foundry Town | Lisboa")
        root.configure(bg=INK)
        root.attributes("-fullscreen", True)
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.frame = tk.Frame(root, bg=INK, padx=48, pady=28)
        self.frame.pack(expand=True)
        tk.Label(self.frame, text="FOUNDRY TOWN", font=(FONT, 24, "bold"),
                 bg=INK, fg=GOLD).pack(pady=12)
        tk.Label(self.frame, text="LISBOA · Build your fortune along the Tejo.",
                 bg=INK, fg=WHITE).pack(pady=8)
        self.status = tk.StringVar(value="Loading your save…")
        tk.Label(self.frame, textvariable=self.status, bg=INK, fg=MINT,
                 wraplength=440).pack(pady=12)
        tk.Label(self.frame, text="CREATE YOUR CHARACTER", font=(FONT, 14, "bold"),
                 bg=INK, fg=WHITE).pack(anchor="w", pady=(4, 8))
        self.character_vars = {
            "name": tk.StringVar(root, "Player"),
            "body": tk.StringVar(root, "Peach"),
            "hair": tk.StringVar(root, "Chestnut"),
            "costume": tk.StringVar(root, "Builder"),
        }
        character_frame = tk.Frame(self.frame, bg=INK)
        character_frame.pack(fill="x", pady=(0, 8))
        self.preview = tk.Canvas(character_frame, width=100, height=116, bg="#20343c", highlightthickness=0)
        self.preview.pack(side="right", padx=(22, 0), pady=4)
        options = tk.Frame(character_frame, bg=INK)
        options.pack(side="left", fill="x", expand=True)
        tk.Label(options, text="Name", bg=INK, fg=WHITE).grid(row=0, column=0, sticky="w", pady=3)
        tk.Entry(options, textvariable=self.character_vars["name"], width=24).grid(row=0, column=1, sticky="ew", pady=3)
        for row, (key, label, choices) in enumerate((
            ("body", "Skin", BODY_COLORS), ("hair", "Hair", HAIR_COLORS), ("costume", "Outfit", COSTUMES),
        ), start=1):
            tk.Label(options, text=label, bg=INK, fg=WHITE).grid(row=row, column=0, sticky="w", pady=3)
            tk.OptionMenu(options, self.character_vars[key], *choices).grid(row=row, column=1, sticky="ew", pady=3)
        options.columnconfigure(1, weight=1)
        for variable in self.character_vars.values():
            variable.trace_add("write", lambda *_: self.draw_character_preview())
        self.draw_character_preview()
        self.new_button = tk.Button(self.frame, text="New Game", command=self.new_game, state="disabled")
        self.new_button.pack(fill="x", pady=4)
        self.continue_button = tk.Button(self.frame, text="Continue", command=self.continue_game, state="disabled")
        self.continue_button.pack(fill="x", pady=4)
        self.rules_button = tk.Button(self.frame, text="Rules & How to Play", command=lambda: show_rules(self.root))
        self.rules_button.pack(fill="x", pady=4)
        tk.Button(self.frame, text="Quit", command=self.close).pack(fill="x", pady=(10, 4))
        self.future = self.worker.submit(self.load, connection)
        self.poll_timer = root.after(50, self.poll)

    @staticmethod
    def load(connection):
        storage, player = connection if connection is not None else desktop_storage()
        revision, saved = storage.load(player)
        if saved is not None:
            unpack_save(saved)
        return storage, player, revision, saved

    def poll(self):
        if not self.future.done():
            self.poll_timer = self.root.after(50, self.poll)
            return
        try:
            self.session = self.future.result()
        except Exception as exc:
            self.status.set(f"Could not load your save. {exc}")
            return
        storage, _, _, saved = self.session
        location = "Online save" if isinstance(storage, RemoteSaves) else "Saved on this computer"
        self.status.set(f"{location} · ${saved['state']['cash']:,}" if saved else f"{location} · No game yet")
        if saved is not None:
            for key, value in saved["state"].get("profile", {}).items():
                if key in self.character_vars:
                    self.character_vars[key].set(value)
        self.new_button.configure(state="normal")
        self.continue_button.configure(state="normal" if saved else "disabled")

    def new_game(self):
        if self.session[3] is not None and not messagebox.askyesno(
            "New Game", "Replace this player's existing progress with a new game?", parent=self.root
        ):
            return
        storage, player, revision, _ = self.session
        self.start((storage, player, revision, None))

    def continue_game(self):
        self.start(self.session)

    def start(self, session):
        self.worker.shutdown(wait=False)
        self.frame.destroy()
        Game(self.root, session, self.character_values())

    def character_values(self):
        return {key: variable.get() for key, variable in self.character_vars.items()}

    def draw_character_preview(self):
        if not hasattr(self, "preview") or not self.preview.winfo_exists():
            return
        preview = self.preview
        preview.delete("all")
        profile = self.character_values()
        draw_character(preview, profile, BODY_COLORS, HAIR_COLORS, COSTUMES, 25, 40, tag="preview")
        preview.scale("all", 0, 0, 2, 2)

    def close(self):
        self.root.after_cancel(self.poll_timer)
        self.worker.shutdown(wait=False)
        self.music.stop()
        self.root.destroy()


if __name__ == "__main__":
    configure_display_dpi()
    window = tk.Tk()
    try:
        StartMenu(window)
    except Exception as exc:
        messagebox.showerror("Could not open Foundry Town", str(exc), parent=window)
        window.destroy()
    else:
        window.mainloop()
