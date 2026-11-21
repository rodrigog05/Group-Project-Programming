"""Fleet purchases, paid cargo, factory stores and save-safe active clocks."""
from copy import deepcopy
from dataclasses import dataclass
import json
import math
import unittest

import businesses
from exchange import initial_state as exchange_state
from logistics import (BUFFER_LIMIT, FLEET_VEHICLES, MAX_ROUTES, OUTPUT_LIMIT,
                       advance_logistics, collect_output, create_route,
                       initial_state, normalize_state, remove_route,
                       route_position, route_status, set_route_enabled, reassign_route)


@dataclass(frozen=True)
class Place:
    name: str
    role: str
    trade: int
    x: int
    y: int

    @property
    def door(self):
        return self.x+88, self.y+104


@dataclass(frozen=True)
class Trade:
    seconds: int


SITES = (Place("Iron Hill Mine", "SUPPLIER", 0, 1010, 935),
         Place("Ironworks", "FACTORY", 0, 268, 345),
         Place("Pine Mill", "SUPPLIER", 1, 1280, 160),
         Place("Marvila Timber Depot", "SUPPLIER", 1, 1280, 345),
         Place("Oak Workshop", "FACTORY", 1, 268, 160),
         Place("Redbank Clay Pit", "SUPPLIER", 2, 2080, 160),
         Place("Ember Kiln", "FACTORY", 2, 748, 345),
         Place("Goldenfield Farm", "SUPPLIER", 3, 1280, 530),
         Place("Quinta de Palmela", "SUPPLIER", 3, 2060, 1430),
         Place("Sunrise Bakery", "FACTORY", 3, 1540, 530))
TRADES = tuple(Trade(seconds) for seconds in (5, 7, 6, 4))


class FakeTown:
    def __init__(self, cash=10000, capacity=12):
        self.cash, self.carry_capacity = cash, capacity
        self.costs, self.expenses_today = [5, 7, 6, 4], [0]*4
        self.other_expenses_today = 0
        self.other_income_today = 0
        self.tolls_today, self.toll_count_today, self.tolls_paid_total = 0, 0, 0
        self.goods, self.supplies = [0]*4, [0]*4
        self.other_cargo = self.reserved = 0
        self.logistics = initial_state(SITES)
        self.exchange = exchange_state()
        self.message = ""

    @property
    def cargo(self):
        return self.other_cargo+sum(self.supplies)+sum(self.goods)


def add(town, kind="van", source="Goldenfield Farm", destination="Sunrise Bakery"):
    assert create_route(town, kind, source, destination, SITES, TRADES)
    return town.logistics["routes"][-1]


def tick(town, seconds):
    return advance_logistics(town, seconds, SITES, TRADES)


def financial_state(town):
    return deepcopy((town.cash, town.expenses_today, town.other_expenses_today,
                     town.tolls_today, town.toll_count_today, town.tolls_paid_total,
                     town.logistics, town.goods, town.supplies))


