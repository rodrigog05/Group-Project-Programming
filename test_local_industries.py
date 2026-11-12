from collections import deque
import json
import math
import unittest
from unittest.mock import patch

from tycoon import DAY_SECONDS, EGG_COST, INDUSTRIES, MAP_BOTTOM, MAP_TOP, REACH, SITES, WIDTH, Town, pack_save, unpack_save


class LocalIndustryTest(unittest.TestCase):
    def approach(self, town, role):
        site = next(site for site in SITES if site.role == role)
        town.x, town.y = site.door[0], site.door[1]+10

    def farm(self, town):
        site = next(site for site in SITES if site.role == "SUPPLIER" and site.trade == 3)
        town.x, town.y = site.door[0], site.door[1]+10

    def test_eggs_purchase_tracks_cost_and_respects_cash_and_capacity(self):
        town = Town()
        self.farm(town)
        town.buy_eggs(bulk=True)
        self.assertEqual((town.eggs, town.cash, town.egg_expenses_today), (4, 60-4*EGG_COST, 4*EGG_COST))
        town.supplies[0] = 8
        town.buy_eggs()
        self.assertEqual(town.eggs, 4)
        town.supplies[0] = 0
        town.cash = 1
        town.buy_eggs()
        self.assertEqual((town.eggs, town.cash), (4, 1))

    def test_pasteis_use_raw_wheat_and_eggs_then_collect_and_sell(self):
        town = Town()
        self.approach(town, "PASTELARIA")
        town.supplies[3], town.eggs = 2, 2
        town.interact()
        self.assertEqual((town.supplies[3], town.eggs, town.reserved), (0, 0, 2))
        town.interact()
        self.assertEqual(town.industry_goods["PASTELARIA"], 0)
        town.elapsed = 8
        town.interact()
        self.assertEqual((town.cargo, town.reserved), (2, 0))
        town.interact()
        self.assertEqual((town.cash, town.cargo), (108, 0))
        self.assertEqual(town.industry_revenue_today["PASTELARIA"], 48)
        self.assertEqual(town.industry_total_sold["PASTELARIA"], 2)

    def test_missing_ingredient_does_not_consume_wheat_or_cooked_bread(self):
        town = Town()
        self.approach(town, "PASTELARIA")
        town.supplies[3], town.goods[3] = 1, 3
        town.interact()
        self.assertIsNone(town.industry_orders["PASTELARIA"])
        self.assertEqual((town.supplies[3], town.goods[3]), (1, 3))

    def test_pastry_orders_reserve_bag_space_while_baking(self):
        town = Town()
        self.approach(town, "PASTELARIA")
        town.supplies[3], town.eggs = 6, 6
        town.interact()
        town.supplies[0] = 6
        self.farm(town)
        town.buy_eggs()
        self.assertEqual(town.eggs, 0)
        self.approach(town, "PASTELARIA")
        town.elapsed = 8
        town.interact()
        self.assertEqual(town.cargo, town.bag_size)

    def test_shipyard_consumes_materials_reserves_contract_and_honors_quote(self):
        town = Town()
        self.approach(town, "SHIPYARD")
        town.supplies[0:2] = [2, 2]
        town.interact()
        self.assertEqual(town.supplies[0:2], [0, 0])
        self.assertEqual((town.reserved, town.cargo), (0, 0))
        self.assertEqual(town.industry_demand["SHIPYARD"], 2)
        town.industry_prices["SHIPYARD"] = 200
        town.interact()
        self.assertEqual(town.cash, 60)
        town.elapsed = 20
        town.interact()
        self.assertEqual((town.cash, town.industry_revenue_today["SHIPYARD"]), (160, 100))
        self.assertEqual(town.industry_total_sold["SHIPYARD"], 1)
        self.assertIsNone(town.industry_orders["SHIPYARD"])
        self.assertEqual(town.cargo, 0)

    def test_shipyard_rejects_jobs_without_demand_or_complete_raw_materials(self):
        town = Town()
        self.approach(town, "SHIPYARD")
        town.supplies[0:2] = [1, 2]
        town.goods[0] = 2
        town.interact()
        self.assertIsNone(town.industry_orders["SHIPYARD"])
        self.assertEqual(town.supplies[0:2], [1, 2])
        town.supplies[0] = 2
        town.industry_demand["SHIPYARD"] = 0
        town.interact()
        self.assertEqual(town.supplies[0:2], [2, 2])

    def test_industry_orders_and_quotes_survive_json_save_round_trip(self):
        town = Town()
        self.approach(town, "PASTELARIA")
        town.supplies[3], town.eggs = 1, 2
        town.interact()
        self.approach(town, "SHIPYARD")
        town.supplies[0:2] = [2, 2]
        town.interact()
        restored, _ = unpack_save(json.loads(json.dumps(pack_save(town, 1000))))
        self.assertEqual(restored.eggs, 1)
        self.assertEqual(restored.industry_orders["PASTELARIA"].quantity, 1)
        self.assertEqual(restored.industry_orders["SHIPYARD"].ready_at, 20)
        self.assertEqual(restored.shipyard_quote, 100)

    def test_legacy_saves_get_industry_defaults_without_losing_progress(self):
        town = Town()
        town.cash = 234
        saved = pack_save(town, 1000)
        for name in tuple(saved["state"]):
            if name.startswith("industry_") or name in ("eggs", "egg_expenses_today", "shipyard_quote"):
                saved["state"].pop(name)
        restored, _ = unpack_save(saved)
        self.assertEqual(restored.cash, 234)
        self.assertEqual(restored.eggs, 0)
        self.assertEqual(restored.industry_prices["PASTELARIA"], 24)

    def test_new_day_refreshes_market_and_analytics_but_keeps_booked_quote(self):
        town = Town()
        town.industry_goods["PASTELARIA"] = 24
        town.industry_revenue_today["PASTELARIA"] = 48
        town.egg_expenses_today = 4
        town.shipyard_quote = 100
        with patch("tycoon.random.random", return_value=.9), patch("tycoon.random.uniform", return_value=1):
            town.sync_market(DAY_SECONDS)
        self.assertLess(town.industry_prices["PASTELARIA"], INDUSTRIES["PASTELARIA"].price)
        self.assertEqual(town.industry_demand["SHIPYARD"], 3)
        self.assertEqual(town.egg_expenses_today, 0)
        self.assertEqual(town.industry_revenue_today["PASTELARIA"], 0)
        self.assertEqual(town.shipyard_quote, 100)

    def test_all_businesses_connect_to_starting_area_across_bridges(self):
        town = Town()
        visited = {(480, 321)}
        queue = deque(visited)
        while queue:
            x, y = queue.popleft()
            for dx, dy in ((8, 0), (-8, 0), (0, 8), (0, -8)):
                point = nx, ny = x+dx, y+dy
                if point in visited or not (17 <= nx <= WIDTH-17 and MAP_TOP+15 <= ny <= MAP_BOTTOM-15):
                    continue
                if town.can_walk(nx, ny):
                    visited.add(point)
                    queue.append(point)
        for site in SITES:
            self.assertTrue(any(math.hypot(x-site.door[0], y-site.door[1]) <= REACH for x, y in visited), site.name)


if __name__ == "__main__":
    unittest.main()
