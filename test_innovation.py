from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from contracts import initial_state as initial_contracts
from innovation import (BRANCH_BY_KEY, RECIPE_BY_KEY, TIER3_RECIPES,
                        advance_innovation, cargo, collect_products,
                        ingredient_owned, initial_state, max_fabrication,
                        next_research, normalize_state, research_level, research_quote,
                        reserved, reset_day, sell_products, start_fabrication,
                        start_research, tax_rate, unlocked_recipes)


class FakeTown:
    def __init__(self, cash=10000, capacity=120):
        self.cash = cash
        self.innovation = initial_state()
        self.other_income_today = 0
        self.other_expenses_today = 0
        self.supplies = [0] * 4
        self.goods = [0] * 4
        self.tier2_goods = 0
        self.other_cargo = 0
        self.other_reserved = 0
        self.carry_capacity = capacity
        self.message = ""

    @property
    def cargo(self):
        return (sum(self.supplies) + sum(self.goods) + self.tier2_goods
                + self.other_cargo + cargo(self))

    @property
    def reserved(self):
        return self.other_reserved + reserved(self)

    def add_cash(self, amount, business=False):
        self.cash += amount
        if not business:
            self.other_income_today += amount


def unlock(town, level=3):
    town.innovation["levels"]["metallurgy"] = level
    for recipe in TIER3_RECIPES:
        town.innovation["demand"][recipe.key] = recipe.buyers if level >= recipe.level else 0


def assets(town):
    return deepcopy((town.cash, town.supplies, town.goods, town.tier2_goods,
                     town.innovation, town.other_income_today, town.other_expenses_today))


def grant(town):
    town.contracts = initial_contracts()
    town.contracts["upgrades"].append("research_grant")


