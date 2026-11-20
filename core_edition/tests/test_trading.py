import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))

from catalog import ROUTES, WAREHOUSE
from economy import Town


def visit(town, shop):
    town.x, town.y = shop.x, shop.y + 16


class Trades(unittest.TestCase):
    def test_every_chain_with_real_doorsteps_and_prices(self):
        for i, r in enumerate(ROUTES):
            with self.subTest(product=r.product):
                t = Town()
                visit(t, r.supplier)
                t.trade(True)
                self.assertEqual(t.cash, 60 - 4 * r.cost)
                visit(t, r.workshop)
                t.trade()
                self.assertEqual((t.materials[i], t.reserved), (0, 4))
                t.advance(r.seconds - 0.25)
                t.trade()
                self.assertEqual(t.goods[i], 0)
                t.advance(0.25)
                t.trade()
                t.trade()
                self.assertEqual((t.goods[i], t.reserved), (4, 0))
                visit(t, r.market)
                t.trade()
                t.trade()
                self.assertEqual((t.cash, t.goods[i]), (60 + 4 * (r.price - r.cost), 0))

    def test_capacity_includes_work_in_progress(self):
        t = Town(cash=400)
        for _ in range(3):
            t.trade(True)
        visit(t, ROUTES[3].workshop)
        t.trade()
        visit(t, ROUTES[0].supplier)
        cash = t.cash
        t.trade()
        self.assertEqual((t.cash, t.reserved, t.carried), (cash, 12, 0))

    def test_remote_trade_and_wrong_market_do_nothing(self):
        t = Town(x=300, y=700, goods=[0, 0, 0, 2])
        t.trade()
        visit(t, ROUTES[0].market)
        t.trade()
        self.assertEqual((t.cash, t.goods), (60, [0, 0, 0, 2]))

    def test_bulk_respects_available_cash(self):
        t = Town(cash=9)
        t.trade(True)
        t.trade()
        self.assertEqual((t.cash, t.materials[3]), (1, 2))

    def test_upgrade_is_affordable_only_once(self):
        t = Town()
        visit(t, WAREHOUSE)
        t.trade()
        self.assertEqual((t.cash, t.capacity), (60, 12))
        t.cash = 150
        t.trade()
        t.trade()
        self.assertEqual((t.cash, t.capacity), (50, 24))
