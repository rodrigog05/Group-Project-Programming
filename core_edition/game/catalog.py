"""The four desktop supply chains. A location is a doorstep in world pixels."""
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
    Route("Iron ore", "Tools", 5, 18, 5,
          Shop("Iron Hill Mine",1098,1219),Shop("Ironworks",356,449),Shop("Tool Market",596,449)),
    Route("Timber", "Furniture", 7, 26, 7,
          Shop("Pine Mill",1368,264),Shop("Oak Workshop",356,264),Shop("Home Market",1628,449)),
    Route("Clay", "Pottery", 6, 22, 6,
          Shop("Redbank Clay Pit",2168,264),Shop("Ember Kiln",836,449),Shop("The Pottery Shop",836,634)),
    Route("Wheat", "Bread", 4, 14, 4,
          Shop("Goldenfield Farm",1368,634),Shop("Sunrise Bakery",1628,634),Shop("Daily Bread Market",356,634)),
)
WAREHOUSE = Shop("Foundry Warehouse",1076,264)


def entrance(x,y):
    for i,route in enumerate(ROUTES):
        for role in ("supplier","workshop","market"):
            if getattr(route,role).nearby(x,y):
                return i,role
    if WAREHOUSE.nearby(x,y):
        return None,"warehouse"
    return None
