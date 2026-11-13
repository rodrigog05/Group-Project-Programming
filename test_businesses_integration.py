"""Ownership across real Town production, deliveries, retail, guidance and saves."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import businesses
from business_signs import BusinessSigns
from journal_market import market_snapshot
from journal_panel import recipe_text
from journal_recipes import RECIPE_BY_KEY
from places_menu import directory_entries
from tycoon import DAY_SECONDS, Game, INDUSTRIES, Order, SITES, TRADES, Town, pack_save, unpack_save


class BusinessIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.town = Town()
        self.town.cash = 100000

    def site(self, name):
        return next(site for site in SITES if site.name == name)

    def buy(self, name):
        self.assertTrue(self.town.purchase_business(name))
        return businesses.record_for(self.town, name)

    def approach(self, name):
        site = self.site(name)
        self.town.x, self.town.y = site.door[0], site.door[1]+18

    def roundtrip(self):
        self.town = unpack_save(json.loads(json.dumps(pack_save(self.town, 1000))))[0]

    def test_old_save_preserves_inventory_contracts_and_delivery_progress_without_gifting_property(self):
        self.town.goods[0], self.town.vehicle = 4, "car"
        self.town.accept_contract("bridge_project")
        self.town.advance_contracts(12.5)
        saved = pack_save(self.town, 1000)
        saved["state"].pop("businesses")
        restored, _ = unpack_save(saved)
        self.assertEqual((restored.cash, restored.goods[0], restored.vehicle), (100000, 4, "car"))
        self.assertEqual(restored.contracts, self.town.contracts)
        self.assertEqual(restored.businesses, businesses.initial_state())

    def test_buying_factory_migrates_paid_manual_order_and_keeps_its_cargo_reservation(self):
        self.town.orders[0] = Order(3, 30)
        record = self.buy("Ironworks")
        self.assertIsNone(self.town.orders[0])
        self.assertEqual((record["manual_order"]["quantity"], self.town.reserved), (3, 3))
        self.roundtrip()
        self.assertEqual((self.town.cash, self.town.reserved), (99400, 3))
        self.town.elapsed = 30
        self.approach("Ironworks")
        self.town.interact()
        self.assertEqual((self.town.goods[0], self.town.reserved), (3, 0))
        self.assertIsNone(businesses.record_for(self.town, "Ironworks")["manual_order"])

    def test_retooled_factory_manual_batches_use_selected_inputs_and_equipment(self):
        record = self.buy("Ironworks")
        self.assertTrue(self.town.specialize_business("Ironworks", 3))
        self.assertTrue(self.town.upgrade_business("Ironworks", "equipment"))
        self.town.supplies[3] = 3
        self.approach("Ironworks")
        self.town.interact()
        self.assertEqual((self.town.supplies[3], self.town.reserved), (0, 3))
        self.assertAlmostEqual(record["manual_order"]["ready_at"], 3.4)
        self.assertIn("bread", self.town.discovered_recipes)
        self.town.advance(3.4)
        self.town.interact()
        self.assertEqual((self.town.goods[3], self.town.goods[0], self.town.reserved), (3, 0, 0))
        self.assertEqual(self.site("Ironworks").trade, 0)

    def test_retooled_factory_receives_wheat_and_collects_bread_from_existing_delivery_network(self):
        self.buy("Ironworks")
        self.town.specialize_business("Ironworks", 3)
        self.assertFalse(self.town.create_delivery_route("drone", "Iron Hill Mine", "Ironworks"))
        self.assertTrue(self.town.create_delivery_route("drone", "Goldenfield Farm", "Ironworks"))
        self.town.advance_deliveries(.25)
        route = self.town.logistics["routes"][0]
        self.town.set_delivery_enabled(route["id"], False)
        self.town.advance_deliveries(route["duration"]+5)
        self.assertEqual(self.town.logistics["factories"]["Ironworks"]["output"], 3)
        self.approach("Ironworks")
        self.town.interact()
        self.assertEqual((self.town.goods[3], self.town.goods[0]), (3, 0))

    def test_expanded_input_output_and_in_progress_batch_survive_reload_above_original_cap(self):
        self.buy("Ironworks")
        self.town.upgrade_business("Ironworks", "storage")
        self.town.upgrade_business("Ironworks", "storage")
        self.town.upgrade_business("Ironworks", "equipment")
        factory = self.town.logistics["factories"]["Ironworks"]
        factory.update(input=70, output=80, order={"quantity": 8, "remaining": 3.5})
        self.roundtrip()
        factory = self.town.logistics["factories"]["Ironworks"]
        self.assertEqual((factory["input"], factory["output"], factory["order"]["quantity"]), (70, 80, 8))
        self.assertEqual(businesses.storage_capacity(self.town, self.site("Ironworks")), 96)
        self.assertEqual((self.town.cargo, self.town.reserved), (0, 0))

    def test_empty_delivery_vehicle_can_be_reassigned_for_free_before_and_after_factory_retool(self):
        self.buy("Ironworks")
        self.town.create_delivery_route("van", "Iron Hill Mine", "Ironworks")
        route = self.town.logistics["routes"][0]
        before_cash = self.town.cash
        self.assertFalse(self.town.specialize_business("Ironworks", 3))
        self.assertTrue(self.town.reassign_delivery_route(route["id"], "Goldenfield Farm", "Sunrise Bakery"))
        self.assertTrue(self.town.specialize_business("Ironworks", 3))
        self.assertTrue(self.town.reassign_delivery_route(route["id"], "Goldenfield Farm", "Ironworks"))
        self.assertEqual((self.town.cash, route["kind"], route["trade"]), (before_cash, "van", 3))
        self.roundtrip()
        self.assertEqual((self.town.logistics["routes"][0]["trade"], self.town.businesses["owned"]["Ironworks"]["trade"]), (3, 3))

    def test_owned_shop_retarget_uses_new_shared_buyers_and_its_existing_local_tourists(self):
        record = self.buy("The Pottery Shop")
        self.assertTrue(self.town.specialize_business("The Pottery Shop", 0))
        self.approach("The Pottery Shop")
        self.town.goods[0] = 5
        self.town.demand[0] = 1
        old_tourists = self.town.tourist_buyers["The Pottery Shop"]
        self.assertEqual(self.town.buyers_for(self.site("The Pottery Shop")), 1+old_tourists)
        before = self.town.cash
        self.town.interact()
        self.assertEqual((record["stock"], self.town.goods[0], self.town.cash), (5, 0, before))
        self.town.advance_businesses(10)
        self.assertEqual((record["stock"], self.town.cash-before, self.town.daily_revenue), (3, 36, 36))
        self.assertEqual(self.town.other_income_today, 0)
        self.assertEqual((self.town.demand[0], self.town.tourist_buyers["The Pottery Shop"]), (0, old_tourists-1))
        self.assertEqual(self.town.exchange["activity_today"]["ALFAMA"]["player"], 2)

    def test_shop_collection_checks_location_and_preserves_all_manual_order_reservations(self):
        record = self.buy("Tool Market")
        record["stock"] = 5
        self.assertEqual(self.town.withdraw_business("Tool Market", 2), 0)
        self.approach("Tool Market")
        self.town.orders[1] = Order(2, 100)
        self.town.goods[3] = 9
        self.assertEqual(self.town.withdraw_business("Tool Market", 2), 1)
        self.assertEqual((self.town.cargo, self.town.reserved, record["stock"]), (10, 2, 4))
        self.assertEqual(self.town.withdraw_business("Tool Market"), 0)

    def test_retail_sale_markup_is_taxed_once_with_property_and_upgrade_expenses(self):
        record = self.buy("Tool Market")
        self.town.upgrade_business("Tool Market", "equipment")
        self.town.goods[0] = 4
        self.approach("Tool Market")
        self.town.stock_business("Tool Market")
        self.town.add_cash(1000)
        self.town.advance_businesses(20)
        self.assertEqual((record["sales_today"], record["revenue_today"], self.town.revenue_today[0]), (4, 76, 76))
        self.assertEqual((self.town.daily_revenue, self.town.daily_expenses), (1076, 700))
        self.town.sync_market(DAY_SECONDS)
        self.assertEqual((self.town.last_day_summary["profit"], self.town.last_day_summary["tax"]), (376, 75))
        self.assertEqual((record["sales_today"], record["total_sold"], self.town.daily_revenue), (0, 4, 0))

    def test_offline_day_changes_do_not_sell_shop_stock_or_advance_retail_clock(self):
        record = self.buy("Tool Market")
        record["stock"] = 12
        self.town.advance_businesses(3.25)
        before = deepcopy(self.town.businesses)
        cash = self.town.cash
        self.town.sync_market(DAY_SECONDS*100)
        self.roundtrip()
        self.assertEqual((self.town.businesses, self.town.cash), (before, cash))

    def test_stored_shop_stock_influences_next_day_market_supply(self):
        record = self.buy("Tool Market")
        record["stock"] = 8
        with patch("tycoon.random.random", return_value=1), patch("tycoon.random.uniform", return_value=1):
            self.town.sync_market(DAY_SECONDS)
        self.assertEqual((self.town.demand[0], self.town.prices[0]), (8, 9))

    def test_current_specializations_appear_in_places_and_journal_without_changing_static_sites(self):
        self.buy("Ironworks")
        self.town.specialize_business("Ironworks", 3)
        self.buy("Tool Market")
        self.town.specialize_business("Tool Market", 3)
        entries = directory_entries(SITES, town=self.town)
        factory = next(row for row in entries["make"] if row.name == "Ironworks")
        shop = next(row for row in entries["sell"] if row.name == "Tool Market")
        self.assertIn("Wheat", factory.detail)
        self.assertIn("Owned", shop.detail)
        self.assertIn("stock your shop", shop.instruction)
        self.approach("Ironworks")
        self.town.supplies[3] = 2
        self.town.interact()
        snapshot = market_snapshot(self.town, TRADES, INDUSTRIES, SITES)
        bread = next(row for row in snapshot.rows if row.key == "trade:3")
        self.assertEqual(bread.orders, 2)
        self.assertIn("Owned shop Tool Market", bread.notes)
        effective = tuple(self.town.business_site(site) for site in SITES)
        text = recipe_text(RECIPE_BY_KEY["bread"], True, effective)
        self.assertIn("Ironworks", text)
        self.assertIn("Base production time", text)
        tools = recipe_text(RECIPE_BY_KEY["tools"], True, effective)
        self.assertNotIn("Ironworks", tools)
        self.assertIn("Businesses (B)", tools)
        self.assertEqual(self.site("Ironworks").trade, 0)


class BusinessShortcutTest(unittest.TestCase):
    def test_b_opens_management_in_town_but_keeps_black_roulette_bet_in_casino(self):
        calls = []
        game = SimpleNamespace(profile_window=None, casino_open=False, keys=set(),
                               open_businesses=lambda: calls.append("businesses"),
                               casino_key=lambda key: calls.append(key))
        Game.key_down(game, SimpleNamespace(keysym="b"))
        game.casino_open = True
        Game.key_down(game, SimpleNamespace(keysym="b"))
        self.assertEqual(calls, ["businesses", "b"])


class BusinessSignsTest(unittest.TestCase):
    def test_specialization_changes_cached_labels_and_preserves_the_painted_doorway(self):
        class Canvas:
            def __init__(self):
                self.items = {}

            def create(self, *coords, **options):
                item = len(self.items)+1
                self.items[item] = [coords, options]
                return item

            create_rectangle = create_text = create

            def itemconfigure(self, tag, **options):
                for key, item in self.items.items():
                    if key == tag or item[1].get("tags") == tag:
                        item[1].update(options)

        town = Town()
        town.cash = 1000
        town.purchase_business("Ironworks")
        site = next(site for site in SITES if site.name == "Ironworks")
        canvas = Canvas()
        camera = SimpleNamespace(sees=lambda *args: True)
        signs = BusinessSigns(canvas, (site,), 1.25, "Segoe UI")
        signs.paint(town, camera)
        old_ids = tuple(canvas.items)
        town.specialize_business("Ironworks", 3)
        signs.paint(town, camera, night=True)
        self.assertEqual(tuple(canvas.items), old_ids)
        texts = [item[1].get("text") for item in canvas.items.values() if "text" in item[1]]
        self.assertEqual(texts, ["Wheat →", "Bread"])
        for item in signs.signs[site.name]["rectangles"]:
            left, top, right, bottom = canvas.items[item][0]
            self.assertTrue(right <= (site.door[0]-12)*1.25 or left >= (site.door[0]+12)*1.25)
        camera.sees = lambda *args: False
        signs.paint(town, camera)
        self.assertTrue(all(item[1]["state"] == "hidden" for item in canvas.items.values()))


if __name__ == "__main__":
    unittest.main()
