from copy import deepcopy
import json
from types import SimpleNamespace
import unittest

from exchange import (ASSETS, ASSET_BY_SYMBOL, advance_city, buy_shares,
                      district_symbol, initial_state, normalize_state,
                      portfolio_rows, record_bridge, record_trade, record_tram,
                      sell_shares, settle_exchange, summary)


class FakeTown:
    def __init__(self, cash=1000):
        self.cash = cash
        self.exchange = initial_state()
        self.other_income_today = 0
        self.other_expenses_today = 0
        self.message = ""
        self.won = False

    def add_cash(self, amount, business=False):
        self.cash += amount
        if not business:
            self.other_income_today += amount
        if self.cash >= 500:
            self.won = True


class ExchangeTest(unittest.TestCase):
    def test_new_portfolios_are_empty_serializable_and_independent(self):
        first, second = initial_state(), initial_state()
        self.assertEqual(json.loads(json.dumps(first)), first)
        self.assertEqual(sum(first["holdings"].values()), 0)
        self.assertEqual(len(first["quotes"]), 7)
        first["holdings"]["TRAM"] = 3
        first["activity_today"]["TRAM"]["city"] = 90
        self.assertEqual(second["holdings"]["TRAM"], 0)
        self.assertEqual(second["activity_today"]["TRAM"]["city"], 0)

    def test_buy_reserves_principal_without_business_expense(self):
        town = FakeTown(100)
        self.assertTrue(buy_shares(town, "BELEM", 2))
        self.assertEqual((town.cash, town.exchange["holdings"]["BELEM"],
                          town.exchange["cost_basis"]["BELEM"]), (10, 2, 90))
        self.assertEqual((town.other_income_today, town.other_expenses_today), (0, 0))

    def test_invalid_orders_and_insufficient_cash_are_atomic(self):
        for symbol, quantity in (("missing", 1), ([], 1), ("BELEM", True),
                                 ("BELEM", 0), ("BELEM", -1), ("BELEM", 1.0),
                                 ("BELEM", "1"), ("BELEM", 3), ("BELEM", 101)):
            with self.subTest(symbol=symbol, quantity=quantity):
                town = FakeTown(100)
                before = deepcopy(town.exchange)
                self.assertFalse(buy_shares(town, symbol, quantity))
                self.assertEqual((town.cash, town.exchange), (100, before))
                self.assertEqual((town.other_income_today, town.other_expenses_today), (0, 0))

    def test_cap_and_overselling_never_partially_execute(self):
        town = FakeTown(10000)
        self.assertTrue(buy_shares(town, "TRAM", 100))
        for action, quantity in ((buy_shares, 1), (sell_shares, 101),
                                 (sell_shares, True), (sell_shares, 0), (sell_shares, -1)):
            before = deepcopy((town.cash, town.exchange, town.other_income_today, town.other_expenses_today))
            self.assertFalse(action(town, "TRAM", quantity))
            self.assertEqual((town.cash, town.exchange, town.other_income_today, town.other_expenses_today), before)

    def test_spread_loss_is_the_only_expense_on_sale(self):
        town = FakeTown(100)
        buy_shares(town, "TRAM", 1)
        self.assertTrue(sell_shares(town, "TRAM", 1))
        self.assertEqual((town.cash, town.other_income_today, town.other_expenses_today), (95, 0, 5))
        self.assertEqual((town.exchange["holdings"]["TRAM"], town.exchange["cost_basis"]["TRAM"]), (0, 0))

    def test_profitable_sale_tax_records_only_gain_and_checks_cash_goal(self):
        town = FakeTown(499)
        buy_shares(town, "BELEM", 1)
        town.exchange["quotes"]["BELEM"] = 56
        sell_shares(town, "BELEM", 1)
        self.assertEqual((town.cash, town.other_income_today, town.other_expenses_today), (504, 5, 0))
        self.assertTrue(town.won)

    def test_partial_sales_preserve_the_entire_weighted_basis(self):
        split, whole = FakeTown(1000), FakeTown(1000)
        for town in (split, whole):
            buy_shares(town, "BELEM", 2)
            town.exchange["quotes"]["BELEM"] = 46
            buy_shares(town, "BELEM", 1)
            town.exchange["quotes"]["BELEM"] = 55
        self.assertEqual(split.exchange["cost_basis"]["BELEM"], 136)
        sell_shares(split, "BELEM", 1)
        self.assertEqual(split.exchange["cost_basis"]["BELEM"], 91)
        sell_shares(split, "BELEM", 1)
        self.assertEqual(split.exchange["cost_basis"]["BELEM"], 46)
        sell_shares(split, "BELEM", 1)
        sell_shares(whole, "BELEM", 3)
        self.assertEqual(split.cash, whole.cash)
        self.assertEqual(split.other_income_today, whole.other_income_today)
        self.assertEqual(split.exchange["cost_basis"]["BELEM"], 0)

    def test_no_share_owned_means_no_dividends_or_retroactive_credit(self):
        town = FakeTown()
        advance_city(town, 290)
        self.assertEqual(sum(town.exchange["pending_cents"].values()), 0)
        buy_shares(town, "BELEM", 1)
        advance_city(town, 10)
        self.assertEqual(town.exchange["pending_cents"]["BELEM"], 6)
        self.assertEqual(settle_exchange(town, 1), 0)

    def test_active_city_gives_balanced_per_share_daily_dividends(self):
        town = FakeTown(10000)
        for asset in ASSETS:
            buy_shares(town, asset.symbol, 1)
        advance_city(town, 300)
        for asset in ASSETS:
            self.assertGreaterEqual(town.exchange["pending_cents"][asset.symbol], 100)
            self.assertLessEqual(town.exchange["pending_cents"][asset.symbol], 300)
        previous_cash = town.cash
        self.assertEqual(settle_exchange(town, 1), 10)
        self.assertEqual((town.cash - previous_cash, town.other_income_today), (10, 10))

    def test_recorded_activity_uses_shares_held_at_each_event(self):
        town = FakeTown()
        shop = SimpleNamespace(x=28, y=160)
        record_trade(town, shop, 40)
        buy_shares(town, "BELEM", 2)
        record_trade(town, shop, 10)
        sell_shares(town, "BELEM", 1)
        record_trade(town, shop, 5)
        self.assertEqual(town.exchange["pending_cents"]["BELEM"], 25)
        self.assertEqual(town.exchange["activity_today"]["BELEM"], {"city": 0, "player": 55})

    def test_paid_transport_and_current_building_position_route_activity(self):
        town = FakeTown(10000)
        for asset in ASSETS:
            buy_shares(town, asset.symbol, 1)
        locations = ((28, 160, "BELEM"), (508, 345, "BAIXA"), (748, 530, "ALFAMA"),
                     (1540, 345, "ORIENTE"), (380, 935, "ALMADA"))
        for x, y, symbol in locations:
            site = SimpleNamespace(x=x, y=y)
            self.assertEqual(district_symbol(site), symbol)
            record_trade(town, site, 2)
            self.assertEqual(town.exchange["pending_cents"][symbol], 2)
        self.assertFalse(record_bridge(town, "Vasco da Gama"))
        self.assertTrue(record_bridge(town, "25 de Abril", 3))
        self.assertTrue(record_tram(town, 4))
        self.assertEqual(town.exchange["pending_cents"]["BRIDGE25"], 3)
        self.assertEqual(town.exchange["pending_cents"]["TRAM"], 4)

    def test_invalid_activity_is_ignored_without_mutation(self):
        town = FakeTown()
        before = deepcopy(town.exchange)
        self.assertFalse(record_trade(town, object(), 1))
        self.assertFalse(record_trade(town, SimpleNamespace(x=float("nan"), y=0), 1))
        for quantity in (True, 0, -1, 1.0, "2", None):
            self.assertFalse(record_trade(town, SimpleNamespace(x=0, y=0), quantity))
            self.assertFalse(record_tram(town, quantity))
            self.assertFalse(record_bridge(town, "25 de Abril", quantity))
        for seconds in (True, 0, -2, float("nan"), float("inf"), "10", None, 10 ** 1000):
            self.assertEqual(advance_city(town, seconds), 0)
        self.assertEqual(town.exchange, before)

    def test_fractional_ticks_match_a_single_large_step(self):
        frames, bulk = FakeTown(), FakeTown()
        buy_shares(frames, "TRAM", 1)
        buy_shares(bulk, "TRAM", 1)
        for _ in range(1200):
            advance_city(frames, .25)
        self.assertEqual(advance_city(bulk, 300), 30)
        self.assertEqual(frames.exchange, bulk.exchange)
        self.assertEqual(advance_city(bulk, 10_000_000), 1_000_000)
        self.assertEqual(bulk.exchange["activity_today"]["TRAM"]["city"], 6_000_180)

    def test_settlement_is_idempotent_after_save_reload_and_skipped_days(self):
        town = FakeTown()
        buy_shares(town, "TRAM", 1)
        advance_city(town, 300)
        saved = json.loads(json.dumps(town.exchange))
        town.exchange = normalize_state(saved)
        self.assertEqual(settle_exchange(town, 9), 1)
        self.assertEqual(town.exchange["pending_cents"]["TRAM"], 80)
        cash = town.cash
        state = deepcopy(town.exchange)
        for day in (9, 8, 0, True, -1, 1.0):
            self.assertEqual(settle_exchange(town, day), 0)
        town.exchange = normalize_state(json.loads(json.dumps(town.exchange)))
        self.assertEqual(settle_exchange(town, 9), 0)
        self.assertEqual((town.cash, town.exchange), (cash, state))
        self.assertEqual(settle_exchange(town, 20), 0)
        self.assertEqual(town.cash, cash)

    def test_fractional_dividends_carry_across_days_and_sales(self):
        town = FakeTown()
        buy_shares(town, "TRAM", 1)
        advance_city(town, 300)
        self.assertEqual(settle_exchange(town, 1), 1)
        advance_city(town, 40)
        sell_shares(town, "TRAM", 1)
        self.assertEqual(town.exchange["pending_cents"]["TRAM"], 104)
        self.assertEqual(settle_exchange(town, 2), 1)
        self.assertEqual(town.exchange["pending_cents"]["TRAM"], 4)
        advance_city(town, 300)
        self.assertEqual(settle_exchange(town, 3), 0)

    def test_city_and_player_units_are_both_in_daily_statement(self):
        town = FakeTown()
        buy_shares(town, "TRAM", 1)
        advance_city(town, 100)
        record_tram(town, 40)
        self.assertEqual(settle_exchange(town, 1), 1)
        statement = town.exchange["last_statement"]
        self.assertEqual((statement["city_activity"]["TRAM"], statement["player_activity"]["TRAM"],
                          statement["activity"]["TRAM"], statement["by_asset"]["TRAM"]), (60, 40, 100, 1))
        self.assertEqual(town.exchange["activity_today"]["TRAM"], {"city": 0, "player": 0})

    def test_daily_quotes_follow_activity_and_stay_in_bounds(self):
        town = FakeTown()
        advance_city(town, 300)
        settle_exchange(town, 1)
        self.assertEqual(town.exchange["quotes"], {asset.symbol: asset.base_price for asset in ASSETS})
        settle_exchange(town, 2)
        for asset in ASSETS:
            self.assertLess(town.exchange["quotes"][asset.symbol], asset.base_price)
        advance_city(town, 100000)
        settle_exchange(town, 3)
        for asset in ASSETS:
            self.assertEqual(town.exchange["quotes"][asset.symbol], (asset.base_price * 125 + 50) // 100)

    def test_normalization_handles_legacy_and_corrupt_data_without_retroactive_income(self):
        for value in (None, [], "old", {"version": 99}, {"version": True}, {"version": 1.0}, {}):
            self.assertEqual(normalize_state(value), initial_state())
        saved = initial_state()
        saved["holdings"].update(BELEM=999, TRAM=True, UNKNOWN=50)
        saved["cost_basis"] = {"BELEM": -1}
        saved["quotes"].update(BELEM=999, BAIXA=-8)
        saved["pending_cents"]["BELEM"] = True
        saved["activity_remainder"] = float("inf")
        saved["activity_today"]["BELEM"] = {"city": "100", "player": -3}
        before = deepcopy(saved)
        restored = normalize_state(saved)
        self.assertEqual(saved, before)
        self.assertEqual((restored["holdings"]["BELEM"], restored["holdings"]["TRAM"]), (100, 0))
        self.assertEqual(restored["cost_basis"]["BELEM"], 4500)
        self.assertNotIn("UNKNOWN", restored["holdings"])
        self.assertEqual((restored["quotes"]["BELEM"], restored["quotes"]["BAIXA"]), (56, 60))
        self.assertEqual(sum(restored["pending_cents"].values()), 0)
        self.assertEqual(restored["activity_remainder"], 0)

    def test_views_are_read_only_and_report_bid_value_and_source_ledgers(self):
        town = FakeTown()
        buy_shares(town, "TRAM", 2)
        advance_city(town, 300)
        settle_exchange(town, 1)
        record_tram(town, 3)
        before = deepcopy(vars(town))
        rows, totals = portfolio_rows(town), summary(town)
        tram = next(row for row in rows if row["symbol"] == "TRAM")
        self.assertEqual((tram["ask"], tram["bid"], tram["owned"], tram["cost_basis"], tram["value"]),
                         (50, 45, 2, 100, 90))
        self.assertEqual((tram["pending_cents"], tram["player_activity"], tram["last_payout"]), (66, 3, 3))
        self.assertEqual((totals["last_payout"], totals["total_dividends"], totals["owned"]), (3, 3, 2))
        totals["last_statement"]["by_asset"]["TRAM"] = 999
        tram["owned"] = 99
        self.assertEqual(vars(town), before)


if __name__ == "__main__":
    unittest.main()
