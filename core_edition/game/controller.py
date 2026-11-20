"""Interpret player actions. The view only reads this state."""

from catalog import ROUTES, WAREHOUSE, entrance
from economy import Town
from world import move


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
            if entrance(self.town.x, self.town.y):
                self.screen = "shop"
                self.message = ""
        elif self.screen == "shop" and key in ("e", "q"):
            i, role = entrance(self.town.x, self.town.y)
            if key == "q" and role != "supplier":
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
        if self.screen == "street":
            dx = int(bool(self.keys & {"right", "d"})) - int(
                bool(self.keys & {"left", "a"})
            )
            dy = int(bool(self.keys & {"down", "s"})) - int(
                bool(self.keys & {"up", "w"})
            )
            before = t.x, t.y
            t.x, t.y = move(t.x, t.y, dx, dy, dt)
            self.moving = before != (t.x, t.y)
            if dx:
                self.facing = 1 if dx > 0 else -1
        if self.save_age >= 5:
            self.save()

    def target(self):
        r = ROUTES[self.route]
        return (r.supplier, r.workshop, r.market, WAREHOUSE)[self.stop]
