from copy import deepcopy
import json
import unittest

from browser_game import advance_clock
from exchange import buy_shares, initial_state, sell_shares
from lisbon_scene import bridge_center
from tycoon import DAY_SECONDS, Order, SITES, Town, pack_save, unpack_save


class ExchangeIntegrationTest(unittest.TestCase):
    def test_legacy_progress_gets_an_empty_portfolio_without_losing_items_or_recipes(self):
        town = Town()
        town.cash, town.vehicle, town.supplies[0] = 234, "van", 11
        town.discover_recipe("pasteis")
        saved = pack_save(town, 1000)
        saved["state"].pop("exchange")
        restored, _ = unpack_save(saved)
        self.assertEqual((restored.cash, restored.vehicle, restored.supplies[0]), (234, "van", 11))
        self.assertEqual(restored.discovered_recipes, ["pasteis"])
        self.assertEqual(restored.exchange, initial_state())

    def test_dividends_are_taxed_once_and_continue_after_reload(self):
        town = Town()
        town.cash = 400
        self.assertTrue(buy_shares(town, "BAIXA", 4))
        self.assertEqual((town.cash, town.daily_expenses), (160, 0))
        advance_clock(town, DAY_SECONDS)
        self.assertEqual(town.last_day_summary["dividends"], 4)
        self.assertEqual((town.last_day_summary["profit"], town.last_day_summary["tax"]), (4, 1))
        self.assertEqual(town.cash, 163)
        restored, _ = unpack_save(json.loads(json.dumps(pack_save(town, 1000))))
        restored.settle_day(1)
        restored.sync_market(DAY_SECONDS+1)
        self.assertEqual((restored.cash, restored.taxes_paid_total), (163, 1))
        self.assertEqual(restored.exchange["total_dividends"]["BAIXA"], 4)
        advance_clock(restored, DAY_SECONDS)
        self.assertEqual((restored.cash, restored.taxes_paid_total), (166, 2))
        self.assertEqual(restored.exchange["total_dividends"]["BAIXA"], 8)

    def test_skipped_wall_clock_days_do_not_create_offline_dividends(self):
        town = Town()
        self.assertTrue(buy_shares(town, "TRAM", 1))
        town.sync_market(DAY_SECONDS*100)
        self.assertEqual(town.cash, 10)
        self.assertEqual(sum(town.exchange["total_dividends"].values()), 0)
        self.assertEqual(town.exchange["quotes"]["TRAM"], 50)
        advance_clock(town, DAY_SECONDS)
        self.assertEqual(town.cash, 11)

    def test_real_sales_raise_the_named_store_price_at_close(self):
        town = Town()
        town.cash = 400
        buy_shares(town, "BAIXA", 1)
        market = next(site for site in SITES if site.name == "Tool Market")
        town.x, town.y = market.door[0], market.door[1]+18
        town.goods[0] = 2
        town.interact()
        self.assertEqual(town.exchange["sales_today"]["BAIXA"], 2)
        self.assertEqual(town.exchange["quotes"]["BAIXA"], 60)
        previous = deepcopy(town.exchange)
        supplier = next(site for site in SITES if site.role == "SUPPLIER")
        town.x, town.y = supplier.door[0], supplier.door[1]+18
        town.interact()
        self.assertEqual(town.exchange, previous)
        advance_clock(town, DAY_SECONDS)
        self.assertEqual(town.exchange["quotes"]["BAIXA"], 61)
        self.assertEqual(town.exchange["quotes"]["BELEM"], 45)
        self.assertEqual(town.last_day_summary["dividends"], 1)

    def test_paid_bridge_tolls_are_independent_of_store_shares(self):
        town = Town()
        town.cash = 400
        buy_shares(town, "TRAM", 1)
        buy_shares(town, "BRIDGE25", 1)
        town.x, town.y = bridge_center(704), 704
        town.bridge_journey = {"origin": "south", "bridge": "25 de Abril"}
        town.check_bridge_crossing(710)
        town.check_bridge_crossing(710)
        self.assertEqual(sum(town.exchange["sales_today"].values()), 0)
        self.assertEqual((town.tolls_today, town.other_expenses_today), (3, 0))

    def test_collecting_a_shipyard_repair_payment_raises_only_that_stock(self):
        town = Town()
        town.industry_orders["SHIPYARD"] = Order(1, 0)
        town.shipyard_quote = 30
        town.interact_industry("SHIPYARD")
        self.assertEqual(town.exchange["sales_today"]["ALMADA"], 1)
        advance_clock(town, DAY_SECONDS)
        self.assertEqual((town.exchange["quotes"]["ALMADA"], town.exchange["quotes"]["BAIXA"]), (41, 60))

    def test_realized_share_profit_is_taxed_without_taxing_returned_principal(self):
        town = Town()
        town.cash = 400
        buy_shares(town, "BELEM", 2)
        town.exchange["quotes"]["BELEM"] = 56
        self.assertTrue(sell_shares(town, "BELEM", 2))
        self.assertEqual((town.cash, town.other_income_today, town.other_expenses_today), (422, 22, 0))
        town.settle_day(1)
        self.assertEqual((town.last_day_summary["profit"], town.last_day_summary["tax"]), (22, 4))

    def test_portfolio_and_store_sales_roundtrip_before_market_close(self):
        town = Town()
        buy_shares(town, "ALFAMA", 1)
        shop = next(site for site in SITES if site.name == "The Pottery Shop")
        town.x, town.y = shop.door[0], shop.door[1] + 18
        town.goods[2] = 2
        town.interact()
        advance_clock(town, 63.5)
        before = deepcopy(town.exchange)
        restored, _ = unpack_save(json.loads(json.dumps(pack_save(town, 1000))))
        self.assertEqual(restored.exchange, before)
        advance_clock(restored, DAY_SECONDS - 63.5)
        self.assertEqual(restored.exchange["quotes"]["ALFAMA"], 36)
        self.assertEqual(restored.last_day_summary["dividends"], 1)


if __name__ == "__main__":
    unittest.main()
