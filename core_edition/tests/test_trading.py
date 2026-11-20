import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))

from catalog import CASINO, CHIPS, FERRY_FARE, GARAGES, PIERS, ROUTES, VEHICLES, WAREHOUSE
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

class Transport(unittest.TestCase):
    def test_vehicles_match_the_desktop_garage(self):
        self.assertEqual([(v.label, v.price, v.trunk, v.road_speed) for v in VEHICLES],
                         [("Motorcycle", 120, 6, 520), ("Car", 240, 48, 690),
                          ("Delivery van", 360, 108, 620), ("F1 car", 480, 0, 900)])

    def test_buying_a_vehicle_adds_its_trunk_and_road_speed(self):
        t = Town(cash=300)
        visit(t, GARAGES[0])
        self.assertIn("Bought", t.buy_vehicle(1))
        self.assertEqual((t.cash, t.vehicle, t.capacity), (60, "car", 12 + 48))
        self.assertIn("already", t.buy_vehicle(1))
        t.x, t.y = 480, 301  # A paved road
        self.assertEqual(t.speed, 690)
        t.x, t.y = 1368, 560 - 30  # Off-road, between buildings
        self.assertEqual(t.speed, 510)

    def test_cannot_switch_to_a_smaller_trunk_or_buy_without_cash(self):
        t = Town(cash=1000, vehicle="van")
        t.materials[0] = 40
        self.assertIn("Unload", t.buy_vehicle(3))  # The F1 car has no trunk
        self.assertEqual((t.vehicle, t.cash), ("van", 1000))
        self.assertIn("more cash", Town(cash=100).buy_vehicle(0))

    def test_ferry_charges_the_fare_and_crosses_both_ways(self):
        t = Town()
        t.x, t.y = PIERS[0].x, PIERS[0].y
        t.goods[0] = 3
        self.assertEqual(t.take_ferry()[0], True)
        self.assertEqual((t.x, t.y, t.cash, t.goods[0]), (PIERS[1].x, PIERS[1].y, 60 - FERRY_FARE, 3))
        self.assertEqual(t.take_ferry()[0], True)
        self.assertEqual((t.x, t.y), (PIERS[0].x, PIERS[0].y))

    def test_failed_ferry_trips_cost_nothing(self):
        t = Town(cash=FERRY_FARE - 1)
        self.assertFalse(t.take_ferry()[0])  # Not at a pier
        t.x, t.y = PIERS[0].x, PIERS[0].y
        crossed, message = t.take_ferry()
        self.assertFalse(crossed)
        self.assertIn("ticket", message)
        self.assertEqual((t.cash, t.x), (FERRY_FARE - 1, PIERS[0].x))


class Screens(unittest.TestCase):
    """Draw every screen headlessly, so a drawing error fails here instead of in the browser."""

    def test_every_screen_draws_from_new_game_and_at_every_doorway(self):
        import os

        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        import pygame

        from controller import Session
        from storage import Storage
        from view import H, View, W

        pygame.display.init()
        pygame.font.init()
        view = View(pygame.display.set_mode((W, H)))
        g = Session(Storage())
        view.draw(g)  # Start menu
        g.key("n")
        view.draw(g)  # New game: the first street frame
        doors = [getattr(r, role) for r in ROUTES for role in ("supplier", "workshop", "market")]
        for place in doors + [WAREHOUSE, *GARAGES, *PIERS, CASINO]:
            with self.subTest(place=place.name):
                g.screen, g.keys = "street", set()
                visit(g.town, place)
                view.draw(g)
                g.key("e")  # Opens the shop, or starts the ferry at a pier
                view.draw(g)
                g.keys.clear()
                g.key("escape")
                g.keys.clear()
        g.key("p")
        view.draw(g)  # Route guide
        g.key("escape")
        visit(g.town, CASINO)
        g.keys.clear()
        g.key("e")
        g.keys.clear()
        g.key("g")
        for _ in range(30):  # Every frame of a spin, then the settled wheel
            g.tick(0.2)
            view.draw(g)


class Roulette(unittest.TestCase):
    def play(self, cash=100):
        from controller import Session
        from storage import Storage
        from test_saves import Backend

        g = Session(Storage(Backend()))
        g.key("n")
        g.town.cash = cash
        visit(g.town, CASINO)
        g.keys.clear()
        g.key("e")
        g.keys.clear()
        return g

    def test_red_pays_double_and_the_win_arrives_when_the_ball_lands(self):
        g = self.play()
        g.spin_wheel("red", 32)  # Default chip is $10
        self.assertEqual(g.town.cash, 90)
        g.spin_wheel("black", 26)  # No new bets while the wheel turns
        self.assertEqual(g.town.cash, 90)
        g.tick(0.25)
        self.assertEqual(g.town.cash, 90)
        for _ in range(20):
            g.tick(0.25)
        self.assertEqual((g.town.cash, g.history, g.spin), (110, [32], None))

    def test_losing_green_and_chip_choice(self):
        g = self.play()
        g.key("5")
        g.key("a")
        self.assertEqual(CHIPS[g.chip], 50)
        g.spin_wheel("green", 26)
        g.settle_spin()
        self.assertEqual(g.town.cash, 50)
        g.spin_wheel("green", 0)
        g.settle_spin()
        self.assertEqual(g.town.cash, 50 + 50 * 35)

    def test_cannot_bet_more_than_your_cash(self):
        g = self.play(cash=4)
        g.key("g")
        self.assertEqual((g.town.cash, g.spin), (4, None))
        self.assertIn("need", g.message)

    def test_leaving_or_saving_mid_spin_keeps_the_win(self):
        g = self.play()
        g.spin_wheel("black", 26)
        g.save()
        self.assertEqual(g.storage.restore().cash, 110)
        g.key("escape")
        self.assertEqual((g.screen, g.town.cash), ("street", 110))

