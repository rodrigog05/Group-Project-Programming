"""All transactions operate on one local town. Production time is active play time."""

from dataclasses import dataclass, field

from catalog import ROUTES, entrance

UPGRADE_PRICE = 100
BASE_CAPACITY = 12


@dataclass
class Order:
    quantity: int
    remaining: float


@dataclass
class Town:
    cash: int = 60
    x: float = 1368
    y: float = 650
    upgraded: bool = False
    materials: list = field(default_factory=lambda: [0] * len(ROUTES))
    goods: list = field(default_factory=lambda: [0] * len(ROUTES))
    orders: list = field(default_factory=lambda: [None] * len(ROUTES))

    @property
    def capacity(self):
        return BASE_CAPACITY * (2 if self.upgraded else 1)

    @property
    def carried(self):
        return sum(self.materials) + sum(self.goods)

    @property
    def reserved(self):
        return sum(order.quantity for order in self.orders if order)

    def advance(self, dt):
        for order in self.orders:
            if order:
                order.remaining = max(0, order.remaining - max(0, dt))

    def trade(self, bulk=False):
        location = entrance(self.x, self.y)
        if location is None:
            return "Walk to a marked doorstep first."
        i, role = location
        if role == "warehouse":
            if self.upgraded:
                return "Your bag is already upgraded."
            if self.cash < UPGRADE_PRICE:
                return f"The larger bag costs ${UPGRADE_PRICE}."
            self.cash -= UPGRADE_PRICE
            self.upgraded = True
            return "Bag upgraded to 24 slots."
        route = ROUTES[i]
        if role == "supplier":
            free = self.capacity - self.carried - self.reserved
            count = min(4 if bulk else 1, free, self.cash // route.cost)
            if not count:
                return (
                    "Your bag is full or reserved."
                    if free == 0
                    else "You need more cash."
                )
            self.materials[i] += count
            self.cash -= count * route.cost
            return f"Bought {count} × {route.material} for ${count * route.cost}."
        if role == "market":
            count = self.goods[i]
            if not count:
                return f"Bring {route.product} here to sell."
            self.cash += count * route.price
            self.goods[i] = 0
            return f"Sold {count} × {route.product} for ${count * route.price}."
        order = self.orders[i]
        if order:
            if order.remaining > 0:
                return "Your order is still in production."
            self.goods[i] += order.quantity
            self.orders[i] = None
            return f"Collected {order.quantity} × {route.product}."
        count = self.materials[i]
        if not count:
            return f"Bring {route.material} here to make {route.product}."
        self.orders[i] = Order(count, route.seconds)
        self.materials[i] = 0
        return f"Making {count} × {route.product}. Ready in {route.seconds}s."
