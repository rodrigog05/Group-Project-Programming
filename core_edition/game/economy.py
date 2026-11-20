"""All transactions operate on one local town. Production time is active play time."""

from dataclasses import dataclass, field

from catalog import FERRY_FARE, PIERS, ROUTES, VEHICLE_BY_KEY, VEHICLES, entrance
from world import SPEED, on_road, walkable

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
    vehicle: str = None  # A key in VEHICLE_BY_KEY, or None on foot

    @property
    def ride(self):
        return VEHICLE_BY_KEY.get(self.vehicle)

    @property
    def capacity(self):
        """Bag slots plus the trunk of the vehicle you drive."""
        trunk = self.ride.trunk if self.ride else 0
        return BASE_CAPACITY * (2 if self.upgraded else 1) + trunk

    @property
    def speed(self):
        if self.ride is None:
            return SPEED
        return self.ride.road_speed if on_road(self.x, self.y) else self.ride.offroad_speed

    def buy_vehicle(self, index):
        """Buy one of the garage's vehicles. Buying a different one replaces your current ride."""
        ride = VEHICLES[index]
        if self.vehicle == ride.key:
            return f"You already drive the {ride.label.lower()}."
        room = BASE_CAPACITY * (2 if self.upgraded else 1) + ride.trunk
        if self.carried + self.reserved > room:
            return f"The {ride.label.lower()} carries {room} items. Unload first."
        if self.cash < ride.price:
            return f"The {ride.label.lower()} costs ${ride.price}. You need more cash."
        self.cash -= ride.price
        self.vehicle = ride.key
        return f"Bought the {ride.label.lower()} for ${ride.price}. Capacity {self.capacity}."

    def take_ferry(self):
        """Pay the fare and land at the other pier. Returns (crossed, message)."""
        location = entrance(self.x, self.y)
        if location is None or location[1] != "ferry":
            return False, "Walk to a ferry pier first."
        destination = PIERS[1 - location[0]]
        if not walkable(destination.x, destination.y):
            return False, "The ferry can't dock right now. No fare was charged."
        if self.cash < FERRY_FARE:
            return False, f"A ferry ticket costs ${FERRY_FARE}. You need more cash."
        self.cash -= FERRY_FARE
        self.x, self.y = destination.x, destination.y
        return True, f"Arrived at {destination.name}. Ticket -${FERRY_FARE}."

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
        if location is None or location[1] in ("garage", "ferry"):
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
