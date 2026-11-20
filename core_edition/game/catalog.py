"""The four desktop supply chains, garages, ferry and casino. A location is a doorstep in world pixels."""

from dataclasses import dataclass
from math import dist


@dataclass(frozen=True)
class Shop:
    name: str
    x: int
    y: int

    def nearby(self, x, y):
        return dist((x, y), (self.x, self.y)) <= 35


@dataclass(frozen=True)
class Route:
    material: str
    product: str
    cost: int
    price: int
    seconds: int
    supplier: Shop
    workshop: Shop
    market: Shop


ROUTES = (
    Route(
        "Iron ore",
        "Tools",
        5,
        18,
        5,
        Shop("Iron Hill Mine", 1098, 1219),
        Shop("Ironworks", 356, 449),
        Shop("Tool Market", 596, 449),
    ),
    Route(
        "Timber",
        "Furniture",
        7,
        26,
        7,
        Shop("Pine Mill", 1368, 264),
        Shop("Oak Workshop", 356, 264),
        Shop("Home Market", 1628, 449),
    ),
    Route(
        "Clay",
        "Pottery",
        6,
        22,
        6,
        Shop("Redbank Clay Pit", 2168, 264),
        Shop("Ember Kiln", 836, 449),
        Shop("The Pottery Shop", 836, 634),
    ),
    Route(
        "Wheat",
        "Bread",
        4,
        14,
        4,
        Shop("Goldenfield Farm", 1368, 634),
        Shop("Sunrise Bakery", 1628, 634),
        Shop("Daily Bread Market", 356, 634),
    ),
)
WAREHOUSE = Shop("Foundry Warehouse", 1076, 264)


@dataclass(frozen=True)
class Vehicle:
    key: str
    label: str
    price: int
    trunk: int
    offroad_speed: int
    road_speed: int


# Same prices and specifications as the desktop game's garages.
VEHICLES = (
    Vehicle("motorcycle", "Motorcycle", 120, 6, 420, 520),
    Vehicle("car", "Car", 240, 48, 510, 690),
    Vehicle("van", "Delivery van", 360, 108, 430, 620),
    Vehicle("f1", "F1 car", 480, 0, 350, 900),
)
VEHICLE_BY_KEY = {vehicle.key: vehicle for vehicle in VEHICLES}
GARAGES = (Shop("Motorworks Garage", 1076, 634), Shop("Cacilhas Garage", 1628, 1464))
# The bridges carry vehicles only. Walkers cross the Tejo on the ferry between these piers.
PIERS = (Shop("Cais do Sodré", 660, 702), Shop("Cacilhas", 1290, 1098))
FERRY_FARE = 2
CASINO = Shop("Lisbon Casino", 1092, 446)
# A European roulette wheel: the 37 pockets in their real order, clockwise from 0.
ROULETTE_POCKETS = (
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10,
    5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26,
)
RED_NUMBERS = frozenset((1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36))
ROULETTE_PAYOUTS = {"red": 2, "black": 2, "green": 36}  # Returned per $1 staked on a win
CHIPS = (5, 10, 25, 50, 100)


def roulette_color(number):
    if number == 0:
        return "green"
    return "red" if number in RED_NUMBERS else "black"


def entrance(x, y):
    """(index, role) for the doorstep or pier the player stands at, or None."""
    for i, route in enumerate(ROUTES):
        for role in ("supplier", "workshop", "market"):
            if getattr(route, role).nearby(x, y):
                return i, role
    if WAREHOUSE.nearby(x, y):
        return None, "warehouse"
    if CASINO.nearby(x, y):
        return None, "casino"
    for i, place in enumerate(GARAGES):
        if place.nearby(x, y):
            return i, "garage"
    for i, place in enumerate(PIERS):
        if place.nearby(x, y):
            return i, "ferry"
    return None
