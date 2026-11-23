from copy import deepcopy
import json
from types import SimpleNamespace
import unittest

from exchange import (ASSETS, buy_shares, initial_state, normalize_state, portfolio_rows,
                      record_trade, sell_shares, settle_exchange, summary)
from place_names import place_name
from browser_game import OPEN_SITES


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
        self.assertEqual(len(first["quotes"]), 5)
        first["holdings"]["TRAM"] = 3
        first["sales_today"]["TRAM"] = 3
        self.assertEqual(second["holdings"]["TRAM"], 0)
        self.assertEqual(second["sales_today"]["TRAM"], 0)

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

    def test_buying_and_selling_at_the_same_price_returns_the_principal(self):
        town = FakeTown(100)
        buy_shares(town, "TRAM", 1)
        self.assertTrue(sell_shares(town, "TRAM", 1))
        self.assertEqual((town.cash, town.other_income_today, town.other_expenses_today), (100, 0, 0))
        self.assertEqual((town.exchange["holdings"]["TRAM"], town.exchange["cost_basis"]["TRAM"]), (0, 0))

    def test_profitable_sale_tax_records_only_gain_and_checks_cash_goal(self):
        town = FakeTown(499)
        buy_shares(town, "BELEM", 1)
        town.exchange["quotes"]["BELEM"] = 56
        sell_shares(town, "BELEM", 1)
        self.assertEqual((town.cash, town.other_income_today, town.other_expenses_today), (510, 11, 0))
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

    def test_dividends_depend_only_on_shares_owned_at_each_close(self):
        town = FakeTown()
        self.assertEqual(settle_exchange(town, 1), 0)
        self.assertTrue(buy_shares(town, "BELEM", 2))
        self.assertTrue(buy_shares(town, "TRAM", 1))
        self.assertEqual(settle_exchange(town, 2), 8)
        self.assertEqual(settle_exchange(town, 3), 8)
        self.assertTrue(sell_shares(town, "BELEM", 1))
        self.assertEqual(settle_exchange(town, 4), 5)
        self.assertEqual(town.exchange["total_dividends"]["BELEM"], 12)
        self.assertEqual(town.exchange["total_dividends"]["TRAM"], 9)

    def test_store_names_match_the_games_public_shops_and_shipyard(self):
        stores = {site.name for site in OPEN_SITES if site.role in ("PUBLIC SHOP", "SHIPYARD")}
        self.assertEqual({asset.store for asset in ASSETS}, stores)
        self.assertEqual(len({asset.name for asset in ASSETS}), len(ASSETS))
        for asset in ASSETS:
            self.assertEqual(asset.name, place_name(asset.store))

    def test_price_rises_once_per_day_and_only_for_the_store_that_made_sales(self):
        town = FakeTown()
        first_store = SimpleNamespace(name="Daily Bread Market")
        other_store = SimpleNamespace(name="Oriente Tool Market")
        self.assertTrue(record_trade(town, first_store, 2))
        self.assertTrue(record_trade(town, first_store, 12))
        self.assertTrue(record_trade(town, other_store, 1))
        self.assertEqual((town.exchange["quotes"]["BELEM"], town.exchange["quotes"]["BRIDGE25"]), (45, 75))
        self.assertEqual(settle_exchange(town, 1), 0)
        self.assertEqual((town.exchange["quotes"]["BELEM"], town.exchange["quotes"]["BRIDGE25"]), (50, 83))
        settle_exchange(town, 2)
        self.assertEqual((town.exchange["quotes"]["BELEM"], town.exchange["quotes"]["BRIDGE25"]), (50, 83))
        self.assertTrue(record_trade(town, first_store, 1))
        settle_exchange(town, 3)
        self.assertEqual((town.exchange["quotes"]["BELEM"], town.exchange["quotes"]["BRIDGE25"]), (55, 83))

    def test_invalid_sales_are_ignored_without_mutation(self):
        town = FakeTown()
        before = deepcopy(town.exchange)
        for site in (object(), SimpleNamespace(name=[]), SimpleNamespace(name="Goldenfield Farm")):
            self.assertFalse(record_trade(town, site, 1))
        for quantity in (True, 0, -1, 1.0, "2", None):
            self.assertFalse(record_trade(town, SimpleNamespace(name="Oriente Tool Market"), quantity))
        self.assertEqual(town.exchange, before)

    def test_settlement_is_idempotent_after_reload_and_skips_offline_dividends(self):
        town = FakeTown()
        self.assertTrue(buy_shares(town, "TRAM", 1))
        self.assertTrue(record_trade(town, SimpleNamespace(name="Mercado das Nações"), 1))
        self.assertEqual(settle_exchange(town, 1), 3)
        town.exchange = normalize_state(json.loads(json.dumps(town.exchange)))
        before = deepcopy(town.exchange)
        for day in (1, 0, True, -1, 1.0):
            self.assertEqual(settle_exchange(town, day), 0)
        self.assertEqual(town.exchange, before)
        cash = town.cash
        self.assertEqual(settle_exchange(town, 20, pay_daily_dividends=False), 0)
        self.assertEqual(town.cash, cash)
        self.assertEqual(town.exchange["quotes"]["TRAM"], 55)

    def test_legacy_positions_and_pending_dividends_are_carried_forward_once(self):
        old = {
            "version": 1, "holdings": {"BELEM": 2}, "cost_basis": {"BELEM": 90},
            "quotes": {"BELEM": 38}, "pending_cents": {"BELEM": 144, "TRAM": 72},
            "total_dividends": {"BELEM": 3},
            "activity_today": {"BELEM": {"city": 24, "player": 5}}, "last_settlement": 1,
            "last_statement": {"day": 1, "by_asset": {"BELEM": 2}},
        }
        original = deepcopy(old)
        town = FakeTown()
        town.exchange = normalize_state(old)
        self.assertEqual(old, original)
        self.assertEqual(town.exchange["holdings"]["BELEM"], 2)
        self.assertEqual(town.exchange["cost_basis"]["BELEM"], 90)
        self.assertEqual(town.exchange["quotes"]["BELEM"], 38)
        self.assertEqual(town.exchange["last_statement"]["paid"], 2)
        self.assertEqual(town.exchange["sales_today"]["BELEM"], 0)
        bread_market = portfolio_rows(town)[0]
        self.assertEqual((bread_market["name"], bread_market["next_dividend"]), ("Daily Bread Market", 6))
        self.assertEqual(settle_exchange(town, 2), 7)
        self.assertEqual(town.exchange["total_dividends"]["BELEM"], 9)
        self.assertEqual(town.exchange["total_dividends"]["TRAM"], 1)
        self.assertEqual(settle_exchange(town, 3), 4)
        self.assertEqual(town.exchange["quotes"]["BELEM"], 38)

    def test_normalization_repairs_bad_positions_and_preserves_a_price_above_the_old_limit(self):
        for value in (None, [], "old", {"version": 99}, {"version": True}, {"version": 1.0}, {}):
            self.assertEqual(normalize_state(value), initial_state())
        saved = initial_state()
        saved["holdings"].update(BELEM=999, TRAM=True, UNKNOWN=50)
        saved["cost_basis"] = {"BELEM": -1}
        saved["quotes"].update(BELEM=75, BRIDGE25=-8, TRAM=0)
        saved["legacy_dividends"]["BELEM"] = True
        saved["sales_today"]["BELEM"] = -3
        restored = normalize_state(saved)
        self.assertEqual((restored["holdings"]["BELEM"], restored["holdings"]["TRAM"]), (100, 0))
        self.assertEqual(restored["cost_basis"]["BELEM"], 4500)
        self.assertNotIn("UNKNOWN", restored["holdings"])
        self.assertEqual((restored["quotes"]["BELEM"], restored["quotes"]["BRIDGE25"], restored["quotes"]["TRAM"]),
                         (75, 75, 50))
        self.assertEqual(sum(restored["legacy_dividends"].values()), 0)
        self.assertEqual(restored["sales_today"]["BELEM"], 0)

    def test_removed_listings_roll_into_their_surviving_stores_once(self):
        old = {
            "version": 2, "holdings": {"BAIXA": 100, "BRIDGE25": 45, "ALFAMA": 2, "TRAM": 1},
            "cost_basis": {"BAIXA": 6000, "BRIDGE25": 3375, "ALFAMA": 70, "TRAM": 50},
            "quotes": {"BRIDGE25": 83, "TRAM": 55},
            "legacy_dividends": {"BAIXA": 2, "BRIDGE25": 1},
            "total_dividends": {"ALFAMA": 3, "TRAM": 4},
            "sales_today": {"ALFAMA": 1, "TRAM": 2},
        }
        town = FakeTown()
        town.exchange = normalize_state(old)
        state = town.exchange
        self.assertEqual((state["holdings"]["BRIDGE25"], state["holdings"]["TRAM"]), (145, 3))
        self.assertEqual((state["cost_basis"]["BRIDGE25"], state["cost_basis"]["TRAM"]), (9375, 120))
        self.assertEqual((state["quotes"]["BRIDGE25"], state["quotes"]["TRAM"]), (83, 55))
        self.assertEqual(state["legacy_dividends"]["BRIDGE25"], 3)
        self.assertEqual(state["total_dividends"]["TRAM"], 7)
        self.assertEqual(state["sales_today"]["TRAM"], 2)
        self.assertEqual(normalize_state(json.loads(json.dumps(state))), state)
        self.assertFalse(buy_shares(town, "BRIDGE25", 1))
        self.assertTrue(sell_shares(town, "BRIDGE25", 145))

    def test_portfolio_views_are_read_only_and_show_the_next_dividend_and_price(self):
        town = FakeTown()
        self.assertTrue(buy_shares(town, "TRAM", 2))
        self.assertEqual(settle_exchange(town, 1), 5)
        self.assertTrue(record_trade(town, SimpleNamespace(name="Mercado das Nações"), 3))
        before = deepcopy(vars(town))
        rows, totals = portfolio_rows(town), summary(town)
        market = next(row for row in rows if row["symbol"] == "TRAM")
        self.assertEqual((market["name"], market["price"], market["owned"], market["value"]),
                         ("The Pottery Shop", 50, 2, 100))
        self.assertEqual((market["next_dividend"], market["next_price"], market["last_payout"]), (6, 55, 5))
        self.assertEqual((totals["last_payout"], totals["total_dividends"], totals["owned"]), (5, 5, 2))
        totals["last_statement"]["by_asset"]["TRAM"] = 999
        market["owned"] = 99
        self.assertEqual(vars(town), before)

if __name__ == "__main__":
    unittest.main()
