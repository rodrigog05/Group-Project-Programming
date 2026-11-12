import math
import unittest

from lisbon_scene import bridge_center
from tycoon import BAG_SIZE, CASH_GOAL, COLLISION_BOUNDS, Order, SITES, Town, pack_save, unpack_save
from vehicles import VEHICLES, on_road


class VehicleTrunkTest(unittest.TestCase):
    def approach(self, town, name):
        site = next(site for site in SITES if site.name == name)
        town.x, town.y = site.door[0], site.door[1]+10
        return site

    def test_each_vehicle_is_affordable_before_victory_and_adds_computed_capacity(self):
        for key, expected in (("motorcycle", 18), ("car", 60), ("van", 120)):
            with self.subTest(vehicle=key):
                town = Town()
                town.cash = 400
                ride = VEHICLES[key]
                self.assertLess(ride.price, CASH_GOAL)
                self.assertTrue(town.purchase_vehicle(key))
                self.assertEqual(town.cash, 400-ride.price)
                self.assertEqual(town.other_expenses_today, ride.price)
                self.assertEqual((town.bag_size, town.carry_capacity), (BAG_SIZE, expected))

    def test_duplicate_and_unaffordable_purchases_do_not_charge(self):
        town = Town()
        self.assertFalse(town.purchase_vehicle("car"))
        self.assertEqual((town.cash, town.other_expenses_today, town.vehicle), (60, 0, None))
        town.cash = 400
        self.assertTrue(town.purchase_vehicle("car"))
        before = town.cash, town.other_expenses_today
        self.assertFalse(town.purchase_vehicle("car"))
        self.assertEqual((town.cash, town.other_expenses_today), before)

    def test_smaller_trunk_cannot_discard_cargo_or_reserved_orders(self):
        town = Town()
        town.vehicle, town.cash = "van", 400
        town.goods[0] = 55
        town.orders[1] = Order(10, 100)
        before = town.cash, town.other_expenses_today
        self.assertFalse(town.purchase_vehicle("car"))
        self.assertEqual(town.vehicle, "van")
        self.assertEqual((town.cash, town.other_expenses_today), before)
        self.assertEqual((town.cargo, town.reserved), (55, 10))

    def test_suppliers_fill_trunk_above_personal_bag_limit(self):
        town = Town()
        town.vehicle, town.cash = "car", 400
        self.approach(town, "Iron Hill Mine")
        town.supplies[0] = 12
        town.interact(bulk=True)
        self.assertEqual(town.supplies[0], 16)
        town.supplies[0] = 58
        town.interact(bulk=True)
        self.assertEqual(town.cargo, 60)
        cash = town.cash
        town.interact(bulk=True)
        self.assertEqual((town.cargo, town.cash), (60, cash))

    def test_reserved_factory_slots_limit_new_raw_materials_in_trunk(self):
        town = Town()
        town.vehicle, town.cash = "car", 400
        town.goods[1] = 10
        town.orders[0] = Order(49, 100)
        self.approach(town, "Iron Hill Mine")
        town.interact(bulk=True)
        self.assertEqual((town.cargo, town.reserved), (11, 49))
        town.interact(bulk=True)
        self.assertEqual(town.cargo+town.reserved, 60)

    def test_standard_and_tier_two_factory_collection_use_trunk(self):
        for name, tier_two in (("Ironworks", False), ("Foundry Precision Works", True)):
            with self.subTest(factory=name):
                town = Town()
                town.vehicle = "car"
                town.goods[3] = 12
                if tier_two:
                    town.tier2_order = Order(48, 0)
                else:
                    town.orders[0] = Order(48, 0)
                self.approach(town, name)
                town.interact()
                self.assertEqual(town.cargo, 60)
                self.assertEqual(town.reserved, 0)

    def test_eggs_and_pastry_collection_use_effective_capacity(self):
        town = Town()
        town.vehicle, town.cash = "car", 400
        town.goods[0] = 58
        self.approach(town, "Goldenfield Farm")
        town.buy_eggs(bulk=True)
        self.assertEqual((town.eggs, town.cargo), (2, 60))

        town = Town()
        town.vehicle = "car"
        town.goods[0] = 12
        town.industry_orders["PASTELARIA"] = Order(48, 0)
        self.approach(town, "Pastéis de Belém")
        town.interact()
        self.assertEqual((town.industry_goods["PASTELARIA"], town.cargo), (48, 60))

    def test_existing_car_saves_gain_capacity_once_and_upgrades_combine(self):
        town = Town()
        town.vehicle = "car"
        for _ in range(3):
            saved = pack_save(town, 1000)
            self.assertNotIn("carry_capacity", saved["state"])
            town, _ = unpack_save(saved)
            self.assertEqual((town.bag_size, town.carry_capacity), (12, 60))
        town.bag_size += 12
        town.warehouse_level += 1
        town, _ = unpack_save(pack_save(town, 1000))
        self.assertEqual((town.bag_size, town.carry_capacity), (24, 72))

    def test_bag_power_up_keeps_vehicle_trunk(self):
        town = Town()
        town.vehicle, town.power_up = "car", 0
        town.x, town.y = 315, 321
        town.collect_power_up()
        self.assertEqual((town.bag_size, town.carry_capacity), (16, 64))

    def test_road_bonus_uses_paved_lanes_and_both_bridges(self):
        town = Town()
        town.vehicle = "car"
        for x, y in ((480, 321), (100, 301), (1500, 1110), (bridge_center(800), 800), (bridge_center(800, True), 800)):
            town.x, town.y = x, y
            with self.subTest(road=(x, y)):
                self.assertTrue(town.road_bonus_active)
                self.assertEqual(town.movement_speed, 690)
        for x, y in ((300, 1250), (300, 1370), (1910, 580), (596, 582), (100, 400), (2028, 210)):
            town.x, town.y = x, y
            with self.subTest(offroad=(x, y)):
                self.assertFalse(on_road(x, y, COLLISION_BOUNDS))
                self.assertEqual(town.movement_speed, 510)

    def test_road_speed_and_power_up_combine_without_changing_walking_speed(self):
        town = Town()
        self.assertEqual(town.movement_speed, 228)
        town.vehicle = "van"
        self.assertEqual(town.movement_speed, 620)
        town.speed_until = 10
        self.assertEqual(town.movement_speed, 930)

    def test_vehicle_move_uses_actual_speed_and_remains_normalized(self):
        town = Town()
        town.vehicle = "car"
        x, y = town.x, town.y
        town.move(1, 1, .01)
        self.assertAlmostEqual(math.hypot(town.x-x, town.y-y), 6.9)


if __name__ == "__main__":
    unittest.main()
