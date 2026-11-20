import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))

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
