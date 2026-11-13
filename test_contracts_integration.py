"""Contract deliveries integrated with Town inventory, rewards, taxes and saves."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest

import contracts
import innovation
from living_world import LivingWorld
from tycoon import DAY_SECONDS, SITES, Town, pack_save, unpack_save


class ContractsIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.town = Town()

    def roundtrip(self):
        self.town = unpack_save(json.loads(json.dumps(pack_save(self.town, 1000))))[0]

    def accept(self, key):
        self.assertTrue(self.town.accept_contract(key))
        return self.town.contracts["active"][-1]

    def stock(self, product, quantity):
        if product in contracts.PRODUCT_ROUTES:
            self.town.goods[contracts.PRODUCT_ROUTES[product]] = quantity
        elif product == "pasteis":
            self.town.industry_goods["PASTELARIA"] = quantity
        else:
            self.town.tier2_goods = quantity

    def complete(self, key):
        record = self.accept(key)
        offer = contracts.active_offer(record)
        self.town.x, self.town.y = offer.location.x, offer.location.y
        while record["delivered"] < record["required"]:
            quantity = min(self.town.carry_capacity, record["required"]-record["delivered"])
            self.stock(offer.product_key, quantity)
            self.assertEqual(self.town.deliver_contract(record["id"]), quantity)
        return record

    def test_legacy_save_adds_empty_contracts_without_resetting_other_progress(self):
        self.town.cash, self.town.goods[0], self.town.vehicle = 312, 4, "car"
        saved = pack_save(self.town, 1000)
        saved["state"].pop("contracts")
        restored, _ = unpack_save(saved)
        self.assertEqual((restored.cash, restored.goods[0], restored.vehicle), (312, 4, "car"))
        self.assertEqual(restored.contracts, contracts.initial_state())

    def test_all_delivery_desks_are_reachable_without_new_collision_or_building_changes(self):
        for location in contracts.LOCATIONS:
            with self.subTest(location=location.name):
                self.assertTrue(self.town.can_walk(location.x, location.y))

    def test_large_festival_accepts_small_bag_trips_and_restores_partial_progress(self):
        record = self.accept("festival_project")
        offer = contracts.active_offer(record)
        self.town.x, self.town.y = offer.location.x, offer.location.y
        ordinary = deepcopy(self.town.industry_demand)
        tourists = deepcopy(self.town.tourist_buyers)
        for index, quantity in enumerate((12, 12, 12, 4)):
            self.stock("pasteis", quantity)
            self.assertLessEqual(self.town.cargo, self.town.carry_capacity)
            self.assertEqual(self.town.deliver_contract(record["id"]), quantity)
            if index == 0:
                self.town.advance_contracts(23.5)
                self.roundtrip()
                record = self.town.contracts["active"][0]
                self.assertEqual(record["delivered"], 12)
                self.assertEqual(contracts.remaining_seconds(self.town, record), 576.5)
                self.assertEqual(self.town.cash, 60)
        self.assertEqual((self.town.cash, self.town.contracts["reputation"], self.town.bag_size), (1460, 30, 16))
        self.assertEqual((self.town.daily_revenue, self.town.other_income_today), (1400, 0))
        self.assertEqual(self.town.industry_demand, ordinary)
        self.assertEqual(self.town.tourist_buyers, tourists)
        self.assertTrue(self.town.won)

    def test_project_reward_and_cargo_upgrade_cannot_replay_after_reload(self):
        record = self.complete("festival_project")
        for _ in range(3):
            self.roundtrip()
            self.assertFalse(self.town.accept_contract("festival_project"))
            self.assertEqual(self.town.deliver_contract(record["id"]), 0)
            self.assertEqual((self.town.cash, self.town.bag_size, self.town.contracts["completed"]), (1460, 16, 1))

    def test_remote_hand_in_and_factory_buffer_goods_cannot_be_delivered(self):
        record = self.accept("bridge_project")
        self.stock("tools", 6)
        self.assertEqual(self.town.deliver_contract(record["id"]), 0)
        self.assertEqual(self.town.goods[0], 6)
        offer = contracts.active_offer(record)
        self.town.x, self.town.y = offer.location.x, offer.location.y
        self.stock("tools", 0)
        self.town.logistics["factories"]["Ironworks"]["output"] = 18
        self.assertEqual(self.town.deliver_contract(record["id"]), 0)
        self.assertEqual(self.town.logistics["factories"]["Ironworks"]["output"], 18)

    def test_expiry_keeps_deposits_and_reports_failure_once_without_reward(self):
        record = self.accept("bridge_project")
        offer = contracts.active_offer(record)
        self.town.x, self.town.y = offer.location.x, offer.location.y
        self.stock("tools", 6)
        self.assertEqual(self.town.deliver_contract(record["id"]), 6)
        self.town.advance_contracts(360)
        self.assertEqual((self.town.contracts["failed"], self.town.goods[0], self.town.cash), (1, 0, 60))
        self.assertIn("Deadline missed", self.town.notice)
        self.town.advance_contracts(1)
        self.assertEqual(self.town.contracts["failed"], 1)
        self.assertEqual(self.town.deliver_contract(record["id"]), 0)

    def test_wall_clock_market_day_does_not_advance_contract_deadlines(self):
        self.accept("festival_project")
        self.town.advance_contracts(25)
        before = deepcopy(self.town.contracts)
        self.town.sync_market(DAY_SECONDS*100)
        self.assertEqual(self.town.contracts, before)
        self.roundtrip()
        self.assertEqual(self.town.contracts, before)

    def test_contract_cash_is_in_profit_once_and_daily_reset_keeps_reputation_and_perks(self):
        self.complete("bridge_project")
        self.assertEqual((self.town.daily_revenue, self.town.other_income_today), (450, 0))
        self.town.sync_market(DAY_SECONDS)
        self.assertEqual((self.town.last_day_summary["profit"], self.town.last_day_summary["tax"]), (450, 90))
        self.assertEqual((self.town.daily_revenue, self.town.contracts["reputation"]), (0, 20))
        self.assertIn("express_roads", self.town.contracts["upgrades"])
        before = self.town.cash
        self.roundtrip()
        self.town.settle_day(1)
        self.assertEqual(self.town.cash, before)

    def test_bridge_upgrade_boosts_road_movement_without_changing_offroad_speed(self):
        self.complete("bridge_project")
        self.roundtrip()
        self.town.x, self.town.y = 478, 400
        self.assertAlmostEqual(self.town.movement_speed, 228*1.1)
        self.town.vehicle = "car"
        self.assertAlmostEqual(self.town.movement_speed, 690*1.1)
        self.town.x, self.town.y = 400, 321
        self.assertFalse(self.town.road_bonus_active)
        self.assertEqual(self.town.movement_speed, 510)

    def test_hotel_grant_keeps_paid_project_cost_and_discounts_next_payment(self):
        self.town.cash = 2000
        self.assertTrue(self.town.start_research("green_energy"))
        self.complete("hotel_project")
        self.roundtrip()
        self.assertEqual(self.town.innovation["project"]["paid_cost"], 200)
        self.town.advance_research(45)
        self.assertEqual(innovation.research_quote(self.town, "green_energy"), 405)
        before = self.town.cash
        self.assertTrue(self.town.start_research("green_energy"))
        self.assertEqual((before-self.town.cash, self.town.innovation["research_spent"]), (405, 605))

    def test_contract_units_feed_city_activity_without_consuming_shop_demand(self):
        before = self.town.demand[0]
        self.complete("bridge_project")
        self.assertEqual(self.town.exchange["activity_today"]["BAIXA"]["player"], 18)
        self.assertEqual(self.town.demand[0], before)


class ContractGuidanceTest(unittest.TestCase):
    def test_custom_arrival_instruction_survives_guidance_and_resets_for_regular_destination(self):
        view = object.__new__(LivingWorld)
        view.game = SimpleNamespace(town=SimpleNamespace(x=596, y=650))
        view.navigation = SimpleNamespace(configure=lambda **kwargs: None, place=lambda **kwargs: None)
        view.update_destination_markers = lambda: None
        view.set_destination("Festival desk", 596, 650, action="C to deliver contract")
        self.assertEqual(view.destination, ("Festival desk", 596.0, 650.0))
        self.assertIn("C to deliver contract", view.navigation_text)
        view.set_destination("Normal shop", 596, 650)
        self.assertIn("E to interact", view.navigation_text)
        view.set_destination(None)
        self.assertIsNone(view.destination_action)


if __name__ == "__main__":
    unittest.main()
