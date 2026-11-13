"""Real Town integration for the delivery network and separate factory stock."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

import logistics
from journal_market import market_snapshot
from tycoon import DAY_SECONDS, INDUSTRIES, Order, SITES, TRADES, Town, pack_save, unpack_save


class LogisticsIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.town = Town()
        self.town.cash = 5000
        self.factory = next(site for site in SITES if site.name == "Sunrise Bakery")

    def route(self, kind="van"):
        self.assertTrue(self.town.create_delivery_route(kind, "Goldenfield Farm", self.factory.name))
        return self.town.logistics["routes"][-1]

    def approach(self, site):
        self.town.x, self.town.y = site.door[0], site.door[1]+18

    def roundtrip(self):
        self.town = unpack_save(json.loads(json.dumps(pack_save(self.town, 1000))))[0]

    def test_old_save_preserves_progress_without_gifting_a_fleet_or_materials(self):
        self.town.vehicle, self.town.tier2_goods = "car", 2
        self.town.discover_recipe("pasteis")
        saved = pack_save(self.town, 1000)
        saved["state"].pop("logistics")
        restored, _ = unpack_save(saved)
        self.assertEqual((restored.cash, restored.vehicle, restored.tier2_goods), (5000, "car", 2))
        self.assertEqual(restored.discovered_recipes, ["pasteis"])
        self.assertEqual(restored.logistics, logistics.initial_state(SITES))

    def test_loaded_vehicle_save_resumes_without_a_second_material_or_fleet_charge(self):
        route = self.route()
        self.town.advance_deliveries(.25)
        self.assertEqual(route["phase"], "outbound")
        self.assertEqual((route["load"], self.town.cash), (6, 5000-320-6*4-1))
        before_cash = self.town.cash
        remaining = route["duration"]-route["elapsed"]
        self.roundtrip()
        restored = self.town.logistics["routes"][0]
        self.assertEqual(restored["load"], 6)
        self.assertAlmostEqual(restored["duration"]-restored["elapsed"], remaining)
        self.assertTrue(self.town.set_delivery_enabled(restored["id"], False))
        self.town.advance_deliveries(remaining+TRADES[3].seconds+1)
        factory = self.town.logistics["factories"][self.factory.name]
        self.assertEqual(factory["output"], 6)
        self.assertEqual(self.town.cash, before_cash)
        self.assertEqual(self.town.daily_expenses, 345)

    def test_automation_makes_products_outside_the_bag_until_collected_at_factory(self):
        route = self.route("drone")
        self.town.advance_deliveries(.25)
        self.town.set_delivery_enabled(route["id"], False)
        self.town.advance_deliveries(route["duration"]+TRADES[3].seconds+2)
        factory = self.town.logistics["factories"][self.factory.name]
        self.assertEqual((factory["output"], self.town.cargo, self.town.reserved), (3, 0, 0))
        self.assertIn("bread", self.town.discovered_recipes)
        self.assertEqual(self.town.collect_delivery_products(self.factory.name), 0)
        self.assertEqual(factory["output"], 3)
        self.approach(self.factory)
        self.assertIn("Auto", self.town.site_status(self.factory))
        self.town.interact()
        self.assertEqual((factory["output"], self.town.goods[3], self.town.cargo), (0, 3, 3))
        self.assertEqual(self.town.daily_revenue, 0)

    def test_full_bag_and_existing_manual_reservations_limit_automatic_collection(self):
        factory = self.town.logistics["factories"][self.factory.name]
        factory["output"] = 12
        self.town.goods[2] = 7
        self.town.orders[1] = Order(2, 100)
        self.approach(self.factory)
        self.assertEqual(self.town.collect_delivery_products(self.factory.name), 3)
        self.assertEqual((factory["output"], self.town.goods[3], self.town.cargo, self.town.reserved), (9, 3, 10, 2))
        self.assertEqual(self.town.collect_delivery_products(self.factory.name), 0)
        self.roundtrip()
        self.assertEqual((self.town.cargo, self.town.reserved), (10, 2))

    def test_personal_material_dropoff_and_ready_manual_orders_keep_interaction_priority(self):
        factory = self.town.logistics["factories"][self.factory.name]
        factory["output"] = 4
        self.town.supplies[3] = 2
        self.approach(self.factory)
        self.town.interact()
        self.assertEqual((self.town.orders[3].quantity, factory["output"]), (2, 4))
        self.town.advance(TRADES[3].seconds)
        self.town.interact()
        self.assertEqual((self.town.goods[3], factory["output"]), (2, 4))
        self.town.interact()
        self.assertEqual((self.town.goods[3], factory["output"]), (6, 0))

    def test_fleet_and_raw_material_expenses_affect_profit_once(self):
        self.route()
        self.town.advance_deliveries(.25)
        self.town.add_cash(1000)
        self.town.settle_day(1)
        self.assertEqual((self.town.last_day_summary["expenses"], self.town.last_day_summary["profit"],
                          self.town.last_day_summary["tax"]), (345, 655, 131))
        self.roundtrip()
        before = self.town.cash
        self.town.settle_day(1)
        self.assertEqual(self.town.cash, before)

    def test_wall_clock_day_changes_never_advance_paid_delivery_or_production(self):
        self.route()
        self.town.advance_deliveries(.25)
        before = deepcopy(self.town.logistics)
        self.town.sync_market(DAY_SECONDS*100)
        self.assertEqual(self.town.logistics, before)

    def test_journal_keeps_automatic_stock_separate_from_player_inventory(self):
        factory = self.town.logistics["factories"][self.factory.name]
        factory.update(input=8, output=6, order={"quantity": 3, "remaining": 2.5})
        self.town.supplies[3], self.town.goods[3] = 2, 1
        before = deepcopy(vars(self.town))
        snapshot = market_snapshot(self.town, TRADES, INDUSTRIES, SITES)
        bread = next(row for row in snapshot.rows if row.key == "trade:3")
        self.assertEqual((bread.raw_stock, bread.stock, bread.orders), ("Wheat: 2", 1, 0))
        self.assertIn("8 raw materials, 3 in production, 6 finished", bread.notes)
        self.assertIn("separate", bread.notes)
        self.assertEqual(vars(self.town), before)

    def test_automatic_finished_stock_contributes_to_market_oversupply(self):
        self.town.logistics["factories"][self.factory.name]["output"] = 10
        with patch("tycoon.random.random", return_value=1), patch("tycoon.random.uniform", return_value=1):
            self.town.sync_market(DAY_SECONDS)
        self.assertEqual((self.town.demand[3], self.town.prices[3]), (10, 7))
        self.assertEqual(self.town.goods[3], 0)
        self.assertEqual(self.town.logistics["factories"][self.factory.name]["output"], 10)


if __name__ == "__main__":
    unittest.main()
