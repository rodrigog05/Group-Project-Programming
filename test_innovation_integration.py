"""Research wired to real inventory, accounts, saves and the cash milestone."""
import json
import unittest

import innovation
from places_menu import directory_entries
from tycoon import DAY_SECONDS, SITES, Town, pack_save, unpack_save


class InnovationIntegrationTest(unittest.TestCase):
    def roundtrip(self, town):
        return unpack_save(json.loads(json.dumps(pack_save(town, 1000))))[0]

    def unlock(self, town, branch, levels):
        for _ in range(levels):
            node = innovation.next_research(town, branch)
            self.assertTrue(town.start_research(branch))
            town.advance_research(node.seconds)

    def test_carcavelos_campus_and_relocated_farm_have_safe_distinct_entrances(self):
        town = Town()
        campus = next(site for site in SITES if site.role == "RESEARCH")
        farm = next(site for site in SITES if site.name == "Goldenfield Farm")
        self.assertLess(campus.x, 238)
        self.assertEqual((farm.x, farm.y), (1280, 530))
        for site in (campus, farm):
            self.assertTrue(town.can_walk(site.door[0], site.door[1]+18))
        entry = next(entry for entry in directory_entries(SITES)["services"] if entry.name == campus.name)
        self.assertEqual(entry.neighborhood, "Carcavelos")
        town.x, town.y = entry.destination
        town.interact()
        self.assertIn("Nova SBE", town.message)
        self.assertEqual(town.discovered_recipes, [])

    def test_existing_save_gets_empty_research_without_losing_player_progress(self):
        town = Town()
        town.cash, town.goods[0], town.vehicle = 312, 4, "van"
        town.discover_recipe("pasteis")
        saved = pack_save(town, 1000)
        saved["state"].pop("innovation")
        saved["state"].pop("milestone_acknowledged")
        restored, _ = unpack_save(saved)
        self.assertEqual((restored.cash, restored.goods[0], restored.vehicle), (312, 4, "van"))
        self.assertEqual(restored.discovered_recipes, ["pasteis"])
        self.assertEqual(restored.innovation, innovation.initial_state())
        self.assertFalse(restored.milestone_acknowledged)

    def test_paid_project_restores_exact_time_without_charging_or_offline_progress(self):
        town = Town()
        town.cash = 600
        self.assertTrue(town.start_research("metallurgy"))
        town.advance_research(23.25)
        restored = self.roundtrip(town)
        self.assertEqual((restored.cash, restored.daily_expenses), (250, 350))
        self.assertEqual(restored.innovation["project"]["remaining"], 36.75)
        restored.sync_market(100*DAY_SECONDS)
        self.assertEqual(restored.innovation["project"]["remaining"], 36.75)
        restored.advance_research(36.75)
        self.assertEqual(restored.innovation["levels"]["metallurgy"], 1)
        self.assertIn("alloy_components", restored.discovered_recipes)
        self.assertEqual(restored.innovation["research_spent"], 350)

    def test_green_energy_changes_actual_tax_and_settlement_remains_idempotent(self):
        town = Town()
        town.cash = 10000
        self.unlock(town, "green_energy", 3)
        self.assertEqual((town.daily_expenses, innovation.tax_rate(town)), (1550, 10))
        town.sync_market(DAY_SECONDS)
        self.assertEqual(town.last_day_summary["tax"], 0)
        town.add_cash(1000)
        town.settle_day(2)
        self.assertEqual((town.last_day_summary["profit"], town.last_day_summary["tax_rate"],
                          town.last_day_summary["tax"]), (1000, 10, 100))
        restored = self.roundtrip(town)
        cash = restored.cash
        restored.settle_day(2)
        self.assertEqual((restored.cash, restored.taxes_paid_total), (cash, 100))

    def test_full_tier_three_chain_consumes_real_goods_and_records_revenue_once(self):
        town = Town()
        town.cash, town.vehicle = 10000, "van"
        self.unlock(town, "metallurgy", 3)
        self.assertTrue(all(key in town.discovered_recipes for key in innovation.RECIPE_BY_KEY))
        town.sync_market(DAY_SECONDS)
        town.supplies[0], town.goods[0], town.tier2_goods = 8, 6, 2
        for key, quantity in (("alloy_components", 4), ("precision_turbines", 2), ("tram_assemblies", 1)):
            self.assertTrue(town.start_fabrication(key, quantity))
            self.assertGreaterEqual(town.reserved, quantity)
            town.advance_research(innovation.RECIPE_BY_KEY[key].seconds)
            self.assertEqual(town.collect_research_products(key), quantity)
        self.assertEqual((town.supplies[0], town.goods[0], town.tier2_goods), (0, 0, 0))
        self.assertEqual((town.cargo, town.reserved), (1, 0))
        before = town.cash
        quote = town.innovation["prices"]["tram_assemblies"]
        self.assertEqual(town.sell_research_products("tram_assemblies"), 1)
        self.assertEqual((town.cash-before, town.daily_revenue, town.other_income_today), (quote, quote, 0))
        self.assertEqual(town.innovation["total_sold"]["tram_assemblies"], 1)
        self.assertEqual(town.cargo, 0)

    def test_lab_reservations_block_raw_purchases_then_transfer_to_carried_goods(self):
        town = Town()
        town.cash = 1000
        self.unlock(town, "metallurgy", 1)
        town.supplies[0], town.goods[0] = 6, 3
        self.assertTrue(town.start_fabrication("alloy_components", 3))
        town.supplies[3] = 9
        farm = next(site for site in SITES if site.name == "Goldenfield Farm")
        town.x, town.y = farm.door[0], farm.door[1]+18
        town.interact()
        self.assertEqual((town.supplies[3], town.cargo, town.reserved), (9, 9, 3))
        town.advance_research(14)
        self.assertEqual(town.collect_research_products("alloy_components"), 3)
        self.assertEqual((town.cargo, town.reserved), (12, 0))
        restored = self.roundtrip(town)
        self.assertEqual((restored.cargo, restored.reserved), (12, 0))

    def test_cash_milestone_can_continue_and_does_not_repeat_after_spending_or_reload(self):
        town = Town()
        self.assertFalse(town.continue_after_milestone())
        town.add_cash(500-town.cash)
        self.assertTrue(town.won)
        self.assertTrue(town.continue_after_milestone())
        self.assertTrue(town.start_research("green_energy"))
        restored = self.roundtrip(town)
        self.assertEqual(restored.cash, 300)
        self.assertTrue(restored.won)
        self.assertTrue(restored.milestone_acknowledged)
        restored.advance_research(45)
        self.assertEqual(innovation.tax_rate(restored), 18)


if __name__ == "__main__":
    unittest.main()
