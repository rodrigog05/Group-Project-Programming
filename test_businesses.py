"""Ownership receipts, real inventory, safe retooling and shared retail demand."""
from copy import deepcopy
from dataclasses import dataclass
import json
from types import SimpleNamespace
import unittest

import businesses as b


@dataclass(frozen=True)
class Place:
    name: str
    role: str
    trade: int
    x: int = 100
    y: int = 160

    @property
    def door(self):
        return self.x+88, self.y+104

    @property
    def bounds(self):
        return self.x, self.y, self.x+176, self.y+104


FACTORY = Place("Ironworks", "FACTORY", 0)
SHOP = Place("Tool Market", "PUBLIC SHOP", 0, 508, 345)
OTHER_SHOP = Place("Oriente Tool Market", "PUBLIC SHOP", 0, 1820, 345)
HOME = Place("Home Market", "PUBLIC SHOP", 1)
SPECIAL = Place("Pastéis de Belém", "PASTELARIA", -1)
SITES = (FACTORY, SHOP, OTHER_SHOP, HOME, SPECIAL)


class FakeTown:
    def __init__(self, cash=10000, capacity=12):
        self.cash, self.carry_capacity, self.elapsed = cash, capacity, 0.0
        self.supplies, self.goods, self.orders = [0]*4, [0]*4, [None]*4
        self.prices, self.demand = [18, 26, 22, 14], [8, 6, 7, 10]
        self.sales_today, self.revenue_today, self.total_sold = [0]*4, [0]*4, [0]*4
        self.other_expenses_today = self.other_income_today = self.foreign_reserved = 0
        self.businesses = b.initial_state()
        self.logistics = {"factories": {FACTORY.name: {"trade": 0, "input": 0, "output": 0, "order": None}}, "routes": []}
        self.tourists = {SHOP.name: 0, OTHER_SHOP.name: 0, HOME.name: 0}
        self.at = None
        self.message = ""

    @property
    def cargo(self):
        return sum(self.goods)+sum(self.supplies)

    @property
    def reserved(self):
        return self.foreign_reserved+b.reserved(self)+sum(order.quantity for order in self.orders if order)

    def nearby(self):
        return self.at

    def buyers_for(self, site):
        return self.demand[site.trade]+self.tourists.get(site.name, 0)

    def _consume_buyers(self, site, quantity):
        assert 0 <= quantity <= self.buyers_for(site)
        ordinary = min(quantity, self.demand[site.trade])
        self.demand[site.trade] -= ordinary
        self.tourists[site.name] -= quantity-ordinary

    def add_cash(self, amount, business=False):
        self.cash += amount
        if not business:
            self.other_income_today += amount


