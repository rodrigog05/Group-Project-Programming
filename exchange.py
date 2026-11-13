"""Fictional Lisbon shares, funded by recorded active-game city activity.

The ledger deliberately knows nothing about wall-clock time or visual NPCs.
Call ``advance_city`` with focused game time, record completed player sales and
paid transport trips, then call ``settle_exchange`` before the day's tax bill.
All money is whole game dollars except pending dividends, which are cents.
"""
from copy import deepcopy
from dataclasses import dataclass
import math


CITY_TICK_SECONDS = 10
BID_PERCENT = 90
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Asset:
    symbol: str
    name: str
    kind: str
    description: str
    base_price: int
    city_units: int
    dividend_cents: int = 1
    cap: int = 100


ASSETS = (
    Asset("BELEM", "Belém Gastronomia", "District",
          "A stake in Belém's competing food and souvenir businesses.", 45, 6),
    Asset("BAIXA", "Baixa-Chiado Comércio", "District",
          "A stake in competing central Lisbon shops and waterfront trade.", 60, 8),
    Asset("ALFAMA", "Alfama Artesãos", "District",
          "A stake in competing Alfama craftspeople and local markets.", 35, 4),
    Asset("ORIENTE", "Oriente Indústria", "District",
          "A stake in competing Marvila, Oriente and Parque das Nações trade.", 55, 7),
    Asset("ALMADA", "Almada Estaleiros", "District",
          "A stake in competing south-bank workshops, shipyards and shops.", 40, 5),
    Asset("BRIDGE25", "Ponte 25 de Abril", "Infrastructure",
          "Dividends follow simulated toll traffic and paid returns to Lisbon.", 75, 8),
    Asset("TRAM", "Rede de Elétricos", "Infrastructure",
          "Dividends follow simulated passenger trips and paid player journeys.", 50, 6),
)
ASSET_BY_SYMBOL = {asset.symbol: asset for asset in ASSETS}


def _zeros():
    return {asset.symbol: 0 for asset in ASSETS}


def _statement():
    return {"day": 0, "paid": 0, "by_asset": _zeros(), "activity": _zeros(),
            "player_activity": _zeros(), "city_activity": _zeros()}


def initial_state():
    """Return an independent, JSON-serializable portfolio with no past income."""
    return {
        "version": SCHEMA_VERSION,
        "holdings": _zeros(),
        "cost_basis": _zeros(),
        "quotes": {asset.symbol: asset.base_price for asset in ASSETS},
        "pending_cents": _zeros(),
        "total_dividends": _zeros(),
        "activity_today": {asset.symbol: {"city": 0, "player": 0} for asset in ASSETS},
        "activity_remainder": 0.0,
        "last_settlement": 0,
        "last_statement": _statement(),
    }


def _whole(value, default=0):
    return value if type(value) is int and value >= 0 else default


