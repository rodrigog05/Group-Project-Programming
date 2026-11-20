"""Interpret player actions. The view only reads this state."""

from catalog import FERRY_FARE, ROUTES, VEHICLES, WAREHOUSE, entrance
from economy import Town
from world import move, walkable

FERRY_SECONDS = 4.5


class Session:
    MENU_SCREENS = ("menu", "rules", "confirm_new")

    def __init__(self, storage):
        self.storage = storage
        self.town = storage.restore()
        self.screen = "menu"
        self.message = ""
        self.route = 3
        self.stop = 0
        self.keys = set()
        self.focus = True
        self.facing = 1
        self.moving = False
        self.elapsed = 0
        self.menu_elapsed = 0
        self.save_age = 0
        self.ferry_elapsed = 0
        self.ferry_heading = 1  # 1 = Lisbon to Almada, -1 = Almada to Lisbon

    def save(self):
        if self.screen in self.MENU_SCREENS:
            return
        self.storage.write(self.town)
        self.save_age = 0

    def menu_key(self, key):
        if self.screen == "rules":
            if key == "escape":
                self.screen = "menu"
            return
        if self.screen == "confirm_new":
            if key == "escape":
                self.screen = "menu"
            elif key == "y":
                self.start_new()
            return
        if key == "n":
            if self.storage.has_save:
                self.screen = "confirm_new"
            else:
                self.start_new()
        elif key == "c" and self.storage.has_save:
            self.screen = "street"
        elif key == "r":
            self.screen = "rules"

    def start_new(self):
        self.town = Town()
        self.screen = "street"
        self.save()

    def key(self, key):
        if key in self.keys:
            return
        self.keys.add(key)
        if self.screen in self.MENU_SCREENS:
            self.menu_key(key)
            return
        if key == "escape":
            self.screen = "street"
            self.message = ""
            self.save()
        elif self.screen == "ferry":
            return
        elif key in ("p", "i") and self.screen in ("street", "guide"):
            self.screen = "guide" if self.screen == "street" else "street"
        elif self.screen == "guide":
            if key in ("1", "2", "3", "4"):
                self.route = int(key) - 1
                self.stop = 0
            elif key in ("a", "b", "c"):
                self.stop = "abc".index(key)
                self.screen = "street"
            elif key == "u":
                self.stop = 3
                self.screen = "street"
        elif key == "e" and self.screen == "street":
            place = entrance(self.town.x, self.town.y)
            if place and place[1] == "ferry":
                crossed, self.message = self.town.take_ferry()
                if crossed:
                    self.screen, self.ferry_elapsed = "ferry", 0
                    self.ferry_heading = 1 if place[0] == 0 else -1
                    self.save()
            elif place:
                self.screen = "shop"
                self.message = ""
        elif self.screen == "shop" and key in ("1", "2", "3", "4")[: len(VEHICLES)]:
            if entrance(self.town.x, self.town.y)[1] == "garage":
                self.message = self.town.buy_vehicle(int(key) - 1)
                self.save()
        elif self.screen == "shop" and key in ("e", "q"):
            i, role = entrance(self.town.x, self.town.y)
            if role == "garage" or (key == "q" and role != "supplier"):
                return
            self.message = self.town.trade(key == "q")
            if i is not None:
                self.route = i
                self.stop = {
                    "supplier": 1,
                    "workshop": 2 if self.town.goods[i] else 1,
                    "market": 0,
                }[role]
            self.save()

    def tick(self, dt):
        self.moving = False
        if not self.focus:
            return
        dt = min(0.25, max(dt, 0))
        if self.screen in self.MENU_SCREENS:
            self.menu_elapsed += dt
            return
        self.elapsed += dt
        self.save_age += dt
        t = self.town
        t.advance(dt)
        if self.screen == "ferry":
            self.ferry_elapsed += dt
            if self.ferry_elapsed >= FERRY_SECONDS:
                self.screen = "street"
        if self.screen == "street":
            dx = int(bool(self.keys & {"right", "d"})) - int(
                bool(self.keys & {"left", "a"})
            )
            dy = int(bool(self.keys & {"down", "s"})) - int(
                bool(self.keys & {"up", "w"})
            )
            before = t.x, t.y
            driving = t.vehicle is not None
            t.x, t.y = move(t.x, t.y, dx, dy, dt, t.speed, driving)
            self.moving = before != (t.x, t.y)
            if self.moving:
                self.message = ""  # Street messages last until the player walks on.
            ahead = t.x + dx * 12, t.y + dy * 12
            if (dx or dy) and not driving and walkable(*ahead, True) and not walkable(*ahead):
                self.message = (f"The bridges are for vehicles only. Take the ferry (${FERRY_FARE}) "
                                "or buy a ride at a garage.")
            if dx:
                self.facing = 1 if dx > 0 else -1
        if self.save_age >= 5:
            self.save()

    def target(self):
        r = ROUTES[self.route]
        return (r.supplier, r.workshop, r.market, WAREHOUSE)[self.stop]
