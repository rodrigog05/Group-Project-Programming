"""Recipe discoveries shared by gameplay, saves and the journal UI."""
from dataclasses import dataclass

from innovation import TIER3_RECIPES, normalize_state as normalize_innovation


@dataclass(frozen=True)
class Recipe:
    key: str
    title: str
    ingredients: tuple
    product: str
    seconds: int
    role: str
    trade: int = -1
    service: bool = False
    research_level: int = 0


RECIPES = (
    Recipe("tools", "Tools", (("Iron ore", 1),), "Tools", 5, "FACTORY", 0),
    Recipe("furniture", "Furniture", (("Timber", 1),), "Furniture", 7, "FACTORY", 1),
    Recipe("pottery", "Pottery", (("Clay", 1),), "Pottery", 6, "FACTORY", 2),
    Recipe("bread", "Bread", (("Wheat", 1),), "Bread", 4, "FACTORY", 3),
    Recipe("precision_machinery", "Precision Machinery", (("Tools", 1), ("Furniture", 1)),
           "Precision Machinery", 12, "TIER2"),
    Recipe("pasteis", "Pastéis de Belém", (("Wheat", 1), ("Eggs", 1)), "Pastéis", 8, "PASTELARIA"),
    Recipe("boat_repair", "Boat repair", (("Timber", 2), ("Iron ore", 2)), "Boat repair", 20, "SHIPYARD", service=True),
) + tuple(Recipe(recipe.key, recipe.product,
                 tuple((item.label, item.quantity) for item in recipe.ingredients),
                 recipe.product, recipe.seconds, "RESEARCH", research_level=recipe.level)
          for recipe in TIER3_RECIPES)
RECIPE_BY_KEY = {recipe.key: recipe for recipe in RECIPES}


def recipe_key_for_site(site):
    if site is None or site.role == "RESEARCH":
        return None
    return next((recipe.key for recipe in RECIPES
                 if recipe.role == site.role and (recipe.trade < 0 or recipe.trade == site.trade)), None)


def normalize_discoveries(values):
    if not isinstance(values, list) or any(not isinstance(value, str) or value not in RECIPE_BY_KEY for value in values):
        raise ValueError("Invalid recipe discoveries in save")
    return list(dict.fromkeys(values))


def infer_discoveries(state):
    """Recover discoveries from legacy production/sales evidence, not cash."""
    found = []
    innovation = normalize_innovation(state.get("innovation"))
    for recipe in RECIPES:
        if recipe.trade >= 0:
            index = recipe.trade
            evidence = any(index < len(state.get(field, ())) and state[field][index]
                           for field in ("goods", "orders", "total_sold", "sales_today", "revenue_today"))
        elif recipe.role == "TIER2":
            evidence = any(state.get(field) for field in
                           ("tier2_order", "tier2_goods", "tier2_total_sold", "tier2_sales_today", "tier2_revenue_today"))
        elif recipe.role == "RESEARCH":
            evidence = (innovation["levels"]["metallurgy"] >= recipe.research_level
                        or any(innovation[field][recipe.key] for field in
                               ("goods", "orders", "total_sold", "sales_today", "revenue_today")))
        else:
            evidence = any(state.get(field, {}).get(recipe.role) for field in
                           ("industry_orders", "industry_goods", "industry_total_sold", "industry_sales_today", "industry_revenue_today"))
        if evidence:
            found.append(recipe.key)
    return found