class BusinessModelTest(unittest.TestCase):
    def buy(self, town, site=SHOP):
        self.assertTrue(b.purchase_business(town, site.name, SITES))
        return b.record_for(town, site)

    def test_new_state_and_read_helpers_do_not_gift_ownership_or_change_legacy_town(self):
        first, second = b.initial_state(), b.initial_state()
        first["owned"]["Anything"] = {}
        self.assertEqual(second["owned"], {})
        legacy = SimpleNamespace(prices=[18, 26, 22, 14])
        before = dict(vars(legacy))
        self.assertFalse(b.is_owned(legacy, FACTORY))
        self.assertEqual((b.trade_for(legacy, FACTORY), b.storage_capacity(legacy, FACTORY), b.batch_size(legacy, FACTORY)), (0, 48, 6))
        self.assertIs(b.effective_site(legacy, FACTORY), FACTORY)
        self.assertEqual(vars(legacy), before)

    def test_factory_purchase_migrates_paid_manual_order_without_losing_reservations(self):
        town = FakeTown()
        town.orders[0] = SimpleNamespace(quantity=3, ready_at=50)
        self.assertEqual(town.reserved, 3)
        record = self.buy(town, FACTORY)
        self.assertEqual((town.cash, town.other_expenses_today, record["invested"]), (9400, 600, 600))
        self.assertIsNone(town.orders[0])
        self.assertEqual(record["manual_order"], {"quantity": 3, "ready_at": 50.0, "trade": 0})
        self.assertEqual(town.reserved, 3)
        self.assertFalse(b.purchase_business(town, FACTORY.name, SITES))
        self.assertEqual(town.cash, 9400)

    def test_invalid_or_unaffordable_purchases_leave_inventory_cash_and_property_untouched(self):
        town = FakeTown(cash=449)
        for name in (SHOP.name, SPECIAL.name, "Unknown", True):
            before = deepcopy(vars(town))
            self.assertFalse(b.purchase_business(town, name, SITES))
            before["message"] = town.message
            self.assertEqual(vars(town), before)

    def test_three_storage_and_equipment_upgrades_charge_each_price_once(self):
        town = FakeTown()
        record = self.buy(town, FACTORY)
        for _ in range(3):
            self.assertTrue(b.upgrade_business(town, FACTORY.name, "storage", SITES))
            self.assertTrue(b.upgrade_business(town, FACTORY.name, "equipment", SITES))
        self.assertEqual((b.storage_capacity(town, FACTORY), b.batch_size(town, FACTORY)), (120, 12))
        self.assertAlmostEqual(b.production_seconds(town, FACTORY, 5), 2.75)
        self.assertEqual((record["invested"], town.other_expenses_today, town.cash), (3750, 3750, 6250))
        self.assertIsNone(b.upgrade_cost(town, FACTORY, "storage"))
        self.assertFalse(b.upgrade_business(town, FACTORY.name, "storage", SITES))
        self.assertFalse(b.upgrade_business(town, FACTORY.name, "equipment", SITES))
        self.assertEqual(b.sale_price(town, FACTORY), 18)

    def test_failed_upgrade_never_charges_or_increments_levels(self):
        town = FakeTown(cash=450)
        record = self.buy(town)
        before = deepcopy(record)
        for kind in ("equipment", "storage", "unknown"):
            self.assertFalse(b.upgrade_business(town, SHOP.name, kind, SITES))
        self.assertEqual((town.cash, record), (0, before))

    def test_factory_retools_to_another_real_product_without_mutating_canonical_site(self):
        town = FakeTown()
        record = self.buy(town, FACTORY)
        self.assertTrue(b.specialize_business(town, FACTORY.name, 3, SITES))
        self.assertEqual((record["trade"], town.logistics["factories"][FACTORY.name]["trade"], FACTORY.trade), (3, 3, 0))
        town.supplies[3] = 2
        b.operate_factory(town, FACTORY)
        self.assertEqual((town.supplies[3], town.reserved), (0, 2))
        self.assertEqual(record["manual_order"], {"quantity": 2, "trade": 3, "ready_at": 4.0})
        town.elapsed = 4
        self.assertEqual(b.operate_factory(town, FACTORY), 2)
        self.assertEqual(town.goods, [0, 0, 0, 2])
        self.assertEqual(town.reserved, 0)

    def test_factory_retooling_refuses_every_kind_of_paid_or_assigned_work(self):
        town = FakeTown()
        record = self.buy(town, FACTORY)
        factory = town.logistics["factories"][FACTORY.name]
        blockers = (("manual", {"quantity": 2, "trade": 0, "ready_at": 10}),
                    ("input", 1), ("output", 1), ("order", {"quantity": 1, "remaining": 1}),
                    ("route", {"destination": FACTORY.name, "phase": "idle", "load": 0}))
        for field, value in blockers:
            with self.subTest(blocker=field):
                if field == "manual":
                    record["manual_order"] = value
                elif field == "route":
                    town.logistics["routes"] = [value]
                else:
                    factory[field] = value
                self.assertFalse(b.specialize_business(town, FACTORY.name, 1, SITES))
                self.assertEqual(record["trade"], 0)
                record["manual_order"], factory["input"], factory["output"], factory["order"], town.logistics["routes"] = None, 0, 0, None, []

    def test_invalid_product_selections_are_atomic(self):
        town = FakeTown()
        record = self.buy(town)
        for value in (True, -1, 4, "1", float("nan")):
            before = deepcopy(record)
            self.assertFalse(b.specialize_business(town, SHOP.name, value, SITES))
            self.assertEqual(record, before)

    def test_equipment_only_accelerates_new_manual_batches(self):
        town = FakeTown()
        record = self.buy(town, FACTORY)
        town.supplies[0] = 3
        b.operate_factory(town, FACTORY)
        town.elapsed = 1
        self.assertTrue(b.upgrade_business(town, FACTORY.name, "equipment", SITES))
        self.assertEqual(record["manual_order"]["ready_at"], 5)
        town.elapsed = 5
        self.assertEqual(b.operate_factory(town, FACTORY), 3)
        town.supplies[0] = 1
        b.operate_factory(town, FACTORY)
        self.assertEqual(record["manual_order"]["ready_at"], 9.25)

    def test_bad_manual_duration_does_not_consume_raw_materials(self):
        town = FakeTown()
        record = self.buy(town, FACTORY)
        town.supplies[0] = 2
        for seconds in (0, -1, "5", float("nan"), float("inf")):
            self.assertEqual(b.operate_factory(town, FACTORY, seconds), 0)
            self.assertEqual((town.supplies[0], record["manual_order"]), (2, None))

    def test_ready_factory_collection_preserves_other_reservations_when_capacity_shrinks(self):
        town = FakeTown(capacity=6)
        record = self.buy(town, FACTORY)
        record["manual_order"] = {"quantity": 4, "ready_at": 0, "trade": 0}
        town.goods[1], town.foreign_reserved = 3, 1
        self.assertEqual(b.operate_factory(town, FACTORY), 2)
        self.assertEqual((town.goods[0], record["manual_order"]["quantity"], town.foreign_reserved), (2, 2, 1))

    def test_shop_storage_is_separate_and_requires_visiting_for_stock_and_withdrawal(self):
        town = FakeTown()
        record = self.buy(town)
        town.goods[0] = 5
        self.assertEqual(b.deposit_shop(town, SHOP), 0)
        self.assertEqual(town.goods[0], 5)
        town.at = SHOP
        self.assertEqual(b.deposit_shop(town, SHOP), 5)
        self.assertEqual((town.cargo, record["stock"]), (0, 5))
        town.at = None
        self.assertEqual(b.withdraw_shop(town, SHOP), 0)
        town.at = SHOP
        self.assertEqual(b.withdraw_shop(town, SHOP, 2), 2)
        self.assertEqual((town.cargo, record["stock"]), (2, 3))

    def test_shop_stock_cannot_be_converted_to_a_different_product_by_retooling(self):
        town = FakeTown()
        record = self.buy(town)
        record["stock"] = 2
        self.assertFalse(b.specialize_business(town, SHOP.name, 3, SITES))
        town.at = SHOP
        self.assertEqual(b.withdraw_shop(town, SHOP), 2)
        self.assertTrue(b.specialize_business(town, SHOP.name, 3, SITES))
        effective = b.effective_site(town, SHOP)
        self.assertEqual((effective.trade, effective.name, effective.door, SHOP.trade), (3, SHOP.name, SHOP.door, 0))
        town.goods[3] = 4
        self.assertEqual(b.deposit_shop(town, SHOP), 4)
        self.assertEqual((record["stock"], town.goods[3], town.goods[0]), (4, 0, 2))

    def test_withdrawal_keeps_factory_reservations_free(self):
        town = FakeTown()
        record = self.buy(town)
        record["stock"], town.goods[1], town.foreign_reserved, town.at = 8, 9, 2, SHOP
        self.assertEqual(b.withdraw_shop(town, SHOP), 1)
        self.assertEqual((record["stock"], town.goods[0], town.cargo+town.reserved), (7, 1, 12))

    def test_retail_cash_arrives_on_active_boundaries_and_is_accounted_once(self):
        town = FakeTown()
        record = self.buy(town)
        town.at, town.goods[0] = SHOP, 3
        b.deposit_shop(town, SHOP)
        self.assertEqual(b.advance_businesses(town, 9.99, SITES), ())
        self.assertEqual(town.cash, 9550)
        events = b.advance_businesses(town, .01, SITES)
        self.assertEqual((len(events), events[0].quantity, events[0].revenue), (1, 2, 36))
        self.assertEqual((town.cash, record["stock"], town.revenue_today[0], town.other_income_today), (9586, 1, 36, 0))
        self.assertEqual((record["total_sold"], record["total_revenue"], town.total_sold[0]), (2, 36, 2))

    def test_two_owned_shops_share_ordinary_buyers_and_keep_tourists_local(self):
        town = FakeTown()
        a, c = self.buy(town), self.buy(town, OTHER_SHOP)
        a["stock"] = c["stock"] = 10
        town.tourists[SHOP.name], town.tourists[OTHER_SHOP.name] = 2, 1
        events = b.advance_businesses(town, 50, SITES)
        self.assertEqual(sum(event.quantity for event in events), 11)
        self.assertEqual((a["total_sold"], c["total_sold"], town.demand[0]), (6, 5, 0))
        self.assertEqual((town.tourists[SHOP.name], town.tourists[OTHER_SHOP.name]), (0, 0))
        self.assertEqual(town.revenue_today[0], 198)
        self.assertEqual(b.advance_businesses(town, 100, SITES), ())

    def test_upgraded_shop_uses_real_price_premium_and_faster_checkout(self):
        town = FakeTown()
        record = self.buy(town)
        for _ in range(3):
            self.assertTrue(b.upgrade_business(town, SHOP.name, "equipment", SITES))
        record["stock"] = 20
        self.assertEqual(b.sale_price(town, SHOP), 21)
        before = town.cash
        events = b.advance_businesses(town, 10, SITES)
        self.assertEqual((events[0].quantity, town.cash-before), (5, 105))
        self.assertEqual(town.prices[0], 18)

    def test_direct_carried_sales_require_visit_and_respect_remaining_buyers(self):
        town = FakeTown()
        record = self.buy(town)
        town.goods[0] = 10
        self.assertEqual(b.sell_shop(town, SHOP, source="carried"), 0)
        town.at = SHOP
        self.assertEqual(b.sell_shop(town, SHOP, source="carried", quantity=20), 8)
        self.assertEqual((town.goods[0], record["stock"], town.demand[0], town.revenue_today[0]), (2, 0, 0, 144))

    def test_shop_capacity_expansion_prevents_overstock_and_preserves_product_quantities(self):
        town = FakeTown(capacity=200)
        record = self.buy(town)
        town.at, town.goods[0] = SHOP, 80
        self.assertEqual(b.deposit_shop(town, SHOP), 48)
        self.assertTrue(b.upgrade_business(town, SHOP.name, "storage", SITES))
        self.assertEqual(b.deposit_shop(town, SHOP), 24)
        self.assertEqual((record["stock"], town.goods[0]), (72, 8))

    def test_saved_orders_inventory_and_retail_remainder_restore_without_payment(self):
        town = FakeTown()
        shop = self.buy(town)
        factory = self.buy(town, FACTORY)
        shop["stock"] = 30
        factory["manual_order"] = {"quantity": 4, "trade": 0, "ready_at": 20.5}
        town.businesses["retail_elapsed"] = 7.25
        before_cash = town.cash
        saved = json.loads(json.dumps(town.businesses))
        town.businesses = b.normalize_state(saved, SITES)
        self.assertEqual((town.businesses, town.cash, town.reserved), (saved, before_cash, 4))
        self.assertEqual(len(b.advance_businesses(town, 2.75, SITES)), 1)
        self.assertEqual(b.record_for(town, SHOP)["stock"], 28)

    def test_large_and_frame_sized_active_steps_produce_the_same_sales_and_clocks(self):
        first = FakeTown()
        self.buy(first)["stock"] = 40
        first.demand[0] = 100
        second = deepcopy(first)
        b.advance_businesses(first, 32.5, SITES)
        for _ in range(325):
            b.advance_businesses(second, .1, SITES)
        self.assertEqual(first.cash, second.cash)
        self.assertEqual(first.goods, second.goods)
        a, c = deepcopy(first.businesses), deepcopy(second.businesses)
        self.assertAlmostEqual(a.pop("retail_elapsed"), c.pop("retail_elapsed"))
        self.assertEqual(a, c)

    def test_bad_time_does_not_advance_or_pay_and_idle_shops_do_not_overwrite_messages(self):
        town = FakeTown()
        self.buy(town)
        before = deepcopy(town.businesses)
        for seconds in (0, -1, True, "1", float("nan"), float("inf")):
            self.assertEqual(b.advance_businesses(town, seconds, SITES), ())
            self.assertEqual(town.businesses, before)
        town.message = "Important contract message"
        b.advance_businesses(town, 10, SITES)
        self.assertEqual(town.message, "Important contract message")

    def test_daily_reset_keeps_stock_orders_investment_and_lifetime_sales(self):
        town = FakeTown()
        record = self.buy(town)
        record["stock"] = 10
        b.advance_businesses(town, 10, SITES)
        before = deepcopy(record)
        b.reset_day(town)
        self.assertEqual((record["sales_today"], record["revenue_today"]), (0, 0))
        for key in ("stock", "invested", "total_sold", "total_revenue"):
            self.assertEqual(record[key], before[key])

    def test_save_normalization_rejects_unknown_ownership_and_sanitizes_counts(self):
        for value in (None, [], {"version": True}, {"version": 999}):
            self.assertEqual(b.normalize_state(value, SITES), b.initial_state())
        town = FakeTown()
        record = self.buy(town)
        record.update(stock=999, storage_level=True, equipment_level=99, trade=True, total_sold=-5)
        town.businesses["owned"]["Unknown"] = dict(record)
        normalized = b.normalize_state(town.businesses, SITES)
        self.assertEqual(tuple(normalized["owned"]), (SHOP.name,))
        restored = normalized["owned"][SHOP.name]
        self.assertEqual((restored["stock"], restored["storage_level"], restored["equipment_level"], restored["trade"], restored["total_sold"]), (48, 0, 3, 0, 0))


if __name__ == "__main__":
    unittest.main()