class LogisticsTest(unittest.TestCase):
    def test_initial_state_is_independent_and_serializable_with_canonical_factories(self):
        first, second = initial_state(SITES), initial_state(SITES)
        self.assertEqual(json.loads(json.dumps(first)), first)
        self.assertEqual(set(first["factories"]), {site.name for site in SITES if site.role == "FACTORY"})
        self.assertEqual(first["factories"]["Oak Workshop"]["trade"], 1)
        first["factories"]["Oak Workshop"]["input"] = 8
        self.assertEqual(second["factories"]["Oak Workshop"]["input"], 0)
        self.assertEqual(initial_state()["routes"], [])

    def test_purchase_spends_fleet_price_once_and_leaves_player_inventory_unchanged(self):
        town = FakeTown()
        route = add(town)
        self.assertEqual((town.cash, town.other_expenses_today), (9680, 320))
        self.assertEqual((town.cargo, town.reserved, town.expenses_today), (0, 0, [0]*4))
        self.assertEqual((route["id"], route["phase"], route["load"], route["enabled"]), (1, "idle", 0, True))
        self.assertGreater(route["duration"], 0)

    def test_wrong_material_invalid_types_or_insufficient_purchase_cash_are_atomic(self):
        town = FakeTown(cash=319)
        for arguments in (("van", "Goldenfield Farm", "Sunrise Bakery"),
                          ("van", "Goldenfield Farm", "Oak Workshop"),
                          ("van", "Sunrise Bakery", "Goldenfield Farm"),
                          ("spaceship", "Goldenfield Farm", "Sunrise Bakery"),
                          ([], "Goldenfield Farm", "Sunrise Bakery"),
                          ("van", [], "Oak Workshop")):
            before = financial_state(town)
            self.assertFalse(create_route(town, *arguments, SITES, TRADES))
            self.assertEqual(financial_state(town), before)

    def test_fleet_limit_applies_to_paused_routes_too(self):
        town = FakeTown()
        for _ in range(MAX_ROUTES):
            route = add(town)
            self.assertTrue(set_route_enabled(town, route["id"], False))
        before = financial_state(town)
        self.assertFalse(create_route(town, "van", "Pine Mill", "Oak Workshop", SITES, TRADES))
        self.assertEqual(financial_state(town), before)

    def test_dispatch_charges_materials_and_running_fee_once_then_delivers_to_factory(self):
        town = FakeTown()
        route = add(town)
        tick(town, .1)
        self.assertEqual((route["phase"], route["load"]), ("outbound", 6))
        self.assertEqual((town.cash, town.expenses_today[3], town.other_expenses_today), (9655, 24, 321))
        tick(town, route["duration"]-.1)
        factory = town.logistics["factories"]["Sunrise Bakery"]
        self.assertEqual((route["phase"], route["load"], route["delivered"], route["trips"]), ("returning", 0, 6, 1))
        self.assertEqual(factory["order"], {"quantity": 6, "remaining": 4.0})
        self.assertEqual((factory["input"], factory["output"], town.cargo), (0, 0, 0))

    def test_partial_affordable_load_pays_no_fee_when_no_unit_is_affordable(self):
        town = FakeTown(cash=329)
        route = add(town)
        tick(town, .1)
        self.assertEqual((route["load"], town.cash, town.expenses_today[3]), (2, 0, 8))
        tick(town, route["duration"]*2+3)
        self.assertEqual((route["phase"], route["materials_spent"], route["running_spent"]), ("idle", 8, 1))
        self.assertIn("cash", route_status(route))
        town.cash = 5
        tick(town, route["retry"]+.01)
        self.assertEqual((route["phase"], route["load"], town.cash), ("outbound", 1, 0))

    def test_pause_before_dispatch_spends_no_materials_or_fuel(self):
        town = FakeTown()
        route = add(town)
        set_route_enabled(town, route["id"], False)
        before = financial_state(town)
        tick(town, 120)
        self.assertEqual(financial_state(town), before)
        self.assertIn("Paused", route_status(route))

    def test_pausing_loaded_vehicle_finishes_delivery_and_return_without_new_dispatch(self):
        town = FakeTown()
        route = add(town)
        tick(town, .1)
        set_route_enabled(town, route["id"], False)
        paid = town.cash
        discoveries = tick(town, route["duration"]*2+10)
        factory = town.logistics["factories"]["Sunrise Bakery"]
        self.assertEqual((route["phase"], route["load"], route["trips"], town.cash), ("idle", 0, 1, paid))
        self.assertEqual((factory["output"], factory["produced"]), (6, 6))
        self.assertIn("bread", discoveries)

    def test_removal_only_at_depot_never_deletes_loaded_cargo_or_factory_stock(self):
        town = FakeTown()
        route = add(town)
        tick(town, .1)
        before = financial_state(town)
        self.assertFalse(remove_route(town, route["id"]))
        self.assertEqual(financial_state(town), before)
        set_route_enabled(town, route["id"], False)
        tick(town, route["duration"]-.1)
        self.assertFalse(remove_route(town, route["id"]))
        tick(town, route["duration"]+10)
        cash = town.cash
        self.assertTrue(remove_route(town, route["id"]))
        self.assertEqual(town.logistics["routes"], [])
        self.assertEqual((town.cash, town.logistics["factories"]["Sunrise Bakery"]["output"]), (cash, 6))

    def test_paid_inflight_save_roundtrip_does_not_charge_duplicate_materials(self):
        town = FakeTown()
        route = add(town)
        tick(town, .2)
        before = deepcopy(town.logistics)
        restored = normalize_state(json.loads(json.dumps(before)), SITES)
        self.assertEqual(restored, before)
        town.logistics = restored
        route = town.logistics["routes"][0]
        paid = town.cash
        set_route_enabled(town, route["id"], False)
        tick(town, route["duration"]*2+10)
        self.assertEqual((town.cash, route["materials_spent"], route["running_spent"]), (paid, 24, 1))
        self.assertEqual(town.logistics["factories"]["Sunrise Bakery"]["output"], 6)

    def test_incoming_fleet_loads_share_one_factory_buffer_limit(self):
        town = FakeTown()
        factory = town.logistics["factories"]["Sunrise Bakery"]
        factory["input"] = 44
        factory["order"] = {"quantity": 6, "remaining": 100}
        routes = [add(town), add(town)]
        tick(town, .1)
        self.assertEqual(sum(route["load"] for route in routes), 4)
        self.assertEqual((routes[0]["load"], routes[1]["phase"]), (4, "idle"))
        self.assertLessEqual(factory["input"]+sum(route["load"] for route in routes), BUFFER_LIMIT)

    def test_output_full_stops_new_dispatch_and_collection_automatically_restarts_supply(self):
        town = FakeTown()
        factory = town.logistics["factories"]["Sunrise Bakery"]
        factory["output"] = OUTPUT_LIMIT
        route = add(town)
        paid = town.cash
        tick(town, 20)
        self.assertEqual((route["phase"], town.cash), ("idle", paid))
        self.assertIn("storage full", route_status(route))
        self.assertEqual(collect_output(town, "Sunrise Bakery", 6), 6)
        tick(town, 2)
        self.assertEqual((route["phase"], route["load"]), ("outbound", 6))

    def test_factory_output_and_pending_order_never_exceed_storage_limit(self):
        town = FakeTown()
        factory = town.logistics["factories"]["Sunrise Bakery"]
        factory["output"], factory["input"] = 46, 12
        tick(town, .1)
        self.assertEqual(factory["order"]["quantity"], 2)
        tick(town, 20)
        self.assertEqual((factory["output"], factory["input"], factory["order"]), (48, 10, None))
        self.assertEqual(collect_output(town, "Sunrise Bakery", 5), 5)
        tick(town, 4)
        self.assertEqual((factory["output"], factory["input"]), (48, 5))

    def test_collection_preserves_personal_order_reservations_and_factory_trade_after_retirement(self):
        town = FakeTown()
        factory = town.logistics["factories"]["Oak Workshop"]
        factory["output"], town.other_cargo, town.reserved = 10, 7, 3
        self.assertEqual(collect_output(town, "Oak Workshop", 6), 2)
        self.assertEqual((town.goods[1], factory["output"], factory["collected"], town.cargo), (2, 8, 2, 9))
        self.assertEqual(collect_output(town, "Oak Workshop"), 0)
        self.assertIn("space", town.message)
        town.other_cargo = 0
        self.assertEqual(collect_output(town, "Oak Workshop"), 7)
        self.assertEqual((town.goods[1], factory["output"], factory["collected"]), (9, 1, 9))

    def test_invalid_collection_and_route_identifiers_do_not_mutate_inventory_or_accounts(self):
        town = FakeTown()
        add(town)
        town.logistics["factories"]["Sunrise Bakery"]["output"] = 6
        for quantity in (0, -1, True, 1.5, "2"):
            before = financial_state(town)
            self.assertEqual(collect_output(town, "Sunrise Bakery", quantity), 0)
            self.assertEqual(financial_state(town), before)
        for identifier in (True, [], None, 999):
            before = financial_state(town)
            self.assertFalse(set_route_enabled(town, identifier, False))
            self.assertFalse(remove_route(town, identifier))
            self.assertEqual(financial_state(town), before)

    def test_south_to_north_van_pays_bridge_toll_on_arrival_once(self):
        town = FakeTown()
        town.exchange["holdings"]["BRIDGE25"] = 1
        route = add(town, source="Iron Hill Mine", destination="Ironworks")
        tick(town, .1)
        set_route_enabled(town, route["id"], False)
        self.assertEqual(town.tolls_today, 0)
        paid = town.cash
        tick(town, route["duration"]-.1)
        self.assertEqual((town.cash, town.tolls_today, town.toll_count_today, town.tolls_paid_total), (paid-3, 3, 1, 3))
        self.assertEqual(town.exchange["pending_cents"]["BRIDGE25"], 1)
        tick(town, route["duration"]+10)
        self.assertEqual((town.tolls_today, route["tolls_spent"], town.toll_count_today), (3, 3, 1))

    def test_vasco_van_and_cross_river_drone_apply_their_own_toll_rules(self):
        for kind in ("van", "drone"):
            with self.subTest(kind=kind):
                town = FakeTown()
                town.exchange["holdings"]["BRIDGE25"] = 1
                route = add(town, kind, "Quinta de Palmela", "Sunrise Bakery")
                tick(town, .1)
                set_route_enabled(town, route["id"], False)
                tick(town, route["duration"]*2+10)
                self.assertEqual((town.tolls_today, route["tolls_spent"]), (3, 3) if kind == "van" else (0, 0))
                self.assertEqual(town.exchange["pending_cents"]["BRIDGE25"], 0)

    def test_exact_event_clocks_match_partitioned_frames_for_continuous_supply(self):
        large, frames = FakeTown(), FakeTown()
        add(large), add(frames)
        tick(large, 53.75)
        for _ in range(215):
            tick(frames, .25)
        self.assertEqual((large.cash, large.expenses_today, large.other_expenses_today),
                         (frames.cash, frames.expenses_today, frames.other_expenses_today))
        self.assertEqual(large.logistics["factories"], frames.logistics["factories"])
        for a, b in zip(large.logistics["routes"], frames.logistics["routes"]):
            for field in a:
                if type(a[field]) is float:
                    self.assertAlmostEqual(a[field], b[field], places=8)
                else:
                    self.assertEqual(a[field], b[field])

    def test_long_running_fleet_stops_at_capacity_without_creating_free_income(self):
        town = FakeTown()
        route = add(town)
        tick(town, 1000)
        factory = town.logistics["factories"]["Sunrise Bakery"]
        self.assertEqual(factory["output"], OUTPUT_LIMIT)
        self.assertLessEqual(factory["input"], BUFFER_LIMIT)
        self.assertEqual((town.cargo, town.reserved, town.other_income_today), (0, 0, 0))
        self.assertEqual(10000-town.cash, town.other_expenses_today+sum(town.expenses_today)+town.tolls_today)
        self.assertEqual(route["delivered"], factory["produced"]+factory["input"])

    def test_route_position_is_read_only_follows_direction_and_distinguishes_flight(self):
        town = FakeTown()
        route = add(town, source="Pine Mill", destination="Oak Workshop")
        initial = route_position(route, SITES)
        tick(town, .1)
        before = deepcopy(town.logistics)
        outbound = route_position(route, SITES)
        self.assertNotEqual(outbound, initial)
        self.assertEqual(town.logistics, before)
        route["elapsed"] = route["duration"]*.5
        middle = route_position(route, SITES)
        route["phase"] = "returning"
        self.assertEqual(route_position(route, SITES), middle)
        route["elapsed"] = route["duration"]
        self.assertEqual(route_position(route, SITES), initial)

    def test_legacy_and_corrupt_data_normalize_without_inferring_paid_cargo_or_progress(self):
        for invalid in (None, [], {"version": True}, {"version": 2}):
            self.assertEqual(normalize_state(invalid, SITES), initial_state(SITES))
        town = FakeTown()
        route = add(town)
        tick(town, .1)
        value = deepcopy(town.logistics)
        bad = deepcopy(route)
        bad.update(id=2, kind=[])
        value["routes"] += [bad, deepcopy(route), {"id": 3, "kind": "van", "source": [], "destination": "Oak Workshop"}]
        value["factories"]["Sunrise Bakery"]["output"] = -10
        value["factories"]["Oak Workshop"]["input"] = math.inf
        cleaned = normalize_state(value, SITES)
        self.assertEqual(cleaned["routes"], [route])
        self.assertEqual((cleaned["factories"]["Sunrise Bakery"]["output"], cleaned["factories"]["Oak Workshop"]["input"]), (0, 0))
        self.assertEqual(cleaned["next_id"], 2)

    def test_non_positive_or_invalid_time_is_a_noop_including_no_dispatch(self):
        town = FakeTown()
        add(town)
        for seconds in (0, -1, True, None, math.inf, math.nan, 10**1000):
            before = financial_state(town)
            self.assertEqual(tick(town, seconds), ())
            self.assertEqual(financial_state(town), before)