def _finite_number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _quote_bounds(asset):
    return ((asset.base_price * 75 + 50) // 100,
            (asset.base_price * 125 + 50) // 100)


def normalize_state(value):
    """Sanitize a saved ledger; absent or unsupported data starts without income.

    Missing fields never infer dividends from time, stock ownership or activity.
    Unknown symbols are discarded and each holding is capped. A missing basis
    for an existing holding uses its original quote, rather than inventing a
    zero-cost holding. The input object is never modified.
    """
    result = initial_state()
    if not isinstance(value, dict):
        return result
    version = value.get("version", SCHEMA_VERSION)
    if type(version) is not int or version != SCHEMA_VERSION:
        return result

    def mapping(key):
        item = value.get(key)
        return item if isinstance(item, dict) else {}

    holdings, basis, quotes = mapping("holdings"), mapping("cost_basis"), mapping("quotes")
    pending, dividends, activity = mapping("pending_cents"), mapping("total_dividends"), mapping("activity_today")
    for asset in ASSETS:
        symbol = asset.symbol
        owned = min(asset.cap, _whole(holdings.get(symbol)))
        result["holdings"][symbol] = owned
        result["cost_basis"][symbol] = _whole(basis.get(symbol), owned * asset.base_price) if owned else 0
        low, high = _quote_bounds(asset)
        result["quotes"][symbol] = min(high, max(low, _whole(quotes.get(symbol), asset.base_price)))
        result["pending_cents"][symbol] = _whole(pending.get(symbol))
        result["total_dividends"][symbol] = _whole(dividends.get(symbol))
        counts = activity.get(symbol)
        if isinstance(counts, dict):
            result["activity_today"][symbol] = {
                "city": _whole(counts.get("city")), "player": _whole(counts.get("player")),
            }

    remainder = value.get("activity_remainder", 0)
    if _finite_number(remainder) and 0 <= remainder < CITY_TICK_SECONDS:
        result["activity_remainder"] = float(remainder)
    result["last_settlement"] = _whole(value.get("last_settlement"))
    saved_statement = mapping("last_statement")
    statement = result["last_statement"]
    statement["day"] = min(result["last_settlement"], _whole(saved_statement.get("day")))
    for field in ("by_asset", "activity", "player_activity", "city_activity"):
        values = saved_statement.get(field)
        if isinstance(values, dict):
            statement[field] = {asset.symbol: _whole(values.get(asset.symbol)) for asset in ASSETS}
    statement["paid"] = sum(statement["by_asset"].values())
    return result


def _state(town):
    """Fast path for the normalized ledger installed when a save is loaded."""
    state = getattr(town, "exchange", None)
    if (not isinstance(state, dict) or type(state.get("version")) is not int
            or state.get("version") != SCHEMA_VERSION):
        state = town.exchange = initial_state()
    return state


def _record(state, symbol, count, source):
    state["activity_today"][symbol][source] += count
    state["pending_cents"][symbol] += (
        state["holdings"][symbol] * count * ASSET_BY_SYMBOL[symbol].dividend_cents
    )


def advance_city(town, seconds):
    """Record simulated city transactions for active game time; return tick count.

    Seven ledger updates happen per completed ten-second bucket, irrespective of
    the number of buckets crossed. No NPC drawing state or offline clock is read.
    Buying shares later cannot claim transactions recorded before the purchase.
    """
    if not _finite_number(seconds) or seconds <= 0:
        return 0
    state = _state(town)
    elapsed = state["activity_remainder"] + seconds
    ticks = int((elapsed + 1e-9) // CITY_TICK_SECONDS)
    state["activity_remainder"] = max(0.0, elapsed - ticks * CITY_TICK_SECONDS)
    if not ticks:
        return 0
    for asset in ASSETS:
        _record(state, asset.symbol, ticks * asset.city_units, "city")
    return ticks


def _quantity(quantity):
    return type(quantity) is int and quantity > 0


def district_symbol(site):
    """Map a trading building's current position to a district share."""
    x, y = getattr(site, "x", None), getattr(site, "y", None)
    if not _finite_number(x) or not _finite_number(y):
        return None
    if y >= 900:
        return "ALMADA"
    if x < 238:
        return "BELEM"
    if x < 718:
        return "BAIXA"
    if x < 958:
        return "ALFAMA"
    return "ORIENTE"


def record_trade(town, site, quantity):
    """Record units actually sold, or completed shipyard jobs, at a building."""
    symbol = district_symbol(site)
    if symbol is None or not _quantity(quantity):
        return False
    _record(_state(town), symbol, quantity, "player")
    return True


def record_bridge(town, name, count=1):
    """Record paid northbound 25 de Abril crossings, after toll collection."""
    if name != "25 de Abril" or not _quantity(count):
        return False
    _record(_state(town), "BRIDGE25", count, "player")
    return True


def record_tram(town, count=1):
    """Record paid player tram journeys, after a successful fare payment."""
    if not _quantity(count):
        return False
    _record(_state(town), "TRAM", count, "player")
    return True


def _asset(symbol):
    return ASSET_BY_SYMBOL.get(symbol) if isinstance(symbol, str) else None


def buy_shares(town, symbol, quantity):
    """Buy at the ask; share principal is an investment, not a daily expense."""
    asset = _asset(symbol)
    if asset is None or not _quantity(quantity):
        town.message = "Choose an available share and a positive whole quantity."
        return False
    state = _state(town)
    if state["holdings"][symbol] + quantity > asset.cap:
        town.message = f"You can hold at most {asset.cap} shares of {asset.name}."
        return False
    cost = state["quotes"][symbol] * quantity
    if town.cash < cost:
        town.message = f"You need ${cost} to buy {quantity} shares of {asset.name}."
        return False
    town.cash -= cost
    state["holdings"][symbol] += quantity
    state["cost_basis"][symbol] += cost
    town.message = f"Bought {quantity} {asset.name} share(s) for ${cost}."
    return True


def sell_shares(town, symbol, quantity):
    """Sell at the bid and recognize only the realized gain or loss for tax.

    Cost basis is the exact aggregate dollars invested. A partial sale allocates
    its proportional whole-dollar basis, leaving every rounding remainder with
    the remaining shares. Selling the entire position consumes that remainder,
    so splitting sales never creates or erases principal.
    """
    asset = _asset(symbol)
    if asset is None or not _quantity(quantity):
        town.message = "Choose an available share and a positive whole quantity."
        return False
    state = _state(town)
    owned = state["holdings"][symbol]
    if quantity > owned:
        town.message = f"You only own {owned} shares of {asset.name}."
        return False
    proceeds = max(1, state["quotes"][symbol] * BID_PERCENT // 100) * quantity
    allocated_basis = state["cost_basis"][symbol] * quantity // owned
    gain = proceeds - allocated_basis
    state["holdings"][symbol] -= quantity
    state["cost_basis"][symbol] -= allocated_basis
    town.cash += proceeds
    if gain >= 0:
        town.other_income_today += gain
    else:
        town.other_expenses_today -= gain
    # Principal is not income, but the resulting cash can still reach the goal.
    town.add_cash(0, business=True)
    town.message = f"Sold {quantity} {asset.name} share(s) for ${proceeds} (gain/loss ${gain:+d})."
    return True


def settle_exchange(town, day):
    """Pay accumulated whole-dollar dividends once for a closing day.

    A skipped day settles only credits already recorded; it does not invent
    transactions for intervening days. Fractional cents remain eligible even
    after a sale. Call this before computing the normal daily profit and tax.
    """
    if not _quantity(day):
        return 0
    state = _state(town)
    if day <= state["last_settlement"]:
        return 0
    statement = _statement()
    statement["day"] = day
    for asset in ASSETS:
        symbol = asset.symbol
        payout, cents = divmod(state["pending_cents"][symbol], 100)
        statement["by_asset"][symbol] = payout
        state["pending_cents"][symbol] = cents
        state["total_dividends"][symbol] += payout
        counts = state["activity_today"][symbol]
        activity = counts["city"] + counts["player"]
        statement["activity"][symbol] = activity
        statement["city_activity"][symbol] = counts["city"]
        statement["player_activity"][symbol] = counts["player"]
        # Thirty city ticks make one five-minute day. Normal traffic leaves the
        # quote at its base; quiet/busy days move it within a 25% band.
        expected = 30 * asset.city_units
        next_quote = (asset.base_price * (3 * expected + min(activity, 2 * expected))
                      + 2 * expected) // (4 * expected)
        low, high = _quote_bounds(asset)
        state["quotes"][symbol] = min(high, max(low, next_quote))
        state["activity_today"][symbol] = {"city": 0, "player": 0}
    statement["paid"] = sum(statement["by_asset"].values())
    state["last_settlement"] = day
    state["last_statement"] = statement
    if statement["paid"]:
        town.add_cash(statement["paid"])
    return statement["paid"]


def portfolio_rows(town):
    """Read-only rows for the exchange panel; dollar values are whole integers."""
    state = getattr(town, "exchange", None)
    if not isinstance(state, dict):
        state = initial_state()
    rows = []
    for asset in ASSETS:
        symbol = asset.symbol
        ask = state["quotes"][symbol]
        bid = max(1, ask * BID_PERCENT // 100)
        owned = state["holdings"][symbol]
        counts = state["activity_today"][symbol]
        rows.append({
            "symbol": symbol, "name": asset.name, "kind": asset.kind,
            "description": asset.description, "ask": ask, "bid": bid,
            "owned": owned, "cap": asset.cap, "cost_basis": state["cost_basis"][symbol],
            "value": owned * bid, "pending_cents": state["pending_cents"][symbol],
            "activity": counts["city"] + counts["player"],
            "player_activity": counts["player"], "city_activity": counts["city"],
            "dividend_cents": asset.dividend_cents,
            "last_payout": state["last_statement"]["by_asset"][symbol],
            "total_dividends": state["total_dividends"][symbol],
        })
    return tuple(rows)


def summary(town):
    """Read-only portfolio totals; value means current cash-out value at the bid."""
    rows = portfolio_rows(town)
    state = getattr(town, "exchange", None)
    if not isinstance(state, dict):
        state = initial_state()
    return {
        "cash": town.cash, "owned": sum(row["owned"] for row in rows),
        "cost_basis": sum(row["cost_basis"] for row in rows),
        "value": sum(row["value"] for row in rows),
        "pending_cents": sum(row["pending_cents"] for row in rows),
        "total_dividends": sum(row["total_dividends"] for row in rows),
        "last_settlement": state["last_settlement"],
        "last_payout": state["last_statement"]["paid"],
        "activity": sum(row["activity"] for row in rows),
        "last_statement": deepcopy(state["last_statement"]),
    }
