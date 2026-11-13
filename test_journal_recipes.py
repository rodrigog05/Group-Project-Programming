import json
import unittest

from journal_recipes import RECIPES, infer_discoveries, recipe_key_for_site
from innovation import TIER3_RECIPES, initial_state
from tycoon import INDUSTRIES, SITES, TRADES, Order, Town, pack_save, unpack_save


class JournalRecipeTest(unittest.TestCase):
    def approach(self, town, role, trade=-1):
        site = next(site for site in SITES if site.role == role and (trade < 0 or site.trade == trade))
        town.x, town.y = site.door[0], site.door[1]+18
        return site

    def test_catalog_matches_real_inputs_outputs_and_production_times(self):
        self.assertEqual(len(RECIPES), 10)
        self.assertEqual(len({recipe.key for recipe in RECIPES}), 10)
        for recipe in RECIPES:
            with self.subTest(recipe=recipe.key):
                if recipe.role == "FACTORY":
                    trade = TRADES[recipe.trade]
                    self.assertEqual(recipe.ingredients, ((trade.supply, 1),))
                    self.assertEqual((recipe.product, recipe.seconds), (trade.product, trade.seconds))
                elif recipe.role in INDUSTRIES:
                    industry = INDUSTRIES[recipe.role]
                    self.assertEqual((recipe.ingredients, recipe.seconds, recipe.service),
                                     (industry.ingredients, industry.seconds, industry.service))
                if recipe.role == "RESEARCH":
                    model = next(item for item in TIER3_RECIPES if item.key == recipe.key)
                    self.assertEqual(recipe.ingredients, tuple((item.label, item.quantity) for item in model.ingredients))
                    self.assertEqual((recipe.seconds, recipe.product, recipe.research_level),
                                     (model.seconds, model.product, model.level))
                else:
                    self.assertTrue(any(recipe_key_for_site(site) == recipe.key for site in SITES))

    def test_interacting_at_production_place_records_recipe_once_even_before_buying_materials(self):
        town = Town()
        self.approach(town, "PASTELARIA")
        town.interact()
        self.assertEqual(town.discovered_recipes, ["pasteis"])
        self.assertIn("Recipe recorded", town.notice)
        self.assertIsNone(town.industry_orders["PASTELARIA"])
        town.interact()
        self.assertEqual(town.discovered_recipes, ["pasteis"])

    def test_supplier_and_services_do_not_discover_recipes(self):
        town = Town()
        for role in ("SUPPLIER", "GARAGE", "WAREHOUSE", "CASINO"):
            self.approach(town, role)
            town.interact()
        self.assertEqual(town.discovered_recipes, [])

    def test_discovery_does_not_change_crafting_inputs_or_cargo(self):
        town = Town()
        self.approach(town, "FACTORY", 3)
        town.supplies[3] = 3
        town.interact()
        self.assertIn("bread", town.discovered_recipes)
        self.assertEqual((town.supplies[3], town.orders[3].quantity), (0, 3))
        town.elapsed = 4
        town.interact()
        self.assertEqual(town.goods[3], 3)

    def test_discoveries_save_and_reload_without_duplication_or_daily_reset(self):
        town = Town()
        town.discover_recipe("pasteis")
        town.discover_recipe("tools")
        for _ in range(3):
            town, _ = unpack_save(json.loads(json.dumps(pack_save(town, 1000))))
            self.assertEqual(town.discovered_recipes, ["pasteis", "tools"])
        town.sync_market(300)
        self.assertEqual(town.discovered_recipes, ["pasteis", "tools"])

    def test_legacy_save_recovers_proven_recipes_without_changing_progress(self):
        town = Town()
        town.cash = 234
        town.orders[1] = Order(3, 50)
        town.total_sold[2] = 7
        town.tier2_goods = 2
        town.industry_total_sold["PASTELARIA"] = 4
        saved = pack_save(town, 1000)
        saved["state"].pop("discovered_recipes")
        restored, _ = unpack_save(saved)
        self.assertEqual(set(restored.discovered_recipes), {"furniture", "pottery", "precision_machinery", "pasteis"})
        self.assertEqual((restored.cash, restored.orders[1].quantity, restored.tier2_goods), (234, 3, 2))
        self.assertEqual(infer_discoveries(vars(Town())), [])

    def test_invalid_discovery_data_is_rejected(self):
        for invalid in ("pasteis", [True], ["unknown_recipe"]):
            saved = pack_save(Town(), 1000)
            saved["state"]["discovered_recipes"] = invalid
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                unpack_save(saved)

    def test_visiting_university_does_not_reveal_locked_recipes(self):
        town = Town()
        campus = self.approach(town, "RESEARCH")
        self.assertIsNone(recipe_key_for_site(campus))
        town.interact()
        self.assertEqual(town.discovered_recipes, [])

    def test_research_discovery_inference_records_only_completed_unlocks_or_proven_goods(self):
        state = {"innovation": initial_state()}
        state["innovation"]["levels"]["metallurgy"] = 2
        state["innovation"]["project"] = {"branch": "metallurgy", "level": 3, "remaining": 40}
        self.assertEqual(infer_discoveries(state), ["alloy_components", "precision_turbines"])
        state["innovation"]["levels"]["metallurgy"] = 0
        state["innovation"]["goods"]["tram_assemblies"] = 1
        self.assertEqual(infer_discoveries(state), ["tram_assemblies"])

    def test_tier3_discoveries_survive_save_roundtrip(self):
        town = Town()
        town.discover_recipe("alloy_components")
        restored, _ = unpack_save(json.loads(json.dumps(pack_save(town, 1000))))
        self.assertEqual(restored.discovered_recipes, ["alloy_components"])


if __name__ == "__main__":
    unittest.main()
