"""Bounded, validated JSON; dedicated storage key, separate from other editions."""

import json
import math
from dataclasses import asdict

from catalog import ROUTES
from economy import Order, Town
from world import walkable

KEY = "foundry-town.core.v1"
MAX_SIZE = 4096


def dump(town):
    return json.dumps(
        {"version": 1, "town": asdict(town)}, allow_nan=False, separators=(",", ":")
    )


def whole(value, maximum):
    return type(value) is int and 0 <= value <= maximum


def finite(value, limit):
    return type(value) in (float, int) and 0 <= value <= limit and math.isfinite(value)


def load(raw):
    if not isinstance(raw, str) or len(raw) > MAX_SIZE:
        raise ValueError("Invalid save size")
    try:
        data = json.loads(raw)
        if (
            type(data) is not dict
            or set(data) != {"version", "town"}
            or type(data["version"]) is not int
            or data["version"] != 1
        ):
            raise ValueError("Unknown save format")
        values = data["town"]
        if type(values) is not dict or set(values) != set(Town.__dataclass_fields__):
            raise ValueError("Invalid fields")
        t = Town(**values)
        if not whole(t.cash, 2**53 - 1) or type(t.upgraded) is not bool:
            raise ValueError("Invalid balance or upgrade")
        if not finite(t.x, 2400) or not finite(t.y, 1780) or not walkable(t.x, t.y):
            raise ValueError("Invalid position")
        for slots in (t.materials, t.goods, t.orders):
            if type(slots) is not list or len(slots) != len(ROUTES):
                raise ValueError("Invalid route count")
        if not all(whole(n, t.capacity) for n in t.materials + t.goods):
            raise ValueError("Invalid inventory")
        for i, order in enumerate(t.orders):
            if order is None:
                continue
            if type(order) is not dict or set(order) != {"quantity", "remaining"}:
                raise ValueError("Invalid order")
            if (
                not whole(order["quantity"], t.capacity)
                or not order["quantity"]
                or not finite(order["remaining"], ROUTES[i].seconds)
            ):
                raise ValueError("Invalid production")
            t.orders[i] = Order(**order)
        if t.carried + t.reserved > t.capacity:
            raise ValueError("Bag over capacity")
        return t
    except (TypeError, OverflowError, RecursionError) as exc:
        raise ValueError("Invalid save") from exc
