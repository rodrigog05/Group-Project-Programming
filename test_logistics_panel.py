"""Verify delivery menus explain compatible routes, costs and collection."""
import copy
from types import SimpleNamespace
import unittest

from logistics import initial_state
from logistics_panel import (collection_allowed, destination_options, factory_text,
                             factory_values, logistics_rules, operating_cost,
                             purchase_text, route_state, route_text, route_values,
                             supplier_options)


def fixture():
    sites = (
        SimpleNamespace(name="Goldenfield Farm", role="SUPPLIER", trade=3),
        SimpleNamespace(name="Sunrise Bakery", role="FACTORY", trade=3),
        SimpleNamespace(name="Pine Mill", role="SUPPLIER", trade=1),
        SimpleNamespace(name="Oak Workshop", role="FACTORY", trade=1),
        SimpleNamespace(name="Marvila Timber Depot", role="SUPPLIER", trade=1),
        SimpleNamespace(name="Pastéis de Belém", role="PASTELARIA", trade=-1),
    )
    trades = tuple(SimpleNamespace(supply=raw, product=product) for raw, product in
                   (("Iron ore", "Tools"), ("Timber", "Furniture"),
                    ("Clay", "Pottery"), ("Wheat", "Bread")))
    town = SimpleNamespace(cash=1000, costs=[5, 9, 6, 7], logistics=initial_state(sites),
                           nearby=lambda: None)
    return town, sites, trades


def delivery():
    return dict(id=7, kind="van", source="Goldenfield Farm", destination="Sunrise Bakery",
                trade=3, enabled=True, phase="outbound", elapsed=2.1, duration=10,
                load=6, retry=0, status="Delivering paid Wheat", delivered=12, trips=2,
                materials_spent=84, running_spent=2, tolls_spent=3)


class LogisticsFormattingTest(unittest.TestCase):
    def test_source_and_destination_filters_follow_the_material(self):
        _, sites, _ = fixture()
        self.assertEqual([site.name for site in supplier_options(sites)],
                         ["Goldenfield Farm", "Marvila Timber Depot", "Pine Mill"])
        self.assertEqual([site.name for site in destination_options(sites, sites[0])], ["Sunrise Bakery"])
        self.assertEqual([site.name for site in destination_options(sites, sites[2])], ["Oak Workshop"])
        self.assertEqual(destination_options(sites, None), ())

    def test_collection_requires_the_exact_nearby_factory(self):
        town, sites, _ = fixture()
        self.assertFalse(collection_allowed(town, "Sunrise Bakery"))
        town.nearby = lambda: sites[3]
        self.assertFalse(collection_allowed(town, "Sunrise Bakery"))
        town.nearby = lambda: sites[1]
        self.assertTrue(collection_allowed(town, "Sunrise Bakery"))
        town.nearby = lambda: SimpleNamespace(name="Sunrise Bakery", role="SHOP")
        self.assertFalse(collection_allowed(town, "Sunrise Bakery"))

    def test_pausing_a_paid_load_is_shown_as_finishing_not_cancelled(self):
        route = delivery()
        self.assertEqual(route_values(route)[-2:], (6, "8s"))
        route["enabled"] = False
        self.assertEqual(route_state(route), "Finishing load")
        route["phase"] = "returning"
        route["load"] = 0
        self.assertEqual(route_state(route), "Return / paused")
        route["phase"] = "idle"
        self.assertEqual(route_values(route)[-3:], ("Paused", 0, "—"))

    def test_route_details_separate_purchase_and_actual_operating_costs(self):
        _, _, trades = fixture()
        route = delivery()
        self.assertEqual(operating_cost(route), 89)
        text = route_text(route, trades)
        for phrase in ("Wheat → automated Bread", "Operating spend: $89", "Materials $84",
                       "Trip fees $2", "Bridge tolls $3", "Vehicle purchase: $320",
                       "Materials delivered: 12", "Completed deliveries: 2", "no refund"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_purchase_preview_uses_current_market_material_cost(self):
        town, sites, trades = fixture()
        before = copy.deepcopy(town.logistics)
        text = purchase_text(town, "van", sites[0], sites[1], trades)
        self.assertIn("Current Wheat cost: $7 each", text)
        self.assertIn("Full-load departure: $43", text)
        self.assertIn("before any bridge toll", text)
        self.assertIn("Cash after vehicle purchase: $680", text)
        self.assertIn("Affordable partial loads", text)
        self.assertIn("separate from the vehicle you drive", text)
        self.assertEqual(town.logistics, before)

    def test_factory_rows_distinguish_materials_production_and_finished_stock(self):
        town, sites, trades = fixture()
        stock = town.logistics["factories"]["Sunrise Bakery"]
        stock.update(input=8, order=dict(quantity=6, remaining=2.2), output=5,
                     produced=11, collected=6)
        self.assertEqual(factory_values(town, sites[1], trades),
                         ("Sunrise Bakery", "Bread", "8/48", "6 · 3s", "5/48", 6))
        text = factory_text(town, sites[1], trades)
        for phrase in ("Factory materials: 8/48 Wheat", "6 Bread · 3s remaining",
                       "Ready output: 5/48 Bread", "Produced in total: 11",
                       "Visit this factory entrance", "separate from your bag",
                       "never sells products automatically"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        town.nearby = lambda: sites[1]
        self.assertIn("You are at this factory", factory_text(town, sites[1], trades))

    def test_rules_explain_persistence_partial_loads_pause_and_manual_sale(self):
        text = logistics_rules()
        for phrase in ("up to 8", "Wheat to Sunrise Bakery", "Timber to Oak Workshop",
                       "$320 purchase, cargo 6", "$600 purchase, cargo 3",
                       "no charge when the vehicle cannot buy even one unit",
                       "48 spaces for delivered raw materials", "up to six products",
                       "Pause prevents future departures", "paid load already in flight",
                       "no vehicle refund", "sell collected products", "no offline delivery catch-up"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
