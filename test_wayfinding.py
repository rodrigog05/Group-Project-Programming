import unittest
from types import SimpleNamespace

from tycoon import INDUSTRIES, SITES, TRADES
from wayfinding import MATERIALS, PRODUCTS, STAGES, site_guide


class WayfindingTest(unittest.TestCase):
    def test_material_and_product_labels_match_game_routes(self):
        self.assertEqual(MATERIALS, tuple(trade.supply for trade in TRADES))
        self.assertEqual(PRODUCTS, tuple(trade.product for trade in TRADES))

    def test_all_trade_sites_have_explicit_distinct_stages_and_items(self):
        for site in SITES:
            guide = site_guide(site)
            with self.subTest(site=site.name):
                self.assertTrue(guide.instruction)
                if site.role == "SUPPLIER":
                    self.assertEqual((guide.stage, guide.marker), ("buy", "1"))
                    self.assertIn(TRADES[site.trade].supply, guide.detail)
                elif site.role == "FACTORY":
                    self.assertEqual((guide.stage, guide.marker), ("make", "2"))
                    self.assertIn(TRADES[site.trade].supply, guide.detail)
                    self.assertIn(TRADES[site.trade].product, guide.detail)
                elif site.role == "PUBLIC SHOP":
                    self.assertEqual((guide.stage, guide.marker), ("sell", "3"))
                    self.assertIn(TRADES[site.trade].product, guide.detail)
                    self.assertIn("does not buy raw materials", guide.instruction)
        main = STAGES[:3]
        self.assertEqual(len({stage.color for stage in main}), 3)
        self.assertEqual(len({stage.marker for stage in main}), 3)

    def test_farms_explain_both_wheat_and_egg_purchase_controls(self):
        for site in SITES:
            if site.role == "SUPPLIER" and site.trade == 3:
                guide = site_guide(site)
                self.assertIn("Wheat + Eggs", guide.detail)
                self.assertIn("F", guide.instruction)
                self.assertIn("R", guide.instruction)

    def test_special_places_explain_same_place_collection_sale_or_payment(self):
        for role in ("PASTELARIA", "SHIPYARD", "TIER2"):
            guide = site_guide(SimpleNamespace(role=role, trade=-1))
            self.assertEqual((guide.stage, guide.marker), ("special", "2+3"))
            self.assertIn("here", guide.instruction)
            self.assertIn("collect", guide.instruction)
        for role, recipe in INDUSTRIES.items():
            guide = site_guide(SimpleNamespace(role=role, trade=-1))
            for ingredient, amount in recipe.ingredients:
                self.assertIn(ingredient, guide.detail)
                self.assertIn(f"{amount} {ingredient[:-1] if ingredient == 'Eggs' else ingredient}", guide.instruction)
            self.assertIn(str(recipe.seconds), guide.instruction)
        tier2 = site_guide(SimpleNamespace(role="TIER2", trade=-1))
        self.assertIn("1 Tools + 1 Furniture", tier2.instruction)
        self.assertIn("Precision Machinery", tier2.instruction)

    def test_residences_do_not_pretend_to_be_businesses(self):
        guide = site_guide(SimpleNamespace(role="RESIDENTIAL", trade=0))
        self.assertEqual(guide.stage, "residential")
        self.assertEqual(guide.marker, "")
        self.assertIn("no trading", guide.instruction)


if __name__ == "__main__":
    unittest.main()
