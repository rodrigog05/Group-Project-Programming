import unittest

from tycoon import Order, SITES, Town, pack_save, unpack_save


class TierTwoFactoryTest(unittest.TestCase):
    def stand_at_precision_works(self, town):
        town.x, town.y = SITES[-1].door[0], SITES[-1].door[1] + 10

    def test_tools_and_furniture_craft_and_sell_precision_machinery(self):
        town = Town()
        self.stand_at_precision_works(town)
        town.goods[0:2] = [2, 1]

        town.interact()
        self.assertEqual(town.goods[0:2], [1, 0])
        self.assertEqual(town.tier2_order.quantity, 1)
        self.assertEqual(town.reserved, 1)

        town.elapsed = 12
        town.interact()
        self.assertIsNone(town.tier2_order)
        self.assertEqual(town.tier2_goods, 1)

        town.interact()
        self.assertEqual(town.tier2_goods, 0)
        self.assertEqual(town.cash, 140)
        self.assertEqual(town.tier2_revenue_today, 80)
        self.assertEqual(town.tier2_total_sold, 1)

    def test_factory_progress_round_trips_and_old_saves_get_defaults(self):
        town = Town()
        town.tier2_goods = 2
        town.tier2_order = Order(1, 42)
        restored, _ = unpack_save(pack_save(town, 1_000))
        self.assertEqual(restored.tier2_goods, 2)
        self.assertEqual((restored.tier2_order.quantity, restored.tier2_order.ready_at), (1, 42))

        old_state = dict(pack_save(Town(), 1_000)["state"])
        for name in ("tier2_order", "tier2_goods", "tier2_demand", "tier2_price", "tier2_sales_today", "tier2_revenue_today", "tier2_total_sold"):
            old_state.pop(name)
        restored, _ = unpack_save({"version": 1, "marketStart": 1_000, "state": old_state})
        self.assertEqual(restored.tier2_goods, 0)
        self.assertEqual(restored.tier2_demand, 5)


if __name__ == "__main__":
    unittest.main()
