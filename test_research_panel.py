"""Check that the campus menu explains unlocks, taxes and material costs."""
import copy
from types import SimpleNamespace
import unittest

from innovation import BRANCH_BY_KEY, RECIPE_BY_KEY, initial_state, reset_day
from research_panel import (branch_text, branch_values, duration_text,
                            fabrication_preview, project_text, quantity_value,
                            recipe_text, recipe_values)


def student():
    return SimpleNamespace(cash=1000, innovation=initial_state(), supplies=[6, 0, 0, 0],
                           goods=[3, 0, 0, 0], tier2_goods=2)


class ResearchFormattingTest(unittest.TestCase):
    def test_quantities_are_whole_positive_ascii_units(self):
        self.assertEqual(quantity_value(" 25 "), 25)
        for value in ("0", "-2", "+1", "1.5", "1e3", "１２", "9999999", "", None, True):
            with self.subTest(value=value):
                self.assertIsNone(quantity_value(value))

    def test_timing_never_labels_unfinished_work_ready(self):
        self.assertEqual(duration_text(.01), "1s")
        self.assertEqual(duration_text(60.01), "1m 01s")
        self.assertEqual(duration_text(120), "2m 00s")
        self.assertEqual(duration_text(0), "0s")

    def test_green_energy_explains_total_discount_and_current_rate(self):
        town = student()
        town.innovation["levels"]["green_energy"] = 2
        text = branch_text(town, BRANCH_BY_KEY["green_energy"])
        self.assertIn("current daily profit tax: 15%", text)
        self.assertIn("10 percentage points in total", text)
        self.assertIn("positive daily net profit", text)
        self.assertIn("does not refund taxes already paid", text)
        self.assertIn("Level 3 · NEXT LEVEL", text)
        self.assertIn("Cost $900", text)

    def test_progress_explains_paid_project_and_serial_research(self):
        town = student()
        town.innovation["project"] = dict(branch="metallurgy", level=1, remaining=9.2)
        self.assertIn("Level 1 researching · 10s remaining", project_text(town))
        self.assertEqual(branch_values(town, BRANCH_BY_KEY["green_energy"])[-1], "Lab occupied")
        self.assertIn("RESEARCHING · 10s remaining", branch_text(town, BRANCH_BY_KEY["metallurgy"]))
        self.assertIn("Pay once", branch_text(town, BRANCH_BY_KEY["metallurgy"]))

    def test_locked_products_explain_research_instead_of_active_buyers(self):
        town = student()
        recipe = RECIPE_BY_KEY["precision_turbines"]
        self.assertEqual(recipe_values(town, recipe)[-2:], ("—", "—"))
        text = recipe_text(town, recipe)
        self.assertIn("LOCKED · Complete Advanced Metallurgy level 2", text)
        self.assertNotIn("Today's selling price", text)
        self.assertIn("1 Precision Machinery · You carry 2", text)
        self.assertIn("2 Alloy Components · You carry 0", text)

    def test_batch_preview_multiplies_inputs_but_keeps_parallel_batch_duration(self):
        town = student()
        text = fabrication_preview(town, RECIPE_BY_KEY["alloy_components"], 3)
        self.assertIn("6 Iron ore, 3 Tools", text)
        self.assertIn("14s per batch", text)
        self.assertIn("Reserves 3 cargo spaces", text)
        self.assertIn("positive whole", fabrication_preview(town, RECIPE_BY_KEY["alloy_components"], None))

    def test_workshop_distinguishes_carried_goods_ready_batches_and_daily_sales(self):
        town = student()
        town.innovation["levels"]["metallurgy"] = 1
        reset_day(town)
        town.innovation["goods"]["alloy_components"] = 3
        town.innovation["prices"]["alloy_components"] = 75
        town.innovation["orders"]["alloy_components"] = dict(quantity=2, remaining=0)
        town.innovation["demand"]["alloy_components"] = 7
        town.innovation["sales_today"]["alloy_components"] = 1
        town.innovation["revenue_today"]["alloy_components"] = 75
        recipe = RECIPE_BY_KEY["alloy_components"]
        before = copy.deepcopy(town.innovation)
        self.assertEqual(recipe_values(town, recipe)[1:], ("Unlocked", 3, "2 ready", 7, "$75"))
        text = recipe_text(town, recipe)
        for phrase in ("Stock in your cargo: 3", "Current batch: 2 · ready to collect",
                       "Buyers remaining today: 7", "Sold today: 1", "Revenue today: $75",
                       "Nova SBE · Carcavelos", "there is no offline fabrication"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertEqual(town.innovation, before)

    def test_complete_branch_has_no_next_cost(self):
        town = student()
        town.innovation["levels"]["metallurgy"] = 3
        self.assertEqual(branch_values(town, BRANCH_BY_KEY["metallurgy"])[2:],
                         ("—", "—", "All levels complete"))
        text = branch_text(town, BRANCH_BY_KEY["metallurgy"])
        for product in ("Alloy Components", "Precision Turbines", "Smart Tram Assemblies"):
            self.assertIn("Unlocks " + product, text)
        self.assertIn("Levels and remaining time save", text)


if __name__ == "__main__":
    unittest.main()
