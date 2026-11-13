"""Check mission instructions, partial delivery and earned reward reporting."""
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from contracts import OFFER_BY_KEY, initial_state
from contracts_panel import (active_text, active_values, delivery_allowed,
                             history_values, offer_text, offer_values,
                             project_state, reputation_text, reward_text)


def player():
    return SimpleNamespace(cash=1000, contracts=initial_state())


def active_record(key="festival_project"):
    offer = OFFER_BY_KEY[key]
    return dict(id=1, key=key, required=offer.quantity, delivered=3,
                deadline=offer.seconds, cash=offer.cash, reputation=offer.reputation,
                upgrade=offer.upgrade)


class ContractsFormattingTest(unittest.TestCase):
    def test_offer_explains_free_acceptance_fixed_reward_and_partial_delivery_loss(self):
        town = player()
        offer = OFFER_BY_KEY["festival_project"]
        with patch("contracts_panel.inventory_amount", return_value=7):
            text = offer_text(town, offer)
        for phrase in ("Deliver 40", "10m 00s", "$1,400 fixed payment", "+30 reputation",
                       "Accepting is free", "partial deliveries", "not returned",
                       "do not use shop buyers", "completed once", "permanent"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertEqual(offer_values(offer)[2:], (40, "10m 00s", "$1,400", "+30"))

    def test_project_state_distinguishes_accepted_and_permanently_complete(self):
        town = player()
        offer = OFFER_BY_KEY["festival_project"]
        town.contracts["active"].append(active_record())
        self.assertEqual(project_state(town, offer), "In progress")
        town.contracts["active"].clear()
        town.contracts["completed_projects"].append(offer.key)
        self.assertEqual(project_state(town, offer), "Completed")

    def test_active_order_displays_saved_requirement_and_payment(self):
        town = player()
        record = active_record()
        record.update(required=42, cash=1450, delivered=5)
        town.contracts["elapsed"] = 30.2
        with patch("contracts_panel.inventory_amount", return_value=7), \
                patch("contracts_panel.near_destination", return_value=False):
            values = active_values(town, record)
            text = active_text(town, record)
        self.assertEqual(values[1:], ("5/42", 7, "9m 30s", "$1,450"))
        for phrase in ("Still needed: 37", "In your cargo: 7", "$1,450 fixed payment",
                       "Travel to this client", "collected into your cargo first",
                       "earn no partial payment", "continues while menus are open"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_deliver_requires_nearby_client_stock_and_unexpired_order(self):
        town, record = player(), active_record()
        with patch("contracts_panel.inventory_amount", return_value=1), \
                patch("contracts_panel.near_destination", return_value=True):
            self.assertTrue(delivery_allowed(town, record))
            town.contracts["elapsed"] = record["deadline"]
            self.assertFalse(delivery_allowed(town, record))
        town.contracts["elapsed"] = 0
        with patch("contracts_panel.inventory_amount", return_value=0), \
                patch("contracts_panel.near_destination", return_value=True):
            self.assertFalse(delivery_allowed(town, record))
        with patch("contracts_panel.inventory_amount", return_value=2), \
                patch("contracts_panel.near_destination", return_value=False):
            self.assertFalse(delivery_allowed(town, record))

    def test_history_reports_only_completed_orders_as_paid(self):
        record = active_record()
        record.update(status="completed", ended_at=10, delivered=40)
        self.assertEqual(history_values(record)[1:], ("Completed", "40/40", "$1,400", "+30"))
        for status in ("failed", "abandoned"):
            record.update(status=status, delivered=3)
            self.assertEqual(history_values(record)[-2:], ("$0", "+0"))

    def test_rewards_include_permanent_project_benefits_without_market_sale(self):
        bridge = OFFER_BY_KEY["bridge_project"]
        hotel = OFFER_BY_KEY["hotel_project"]
        self.assertIn("10%", reward_text(bridge.cash, bridge.reputation, bridge.upgrade))
        self.assertIn("10%", reward_text(hotel.cash, hotel.reputation, hotel.upgrade))
        self.assertEqual(reward_text(50, 3), "$50 fixed payment · +3 reputation")

    def test_reputation_text_separates_total_earnings_today_and_claimed_upgrades(self):
        town = player()
        town.contracts.update(reputation=30, completed=2, failed=1, abandoned=1,
                              cash_earned=1800, revenue_today=1400)
        town.contracts["upgrades"].append("cargo_expansion")
        before = copy.deepcopy(town.contracts)
        text = reputation_text(town)
        for phrase in ("30 reputation", "Completed orders: 2", "Failed: 1", "Abandoned: 1",
                       "$1,800", "Today: $1,400", "UNLOCKED", "Not yet unlocked",
                       "Higher reputation", "Permanent upgrades remain", "no offline deadline catch-up"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertEqual(town.contracts, before)


if __name__ == "__main__":
    unittest.main()
