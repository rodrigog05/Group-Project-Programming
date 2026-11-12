"""Local daily tourist buyers attracted by Lisbon's monuments.

The compact game map uses district catchments, rather than a real-world
distance model. Only consumer shops receive visitors: suppliers, factories,
industrial machinery contracts and boat-repair jobs keep their own demand.
Overlapping district auras add together; their extra buyers are tracked per
shop so a landmark cannot increase another district's shared market pool.
"""
from dataclasses import dataclass

from lisbon_landmarks import LANDMARKS


@dataclass(frozen=True)
class TourismAura:
    landmark_kind: str
    district: str
    bounds: tuple
    daily_buyers: int

    @property
    def monument(self):
        return next(landmark.name for landmark in LANDMARKS if landmark.kind == self.landmark_kind)


TOURISM_AURAS = (
    TourismAura("monastery", "Belém", (0, 104, 238, 718), 6),
    TourismAura("tower", "Belém", (0, 104, 238, 718), 3),
    TourismAura("square", "Baixa / central waterfront", (238, 345, 958, 718), 4),
    TourismAura("castle", "Alfama", (718, 104, 958, 718), 3),
)


def tourism_sources(site):
    if site.role not in ("PUBLIC SHOP", "PASTELARIA"):
        return ()
    if hasattr(site, "bounds"):
        left, top, right, bottom = site.bounds
        x, y = (left+right)/2, (top+bottom)/2
    else:
        x, y = site.x+88, site.y+52
    return tuple(aura for aura in TOURISM_AURAS
                 if aura.bounds[0] <= x < aura.bounds[2] and aura.bounds[1] <= y < aura.bounds[3])


def tourism_bonus(site):
    return sum(aura.daily_buyers for aura in tourism_sources(site))


def new_tourist_pools(sites):
    return {site.name: bonus for site in sites if (bonus := tourism_bonus(site)) > 0}


def tourism_description(site):
    sources = tourism_sources(site)
    if not sources:
        return ""
    names = ", ".join(f"{aura.monument} (+{aura.daily_buyers})" for aura in sources)
    return f"Tourism: +{tourism_bonus(site)} extra buyers per day from {names}."


def monument_description(landmark, sites):
    affected = [(site.name, aura.daily_buyers) for site in sites for aura in tourism_sources(site)
                if aura.landmark_kind == landmark.kind]
    if not affected:
        return ""
    return "Tourism boosts " + ", ".join(f"{name} (+{bonus} buyers/day)" for name, bonus in affected) + "."
