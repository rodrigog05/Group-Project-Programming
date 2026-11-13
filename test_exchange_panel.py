"""Verify the portfolio explains costs, activity eligibility and cents correctly."""
import copy
import unittest

from exchange_panel import (activity_text, asset_text, exchange_rules, money_cents,
                            portfolio_text, portfolio_values, share_quantity,
                            trade_preview)


def share_row():
    return dict(symbol="BELEM", name="Belém Gastronomia", kind="District", description="Local trade and pastries.",
                ask=45, bid=40, owned=2, cap=100, cost_basis=90, value=80,
                pending_cents=235, activity=12, player_activity=0, city_activity=12,
                dividend_cents=1, last_payout=1, total_dividends=3)


def account():
    return dict(cash=70, owned=2, cost_basis=90, value=80, pending_cents=235,
                total_dividends=3, last_settlement=0, last_payout=0, activity=12,
                last_statement=dict(day=0, paid=0, by_asset={}))


class ExchangeFormattingTest(unittest.TestCase):
    def test_pending_dividends_keep_cent_precision(self):
        self.assertEqual(money_cents(1), "$0.01")
        self.assertEqual(money_cents(235), "$2.35")
        self.assertEqual(money_cents(120005), "$1,200.05")
        self.assertEqual(money_cents(-3), "-$0.03")

    def test_quantity_requires_bounded_positive_whole_ascii_units(self):
        self.assertEqual(share_quantity(" 5 "), 5)
        for value in ("", "0", "-1", "+2", "1.5", "1e2", "１２", "9999999", True, None):
            with self.subTest(value=value):
                self.assertIsNone(share_quantity(value))

    def test_portfolio_distinguishes_purchase_basis_from_sell_value(self):
        row = share_row()
        self.assertEqual(portfolio_values(row)[1:7], ("$45", "$40", 2, "$90", "$80", "$2.35"))
        text = portfolio_text(account())
        self.assertIn("Cost basis $90", text)
        self.assertIn("Exit value $80", text)
        self.assertIn("$2.35 before tax", text)

    def test_trade_preview_explains_cash_ownership_and_holding_limits(self):
        row = share_row()
        self.assertIn("need $20 more", trade_preview(row, 2, 70))
        self.assertIn("Sell 2: $80", trade_preview(row, 2, 70))
        self.assertIn("you own 2", trade_preview(row, 3, 500))
        self.assertIn("maximum 100", trade_preview(row, 99, 10000))
        self.assertIn("positive whole", trade_preview(row, None, 70))

    def test_details_explain_activity_eligibility_and_keep_earned_dividends(self):
        row = share_row()
        before = copy.deepcopy(row)
        text = asset_text(row)
        self.assertIn("$0.01 per share", text)
        self.assertIn("12 city units + 0 from you", text)
        self.assertIn("Only activity after buying", text)
        self.assertIn("already earned remain pending", text)
        self.assertEqual(row, before)

    def test_activity_statement_distinguishes_pending_from_paid(self):
        row, snapshot = share_row(), account()
        self.assertIn("first dividend statement", activity_text((row,), snapshot))
        snapshot.update(last_settlement=2, last_payout=3,
                        last_statement=dict(day=2, paid=3, by_asset={"BELEM": 3}))
        text = activity_text((row,), snapshot)
        self.assertIn("Your pending: $2.35", text)
        self.assertIn("Day 2", text)
        self.assertIn("Dividends paid: $3", text)
        self.assertIn("Belém Gastronomia: $3", text)
        self.assertIn("no offline activity", text)

    def test_rules_explain_active_simulation_spread_tax_and_saved_progress(self):
        text = exchange_rules()
        for phrase in ("90%", "rounded down", "every 10 seconds", "while this window is open",
                       "does not collect earlier", "remaining cents carry forward", "not a business expense",
                       "Time away does not create dividends", "25 de Abril", "Vasco da Gama"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
