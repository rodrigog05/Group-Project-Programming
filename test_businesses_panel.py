"""Check property management explains stock, upgrades and specialization."""
import copy
from types import SimpleNamespace
import unittest

from businesses import initial_state
from businesses_panel import (factory_stock_text, management_text, properties,
                              property_text, property_values, shop_actions_allowed,
                              shop_text, upgrade_label)


def fixture():
    sites = (SimpleNamespace(name="Ironworks", role="FACTORY", trade=0),
             SimpleNamespace(name="Tool Market", role="PUBLIC SHOP", trade=0),
             SimpleNamespace(name="Pastéis de Belém", role="PASTELARIA", trade=-1),
             SimpleNamespace(name="Foundry Precision Works", role="TIER2", trade=-1))
    trades = tuple(SimpleNamespace(supply=raw, product=product, seconds=seconds) for raw, product, seconds in
                   (("Iron ore", "Tools", 5), ("Timber", "Furniture", 7),
                    ("Clay", "Pottery", 6), ("Wheat", "Bread", 4)))
    town = SimpleNamespace(cash=1000, businesses=initial_state(), elapsed=10,
        goods=[4, 0, 0, 0], prices=[18, 26, 22, 14], nearby=lambda: None,
        buyer_status=lambda site: "8 daily + 4 tourist buyers",
        logistics={"routes": [], "factories": {"Ironworks": {
            "trade": 0, "input": 0, "order": None, "output": 0, "produced": 0, "collected": 0}}})
    return town, sites, trades


def own(town, site, **updates):
    record = dict(role=site.role, trade=site.trade, storage_level=0, equipment_level=0,
                  manual_order=None, stock=0, sales_today=0, revenue_today=0,
                  total_sold=0, total_revenue=0, invested=600 if site.role == "FACTORY" else 450)
    record.update(updates)
    town.businesses["owned"][site.name] = record
    return record


class BusinessFormattingTest(unittest.TestCase):
    def test_property_directory_excludes_fixed_recipe_businesses(self):
        _, sites, _ = fixture()
        self.assertEqual([site.name for site in properties(sites)], ["Ironworks", "Tool Market"])

    def test_owned_property_uses_its_selected_product(self):
        town, sites, trades = fixture()
        self.assertEqual(property_values(town, sites[0], trades)[2:], ("Tools", "For sale", "$600"))
        own(town, sites[0], trade=3)
        self.assertEqual(property_values(town, sites[0], trades)[2:], ("Bread", "Owned", "Owned"))
        text = management_text(town, sites[0], trades)
        self.assertIn("Specialization: Bread · Raw material: Wheat", text)
        self.assertIn("4s per batch", text)

    def test_purchase_details_preserve_unowned_play_and_explain_npc_payment(self):
        town, sites, trades = fixture()
        text = property_text(town, sites[1], trades)
        for phrase in ("Purchase: $450", "Your cash: $1,000", "use unowned factories and shops as before",
                       "Deposited stock pays only when NPC buyers purchase it", "unlimited demand",
                       "university retain their own recipes"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_upgrade_labels_show_next_price_and_stop_at_maximum(self):
        town, sites, _ = fixture()
        record = own(town, sites[0], storage_level=2, equipment_level=1)
        self.assertEqual(upgrade_label(town, sites[0], "storage"), "Storage level 3 · $800")
        self.assertEqual(upgrade_label(town, sites[0], "equipment"), "Equipment level 2 · $500")
        record["storage_level"] = 3
        self.assertEqual(upgrade_label(town, sites[0], "storage"), "Storage fully upgraded")

    def test_factory_stats_distinguish_automatic_storage_from_manual_orders(self):
        town, sites, trades = fixture()
        own(town, sites[0], storage_level=1,
            manual_order=dict(quantity=2, ready_at=14.25, trade=0))
        town.logistics["factories"]["Ironworks"].update(input=8, output=5, produced=11, collected=6,
                                                      order=dict(quantity=6, remaining=2.2))
        text = factory_stock_text(town, sites[0], trades)
        for phrase in ("material buffer: 8/72 Iron ore", "6 Tools · 3s remaining", "output: 5/72 Tools",
                       "Produced automatically: 11", "Collected: 6", "carried materials: 2 Tools · 5s remaining",
                       "separate from your cargo"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_shop_controls_require_ownership_and_physical_visit(self):
        town, sites, _ = fixture()
        town.nearby = lambda: sites[1]
        self.assertFalse(shop_actions_allowed(town, sites[1]))
        own(town, sites[1])
        self.assertTrue(shop_actions_allowed(town, sites[1]))
        town.nearby = lambda: sites[0]
        self.assertFalse(shop_actions_allowed(town, sites[1]))
        self.assertFalse(shop_actions_allowed(town, sites[0]))
        self.assertFalse(shop_actions_allowed(town, None))

    def test_shop_quote_and_customer_limits_include_equipment_but_keep_real_buyers(self):
        town, sites, trades = fixture()
        own(town, sites[1], equipment_level=2, stock=5, storage_level=1,
            sales_today=3, revenue_today=60, total_sold=7, total_revenue=140)
        before = copy.deepcopy(town.businesses)
        text = management_text(town, sites[1], trades)
        for phrase in ("Stored products: 5/72 Tools", "selling quote: $20 each", "4 customers every 10 focused seconds",
                       "8 daily + 4 tourist buyers", "Revenue today: $60", "Total revenue: $140",
                       "Each equipment level adds 5%", "Depositing products earns no cash"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        counter = shop_text(town, sites[1], trades)
        for phrase in ("Your carried stock: 4", "Visit this shop entrance", "no immediate payment",
                       "Withdraw returns unsold stock", "same daily and tourist buyers"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, counter)
        self.assertEqual(town.businesses, before)

    def test_paused_assigned_route_still_blocks_factory_specialization(self):
        town, sites, trades = fixture()
        own(town, sites[0])
        town.logistics["routes"].append(dict(destination="Ironworks", enabled=False))
        text = management_text(town, sites[0], trades)
        self.assertIn("reassign all delivery routes", text)
        self.assertIn("no delivery route assigned", text)
        self.assertIn("Upgrades remain with the property", text)


if __name__ == "__main__":
    unittest.main()
