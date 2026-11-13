"""Shared, explicit place descriptions for signs, the map and the Places guide.

This module deliberately has no dependency on the game or its rendering code.
"""
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Stage:
    key: str
    marker: str
    title: str
    color: str


STAGES = (
    Stage("buy", "1", "BUY RAW MATERIALS", "#96620c"),
    Stage("make", "2", "MAKE PRODUCTS", "#23679b"),
    Stage("sell", "3", "SELL PRODUCTS", "#167253"),
    Stage("special", "2+3", "MAKE + SELL", "#724b94"),
    Stage("services", "+", "TOWN SERVICES", "#526274"),
    Stage("residential", "", "LISBOA HOMES", "#5d7060"),
)
STAGE_BY_KEY = {stage.key: stage for stage in STAGES}
MATERIALS = ("Iron ore", "Timber", "Clay", "Wheat")
PRODUCTS = ("Tools", "Furniture", "Pottery", "Bread")


@dataclass(frozen=True)
class SiteGuide:
    stage: str
    marker: str
    title: str
    color: str
    detail: str
    instruction: str

    @property
    def badge(self):
        return f"{self.marker}  {self.title}" if self.marker else self.title


def _description(stage, detail, instruction, title=None):
    style = STAGE_BY_KEY[stage]
    return SiteGuide(stage, style.marker, title or style.title, style.color, detail, instruction)


@lru_cache(maxsize=32)
def _guide(role, trade):
    valid_trade = isinstance(trade, int) and 0 <= trade < len(MATERIALS)
    material = MATERIALS[trade] if valid_trade else "Raw materials"
    product = PRODUCTS[trade] if valid_trade else "Products"
    if role == "SUPPLIER":
        if trade == 3:
            return _description("buy", "Wheat + Eggs",
                                "Buy Wheat with E (one) or Q (up to four). Buy Eggs with F (one) or R (up to four).")
        return _description("buy", material,
                            f"Buy {material} with E (one) or Q (up to four), then take it to a factory.")
    if role == "FACTORY":
        return _description("make", f"{material} → {product}",
                            f"Bring {material} and press E to start production. Return and press E to collect {product}, then take it to a market.")
    if role == "PUBLIC SHOP":
        return _description("sell", f"Sell {product} here",
                            f"Bring finished {product} and press E to sell to today's customers. This market does not buy raw materials.")
    if role == "TIER2":
        return _description("special", "Tools + Furniture → Machinery",
                            "Bring 1 Tools + 1 Furniture per Precision Machinery. Press E to craft, return after 12 seconds to collect, then press E again here to sell.")
    if role == "PASTELARIA":
        return _description("special", "Wheat + Eggs → Pastéis",
                            "Bring 1 Wheat + 1 Egg per Pastel. Press E to bake, return after 8 seconds to collect, then press E again here to sell your Pastéis.")
    if role == "SHIPYARD":
        return _description("special", "2 Timber + 2 Iron ore → Repair",
                            "Bring 2 Timber + 2 Iron ore and press E to start a boat repair. Return after 20 seconds and press E to collect payment here.",
                            title="REPAIR + GET PAID")
    if role == "GARAGE":
        return _description("services", "Cars, vans + motorcycles",
                            "Press E to buy a motorcycle ($120), car ($240) or delivery van ($360). "
                            "The car adds 48 trunk slots; the van adds 108. Vehicle trunks combine with bag and warehouse upgrades, "
                            "and vehicles move faster on roads.", title="BUY VEHICLES")
    if role == "WAREHOUSE":
        return _description("services", "Increase your bag capacity", "Press E to buy more storage when your bag is full.", title="BUY STORAGE")
    if role == "EXCHANGE":
        return SiteGuide("services", "$", "STOCK EXCHANGE", "#947123",
                         "District + infrastructure shares",
                         "Press E to buy or sell shares in districts, bridge tolls and the tram network. "
                         "Owned shares earn dividends from city activity.")
    if role == "RESEARCH":
        return SiteGuide("services", "R", "INOVAÇÃO", "#246b80",
                         "Research + tier-3 workshop",
                         "Press E at Nova SBE in Carcavelos to fund research with cash and active play time. "
                         "Green Energy lowers operating taxes; Advanced Metallurgy unlocks tier-3 recipes. "
                         "Craft, collect and sell advanced products in the campus workshop.")
    if role == "CASINO":
        return _description("services", "Roulette", "Press E to enter the casino and play roulette.", title="CASINO")
    return _description("residential", "Lisboa · Residências", "Residential building; no trading or production.")


def site_guide(site):
    """Return the same immutable guide wherever a site's purpose is displayed."""
    return _guide(site.role, site.trade)
