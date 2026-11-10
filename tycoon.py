"""Foundry Town, a small business tycoon built with Tkinter."""
from dataclasses import dataclass
import math
from pathlib import Path
import time
import tkinter as tk


WIDTH = 960
MAP_TOP, MAP_BOTTOM = 104, 940
HEIGHT = MAP_BOTTOM + 95
DAY_SECONDS = 24 * 60 * 60
START_CASH, CASH_GOAL, BAG_SIZE = 60, 500, 12
PLAYER_RADIUS, REACH = 10, 35
POWER_INTERVAL = 30
POWER_UPS = (
    ("Bag upgrade", "+", "#80e2b9", 315, 321),
    ("Speed boost", "»", "#86caff", 646, 904),
    ("Cash bonus", "$", "#ffc66c", 812, 708),
)
FONT = "Segoe UI"
WHITE, MUTED, INK = "#f2f7f6", "#a3babb", "#101f28"
GOLD, MINT = "#ffc66c", "#6de0b3"
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

# Name, trade index, and changes to material cost, sale price, and daily demand.
MARKET_EVENTS = (
    ("Builders' boom", 0, 1, 5, 4),
    ("Timber surplus", 1, -2, -4, 3),
    ("Pottery fair", 2, 1, 6, 5),
    ("Harvest festival", 3, -1, 4, 6),
)


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
    Site("Iron Hill Mine", "SUPPLIER", 0, 60, 155, "#d6a46e"),
    Site("Ironworks", "FACTORY", 0, 392, 155, "#ef8f76"),
    Site("Tool Market", "PUBLIC SHOP", 0, 724, 155, "#72d8bc"),
    Site("Pine Mill", "SUPPLIER", 1, 60, 362, "#d6a46e"),
    Site("Oak Workshop", "FACTORY", 1, 392, 362, "#ef8f76"),
    Site("Home Market", "PUBLIC SHOP", 1, 724, 362, "#72d8bc"),
    Site("Redbank Clay Pit", "SUPPLIER", 2, 60, 555, "#e6a17f"),
    Site("Ember Kiln", "FACTORY", 2, 392, 555, "#f3a376"),
    Site("The Pottery Shop", "PUBLIC SHOP", 2, 724, 555, "#d2a7e5"),
    Site("Goldenfield Farm", "SUPPLIER", 3, 60, 748, "#e3c77e"),
    Site("Sunrise Bakery", "FACTORY", 3, 392, 748, "#ebbe83"),
    Site("Daily Bread Market", "PUBLIC SHOP", 3, 724, 748, "#f3ca85"),
)


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
        self.demand = [trade.demand for trade in TRADES]
        self.market_elapsed = 0
        self.costs = [trade.cost for trade in TRADES]
        self.prices = [trade.price for trade in TRADES]
        self.market_event = None
        self.elapsed = 0.0
        self.x, self.y = 480.0, 321.0
        self.facing = 1
        self.won = False
        self.bag_size = BAG_SIZE
        self.speed_until = 0
        self.power_up = None
        self.profile = {"name": "Player", "body": "Peach", "hair": "Chestnut", "costume": "Builder"}
        self.notice = ""
        self.notice_until = 0
        self.message = "Start at a supplier. Buy materials, make goods, then sell them in town."

    def set_profile(self, values):
        name = values.get("name")
        if isinstance(name, str):
            self.profile["name"] = " ".join(name.split())[:24] or "Player"
        for key, choices in (("body", BODY_COLORS), ("hair", HAIR_COLORS), ("costume", COSTUMES)):
            value = values.get(key)
            if isinstance(value, str) and value in choices:
                self.profile[key] = value

    def congratulate(self, quantity, item):
        self.notice = f"Congratulations {self.profile['name']}, you just collect {quantity} {item}"
        self.notice_until = self.elapsed + 4

    @property
    def day(self):
        return int(self.market_elapsed // DAY_SECONDS) + 1

    def sync_market(self, elapsed):
        previous_day = self.day
        self.market_elapsed = max(self.market_elapsed, elapsed)
        if self.day == previous_day:
            return
        self.costs = [trade.cost for trade in TRADES]
        self.prices = [trade.price for trade in TRADES]
        self.demand = [trade.demand for trade in TRADES]
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

    @property
    def cargo(self):
        return sum(self.supplies) + sum(self.goods)

    @property
    def reserved(self):
        return sum(order.quantity for order in self.orders if order is not None)

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
            self.message = f"Bag upgrade collected. You now have {self.bag_size} slots."
        elif self.power_up == 1:
            self.speed_until = self.elapsed + 15
            self.message = "Speed boost collected. Move 50% faster for 15 seconds."
        else:
            self.message = "Cash bonus collected. You earned $30."
            self.add_cash(30)
        self.power_up = None

    def add_cash(self, amount):
        self.cash += amount
        if self.cash >= CASH_GOAL and not self.won:
            self.won = True
            self.message = f"Goal reached on Day {self.day}! Keep trading to grow your business."

    def move(self, dx, dy, seconds):
        length = math.hypot(dx, dy)
        if not length:
            return
        if dx:
            self.facing = 1 if dx > 0 else -1
        speed = 342 if self.elapsed < self.speed_until else 228
        distance = speed * seconds / length
        next_x = min(WIDTH - 17, max(17, self.x + dx * distance))
        next_y = min(MAP_BOTTOM - 15, max(MAP_TOP + 15, self.y + dy * distance))
        if self.can_walk(next_x, self.y):
            self.x = next_x
        if self.can_walk(self.x, next_y):
            self.y = next_y
        self.collect_power_up()

    def can_walk(self, x, y):
        return not any(
            left - PLAYER_RADIUS < x < right + PLAYER_RADIUS
            and top - PLAYER_RADIUS < y < bottom + PLAYER_RADIUS
            for left, top, right, bottom in (site.bounds for site in SITES)
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
        index = site.trade
        trade = TRADES[index]
        space = self.bag_size - self.cargo
        if site.role == "SUPPLIER":
            space -= self.reserved
            quantity = min(4 if bulk else 1, space, self.cash // self.costs[index])
            if not quantity:
                if not space and self.reserved:
                    self.message = "Bag space is reserved for your factory orders."
                else:
                    self.message = "Your bag is full." if not space else "You need more cash for supplies."
                return
            cost = quantity * self.costs[index]
            self.cash -= cost
            self.supplies[index] += quantity
            self.message = f"Picked up {quantity} × {trade.supply} for ${cost}."
            self.congratulate(quantity, trade.supply.lower())
        elif site.role == "FACTORY":
            order = self.orders[index]
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
            quantity = min(self.goods[index], self.demand[index])
            if not quantity:
                self.message = (
                    f"Bring {trade.product.lower()} to sell." if not self.goods[index]
                    else "Today's customers are served. Come back tomorrow."
                )
                return
            revenue = quantity * self.prices[index]
            self.goods[index] -= quantity
            self.demand[index] -= quantity
            self.message = f"Sold {quantity} × {trade.product} to customers for ${revenue}."
            self.congratulate(quantity, trade.product.lower())
            self.add_cash(revenue)

    def site_status(self, site):
        index = site.trade
        trade = TRADES[index]
        if site.role == "SUPPLIER":
            return f"${self.costs[index]} / {trade.supply.lower()}"
        if site.role == "PUBLIC SHOP":
            return f"${self.prices[index]} each  ·  {self.demand[index]} buyers"
        order = self.orders[index]
        if order is None:
            return f"{trade.supply} → {trade.product}"
        if order.ready_at <= self.elapsed:
            return f"Ready for pickup  ·  {order.quantity}"
        return f"In production  ·  {math.ceil(order.ready_at - self.elapsed)}s"

    def action_hint(self, site):
        if site.role == "SUPPLIER":
            return "E  Buy one    •    Q  Buy up to four"
        if site.role == "PUBLIC SHOP":
            return "E  Sell to today's customers"
        order = self.orders[site.trade]
        if order is None:
            return "E  Drop off matching supplies"
        if order.ready_at <= self.elapsed:
            return "E  Collect finished goods"
        return "Production running"


class Game:
    display_scale = 1

    def __init__(self, root):
        self.root = root
        self.town = Town()
        self.market_started_at = market_start()
        self.keys = set()
        self.profile_window = None
        self.last_tick = time.monotonic()
        root.title("Foundry Town | Business Tycoon")
        root.resizable(False, False)
        self.display_scale = min(1, (root.winfo_screenheight() - 100) / HEIGHT,
                                 (root.winfo_screenwidth() - 40) / WIDTH)
        self.canvas = tk.Canvas(root, width=round(WIDTH * self.display_scale),
                                height=round(HEIGHT * self.display_scale), highlightthickness=0, bg=INK)
        self.canvas.pack()
        root.bind("<KeyPress>", self.key_down)
        root.bind("<KeyRelease>", self.key_up)
        root.bind("<FocusOut>", lambda event: self.keys.clear())
        self.canvas.bind("<Button-1>", self.click_profile)
        self.draw_city()
        self.canvas.scale("all", 0, 0, self.display_scale, self.display_scale)
        self.tick()

    def key_down(self, event):
        if self.profile_window is not None:
            return
        key = event.keysym.lower()
        if key not in self.keys and key in ("e", "q"):
            if key == "e" or (self.town.nearby() and self.town.nearby().role == "SUPPLIER"):
                self.town.interact(bulk=(key == "q"))
        self.keys.add(key)

    def key_up(self, event):
        self.keys.discard(event.keysym.lower())

    def tick(self):
        now = time.monotonic()
        dt = now - self.last_tick
        self.last_tick = now
        self.town.sync_market(time.time() - self.market_started_at)
        if self.profile_window is None and self.root.focus_displayof() is not None:
            self.town.advance(dt)
        dx = int("d" in self.keys or "right" in self.keys) - int("a" in self.keys or "left" in self.keys)
        dy = int("s" in self.keys or "down" in self.keys) - int("w" in self.keys or "up" in self.keys)
        self.town.move(dx, dy, min(dt, 0.05))
        self.draw_live()
        self.canvas.scale("live", 0, 0, self.display_scale, self.display_scale)
        self.root.after(25, self.tick)

    def click_profile(self, event):
        x, y = event.x / self.display_scale, event.y / self.display_scale
        if not (880 <= x <= 936 and 19 <= y <= 77) or self.profile_window is not None:
            return
        self.keys.clear()
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
        self.canvas.create_text(
            x, y, text=value, fill=color, anchor=anchor,
            font=(FONT, max(1, round(size * self.display_scale)), "bold" if bold else "normal"), tags=tag,
        )

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
            for x in (23, 249, 378, 580, 708, 934):
                self.canvas.create_oval(x-10, y-7, x+12, y+10, fill="#203a34", width=0)
                self.canvas.create_oval(x-10, y-12, x+9, y+6, fill="#41775b", width=0)
                self.canvas.create_oval(x-6, y-11, x+5, y, fill="#53956d", width=0)
        for name, y in (("01   METAL DISTRICT", 131), ("02   TIMBER DISTRICT", 352),
                        ("03   CLAY DISTRICT", 545), ("04   FARM DISTRICT", 738)):
            self.label(60, y, name, 10, "#bee2c4", True)
        for site in SITES:
            self.draw_site(site)
        self.box(0, 0, WIDTH, MAP_TOP, INK)
        self.label(24, 31, "FOUNDRY TOWN", 21, WHITE, True)
        self.label(25, 66, "BUSINESS TYCOON", 10, MINT, True)
        self.box(0, 102, WIDTH, 104, "#385159")
        self.box(0, MAP_BOTTOM, WIDTH, HEIGHT, INK)
        self.box(0, MAP_BOTTOM, WIDTH, MAP_BOTTOM + 2, "#385159")
        self.label(24, MAP_BOTTOM + 73, "W A S D   Move       E   Interact       Q   Buy four at suppliers", 10, MUTED)

    def draw_site(self, site):
        x, y, right, bottom = site.bounds
        door_x, _ = site.door
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
            canvas.create_oval(x+21, y+57, right-21, bottom-3, fill="#393d2c", width=0)

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

    def draw_gold_pile(self):
        farm = SITES[9]
        phase = self.town.elapsed * math.tau / 6
        scale = .68 + .32 * (1 - math.cos(phase))
        for offset_x, offset_y, elevation, radius in (
            (-26, -11, 0, 14), (-8, -16, 0, 15), (13, -15, 0, 14), (29, -6, 0, 13),
            (-31, 7, 0, 12), (-12, 7, 0, 16), (10, 7, 0, 15), (27, 9, 0, 11),
            (-15, -6, 8, 12), (7, -5, 9, 13), (1, -5, 17, 10),
        ):
            nugget = ((-1, -.45, 0), (-.45, -.9, 0), (.65, -.66, 0), (1, .2, 0),
                      (.4, .75, 0), (-.7, .62, 0), (-.55, -.25, .63), (.31, -.46, .85),
                      (.66, .23, .51), (-.23, .39, .74))
            vertices = [(scale*(offset_x+px*radius), scale*(offset_y+py*radius),
                         scale*(elevation+pz*radius)) for px, py, pz in nugget]
            faces = (
                ((0, 1, 7, 6), "#d49a29"), ((1, 2, 3, 8, 7), "#b97817"),
                ((3, 4, 8), "#965913"), ((4, 5, 9, 8), "#bb7c1c"),
                ((5, 0, 6, 9), "#e2a638"), ((6, 7, 9), "#ffe184"),
                ((7, 8, 9), "#f0bd49"),
            )
            self.draw_mesh(farm.x+88, farm.y+87, vertices, faces, skew=.22, tag="live")

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

    def draw_live(self):
        canvas, town = self.canvas, self.town
        canvas.delete("live")
        nearby = town.nearby()
        self.label(308, 30, f"DAY {town.day:02}", 14, WHITE, True, tag="live")
        day_fraction = (town.market_elapsed % DAY_SECONDS) / DAY_SECONDS
        self.box(308, 52, 412, 59, "#304851", "live")
        self.box(308, 52, 308 + 104 * day_fraction, 59, MINT, "live")
        minutes_left = math.ceil(DAY_SECONDS * (1 - day_fraction) / 60)
        hours, minutes = divmod(minutes_left, 60)
        self.label(308, 77, f"{hours}h {minutes:02}m left", 9, MUTED, tag="live")
        self.label(451, 30, f"CASH  ${town.cash:,}", 14, GOLD, True, tag="live")
        self.box(451, 52, 631, 59, "#304851", "live")
        self.box(451, 52, 451 + 180 * min(town.cash / CASH_GOAL, 1), 59, GOLD, "live")
        goal_text = "GOAL REACHED" if town.won else f"${CASH_GOAL} GOAL"
        self.label(451, 77, goal_text, 9, MUTED, tag="live")
        reserved = f"   +{town.reserved} at factory" if town.reserved else ""
        self.label(673, 25, f"BAG  {town.cargo}/{town.bag_size}{reserved}", 12, WHITE, True, tag="live")
        supplies = "  ".join(f"{name} {quantity}" for name, quantity in zip(("Ore", "Wood", "Clay", "Wheat"), town.supplies))
        goods = "  ".join(f"{name} {quantity}" for name, quantity in zip(("Tools", "Furn.", "Pots", "Bread"), town.goods))
        self.label(673, 51, supplies, 9, MUTED, tag="live")
        self.label(673, 74, goods, 9, MUTED, tag="live")
        self.box(880, 19, 936, 77, "#304851", "live")
        canvas.create_oval(899, 28, 917, 46, fill=GOLD, width=0, tags="live")
        canvas.create_oval(892, 46, 924, 65, fill=GOLD, width=0, tags="live")
        for site in SITES:
            status_y = 34 if site.role == "SUPPLIER" else 72
            self.label(site.x + 12, site.y + status_y, town.site_status(site), 10, MUTED, tag="live")
            if site == nearby:
                x, y, right, bottom = site.bounds
                canvas.create_rectangle(x-2, y-2, right+2, bottom+2, outline=GOLD, width=2, tags="live")
        self.draw_mine_cart()
        self.draw_gold_pile()
        if town.power_up is not None:
            name, symbol, color, power_x, power_y = POWER_UPS[town.power_up]
            canvas.create_oval(power_x-16, power_y-16, power_x+16, power_y+16,
                               fill=INK, outline=color, width=3, tags="live")
            self.label(power_x, power_y, symbol, 15, color, True, anchor="center", tag="live")
            self.label(power_x, power_y-24, name, 10, WHITE, True, anchor="center", tag="live")
        x, y = town.x, town.y
        if town.elapsed < town.speed_until:
            canvas.create_oval(x-14, y-14, x+14, y+14, outline="#86caff", width=2, tags="live")
        profile = town.profile
        outfit, accessory = COSTUMES[profile["costume"]]
        canvas.create_oval(x-11, y+4, x+11, y+12, fill="#1d3330", width=0, tags="live")
        canvas.create_oval(x-9, y-4, x+9, y+9, fill=outfit, outline=INK, width=2, tags="live")
        canvas.create_oval(x-7, y-13, x+7, y, fill=BODY_COLORS[profile["body"]], outline=INK, width=2, tags="live")
        self.box(x-7, y-13, x+7, y-8, HAIR_COLORS[profile["hair"]], "live")
        self.box(x-8, y-16, x+8, y-13, accessory, "live")
        self.box(x-3, y+3, x+3, y+6, accessory, "live")
        if profile["costume"] == "Chef":
            canvas.create_oval(x-6, y-22, x+6, y-14, fill=accessory, width=0, tags="live")
        elif profile["costume"] == "Explorer":
            self.box(x-11, y-15, x+11, y-12, accessory, "live")
        elif profile["costume"] == "Racer":
            self.box(x-8, y-2, x+8, y+1, accessory, "live")
        elif profile["costume"] == "Astronaut":
            canvas.create_oval(x-9, y-17, x+9, y+1, outline=accessory, width=2, tags="live")
        elif profile["costume"] == "Wizard":
            self.box(x-4, y-19, x+4, y-15, accessory, "live")
            self.box(x-2, y-22, x+2, y-18, accessory, "live")
        eye_x = x + 3 * town.facing
        self.box(eye_x, y-6, eye_x+2, y-4, INK, "live")
        self.label(24, MAP_BOTTOM + 23, town.message, 11, WHITE, True, tag="live")
        hint = f"{nearby.name}   ·   {town.action_hint(nearby)}" if nearby else "Follow the colored doorsteps to interact with businesses."
        self.label(24, MAP_BOTTOM + 46, hint, 10, GOLD if nearby else MUTED, tag="live")
        if town.elapsed < town.speed_until:
            power_status = f"Speed boost  ·  {math.ceil(town.speed_until-town.elapsed)}s"
        elif town.power_up is not None:
            power_status = "Power-up on the map"
        else:
            power_status = f"Next power-up in {math.ceil(POWER_INTERVAL-town.elapsed % POWER_INTERVAL)}s"
        self.label(936, MAP_BOTTOM + 73, power_status, 10, MINT, anchor="e", tag="live")
        if town.market_event:
            title, effects = town.market_event
            self.box(237, 107, 723, 146, INK, "live")
            self.box(237, 107, 723, 109, GOLD, "live")
            self.label(480, 119, f"MARKET EVENT  ·  {title}", 10, GOLD, True, anchor="center", tag="live")
            self.label(480, 135, effects, 9, WHITE, anchor="center", tag="live")
        if town.elapsed < town.notice_until:
            offset = 42 if town.market_event else 0
            self.box(194, 106+offset, 766, 144+offset, INK, "live")
            self.box(194, 106+offset, 766, 109+offset, GOLD, "live")
            self.label(480, 126+offset, town.notice, 11, GOLD, True, anchor="center", tag="live")


if __name__ == "__main__":
    window = tk.Tk()
    Game(window)
    window.mainloop()
