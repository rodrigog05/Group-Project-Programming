"""Contract deposits, exact-once rewards, deadlines and persistent city upgrades."""
from copy import deepcopy
import json
import math
import unittest

from contracts import (ACTIVE_LIMIT, CYCLE_SECONDS, HISTORY_LIMIT, OFFER_BY_KEY,
                       PRODUCT_ROUTES, PROJECTS, accept_contract, active_offer,
                       advance_contracts, abandon_contract, available_offers,
                       deliver_contract, initial_state, inventory_amount,
                       near_destination, normalize_state, rank_name,
                       remaining_seconds, research_cost, reset_day, road_multiplier)


class FakeTown:
    def __init__(self):
        self.contracts = initial_state()
        self.goods, self.supplies = [0]*4, [0]*4
        self.industry_goods = {"PASTELARIA": 0}
        self.tier2_goods = 0
        self.discovered_recipes = []
        self.cash, self.bag_size, self.other_income_today = 60, 12, 0
        self.x, self.y = 480, 321
        self.message, self.cash_calls = "", []
        self.demand = [8, 6, 7, 10]
        self.logistics = {"factories": {"Sunrise Bakery": {"output": 48}}}

    def add_cash(self, amount, business=False):
        self.cash += amount
        if not business:
            self.other_income_today += amount
        self.cash_calls.append((amount, business))


def accept(town, key):
    assert accept_contract(town, key), town.message
    return town.contracts["active"][-1]


def stock(town, product, quantity):
    if product in PRODUCT_ROUTES:
        town.goods[PRODUCT_ROUTES[product]] = quantity
    elif product == "pasteis":
        town.industry_goods["PASTELARIA"] = quantity
    else:
        town.tier2_goods = quantity


def arrive(town, key):
    location = OFFER_BY_KEY[key].location
    town.x, town.y = location.x, location.y


def complete(town, key):
    record = accept(town, key)
    offer = active_offer(record)
    stock(town, offer.product_key, record["required"])
    arrive(town, key)
    assert deliver_contract(town, record["id"]) == record["required"]
    return record


