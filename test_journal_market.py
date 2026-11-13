from copy import deepcopy
import unittest
from unittest.mock import patch

from journal_market import market_snapshot
from tycoon import DAY_SECONDS, INDUSTRIES, Order, SITES, TRADES, Town


def row(snapshot, key):
    return next(item for item in snapshot.rows if item.key == key)


class JournalMarketTest(unittest.TestCase):
    def test_explicit_models_do_not_reimport_the_game_module(self):
        town = Town()
        with patch("builtins.__import__", side_effect=AssertionError("Unexpected import")):
            snapshot = market_snapshot(town, TRADES, INDUSTRIES, SITES)
        self.assertEqual(len(snapshot.rows), 10)

    def test_shared_buyers_are_not_multiplied_by_number_of_markets(self):
        town = Town()
        town.demand[0] = 2
        snapshot = market_snapshot(town)
        tools = row(snapshot, "trade:0")
        self.assertEqual((tools.ordinary_buyers, tools.tourist_buyers, tools.remaining_buyers), (2, 4, 6))
        self.assertIn("Tool Market", tools.notes)
        self.assertIn("Oriente Tool Market", tools.notes)
        self.assertEqual(len([item for item in snapshot.rows if item.product == "Tools"]), 1)
        self.assertEqual(len([shop for shop in snapshot.tourist_shops if shop.product == "Tools"]), 1)

    def test_raw_stock_finished_stock_and_ready_orders_remain_distinct(self):
        town = Town()
        town.supplies[2], town.goods[2] = 7, 3
        town.orders[2] = Order(5, 1)
        town.elapsed = 10
        pottery = row(market_snapshot(town), "trade:2")
        self.assertEqual(pottery.raw_stock, "Clay: 7")
        self.assertEqual((pottery.raw_cost, pottery.stock, pottery.orders), (6, 3, 5))
        self.assertIn("finished output waiting for pickup", market_snapshot(town).notes)

    def test_sales_and_tourist_depletion_appear_without_mutating_the_game(self):
        town = Town()
        shop = next(site for site in SITES if site.name == "Tool Market")
        town.x, town.y = shop.door[0], shop.door[1]+18
        town.demand[0], town.goods[0] = 2, 5
        town.interact()
        before = deepcopy(vars(town))
        snapshot = market_snapshot(town)
        tools = row(snapshot, "trade:0")
        self.assertEqual((tools.sold_today, tools.stock, tools.ordinary_buyers, tools.tourist_buyers), (5, 0, 0, 1))
        self.assertEqual(tools.revenue_today, 90)
        local = next(item for item in snapshot.tourist_shops if item.name == "Tool Market")
        self.assertEqual((local.remaining, local.maximum), (1, 4))
        self.assertEqual(vars(town), before)

    def test_pastel_inputs_cost_and_local_buyers_use_current_values(self):
        town = Town()
        town.costs[3], town.supplies[3], town.eggs = 9, 4, 6
        town.industry_goods["PASTELARIA"] = 3
        town.industry_orders["PASTELARIA"] = Order(2, 50)
        town.industry_demand["PASTELARIA"] = 5
        town.tourist_buyers["Pastéis de Belém"] = 2
        pastries = row(market_snapshot(town), "industry:PASTELARIA")
        self.assertEqual(pastries.raw_cost, 11)
        self.assertIn("Wheat: 4", pastries.raw_stock)
        self.assertIn("Eggs: 6", pastries.raw_stock)
        self.assertEqual((pastries.stock, pastries.orders, pastries.remaining_buyers), (3, 2, 7))

    def test_machinery_inputs_and_service_jobs_do_not_invent_stored_boats(self):
        town = Town()
        town.goods[0:2] = [3, 2]
        town.tier2_goods, town.tier2_order = 1, Order(2, 20)
        town.industry_orders["SHIPYARD"] = Order(1, 100)
        town.industry_demand["SHIPYARD"] = 2
        town.shipyard_quote = 130
        town.industry_prices["SHIPYARD"] = 90
        snapshot = market_snapshot(town)
        machinery = row(snapshot, "tier2")
        self.assertIsNone(machinery.raw_cost)
        self.assertEqual((machinery.stock, machinery.orders), (1, 2))
        self.assertEqual(machinery.raw_stock, "Tools: 3 · Furniture: 2")
        repair = row(snapshot, "industry:SHIPYARD")
        self.assertIsNone(repair.stock)
        self.assertEqual((repair.stock_label, repair.demand_label), ("Service", "Jobs"))
        self.assertEqual((repair.orders, repair.remaining_buyers, repair.price, repair.raw_cost), (1, 2, 90, 24))
        self.assertIn("$130", repair.notes)

    def test_daily_refresh_is_reflected_without_hidden_history(self):
        town = Town()
        town.market_elapsed = DAY_SECONDS-1
        town.sales_today[0], town.revenue_today[0] = 3, 54
        town.tourist_buyers["Tool Market"] = 0
        with patch("tycoon.random.random", return_value=.9), patch("tycoon.random.uniform", return_value=1):
            town.sync_market(DAY_SECONDS)
        snapshot = market_snapshot(town)
        self.assertEqual((snapshot.day, snapshot.seconds_to_reset), (2, DAY_SECONDS))
        tools = row(snapshot, "trade:0")
        self.assertEqual((tools.sold_today, tools.revenue_today, tools.ordinary_buyers, tools.tourist_buyers), (0, 0, 8, 4))

    def test_active_event_and_reset_countdown_are_captured(self):
        town = Town()
        town.market_elapsed = DAY_SECONDS*2+12.25
        town.market_event = ("Pottery fair", "More pottery buyers today")
        snapshot = market_snapshot(town)
        self.assertEqual((snapshot.day, snapshot.seconds_to_reset), (3, 288))
        self.assertEqual((snapshot.event_title, snapshot.event_detail), town.market_event)

    def test_locked_tier3_products_explain_research_and_have_no_buyers(self):
        town = Town()
        # A stale demand field cannot imply a market for a locked recipe.
        town.innovation["demand"]["alloy_components"] = 8
        before = deepcopy(vars(town))
        snapshot = market_snapshot(town)
        alloy = row(snapshot, "innovation:alloy_components")
        self.assertEqual((alloy.price, alloy.stock, alloy.orders, alloy.remaining_buyers), (75, 0, 0, 0))
        self.assertIn("Locked", alloy.notes)
        self.assertIn("Advanced Metallurgy level 1", alloy.notes)
        self.assertIn("Nova SBE in Carcavelos", alloy.notes)
        self.assertIsNone(alloy.raw_cost)
        self.assertEqual(vars(town), before)

    def test_tier3_market_distinguishes_shared_inputs_stock_orders_and_revenue(self):
        town = Town()
        town.innovation["levels"]["metallurgy"] = 2
        town.tier2_goods = 3
        town.innovation["goods"]["alloy_components"] = 5
        town.innovation["goods"]["precision_turbines"] = 2
        town.innovation["orders"]["precision_turbines"] = {"quantity": 1, "remaining": 0}
        town.innovation["sales_today"]["precision_turbines"] = 1
        town.innovation["revenue_today"]["precision_turbines"] = 350
        town.innovation["prices"]["precision_turbines"] = 330
        town.innovation["demand"]["precision_turbines"] = 3
        before = deepcopy(vars(town))
        turbine = row(market_snapshot(town), "innovation:precision_turbines")
        self.assertEqual(turbine.raw_stock, "Precision Machinery: 3 · Alloy Components: 5")
        self.assertIsNone(turbine.raw_cost)
        self.assertEqual((turbine.price, turbine.stock, turbine.orders), (330, 2, 1))
        self.assertEqual((turbine.sold_today, turbine.revenue_today, turbine.remaining_buyers), (1, 350, 3))
        self.assertIn("same inventory", turbine.notes)
        self.assertEqual(vars(town), before)


if __name__ == "__main__":
    unittest.main()
