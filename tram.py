"""Affordable north-bank tram trips, independent of the UI and saved schema."""
from dataclasses import dataclass
import math
from exchange import record_tram


TRAM_FARE = 3
TRAM_REACH = 40


@dataclass(frozen=True)
class TramStop:
    name: str
    x: float
    y: float = 704

    @property
    def position(self):
        return self.x, self.y


TRAM_STOPS = (
    TramStop("Belém", 100),
    TramStop("Alcântara", 420),
    TramStop("Baixa · Praça do Comércio", 660),
    TramStop("Alfama", 900),
    TramStop("Beato", 1140),
    TramStop("Marvila", 1460),
    TramStop("Parque das Nações", 2180),
)


def nearby_stop(x, y):
    stop = min(TRAM_STOPS, key=lambda item: math.hypot(x-item.x, y-item.y))
    return stop if math.hypot(x-stop.x, y-stop.y) <= TRAM_REACH else None


def ride_tram(town, destination_name):
    """Validate a trip before charging; failed bookings never move cargo or cash."""
    origin = nearby_stop(town.x, town.y)
    if origin is None or not town.can_walk(town.x, town.y):
        town.message = "Walk to a marked tram stop on the north-bank promenade first."
        return False
    destination = next((stop for stop in TRAM_STOPS if stop.name == destination_name), None)
    if destination is None:
        town.message = "Choose a tram stop from the route."
        return False
    if destination == origin:
        town.message = f"You are already at {origin.name}. Choose another stop."
        return False
    if not town.can_walk(destination.x, destination.y):
        town.message = "That tram stop is unavailable. No fare was charged."
        return False
    if town.cash < TRAM_FARE:
        town.message = f"A tram ticket costs ${TRAM_FARE}. You need more cash."
        return False
    town.cash -= TRAM_FARE
    town.other_expenses_today += TRAM_FARE
    record_tram(town)
    town.facing = 1 if destination.x > town.x else -1
    town.x, town.y = destination.position
    town.bridge_journey = None
    town.message = f"Elétrico · Arrived at {destination.name} · Ticket -${TRAM_FARE}."
    town.notice = town.message
    town.notice_until = town.elapsed+5
    return True