class ContractsTest(unittest.TestCase):
    def test_initial_ledgers_are_empty_independent_and_json_serializable(self):
        first, second = initial_state(), initial_state()
        self.assertEqual(json.loads(json.dumps(first)), first)
        first["active"].append({"id": 1})
        first["delivered"]["bread"] = 12
        self.assertEqual((second["active"], second["delivered"]["bread"]), ([], 0))

    def test_board_reads_do_not_reroll_or_advance_and_rotation_survives_reload(self):
        town = FakeTown()
        before = deepcopy(town.contracts)
        first = tuple(offer.key for offer in available_offers(town) if offer.kind == "contract")
        self.assertEqual(len(first), 3)
        self.assertEqual(tuple(offer.key for offer in available_offers(town) if offer.kind == "contract"), first)
        self.assertEqual(town.contracts, before)
        advance_contracts(town, CYCLE_SECONDS)
        rotated = tuple(offer.key for offer in available_offers(town) if offer.kind == "contract")
        self.assertNotEqual(rotated, first)
        town.contracts = normalize_state(json.loads(json.dumps(town.contracts)))
        self.assertEqual(tuple(offer.key for offer in available_offers(town) if offer.kind == "contract"), rotated)

    def test_acceptance_is_free_but_limits_slots_and_rejects_duplicate_or_invalid_offers(self):
        town = FakeTown()
        for offer in PROJECTS:
            accept(town, offer.key)
        self.assertEqual(len(town.contracts["active"]), ACTIVE_LIMIT)
        self.assertEqual((town.cash, town.goods), (60, [0]*4))
        before = deepcopy(town.contracts)
        for key in ("bread_relief", "festival_project", "missing", [], True):
            self.assertFalse(accept_contract(town, key))
            self.assertEqual(town.contracts, before)

    def test_partial_festival_deliveries_pay_once_and_add_four_slots_once(self):
        town = FakeTown()
        record = accept(town, "festival_project")
        arrive(town, "festival_project")
        for quantity in (12, 12, 12):
            stock(town, "pasteis", quantity)
            self.assertEqual(deliver_contract(town, record["id"]), quantity)
            self.assertEqual((town.cash, town.bag_size, town.contracts["reputation"]), (60, 12, 0))
        stock(town, "pasteis", 8)
        self.assertEqual(deliver_contract(town, record["id"]), 4)
        self.assertEqual((town.cash, town.bag_size, town.contracts["reputation"]), (1460, 16, 30))
        self.assertEqual((town.industry_goods["PASTELARIA"], town.contracts["delivered"]["pasteis"]), (4, 40))
        self.assertEqual(town.cash_calls, [(1400, True)])
        self.assertEqual((town.contracts["cash_earned"], town.contracts["revenue_today"], town.other_income_today), (1400, 1400, 0))
        self.assertEqual(deliver_contract(town, record["id"]), 0)
        advance_contracts(town, CYCLE_SECONDS*100)
        town.contracts = normalize_state(json.loads(json.dumps(town.contracts)))
        self.assertFalse(accept_contract(town, "festival_project"))
        self.assertEqual((town.cash, town.bag_size), (1460, 16))

    def test_wrong_location_and_invalid_quantities_do_not_consume_or_reward(self):
        town = FakeTown()
        record = accept(town, "bridge_project")
        stock(town, "tools", 18)
        before = deepcopy((town.contracts, town.goods, town.cash))
        self.assertEqual(deliver_contract(town, record["id"]), 0)
        self.assertEqual((town.contracts, town.goods, town.cash), before)
        arrive(town, "bridge_project")
        for quantity in (0, -1, 1.5, True, "2", []):
            self.assertEqual(deliver_contract(town, record["id"], quantity), 0)
            self.assertEqual((town.contracts, town.goods, town.cash), before)
        self.assertEqual(deliver_contract(town, True, 1), 0)

    def test_collection_radius_is_inclusive_and_finished_carried_goods_only_are_used(self):
        town = FakeTown()
        record = accept(town, "bread_relief")
        offer = active_offer(record)
        town.supplies[3] = 100
        arrive(town, offer.key)
        town.x += 45
        self.assertTrue(near_destination(town, offer))
        self.assertEqual(deliver_contract(town, record["id"]), 0)
        town.goods[3] = 4
        self.assertEqual(deliver_contract(town, record["id"], 10), 4)
        self.assertEqual((town.supplies[3], town.logistics["factories"]["Sunrise Bakery"]["output"]), (100, 48))
        town.x += .001
        self.assertFalse(near_destination(town, offer))

    def test_contracts_do_not_consume_normal_buyer_pools_or_pay_partial_deposits(self):
        town = FakeTown()
        record = accept(town, "bread_relief")
        arrive(town, "bread_relief")
        town.goods[3] = 16
        buyers = town.demand[:]
        self.assertEqual(deliver_contract(town, record["id"], 8), 8)
        self.assertEqual((town.cash, town.contracts["reputation"]), (60, 0))
        self.assertEqual(deliver_contract(town, record["id"], 999), 8)
        self.assertEqual((town.cash, town.contracts["reputation"], town.demand), (380, 8, buyers))
        self.assertFalse(accept_contract(town, "bread_relief"))

    def test_deadline_expires_once_at_exact_boundary_and_deposits_stay_spent(self):
        town = FakeTown()
        record = accept(town, "bridge_project")
        stock(town, "tools", 6)
        arrive(town, "bridge_project")
        deliver_contract(town, record["id"])
        advance_contracts(town, record["deadline"]-.01)
        self.assertAlmostEqual(remaining_seconds(town, record), .01)
        expired = advance_contracts(town, .01)
        self.assertEqual((len(expired), expired[0]["key"]), (1, "bridge_project"))
        self.assertEqual((town.goods[0], town.cash, town.contracts["reputation"]), (0, 60, 0))
        self.assertEqual((town.contracts["failed"], town.contracts["history"][-1]["status"]), (1, "failed"))
        self.assertEqual(advance_contracts(town, .25), ())
        self.assertEqual(deliver_contract(town, record["id"]), 0)
        self.assertEqual(town.contracts["failed"], 1)

    def test_abandon_is_final_and_retry_waits_until_next_board_cycle(self):
        town = FakeTown()
        record = accept(town, "festival_project")
        arrive(town, "festival_project")
        stock(town, "pasteis", 12)
        deliver_contract(town, record["id"])
        self.assertTrue(abandon_contract(town, record["id"]))
        self.assertEqual((town.industry_goods["PASTELARIA"], town.cash, town.contracts["abandoned"]), (0, 60, 1))
        self.assertFalse(accept_contract(town, "festival_project"))
        advance_contracts(town, CYCLE_SECONDS)
        replacement = accept(town, "festival_project")
        self.assertGreater(replacement["id"], record["id"])
        self.assertEqual(replacement["delivered"], 0)

    def test_saved_partial_order_keeps_time_goods_and_rewards_without_offline_catchup(self):
        town = FakeTown()
        record = accept(town, "hotel_project")
        arrive(town, "hotel_project")
        stock(town, "furniture", 5)
        deliver_contract(town, record["id"])
        advance_contracts(town, 123.25)
        before = deepcopy(town.contracts)
        town.contracts = normalize_state(json.loads(json.dumps(town.contracts)))
        self.assertEqual(town.contracts, before)
        self.assertEqual((remaining_seconds(town, town.contracts["active"][0]), town.cash, town.bag_size), (356.75, 60, 12))
        self.assertEqual(town.cash_calls, [])

    def test_bridge_and_hotel_upgrades_affect_only_their_named_future_benefits(self):
        town = FakeTown()
        self.assertEqual((road_multiplier(town), research_cost(town, 200)), (1, 200))
        complete(town, "bridge_project")
        self.assertEqual((road_multiplier(town), research_cost(town, 200)), (1.1, 200))
        complete(town, "hotel_project")
        self.assertEqual((research_cost(town, 200), research_cost(town, 201), research_cost(town, 1)), (180, 181, 1))
        self.assertEqual((town.contracts["reputation"], town.bag_size), (45, 12))
        town.contracts = normalize_state(json.loads(json.dumps(town.contracts)))
        self.assertEqual((road_multiplier(town), research_cost(town, 200)), (1.1, 180))

    def test_project_claim_evidence_prevents_replay_even_if_one_marker_is_missing(self):
        town = FakeTown()
        complete(town, "festival_project")
        saved = deepcopy(town.contracts)
        for missing in ("completed_projects", "upgrades"):
            damaged = deepcopy(saved)
            damaged.pop(missing)
            town.contracts = normalize_state(damaged)
            self.assertIn("festival_project", town.contracts["completed_projects"])
            self.assertIn("cargo_expansion", town.contracts["upgrades"])
            self.assertFalse(accept_contract(town, "festival_project"))
            self.assertEqual(town.bag_size, 16)

    def test_reputation_and_discovered_recipe_unlock_high_value_equipment_orders(self):
        town = FakeTown()
        town.contracts["reputation"] = 50
        self.assertEqual(rank_name(town), "Trusted Supplier")
        for cycle in range(4):
            town.contracts["elapsed"] = cycle*CYCLE_SECONDS
            self.assertNotIn("campus_machinery", {offer.key for offer in available_offers(town)})
        town.discovered_recipes.append("precision_machinery")
        keys = set()
        for cycle in range(4):
            town.contracts["elapsed"] = cycle*CYCLE_SECONDS
            keys.update(offer.key for offer in available_offers(town))
        self.assertIn("campus_machinery", keys)

    def test_history_is_bounded_while_lifetime_income_reputation_and_counts_persist(self):
        town = FakeTown()
        expected_cash = expected_rep = 0
        for cycle in range(HISTORY_LIMIT+5):
            if cycle:
                advance_contracts(town, CYCLE_SECONDS)
            offer = next(offer for offer in available_offers(town) if offer.kind == "contract")
            complete(town, offer.key)
            expected_cash += offer.cash
            expected_rep += offer.reputation
        self.assertEqual((len(town.contracts["history"]), town.contracts["completed"]), (HISTORY_LIMIT, HISTORY_LIMIT+5))
        self.assertEqual((town.contracts["cash_earned"], town.contracts["reputation"]), (expected_cash, expected_rep))
        restored = normalize_state(json.loads(json.dumps(town.contracts)))
        self.assertEqual(restored, town.contracts)

    def test_large_and_fractional_steps_have_identical_expiry_and_rotation_results(self):
        first, second = FakeTown(), FakeTown()
        accept(first, "bread_relief")
        accept(second, "bread_relief")
        advance_contracts(first, 1000)
        for _ in range(4000):
            advance_contracts(second, .25)
        self.assertEqual(first.contracts, second.contracts)

    def test_daily_reset_clears_only_current_revenue_and_keeps_active_progress(self):
        town = FakeTown()
        complete(town, "bridge_project")
        accept(town, "hotel_project")
        before = deepcopy(town.contracts)
        reset_day(town)
        before["revenue_today"] = 0
        self.assertEqual(town.contracts, before)
        self.assertEqual(town.contracts["cash_earned"], 450)

    def test_invalid_time_and_identifiers_do_not_mutate_the_ledger(self):
        town = FakeTown()
        accept(town, "bread_relief")
        before = deepcopy(town.contracts)
        for seconds in (0, -1, True, math.inf, math.nan, 1e308, "1", []):
            self.assertEqual(advance_contracts(town, seconds), ())
            self.assertEqual(town.contracts, before)
        for identifier in (None, "1", True, -1, []):
            self.assertFalse(abandon_contract(town, identifier))
            self.assertEqual(deliver_contract(town, identifier), 0)
            self.assertEqual(town.contracts, before)

    def test_legacy_and_malformed_state_cannot_create_money_or_free_active_claims(self):
        for value in (None, [], "state", {"version": True}, {"version": 99}):
            self.assertEqual(normalize_state(value), initial_state())
        town = FakeTown()
        record = accept(town, "bread_relief")
        saved = deepcopy(town.contracts)
        saved.update(reputation=True, elapsed=math.inf, history=[{}, {"id": True}],
                     upgrades=[{}, "unknown"], completed_projects=[[], "missing"])
        saved["active"] = [dict(record, key=[]), dict(record, delivered=record["required"]),
                           dict(record, deadline=math.nan), dict(record, id=True)]
        restored = normalize_state(saved)
        self.assertEqual((restored["active"], restored["reputation"], restored["elapsed"], restored["upgrades"]), ([], 0, 0, []))
        self.assertEqual((town.cash, town.bag_size, town.cash_calls), (60, 12, []))

    def test_restoring_expired_or_closed_records_never_replays_rewards(self):
        town = FakeTown()
        record = accept(town, "bread_relief")
        saved = deepcopy(town.contracts)
        saved["elapsed"] = record["deadline"]
        town.contracts = normalize_state(saved)
        self.assertEqual(len(advance_contracts(town, .01)), 1)
        town.contracts["active"].append(dict(record))
        town.contracts = normalize_state(town.contracts)
        self.assertEqual(town.contracts["active"], [])
        self.assertEqual((town.contracts["failed"], town.cash, town.cash_calls), (1, 60, []))

    def test_all_inventory_adapters_use_finished_products_in_the_correct_slot(self):
        town = FakeTown()
        town.goods = [1, 2, 3, 4]
        town.industry_goods["PASTELARIA"], town.tier2_goods = 5, 6
        for key, count in (("tools", 1), ("furniture", 2), ("pottery", 3),
                           ("bread", 4), ("pasteis", 5), ("precision_machinery", 6)):
            self.assertEqual(inventory_amount(town, key), count)
        self.assertEqual(inventory_amount(town, []), 0)


if __name__ == "__main__":
    unittest.main()
