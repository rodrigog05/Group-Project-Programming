import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))

from controller import Session
from economy import Order, Town
from storage import Storage

from saves import dump, load


class Backend:
    def __init__(self, data=None):
        self.data = data

    def getItem(self, key):
        return self.data

    def setItem(self, key, value):
        self.data = value


class Saves(unittest.TestCase):
    def test_start_menu_never_saves_or_advances_until_play_begins(self):
        backend = Backend(dump(Town(cash=93, orders=[Order(1, 4), None, None, None])))
        original = backend.data
        game = Session(Storage(backend))
        game.key("r")
        self.assertEqual(game.screen, "rules")
        for _ in range(40):
            game.tick(0.25)
        game.save()
        self.assertEqual(backend.data, original)
        self.assertEqual(game.town.orders[0].remaining, 4)
        game.key("escape")
        game.keys.clear()
        game.key("n")
        self.assertEqual(game.screen, "confirm_new")
        game.save()
        self.assertEqual(backend.data, original)
        game.key("escape")
        game.key("c")
        self.assertEqual((game.screen, game.town.cash), ("street", 93))

    def test_new_game_requires_confirmation_only_when_save_exists(self):
        backend = Backend()
        game = Session(Storage(backend))
        game.key("c")
        self.assertIsNone(backend.data)
        self.assertEqual(game.screen, "menu")
        game.key("n")
        self.assertEqual(load(backend.data), Town())
        backend.data = dump(Town(cash=93))
        game = Session(Storage(backend))
        game.key("n")
        self.assertEqual(load(backend.data).cash, 93)
        game.key("y")
        self.assertEqual((game.screen, load(backend.data)), ("street", Town()))

    def test_roundtrip_preserves_partial_order_and_no_offline_production(self):
        t = Town(cash=53, orders=[None, Order(1, 3.25), None, None], upgraded=True)
        self.assertEqual(load(dump(t)), t)

    def test_reject_invalid_balances_positions_inventory_and_orders(self):
        for changes in (
            {"cash": True},
            {"cash": -1},
            {"cash": 3.3},
            {"x": float("nan")},
            {"x": 1e300},
            {"x": 500, "y": 800},
            {"upgraded": "yes"},
            {"materials": [0]},
            {"goods": [13, 0, 0, 0]},
            {"orders": [{"quantity": 1, "remaining": -1}, None, None, None]},
            {
                "orders": [{"quantity": 12, "remaining": 4}, None, None, None],
                "goods": [1, 0, 0, 0],
            },
            {"unrecognized": 0},
        ):
            d = json.loads(dump(Town()))
            d["town"].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                load(json.dumps(d))

    def test_version_1_saves_load_on_foot_and_vehicles_round_trip(self):
        old = json.loads(dump(Town(cash=93)))
        old["version"] = 1
        del old["town"]["vehicle"]
        town = load(json.dumps(old))
        self.assertEqual((town.cash, town.vehicle), (93, None))
        self.assertEqual(load(dump(Town(vehicle="van"))).vehicle, "van")

    def test_reject_unknown_vehicles_and_walkers_saved_on_a_bridge(self):
        with self.assertRaises(ValueError):
            load(dump(Town(vehicle="rocket")))
        with self.assertRaises(ValueError):
            load(dump(Town(x=300, y=900)))
        self.assertEqual(load(dump(Town(x=300, y=900, vehicle="car"))).y, 900)

    def test_corrupt_or_unknown_save_is_preserved(self):
        for raw in ("[]", "{", " " * 5000, '{"version":2,"town":{}}'):
            backend = Backend(raw)
            s = Storage(backend)
            t = s.restore()
            s.write(t)
            self.assertTrue(s.blocked)
            self.assertEqual(backend.data, raw)

    def test_clean_storage_initializes_and_quota_failure_leaves_game_playable(self):
        backend = Backend()
        s = Storage(backend)
        t = s.restore()
        t.trade()
        s.write(t)
        self.assertEqual(load(backend.data).cash, 56)

        def fail(*_):
            raise OSError("quota")

        backend.setItem = fail
        t.trade()
        s.write(t)
        self.assertEqual(t.cash, 52)
        self.assertIn("Could not save", s.notice)
