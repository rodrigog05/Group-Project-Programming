import unittest
from unittest.mock import patch

from tycoon import DAY_SECONDS, LEGACY_DAY_SECONDS, TRADES, Town, pack_save, unpack_save


class DynamicMarketTest(unittest.TestCase):
    def roll_day(self, town):
        town.market_elapsed = DAY_SECONDS - 1
        town.sync_market(DAY_SECONDS)

    def test_oversupply_lowers_prices(self):
        town = Town()
        town.goods[0] = TRADES[0].demand * 2
        with patch("tycoon.random.random", return_value=0.9), patch("tycoon.random.uniform", return_value=1):
            self.roll_day(town)
        self.assertLess(town.prices[0], TRADES[0].price)

    def test_unexpected_demand_spike_raises_prices(self):
        town = Town()
        with patch("tycoon.random.random", return_value=0.0):
            self.roll_day(town)
        self.assertGreater(town.prices[0], TRADES[0].price)
        self.assertGreater(town.demand[0], TRADES[0].demand)

    def test_new_market_analytics_round_trip_and_old_save_defaults(self):
        town = Town()
        town.sales_today[0] = 3
        town.revenue_today[0] = 54
        town.expenses_today[0] = 15
        town.total_sold[0] = 3
        restored, _ = unpack_save(pack_save(town, 1_000))
        self.assertEqual(restored.sales_today, town.sales_today)
        self.assertEqual(restored.revenue_today, town.revenue_today)
        old_state = dict(pack_save(Town(), 1_000)["state"])
        for name in ("sales_today", "revenue_today", "expenses_today", "total_sold"):
            old_state.pop(name)
        old_save = {"version": 1, "marketStart": 1_000, "state": old_state}
        restored, _ = unpack_save(old_save)
        self.assertEqual(restored.total_sold, [0] * len(TRADES))

    def test_day_length_is_five_minutes_and_legacy_progress_is_scaled(self):
        self.assertEqual(DAY_SECONDS, 5 * 60)
        town = Town()
        town.market_elapsed = LEGACY_DAY_SECONDS + LEGACY_DAY_SECONDS // 2
        old_save = pack_save(town, 1_000)
        old_save.pop("dayLength")
        restored, _ = unpack_save(old_save)
        self.assertEqual(restored.market_elapsed, DAY_SECONDS * 1.5)


if __name__ == "__main__":
    unittest.main()
