import json
import unittest
from unittest.mock import patch

from lisbon_landmarks import LANDMARKS
from tourism import TOURISM_AURAS, monument_description, new_tourist_pools, tourism_bonus, tourism_sources
from tycoon import DAY_SECONDS, SITES, TRADES, Town, pack_save, unpack_save


def named(name):
    return next(site for site in SITES if site.name == name)


def approach(town, name):
    site = named(name)
    town.x, town.y = site.door[0], site.door[1]+18
    return site


class TourismTest(unittest.TestCase):
    def test_invalid_saved_tourist_counts_are_rejected(self):
        for invalid in (-1, True, 1000, "4"):
            saved = pack_save(Town(), 1000)
            saved["state"]["tourist_buyers"]["Pastéis de Belém"] = invalid
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                unpack_save(saved)

    def test_all_monuments_attract_local_consumer_buyers(self):
        self.assertEqual({aura.landmark_kind for aura in TOURISM_AURAS}, {landmark.kind for landmark in LANDMARKS})
        self.assertEqual(tourism_bonus(named("Pastéis de Belém")), 9)
        self.assertEqual(tourism_bonus(named("Daily Bread Market")), 4)
        self.assertEqual(tourism_bonus(named("The Pottery Shop")), 7)
        for landmark in LANDMARKS:
            self.assertIn("buyers/day", monument_description(landmark, SITES))
        names = {aura.monument for aura in tourism_sources(named("Pastéis de Belém"))}
        self.assertIn("Mosteiro dos Jerónimos", names)
        self.assertIn("Torre de Belém", names)

    def test_initial_day_has_bonuses_without_changing_shared_base_demand(self):
        town = Town()
        affected, other = named("Tool Market"), named("Oriente Tool Market")
        self.assertEqual(town.tourism_for(affected), 4)
        self.assertEqual(town.buyers_for(affected), town.demand[0]+4)
        self.assertEqual(town.buyers_for(other), town.demand[0])
        self.assertEqual(tourism_bonus(other), 0)
        self.assertIn("+4 tourists", town.site_status(affected))

    def test_public_shop_consumes_base_first_then_its_own_tourists(self):
        town = Town()
        shop = approach(town, "Tool Market")
        town.demand[0], town.goods[0] = 3, 2
        town.interact()
        self.assertEqual((town.demand[0], town.tourism_for(shop)), (1, 4))
        town.goods[0] = 4
        town.interact()
        self.assertEqual((town.demand[0], town.tourism_for(shop)), (0, 1))
        self.assertEqual((town.sales_today[0], town.revenue_today[0]), (6, 6*town.prices[0]))
        self.assertEqual(town.buyers_for(named("Oriente Tool Market")), 0)
        town.goods[0] = 3
        town.interact()
        self.assertEqual((town.goods[0], town.buyers_for(shop)), (2, 0))
        cash = town.cash
        town.interact()
        self.assertEqual(town.cash, cash)

    def test_unrelated_market_cannot_spend_another_shops_tourists(self):
        town = Town()
        other = approach(town, "Mercado das Nações")
        pottery = named("The Pottery Shop")
        town.demand[2], town.goods[2] = 0, 3
        town.interact()
        self.assertEqual(town.goods[2], 3)
        self.assertEqual(town.buyers_for(other), 0)
        self.assertEqual(town.tourism_for(pottery), 7)
        approach(town, pottery.name)
        town.interact()
        self.assertEqual(town.goods[2], 0)
        self.assertEqual(town.tourism_for(pottery), 4)

    def test_pasteis_sell_to_tourists_after_ordinary_customers_run_out(self):
        town = Town()
        shop = approach(town, "Pastéis de Belém")
        town.industry_demand["PASTELARIA"] = 1
        town.industry_goods["PASTELARIA"] = 12
        town.interact()
        self.assertEqual((town.industry_demand["PASTELARIA"], town.tourism_for(shop)), (0, 0))
        self.assertEqual(town.industry_goods["PASTELARIA"], 2)
        self.assertEqual(town.industry_sales_today["PASTELARIA"], 10)
        self.assertEqual(town.industry_revenue_today["PASTELARIA"], 10*town.industry_prices["PASTELARIA"])
        cash = town.cash
        town.interact()
        self.assertEqual(town.cash, cash)

    def test_new_day_refreshes_pools_once_and_keeps_price_rules(self):
        town = Town()
        town.tourist_buyers = {name: 0 for name in town.tourist_buyers}
        with patch("tycoon.random.random", return_value=.9), patch("tycoon.random.uniform", return_value=1):
            town.sync_market(DAY_SECONDS)
            self.assertEqual(town.tourist_buyers, new_tourist_pools(SITES))
            self.assertEqual(town.demand, [trade.demand for trade in TRADES])
            self.assertEqual(town.prices, [trade.price for trade in TRADES])
            town.tourist_buyers["Tool Market"] = 1
            town.sync_market(DAY_SECONDS+100)
            self.assertEqual(town.tourist_buyers["Tool Market"], 1)

    def test_partial_and_exhausted_pools_survive_repeated_json_save_roundtrips(self):
        town = Town()
        town.tourist_buyers["Pastéis de Belém"] = 0
        town.tourist_buyers["The Pottery Shop"] = 2
        town.demand[2] = 0
        for _ in range(3):
            town, _ = unpack_save(json.loads(json.dumps(pack_save(town, 1000))))
            self.assertEqual(town.tourism_for(named("Pastéis de Belém")), 0)
            self.assertEqual(town.buyers_for(named("The Pottery Shop")), 2)
        town.sync_market(50)
        self.assertEqual(town.tourist_buyers["The Pottery Shop"], 2)

    def test_legacy_save_gains_new_feature_without_losing_existing_progress(self):
        town = Town()
        town.cash, town.goods[2], town.demand[2] = 234, 3, 0
        saved = pack_save(town, 1000)
        saved["state"].pop("tourist_buyers")
        restored, _ = unpack_save(saved)
        self.assertEqual((restored.cash, restored.goods[2], restored.demand[2]), (234, 3, 0))
        self.assertEqual(restored.tourist_buyers, new_tourist_pools(SITES))

    def test_suppliers_factories_and_industrial_contracts_are_not_consumer_shops(self):
        town = Town()
        for site in SITES:
            if site.role not in ("PUBLIC SHOP", "PASTELARIA"):
                with self.subTest(site=site.name):
                    self.assertEqual(tourism_bonus(site), 0)
                    self.assertEqual(town.buyers_for(site), 0)


if __name__ == "__main__":
    unittest.main()
