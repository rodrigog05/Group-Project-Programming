import json
import math
import unittest

from lisbon_scene import BRIDGE_TOLL, bridge_center
from tycoon import DAY_SECONDS, SITES, Town, pack_save, unpack_save


def travel(town, target_y, eastern=False):
    direction = 1 if target_y > town.y else -1
    while abs(target_y-town.y) > .001:
        y = town.y+direction*min(4, abs(target_y-town.y))
        x = bridge_center(y, eastern)
        dx, dy = x-town.x, y-town.y
        old_y = town.y
        town.move(dx, dy, math.hypot(dx, dy)/town.movement_speed)
        if abs(town.y-old_y) < .001:
            raise AssertionError(f"Blocked bridge at {town.x}, {town.y}")


class BridgeTollTest(unittest.TestCase):
    def town_on_bank(self, eastern=False, south=True, cash=60):
        town = Town()
        town.y = 920 if south else 700
        town.x = bridge_center(town.y, eastern)
        town.cash = cash
        return town

    def test_both_bridges_charge_once_only_when_returning_to_lisbon(self):
        for eastern in (False, True):
            for vehicle in (None, "motorcycle", "car", "van"):
                with self.subTest(eastern=eastern, vehicle=vehicle):
                    town = self.town_on_bank(eastern, south=False)
                    town.vehicle = vehicle
                    travel(town, 920, eastern)
                    self.assertEqual(town.cash, 60)
                    travel(town, 700, eastern)
                    self.assertEqual(town.cash, 60-BRIDGE_TOLL)
                    self.assertEqual(town.toll_count_today, 1)
                    self.assertEqual(town.tolls_today, BRIDGE_TOLL)
                    self.assertIsNone(town.bridge_journey)

    def test_turning_back_mid_bridge_or_wiggling_at_north_exit_does_not_charge(self):
        town = self.town_on_bank()
        travel(town, 800)
        travel(town, 920)
        self.assertEqual(town.cash, 60)
        travel(town, 700)
        for target in (712, 704, 712, 700):
            travel(town, target)
        self.assertEqual(town.cash, 60-BRIDGE_TOLL)
        self.assertEqual(town.toll_count_today, 1)
        travel(town, 920)
        travel(town, 700)
        self.assertEqual(town.tolls_paid_total, BRIDGE_TOLL*2)

    def test_saved_crossing_completes_once_after_reload(self):
        town = self.town_on_bank(True)
        travel(town, 800, True)
        restored, _ = unpack_save(json.loads(json.dumps(pack_save(town, 1000))))
        self.assertEqual(restored.bridge_journey["origin"], "south")
        travel(restored, 700, True)
        restored, _ = unpack_save(pack_save(restored, 1000))
        travel(restored, 704, True)
        self.assertEqual(restored.tolls_paid_total, BRIDGE_TOLL)

    def test_unaffordable_toll_is_still_charged_without_negative_purchase_exploit(self):
        town = self.town_on_bank(cash=1)
        travel(town, 700)
        self.assertEqual(town.cash, 1-BRIDGE_TOLL)
        mine = next(s for s in SITES if s.role == "SUPPLIER" and s.trade == 0)
        town.x, town.y = mine.door[0], mine.door[1]+10
        town.interact()
        self.assertEqual(town.cash, 1-BRIDGE_TOLL)
        self.assertEqual(town.supplies[0], 0)


class DailyTaxTest(unittest.TestCase):
    def test_tax_uses_all_revenue_less_materials_upgrades_bets_and_tolls(self):
        town = Town()
        town.cash = 200
        town.revenue_today[0] = 100
        town.other_income_today = 20
        town.expenses_today[0] = 30
        town.other_expenses_today = 10
        town.egg_expenses_today = 4
        town.tolls_today = 3
        town.toll_count_today = 1
        town.sync_market(DAY_SECONDS)
        self.assertEqual(town.cash, 185)
        self.assertEqual(town.last_day_summary["profit"], 73)
        self.assertEqual(town.last_day_summary["tax"], 15)
        self.assertEqual(town.last_day_summary["net_profit"], 58)
        self.assertEqual(town.taxes_paid_total, 15)
        self.assertEqual((town.daily_revenue, town.daily_expenses), (0, 0))

    def test_pastel_profit_is_not_double_counted_or_taxed_on_gross_sales(self):
        town = Town()
        farm = next(s for s in SITES if s.role == "SUPPLIER" and s.trade == 3)
        town.x, town.y = farm.door[0], farm.door[1]+10
        town.interact()
        town.buy_eggs()
        shop = next(s for s in SITES if s.role == "PASTELARIA")
        town.x, town.y = shop.door[0], shop.door[1]+10
        town.interact()
        town.elapsed = 8
        town.interact()
        town.interact()
        self.assertEqual((town.daily_revenue, town.daily_expenses, town.cash), (24, 6, 78))
        town.sync_market(DAY_SECONDS)
        self.assertEqual(town.last_day_summary["tax"], 4)
        self.assertEqual(town.cash, 74)

    def test_losses_break_even_and_starting_funds_are_not_taxed(self):
        for revenue, costs in ((0, 0), (10, 10), (10, 15)):
            town = Town()
            town.revenue_today[0], town.expenses_today[0] = revenue, costs
            town.sync_market(DAY_SECONDS)
            self.assertEqual(town.cash, 60)
            self.assertEqual(town.last_day_summary["tax"], 0)

    def test_jump_across_offline_days_and_reload_never_charge_twice(self):
        town = Town()
        town.add_cash(100)
        town.sync_market(DAY_SECONDS*5)
        self.assertEqual((town.cash, town.taxes_paid_total), (140, 20))
        restored, _ = unpack_save(json.loads(json.dumps(pack_save(town, 1000))))
        restored.sync_market(DAY_SECONDS*5+1)
        restored.settle_day(1)
        self.assertEqual((restored.cash, restored.taxes_paid_total), (140, 20))
        restored.sync_market(DAY_SECONDS*6)
        self.assertEqual(restored.taxes_paid_total, 20)

    def test_casino_tax_is_on_winnings_less_stake(self):
        town = Town()
        payout = town.bet_roulette("red", 10, 32)
        town.add_cash(payout)
        self.assertEqual(town.daily_net_profit, 10)
        town.sync_market(DAY_SECONDS)
        self.assertEqual((town.cash, town.taxes_paid_total), (68, 2))

    def test_legacy_save_defaults_keep_progress_and_do_not_create_old_tolls(self):
        town = Town()
        town.cash = 234
        data = pack_save(town, 1000)
        fields = ("other_income_today", "other_expenses_today", "tolls_today", "toll_count_today",
                  "tolls_paid_total", "taxes_paid_total", "last_tax_day", "last_day_summary", "bridge_journey")
        for field in fields:
            data["state"].pop(field)
        restored, _ = unpack_save(data)
        self.assertEqual((restored.cash, restored.tolls_paid_total, restored.taxes_paid_total), (234, 0, 0))
        self.assertIsNone(restored.bridge_journey)


if __name__ == "__main__":
    unittest.main()
