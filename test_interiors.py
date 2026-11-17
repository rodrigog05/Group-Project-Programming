import unittest

import businesses
from interiors import INTERIOR_ROLES, actions_for, vendor_greeting
from tycoon import SITES, TRADES, Town


class InteriorTest(unittest.TestCase):
    def test_every_trading_building_has_an_interior_but_services_keep_their_own_screens(self):
        self.assertEqual(set(INTERIOR_ROLES), {"SUPPLIER", "FACTORY", "PUBLIC SHOP", "PASTELARIA", "SHIPYARD", "TIER2"})
        for role in ("GARAGE", "WAREHOUSE", "EXCHANGE", "RESEARCH", "CASINO"):
            self.assertNotIn(role, INTERIOR_ROLES)

    def test_vendors_quote_live_prices(self):
        town = Town()
        town.costs[0] = 9
        town.prices[1] = 31
        mine = next(site for site in SITES if site.role == "SUPPLIER" and site.trade == 0)
        market = next(site for site in SITES if site.role == "PUBLIC SHOP" and site.trade == 1)
        self.assertIn("Iron ore for $9 each", vendor_greeting(town, mine))
        self.assertIn(f"I buy your {TRADES[1].product} for $31 each", vendor_greeting(town, market))

    def test_every_interior_building_greets_and_offers_actions(self):
        town = Town()
        for site in SITES:
            if site.role not in INTERIOR_ROLES:
                continue
            with self.subTest(site=site.name):
                self.assertTrue(vendor_greeting(town, site))
                keys = [key for _, key in actions_for(town, site)]
                self.assertIn("e", keys)
                if site.role == "SUPPLIER":
                    self.assertIn("q", keys)
                    self.assertEqual("f" in keys, site.trade == 3)

    def test_owned_shop_vendor_welcomes_the_owner(self):
        town = Town()
        shop = next(site for site in SITES if site.role == "PUBLIC SHOP")
        town.cash = 10000
        self.assertTrue(businesses.purchase_business(town, shop.name, SITES))
        self.assertIn("boss", vendor_greeting(town, shop))
        self.assertEqual(actions_for(town, shop), [("Stock shop  ·  E", "e")])


if __name__ == "__main__":
    unittest.main()
