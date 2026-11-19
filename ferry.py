"""The cacilheiro ferry across the Tejo, for players without a vehicle.

The bridges only carry vehicles, so the ferry between Cais do Sodré (Lisbon)
and Cacilhas (Almada) is how a player on foot crosses the river.
"""
from dataclasses import dataclass
import math

from lisbon_scene import RIVER_BOTTOM, RIVER_TOP

FERRY_FARE = 2
FERRY_REACH = 40


@dataclass(frozen=True)
class Pier:
    name: str
    x: float
    y: float

    @property
    def position(self):
        return self.x, self.y

    @property
    def north(self):
        return self.y < RIVER_TOP

    @property
    def kiosk(self):
        """The ticket kiosk at the land end of the jetty, facing the boarding point."""
        if self.north:
            return self.x-30, RIVER_TOP+2, self.x+30, RIVER_TOP+38
        return self.x-30, RIVER_BOTTOM-38, self.x+30, RIVER_BOTTOM-2


# Boarding points on each quay, just clear of the water.
FERRY_PIERS = (
    Pier("Cais do Sodré", 660, RIVER_TOP-16),
    Pier("Cacilhas", 1290, RIVER_BOTTOM+18),
)


def nearby_pier(x, y):
    pier = min(FERRY_PIERS, key=lambda item: math.hypot(x-item.x, y-item.y))
    return pier if math.hypot(x-pier.x, y-pier.y) <= FERRY_REACH else None


def other_pier(pier):
    return next(item for item in FERRY_PIERS if item != pier)


def ride_ferry(town):
    """Charge the fare and land the player at the other pier. Failed trips cost nothing.

    Returns (origin, destination) on success, otherwise None with town.message explaining why.
    """
    origin = nearby_pier(town.x, town.y)
    if origin is None:
        town.message = "Walk to a ferry pier at Cais do Sodré or Cacilhas first."
        return None
    destination = other_pier(origin)
    if not town.can_walk(*destination.position):
        town.message = "The ferry can't dock right now. No fare was charged."
        return None
    if town.cash < FERRY_FARE:
        town.message = f"A ferry ticket costs ${FERRY_FARE}. You need more cash."
        return None
    town.cash -= FERRY_FARE
    town.other_expenses_today += FERRY_FARE
    town.x, town.y = destination.position
    town.facing = 1 if destination.x > origin.x else -1
    town.message = f"Ferry · Arrived at {destination.name} · Ticket -${FERRY_FARE}."
    return origin, destination