class OwnedFactoryLogisticsTest(unittest.TestCase):
    def own(self, town, name, trade, storage=0, equipment=0):
        if not hasattr(town, "businesses"):
            town.businesses = businesses.initial_state()
        town.businesses["owned"][name] = {
            "role": "FACTORY", "trade": trade, "storage_level": storage,
            "equipment_level": equipment, "manual_order": None, "stock": 0,
            "sales_today": 0, "revenue_today": 0, "total_sold": 0,
            "total_revenue": 0, "invested": 600,
        }

    def test_retooled_factory_accepts_matching_material_and_keeps_physical_route_after_reload(self):
        town = FakeTown()
        self.own(town, "Ironworks", 3)
        self.assertFalse(create_route(town, "van", "Iron Hill Mine", "Ironworks", SITES, TRADES))
        self.assertTrue(create_route(town, "van", "Goldenfield Farm", "Ironworks", SITES, TRADES))
        route = town.logistics["routes"][0]
        tick(town, .25)
        self.assertEqual((route["trade"], route["load"]), (3, 6))
        position = route_position(route, SITES)
        self.assertNotEqual(position, (0, 0))
        restored = normalize_state(json.loads(json.dumps(town.logistics)), SITES,
                                   businesses_state=town.businesses)
        self.assertEqual(restored["routes"], [route])
        self.assertEqual(restored["factories"]["Ironworks"]["trade"], 3)
        self.assertEqual(route_position(restored["routes"][0], SITES), position)

    def test_expanded_storage_and_larger_equipment_batch_survive_save_normalization(self):
        town = FakeTown()
        self.own(town, "Sunrise Bakery", 3, storage=3, equipment=3)
        factory = town.logistics["factories"]["Sunrise Bakery"]
        factory.update(input=90, output=70, order={"quantity": 12, "remaining": 1.5})
        restored = normalize_state(json.loads(json.dumps(town.logistics)), SITES,
                                   businesses_state=town.businesses)
        self.assertEqual(restored["factories"]["Sunrise Bakery"], factory)

    def test_equipment_changes_new_batches_without_retiming_an_existing_paid_order(self):
        town = FakeTown()
        self.own(town, "Sunrise Bakery", 3, equipment=3)
        factory = town.logistics["factories"]["Sunrise Bakery"]
        factory["input"] = 20
        tick(town, .1)
        self.assertEqual(factory["order"]["quantity"], 12)
        self.assertAlmostEqual(factory["order"]["remaining"], 4*.55-.1)
        factory.update(input=0, order={"quantity": 6, "remaining": 3.8})
        tick(town, .1)
        self.assertAlmostEqual(factory["order"]["remaining"], 3.7)

    def test_reassignment_is_free_and_preserves_existing_vehicle_and_cost_history(self):
        town = FakeTown()
        route = add(town)
        route.update(delivered=12, trips=2, materials_spent=48, running_spent=2)
        self.own(town, "Ironworks", 1)
        before_cash, before_expenses = town.cash, town.other_expenses_today
        self.assertTrue(reassign_route(town, route["id"], "Pine Mill", "Ironworks", SITES, TRADES))
        self.assertEqual((town.cash, town.other_expenses_today), (before_cash, before_expenses))
        self.assertEqual((route["id"], route["kind"], route["delivered"], route["materials_spent"]), (1, "van", 12, 48))
        self.assertEqual((route["source"], route["destination"], route["trade"]), ("Pine Mill", "Ironworks", 1))
        tick(town, .1)
        self.assertEqual((route["phase"], route["load"]), ("outbound", 6))

    def test_paid_or_incompatible_reassignments_do_not_change_cargo_or_accounting(self):
        town = FakeTown()
        route = add(town)
        before = financial_state(town)
        self.assertFalse(reassign_route(town, route["id"], "Goldenfield Farm", "Oak Workshop", SITES, TRADES))
        self.assertEqual(financial_state(town), before)
        tick(town, .1)
        before = financial_state(town)
        self.assertFalse(reassign_route(town, route["id"], "Pine Mill", "Oak Workshop", SITES, TRADES))
        self.assertEqual(financial_state(town), before)

    def test_stale_route_waits_without_purchasing_the_wrong_material(self):
        town = FakeTown()
        route = add(town)
        self.own(town, "Sunrise Bakery", 1)
        before_cash = town.cash
        tick(town, .25)
        self.assertEqual((town.cash, route["load"], route["phase"]), (before_cash, 0, "idle"))
        self.assertIn("specialization", route["status"])


if __name__ == "__main__":
    unittest.main()