class InnovationTest(unittest.TestCase):
    def test_hotel_grant_changes_new_payment_and_accounting_without_mutating_base_prices(self):
        town = FakeTown(315)
        grant(town)
        self.assertEqual(research_quote(town, "metallurgy"), 315)
        self.assertTrue(start_research(town, "metallurgy"))
        self.assertEqual((town.cash, town.other_expenses_today,
                          town.innovation["research_spent"], town.innovation["project"]["paid_cost"]),
                         (0, 315, 315, 315))
        self.assertEqual(BRANCH_BY_KEY["metallurgy"].levels[0].cost, 350)
        before = assets(town)
        self.assertFalse(start_research(town, "metallurgy"))
        self.assertEqual(assets(town), before)

    def test_grant_quote_rejects_insufficient_cash_atomically_and_legacy_towns_keep_base_prices(self):
        town = FakeTown(314)
        self.assertEqual(research_quote(town, "metallurgy"), 350)
        grant(town)
        before = assets(town)
        self.assertFalse(start_research(town, "metallurgy"))
        self.assertIn("$315", town.message)
        self.assertEqual(assets(town), before)
        self.assertIsNone(research_quote(town, "missing"))
        town.innovation["levels"]["metallurgy"] = 3
        self.assertIsNone(research_quote(town, "metallurgy"))

    def test_earning_grant_during_paid_research_does_not_refund_or_recharge_on_reload(self):
        town = FakeTown(1000)
        self.assertTrue(start_research(town, "green_energy"))
        advance_innovation(town, 19.25)
        grant(town)
        town.innovation = normalize_state(json.loads(json.dumps(town.innovation)))
        self.assertEqual((town.cash, town.other_expenses_today, town.innovation["research_spent"]),
                         (800, 200, 200))
        self.assertEqual(town.innovation["project"]["paid_cost"], 200)
        self.assertEqual(town.innovation["project"]["remaining"], 25.75)
        advance_innovation(town, 25.75)
        self.assertEqual((town.cash, town.innovation["research_spent"]), (800, 200))
        self.assertEqual(research_quote(town, "green_energy"), 405)
        self.assertTrue(start_research(town, "green_energy"))
        self.assertEqual((town.cash, town.other_expenses_today, town.innovation["research_spent"]),
                         (395, 605, 605))

    def test_discounted_and_legacy_paid_quotes_survive_save_normalization_without_payment(self):
        town = FakeTown(500)
        grant(town)
        start_research(town, "green_energy")
        saved = json.loads(json.dumps(town.innovation))
        self.assertEqual(normalize_state(saved), town.innovation)
        self.assertEqual(normalize_state(saved)["project"]["paid_cost"], 180)
        legacy_town = FakeTown(500)
        start_research(legacy_town, "green_energy")
        legacy_saved = json.loads(json.dumps(legacy_town.innovation))
        legacy_saved["project"].pop("paid_cost")
        legacy = normalize_state(legacy_saved)
        self.assertEqual(legacy["project"]["paid_cost"], 200)
        self.assertEqual(legacy["research_spent"], 200)
        self.assertEqual(legacy_town.cash, 300)
        self.assertEqual(town.cash, 320)

    def test_initial_states_are_independent_empty_and_json_serializable(self):
        first, second = initial_state(), initial_state()
        self.assertEqual(json.loads(json.dumps(first)), first)
        self.assertEqual(first["levels"], {"green_energy": 0, "metallurgy": 0})
        self.assertIsNone(first["project"])
        for field in ("goods", "demand", "sales_today", "revenue_today", "total_sold", "total_revenue"):
            self.assertEqual(sum(first[field].values()), 0)
        first["goods"]["alloy_components"] = 5
        self.assertEqual(second["goods"]["alloy_components"], 0)

    def test_research_pays_once_and_completes_only_after_active_seconds(self):
        town = FakeTown(500)
        self.assertTrue(start_research(town, "green_energy"))
        self.assertEqual((town.cash, town.other_expenses_today,
                          town.innovation["research_spent"]), (300, 200, 200))
        self.assertEqual(tax_rate(town), 20)
        for seconds in (0, -1, True, "45", float("inf"), float("nan")):
            self.assertEqual(advance_innovation(town, seconds), ())
            self.assertEqual(town.innovation["project"]["remaining"], 45.0)
        self.assertEqual(advance_innovation(town, 44), ())
        completion, = advance_innovation(town, 1)
        self.assertEqual((completion.branch, completion.level, completion.unlocked_recipes),
                         ("green_energy", 1, ()))
        self.assertEqual(tax_rate(town), 18)
        self.assertIsNone(town.innovation["project"])
        self.assertEqual(advance_innovation(town, 500), ())
        self.assertEqual((town.cash, town.other_expenses_today), (300, 200))

    def test_both_branches_progress_sequentially_with_total_tax_discounts(self):
        town = FakeTown()
        for index, rate in enumerate((18, 15, 10), 1):
            node = next_research(town, "green_energy")
            self.assertEqual(node.level, index)
            self.assertTrue(start_research(town, "green_energy"))
            advance_innovation(town, node.seconds)
            self.assertEqual(tax_rate(town), rate)
        self.assertEqual(tax_rate(town, base=5), 0)
        self.assertIsNone(next_research(town, "green_energy"))
        self.assertFalse(start_research(town, "green_energy"))
        self.assertEqual(town.innovation["research_spent"], 1550)
        for level, recipe in enumerate(TIER3_RECIPES, 1):
            self.assertTrue(start_research(town, "metallurgy"))
            self.assertEqual(len(unlocked_recipes(town)), level - 1)
            completion, = advance_innovation(town, 1000)
            self.assertEqual((completion.level, completion.unlocked_recipes), (level, (recipe.key,)))
            self.assertEqual(len(unlocked_recipes(town)), level)
            self.assertEqual(town.innovation["demand"][recipe.key], recipe.buyers)
        self.assertEqual(research_level(town, "metallurgy"), 3)
        self.assertFalse(start_research(town, "metallurgy"))
        self.assertEqual(town.innovation["research_spent"], 4300)

    def test_invalid_research_and_an_active_project_are_atomic(self):
        town = FakeTown(199)
        for branch in ("green_energy", "metallurgy", "missing", [], True, None):
            before = assets(town)
            self.assertFalse(start_research(town, branch))
            self.assertEqual(assets(town), before)
        town.cash = 1000
        start_research(town, "green_energy")
        before = assets(town)
        for branch in ("green_energy", "metallurgy"):
            self.assertFalse(start_research(town, branch))
            self.assertEqual(assets(town), before)

    def test_resume_project_neither_charges_again_nor_grants_offline_time(self):
        town = FakeTown(350)
        start_research(town, "metallurgy")
        advance_innovation(town, 19.25)
        saved = json.loads(json.dumps(town.innovation))
        loaded = FakeTown(town.cash)
        loaded.innovation = normalize_state(saved)
        self.assertEqual(loaded.innovation["project"]["remaining"], 40.75)
        self.assertEqual(research_level(loaded, "metallurgy"), 0)
        self.assertEqual(advance_innovation(loaded, 40), ())
        completed, = advance_innovation(loaded, .75)
        self.assertEqual(completed.unlocked_recipes, ("alloy_components",))
        self.assertEqual((loaded.cash, loaded.other_expenses_today), (0, 0))
        self.assertEqual(loaded.innovation["research_spent"], 350)

    def test_alloy_crafting_consumes_exact_inputs_and_reserves_output(self):
        town = FakeTown(capacity=12)
        unlock(town, 1)
        town.supplies[0], town.goods[0] = 6, 3
        self.assertEqual(max_fabrication(town, "alloy_components"), 3)
        self.assertTrue(start_fabrication(town, "alloy_components", 3))
        self.assertEqual((town.supplies[0], town.goods[0], town.cargo, town.reserved), (0, 0, 0, 3))
        self.assertEqual(collect_products(town, "alloy_components"), 0)
        advance_innovation(town, 14)
        self.assertEqual(collect_products(town, "alloy_components", 2), 2)
        self.assertEqual((town.cargo, town.reserved), (2, 1))
        self.assertEqual(collect_products(town, "alloy_components"), 1)
        self.assertIsNone(town.innovation["orders"]["alloy_components"])
        self.assertEqual((town.cargo, town.reserved, town.cash), (3, 0, 10000))

    def test_invalid_production_never_loses_inputs_or_reservations(self):
        town = FakeTown()
        town.supplies[0], town.goods[0] = 6, 3
        for key, quantity in (("alloy_components", 1), ("bad", 1), ([], 1),
                              ("alloy_components", True), ("alloy_components", 0),
                              ("alloy_components", -1), ("alloy_components", 1.0)):
            before = assets(town)
            self.assertFalse(start_fabrication(town, key, quantity))
            self.assertEqual(assets(town), before)
        unlock(town, 1)
        before = assets(town)
        self.assertFalse(start_fabrication(town, "alloy_components", 4))
        self.assertEqual(assets(town), before)
        start_fabrication(town, "alloy_components", 1)
        before = assets(town)
        self.assertFalse(start_fabrication(town, "alloy_components", 1))
        self.assertEqual(assets(town), before)

    def test_prerequisites_use_completed_research_not_paid_pending_project(self):
        town = FakeTown()
        town.supplies[0], town.goods[0] = 2, 1
        start_research(town, "metallurgy")
        self.assertEqual(max_fabrication(town, "alloy_components"), 0)
        self.assertFalse(start_fabrication(town, "alloy_components", 1))
        advance_innovation(town, 60)
        self.assertTrue(start_fabrication(town, "alloy_components", 1))
        town.tier2_goods = 1
        town.innovation["goods"]["alloy_components"] = 2
        self.assertFalse(start_fabrication(town, "precision_turbines", 1))

    def test_multistage_chain_consumes_base_tier_two_and_tier_three_materials(self):
        town = FakeTown()
        unlock(town)
        town.supplies[0], town.goods[0], town.tier2_goods = 8, 6, 2
        self.assertTrue(start_fabrication(town, "alloy_components", 4))
        advance_innovation(town, 14)
        self.assertEqual(collect_products(town, "alloy_components"), 4)
        self.assertTrue(start_fabrication(town, "precision_turbines", 2))
        self.assertEqual((town.tier2_goods, cargo(town)), (0, 0))
        advance_innovation(town, 25)
        self.assertEqual(collect_products(town, "precision_turbines"), 2)
        self.assertTrue(start_fabrication(town, "tram_assemblies", 1))
        self.assertEqual((town.goods[0], cargo(town)), (0, 0))
        advance_innovation(town, 40)
        self.assertEqual(collect_products(town, "tram_assemblies"), 1)
        self.assertEqual(sell_products(town, "tram_assemblies"), 1)
        self.assertEqual((town.cash, town.innovation["revenue_today"]["tram_assemblies"]), (11200, 1200))

    def test_three_independent_orders_and_research_run_in_parallel(self):
        town = FakeTown()
        unlock(town)
        town.supplies[0], town.goods[0], town.tier2_goods = 2, 3, 1
        town.innovation["goods"]["alloy_components"] = 2
        town.innovation["goods"]["precision_turbines"] = 2
        for recipe in TIER3_RECIPES:
            self.assertTrue(start_fabrication(town, recipe.key))
        self.assertEqual(town.reserved, 3)
        start_research(town, "green_energy")
        advance_innovation(town, 14)
        self.assertEqual(town.innovation["orders"]["alloy_components"]["remaining"], 0)
        self.assertEqual(town.innovation["orders"]["precision_turbines"]["remaining"], 11)
        self.assertEqual(town.innovation["orders"]["tram_assemblies"]["remaining"], 26)
        self.assertEqual(town.innovation["project"]["remaining"], 31)

    def test_start_capacity_accounts_for_freed_inputs_and_all_other_reservations(self):
        town = FakeTown(capacity=12)
        unlock(town, 1)
        town.supplies[0], town.goods[0] = 2, 1
        town.other_cargo, town.other_reserved = 7, 2
        self.assertTrue(start_fabrication(town, "alloy_components", 1))
        self.assertEqual((town.cargo, town.reserved), (7, 3))
        self.assertLessEqual(town.cargo + town.reserved, town.carry_capacity)
        second = FakeTown(capacity=12)
        unlock(second, 1)
        second.supplies[0], second.goods[0] = 2, 1
        second.other_cargo, second.other_reserved = 11, 2
        before = assets(second)
        self.assertFalse(start_fabrication(second, "alloy_components", 1))
        self.assertEqual(max_fabrication(second, "alloy_components"), 0)
        self.assertEqual(assets(second), before)

    def test_full_and_partial_pickup_preserves_other_order_reservations(self):
        town = FakeTown(capacity=12)
        unlock(town)
        town.innovation["orders"]["alloy_components"] = {"quantity": 4, "remaining": 0.0}
        town.other_cargo, town.other_reserved = 10, 2
        before = assets(town)
        self.assertEqual(collect_products(town, "alloy_components"), 0)
        self.assertEqual(assets(town), before)
        town.other_cargo = 8
        self.assertEqual(collect_products(town, "alloy_components"), 2)
        self.assertEqual(town.innovation["orders"]["alloy_components"]["quantity"], 2)
        self.assertEqual((town.cargo, town.other_reserved), (10, 2))
        town.other_cargo = 6
        self.assertEqual(collect_products(town, "alloy_components"), 2)
        self.assertEqual(town.cargo + town.reserved, 12)

    def test_sales_respect_buyers_and_record_revenue_once_as_business_income(self):
        town = FakeTown()
        unlock(town, 1)
        town.innovation["goods"]["alloy_components"] = 12
        self.assertEqual(sell_products(town, "alloy_components", 3), 3)
        self.assertEqual(sell_products(town, "alloy_components", 30), 5)
        self.assertEqual((town.cash, town.other_income_today, town.other_expenses_today), (10600, 0, 0))
        self.assertEqual((town.innovation["goods"]["alloy_components"],
                          town.innovation["demand"]["alloy_components"],
                          town.innovation["sales_today"]["alloy_components"],
                          town.innovation["revenue_today"]["alloy_components"],
                          town.innovation["total_sold"]["alloy_components"],
                          town.innovation["total_revenue"]["alloy_components"]), (4, 0, 8, 600, 8, 600))
        before = assets(town)
        self.assertEqual(sell_products(town, "alloy_components"), 0)
        self.assertEqual(assets(town), before)

    def test_reset_day_refills_only_unlocked_buyers_and_preserves_long_term_assets(self):
        town = FakeTown()
        unlock(town, 1)
        town.innovation["goods"]["alloy_components"] = 9
        sell_products(town, "alloy_components")
        start_research(town, "metallurgy")
        advance_innovation(town, 10)
        project = deepcopy(town.innovation["project"])
        with patch("innovation.random.random", return_value=.5), patch("innovation.random.uniform", return_value=1.0):
            reset_day(town)
        self.assertEqual(town.innovation["demand"], {"alloy_components": 8, "precision_turbines": 0, "tram_assemblies": 0})
        self.assertEqual(town.innovation["project"], project)
        self.assertEqual(town.innovation["goods"]["alloy_components"], 1)
        self.assertEqual(town.innovation["total_sold"]["alloy_components"], 8)
        self.assertEqual(town.innovation["total_revenue"]["alloy_components"], 600)
        self.assertEqual(sum(town.innovation["revenue_today"].values()), 0)
        self.assertEqual(sum(town.innovation["sales_today"].values()), 0)
        self.assertEqual(sell_products(town, "alloy_components"), 1)

    def test_invalid_collections_and_sales_are_atomic(self):
        town = FakeTown()
        unlock(town)
        town.innovation["goods"]["alloy_components"] = 1
        town.innovation["orders"]["alloy_components"] = {"quantity": 1, "remaining": 0}
        for action in (collect_products, sell_products):
            for key, quantity in (([], 1), ("missing", 1), ("alloy_components", True),
                                  ("alloy_components", 0), ("alloy_components", -1),
                                  ("alloy_components", 1.5), ("alloy_components", "1")):
                before = assets(town)
                self.assertEqual(action(town, key, quantity), 0)
                self.assertEqual(assets(town), before)
        town.innovation["levels"]["metallurgy"] = 0
        for action in (collect_products, sell_products):
            before = assets(town)
            self.assertEqual(action(town, "alloy_components"), 0)
            self.assertEqual(assets(town), before)

    def test_ingredient_helpers_cover_all_stock_sources(self):
        town = FakeTown()
        town.supplies[0], town.goods[0], town.tier2_goods = 7, 8, 9
        town.innovation["goods"]["alloy_components"] = 10
        town.innovation["goods"]["precision_turbines"] = 11
        self.assertEqual([ingredient_owned(town, item) for recipe in TIER3_RECIPES
                          for item in recipe.ingredients], [7, 8, 9, 10, 11, 8])

    def test_missing_legacy_or_unsupported_state_grants_no_progress_or_income(self):
        for saved in (None, [], "state", {}, {"version": 2}, {"version": True}):
            normalized = normalize_state(saved)
            self.assertEqual(normalized, initial_state())
        town = SimpleNamespace()
        self.assertEqual(cargo(town), 0)
        self.assertEqual(reserved(town), 0)
        self.assertEqual(tax_rate(town), 20)
        self.assertEqual(next_research(town, "unknown"), None)
        self.assertEqual(research_level(town, []), 0)

    def test_normalization_preserves_paid_timers_stock_and_independent_copy(self):
        town = FakeTown()
        unlock(town, 2)
        town.innovation["goods"]["alloy_components"] = 4
        town.innovation["orders"]["precision_turbines"] = {"quantity": 2, "remaining": 7.25}
        start_research(town, "green_energy")
        advance_innovation(town, 2)
        saved = deepcopy(town.innovation)
        loaded = normalize_state(saved)
        self.assertEqual(loaded, saved)
        loaded["goods"]["alloy_components"] = 99
        loaded["project"]["remaining"] = 0
        self.assertEqual(saved, town.innovation)

    def test_malformed_progress_and_orders_cannot_unlock_or_create_income(self):
        saved = initial_state()
        saved["levels"] = {"green_energy": True, "metallurgy": 99}
        saved["project"] = {"branch": "metallurgy", "level": 3, "remaining": 1}
        saved["orders"]["alloy_components"] = {"quantity": 4, "remaining": 0}
        saved["goods"]["alloy_components"] = 2
        saved["goods"]["precision_turbines"] = -1
        saved["revenue_today"]["alloy_components"] = True
        normalized = normalize_state(saved)
        self.assertEqual(normalized["levels"], {"green_energy": 0, "metallurgy": 0})
        self.assertIsNone(normalized["project"])
        self.assertIsNone(normalized["orders"]["alloy_components"])
        self.assertEqual(normalized["goods"]["alloy_components"], 2)
        self.assertEqual(normalized["goods"]["precision_turbines"], 0)
        self.assertEqual(sum(normalized["demand"].values()), 0)
        self.assertEqual(sum(normalized["revenue_today"].values()), 0)

    def test_invalid_saved_project_timers_cannot_skip_research(self):
        for project in ({"branch": [], "level": 1, "remaining": 20},
                        {"branch": "metallurgy", "level": True, "remaining": 20},
                        {"branch": "metallurgy", "level": 1, "remaining": float("inf")},
                        {"branch": "metallurgy", "level": 1, "remaining": -1},
                        {"branch": "metallurgy", "level": 1, "remaining": 61}):
            saved = initial_state()
            saved["project"] = project
            self.assertIsNone(normalize_state(saved)["project"])

    def test_normalized_sales_do_not_refill_buyers_or_invent_revenue(self):
        saved = {"levels": {"metallurgy": 1}, "sales_today": {"alloy_components": 3}}
        normalized = normalize_state(saved)
        self.assertEqual(normalized["demand"]["alloy_components"], 5)
        self.assertEqual(normalized["revenue_today"]["alloy_components"], 0)
        self.assertEqual(normalized["total_revenue"]["alloy_components"], 0)
        saved["demand"] = {"alloy_components": 99}
        self.assertEqual(normalize_state(saved)["demand"]["alloy_components"], 21)

    def test_daily_oversupply_depresses_prices_using_sold_and_carried_stock(self):
        town = FakeTown()
        unlock(town, 1)
        town.innovation["goods"]["alloy_components"] = 12
        town.innovation["sales_today"]["alloy_components"] = 4
        with patch("innovation.random.random", return_value=.5), patch("innovation.random.uniform", return_value=1.0):
            reset_day(town)
        self.assertEqual(town.innovation["prices"]["alloy_components"], 30)
        self.assertEqual(town.innovation["demand"]["alloy_components"], 8)
        self.assertEqual(town.innovation["sales_today"]["alloy_components"], 0)
        self.assertEqual(town.innovation["prices"]["precision_turbines"], 360)
        self.assertEqual(town.innovation["demand"]["precision_turbines"], 0)

    def test_demand_spikes_raise_quotes_and_survive_save_after_large_sales(self):
        town = FakeTown()
        unlock(town)
        with patch("innovation.random.random", return_value=.01):
            reset_day(town)
        for recipe in TIER3_RECIPES:
            self.assertEqual(town.innovation["demand"][recipe.key], round(recipe.buyers * 2.5))
            self.assertEqual(town.innovation["prices"][recipe.key], round(recipe.base_price * 1.9))
        town.innovation["goods"]["alloy_components"] = 12
        self.assertEqual(sell_products(town, "alloy_components"), 12)
        self.assertEqual(town.innovation["sales_today"]["alloy_components"], 12)
        self.assertEqual(town.innovation["demand"]["alloy_components"], 8)
        self.assertEqual(normalize_state(json.loads(json.dumps(town.innovation))), town.innovation)

    def test_daily_demand_variation_follows_sampled_factor_without_spike(self):
        town = FakeTown()
        unlock(town)
        with patch("innovation.random.random", return_value=.5), patch("innovation.random.uniform", return_value=.85):
            reset_day(town)
        self.assertEqual(town.innovation["demand"]["alloy_components"], 7)
        self.assertEqual(town.innovation["prices"]["alloy_components"], 69)


if __name__ == "__main__":
    unittest.main()
