import unittest

from journal_market import market_snapshot
from journal_panel import market_text, market_values, recipe_text
from journal_recipes import RECIPE_BY_KEY
from tycoon import INDUSTRIES, SITES, TRADES, Town


class JournalFormattingTest(unittest.TestCase):
    def test_locked_recipe_gives_location_without_revealing_ingredients(self):
        text = recipe_text(RECIPE_BY_KEY["pasteis"], False, SITES)
        self.assertIn("Pastéis de Belém", text)
        self.assertIn("press E", text)
        self.assertNotIn("Wheat", text)
        self.assertNotIn("Eggs", text)

    def test_recorded_recipe_shows_inputs_time_and_correct_sale_location(self):
        pastry = recipe_text(RECIPE_BY_KEY["pasteis"], True, SITES)
        self.assertIn("1 × Wheat", pastry)
        self.assertIn("1 × Eggs", pastry)
        self.assertIn("8 seconds", pastry)
        self.assertIn("same building", pastry)
        tools = recipe_text(RECIPE_BY_KEY["tools"], True, SITES)
        self.assertIn("Ironworks", tools)
        self.assertIn("Tool Market", tools)
        self.assertIn("Oriente Tool Market", tools)
        repair = recipe_text(RECIPE_BY_KEY["boat_repair"], True, SITES)
        self.assertIn("agreed payment", repair)
        self.assertIn("do not occupy cargo space", repair)

    def test_market_views_distinguish_shared_buyers_and_local_tourists(self):
        town = Town()
        snapshot = market_snapshot(town, trades=TRADES, industries=INDUSTRIES, sites=SITES)
        row = next(row for row in snapshot.rows if row.key == "trade:2")
        values = market_values(row)
        self.assertEqual(values[5:7], (7, 7))
        detail = market_text(row, snapshot)
        self.assertIn("Your stock", detail)
        self.assertIn("The Pottery Shop", detail)
        self.assertIn("counted once", detail)
        self.assertIn("Total remaining buyers: 14", detail)
        service = next(row for row in snapshot.rows if row.key == "industry:SHIPYARD")
        self.assertEqual(market_values(service)[2], "Service")
        self.assertIn("jobs", market_text(service, snapshot))

    def test_locked_tier3_recipe_requires_completed_research_rather_than_only_visiting(self):
        text = recipe_text(RECIPE_BY_KEY["precision_turbines"], False, SITES)
        self.assertIn("Complete Advanced Metallurgy level 2", text)
        self.assertIn("Nova SBE in Carcavelos", text)
        self.assertIn("cash and active play time", text)
        self.assertNotIn("Precision Machinery", text)
        self.assertNotIn("Alloy Components", text)

    def test_recorded_tier3_recipe_explains_workshop_controls_and_shared_capacity(self):
        text = recipe_text(RECIPE_BY_KEY["alloy_components"], True, SITES)
        self.assertIn("2 × Iron ore", text)
        self.assertIn("1 × Tools", text)
        self.assertIn("14 seconds", text)
        self.assertIn("Advanced Workshop", text)
        for label in ("Quantity", "Fabricate", "Collect", "Sell here", "active play time", "normal cargo capacity"):
            self.assertIn(label, text)


if __name__ == "__main__":
    unittest.main()
