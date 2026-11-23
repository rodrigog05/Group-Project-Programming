from copy import deepcopy
import json
import unittest

from browser_game import advance_clock
from exchange import advance_city, buy_shares, initial_state, portfolio_rows, sell_shares
from lisbon_scene import bridge_center
from tycoon import DAY_SECONDS, SITES, Town, pack_save, unpack_save


class ExchangeIntegrationTest(unittest.TestCase):
    def test_normal_belem_quotes_and_dividends_across_two_market_days(self):
        town = Town()
        self.assertTrue(buy_shares(town, "BELEM", 1))
        for day, dividend, pending in ((1, 0, 72), (2, 1, 44)):
            for _ in range(DAY_SECONDS * 4):
                advance_clock(town, .25)
            belem = next(row for row in portfolio_rows(town) if row["symbol"] == "BELEM")
            self.assertEqual(town.last_day_summary["day"], day)
            self.assertEqual((belem["ask"], belem["bid"], belem["last_payout"], belem["pending_cents"]),
                             (45, 40, dividend, pending))
        self.assertEqual(town.cash, 16)

    def test_busy_day_raises_only_its_district_quote_and_the_next_normal_day_resets_it(self):
        town = Town()
        self.assertTrue(buy_shares(town, "BAIXA", 1))
        market = next(site for site in SITES if site.name == "Tool Market")
        town.x, town.y = market.door[0], market.door[1] + 18
        town.goods[0] = 12
        town.interact()
        self.assertEqual(town.exchange["activity_today"]["BAIXA"]["player"], 12)
        advance_clock(town, DAY_SECONDS)
        quotes = town.exchange["quotes"]
        self.assertEqual((quotes["BAIXA"], quotes["BELEM"]), (62, 45))
        self.assertEqual(town.last_day_summary["dividends"], 1)
        self.assertEqual(town.exchange["pending_cents"]["BAIXA"], 8)
        advance_clock(town, DAY_SECONDS)
        self.assertEqual(quotes["BAIXA"], 60)

    def test_existing_belem_quote_is_recalculated_at_the_next_market_close(self):
        town = Town()
        town.exchange["quotes"]["BELEM"] = 38
        restored, _ = unpack_save(pack_save(town, 0))
        self.assertEqual(restored.exchange["quotes"]["BELEM"], 38)
        advance_clock(restored, DAY_SECONDS)
        self.assertEqual(restored.exchange["quotes"]["BELEM"], 45)

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

    def test_dividends_are_taxed_once_and_fractional_credits_survive_reload(self):
        town = Town()
        town.cash = 400
        self.assertTrue(buy_shares(town, "BAIXA", 2))
        self.assertEqual((town.cash, town.daily_expenses), (280, 0))
        advance_city(town, 300)
        town.sync_market(DAY_SECONDS)
        self.assertEqual(town.last_day_summary["dividends"], 4)
        self.assertEqual((town.last_day_summary["profit"], town.last_day_summary["tax"]), (4, 1))
        self.assertEqual((town.cash, town.exchange["pending_cents"]["BAIXA"]), (283, 80))
        restored, _ = unpack_save(json.loads(json.dumps(pack_save(town, 1000))))
        restored.settle_day(1)
        restored.sync_market(DAY_SECONDS+1)
        self.assertEqual((restored.cash, restored.taxes_paid_total), (283, 1))
        self.assertEqual(restored.exchange["total_dividends"]["BAIXA"], 4)

    def test_skipped_wall_clock_days_do_not_create_offline_city_income(self):
        town = Town()
        self.assertTrue(buy_shares(town, "TRAM", 1))
        town.sync_market(DAY_SECONDS*100)
        self.assertEqual(town.cash, 10)
        self.assertEqual(sum(town.exchange["total_dividends"].values()), 0)
        self.assertEqual(sum(town.exchange["pending_cents"].values()), 0)

    def test_real_sales_record_local_activity_but_raw_material_purchases_do_not(self):
        town = Town()
        town.cash = 400
        buy_shares(town, "BAIXA", 1)
        market = next(site for site in SITES if site.name == "Tool Market")
        town.x, town.y = market.door[0], market.door[1]+18
        town.goods[0] = 2
        town.interact()
        self.assertEqual(town.exchange["activity_today"]["BAIXA"]["player"], 2)
        self.assertEqual(town.exchange["pending_cents"]["BAIXA"], 2)
        previous = deepcopy(town.exchange)
        supplier = next(site for site in SITES if site.role == "SUPPLIER")
        town.x, town.y = supplier.door[0], supplier.door[1]+18
        town.interact()
        self.assertEqual(town.exchange, previous)

    def test_paid_bridge_events_feed_only_their_infrastructure_share(self):
        # The tram is scenery now, so only bridge crossings add player activity.
        town = Town()
        town.cash = 400
        buy_shares(town, "TRAM", 1)
        buy_shares(town, "BRIDGE25", 1)
        town.x, town.y = bridge_center(704), 704
        town.bridge_journey = {"origin": "south", "bridge": "25 de Abril"}
        town.check_bridge_crossing(710)
        town.check_bridge_crossing(710)
        self.assertEqual(town.exchange["activity_today"]["BRIDGE25"]["player"], 1)
        self.assertEqual((town.exchange["pending_cents"]["TRAM"], town.exchange["pending_cents"]["BRIDGE25"]), (0, 1))
        self.assertEqual((town.tolls_today, town.other_expenses_today), (3, 0))

    def test_realized_share_profit_is_taxed_without_taxing_returned_principal(self):
        town = Town()
        town.cash = 400
        buy_shares(town, "BELEM", 2)
        town.exchange["quotes"]["BELEM"] = 56
        self.assertTrue(sell_shares(town, "BELEM", 2))
        self.assertEqual((town.cash, town.other_income_today, town.other_expenses_today), (410, 10, 0))
        town.settle_day(1)
        self.assertEqual((town.last_day_summary["profit"], town.last_day_summary["tax"]), (10, 2))

    def test_portfolio_and_partial_activity_clock_roundtrip_exactly(self):
        town = Town()
        buy_shares(town, "ALFAMA", 1)
        advance_city(town, 63.5)
        before = deepcopy(town.exchange)
        restored, _ = unpack_save(json.loads(json.dumps(pack_save(town, 1000))))
        self.assertEqual(restored.exchange, before)


if __name__ == "__main__":
    unittest.main()
