"""Store shares with percentage dividends and a daily price increase after a sale."""
from copy import deepcopy
from dataclasses import dataclass

from place_names import place_name


DAILY_DIVIDEND_PERCENT = 5
PRICE_INCREASE_PERCENT = 10
SCHEMA_VERSION = 3


@dataclass(frozen=True)
class Asset:
    # Keep the original symbols so saved positions retain their identity.
    symbol: str
    store: str
    base_price: int
    cap: int = 100

    @property
    def name(self):
        return place_name(self.store)


ASSETS = (
    Asset("BELEM", "Daily Bread Market", 45),
    Asset("BRIDGE25", "Oriente Tool Market", 75),
    Asset("ORIENTE", "Home Market", 55),
    Asset("TRAM", "Mercado das Nações", 50),
    Asset("ALMADA", "Estaleiro do Tejo", 40),
)
ASSET_BY_SYMBOL = {asset.symbol: asset for asset in ASSETS}
ASSET_BY_STORE = {asset.store: asset for asset in ASSETS}
RETIRED_SHARES = {"BAIXA": ("BRIDGE25", 60), "ALFAMA": ("TRAM", 35)}


def _zeros():
    return {asset.symbol: 0 for asset in ASSETS}


def _statement():
    return {"day": 0, "paid": 0, "by_asset": _zeros()}


def initial_state():
    """Return an independent, JSON-serializable portfolio with no past income."""
    return {
        "version": SCHEMA_VERSION,
        "holdings": _zeros(),
        "cost_basis": _zeros(),
        "quotes": {asset.symbol: asset.base_price for asset in ASSETS},
        "previous_quotes": {asset.symbol: asset.base_price for asset in ASSETS},
        "legacy_dividends": _zeros(),
        "total_dividends": _zeros(),
        "sales_today": _zeros(),
        "last_settlement": 0,
        "last_statement": _statement(),
    }


def _whole(value, default=0):
    return value if type(value) is int and value >= 0 else default


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
    version = value.get("version", 1)
    if type(version) is not int or version not in (1, 2, SCHEMA_VERSION):
        return result

    def mapping(key):
        item = value.get(key)
        return item if isinstance(item, dict) else {}

    holdings, basis, quotes = mapping("holdings"), mapping("cost_basis"), mapping("quotes")
    previous_quotes = mapping("previous_quotes")
    pending = mapping("pending_cents" if version == 1 else "legacy_dividends")
    dividends, sales = mapping("total_dividends"), mapping("sales_today")
    payouts = mapping("last_statement").get("by_asset")
    payouts = payouts if isinstance(payouts, dict) else {}
    statement = result["last_statement"]
    for asset in ASSETS:
        symbol = asset.symbol
        # A player who owned both old listings may exceed the new purchase cap.
        limit = asset.cap * 2 if version == SCHEMA_VERSION and symbol in ("BRIDGE25", "TRAM") else asset.cap
        owned = min(limit, _whole(holdings.get(symbol)))
        result["holdings"][symbol] = owned
        result["cost_basis"][symbol] = _whole(basis.get(symbol), owned * asset.base_price) if owned else 0
        quote = _whole(quotes.get(symbol)) or asset.base_price
        previous = _whole(previous_quotes.get(symbol))
        if version == 1:
            low = (asset.base_price * 75 + 50) // 100
            high = (asset.base_price * 125 + 50) // 100
            quote = min(high, max(low, quote))
            if previous:
                previous = min(high, max(low, previous))
        result["quotes"][symbol] = quote
        result["previous_quotes"][symbol] = previous or quote
        credit = _whole(pending.get(symbol))
        # Round legacy fractional dividends up once so no earned credit is lost.
        result["legacy_dividends"][symbol] = (credit + 99) // 100 if version == 1 else credit
        result["total_dividends"][symbol] = _whole(dividends.get(symbol))
        result["sales_today"][symbol] = _whole(sales.get(symbol)) if version >= 2 else 0
        statement["by_asset"][symbol] = _whole(payouts.get(symbol))

    if version < SCHEMA_VERSION:
        for retired, (replacement, base_price) in RETIRED_SHARES.items():
            owned = min(ASSET_BY_SYMBOL[replacement].cap, _whole(holdings.get(retired)))
            result["holdings"][replacement] += owned
            if owned:
                result["cost_basis"][replacement] += _whole(basis.get(retired), owned * base_price)
            credit = _whole(pending.get(retired))
            result["legacy_dividends"][replacement] += (credit + 99) // 100 if version == 1 else credit
            result["total_dividends"][replacement] += _whole(dividends.get(retired))
            statement["by_asset"][replacement] += _whole(payouts.get(retired))

    result["last_settlement"] = _whole(value.get("last_settlement"))
    saved_statement = mapping("last_statement")
    statement["day"] = min(result["last_settlement"], _whole(saved_statement.get("day")))
    statement["paid"] = sum(statement["by_asset"].values())
    return result


def _state(town):
    """Fast path for the normalized ledger installed when a save is loaded."""
    state = getattr(town, "exchange", None)
    if (not isinstance(state, dict) or type(state.get("version")) is not int
            or state.get("version") != SCHEMA_VERSION):
        state = town.exchange = normalize_state(state)
    return state


def _quantity(quantity):
    return type(quantity) is int and quantity > 0


def record_trade(town, site, quantity):
    """Record sales or paid jobs for the listed business that made them."""
    name = getattr(site, "name", None)
    asset = ASSET_BY_STORE.get(name) if isinstance(name, str) else None
    if asset is None or not _quantity(quantity):
        return False
    _state(town)["sales_today"][asset.symbol] += quantity
    return True


def _asset(symbol):
    return ASSET_BY_SYMBOL.get(symbol) if isinstance(symbol, str) else None


def buy_shares(town, symbol, quantity):
    """Buy at the quoted price and record the cost basis."""
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
    """Sell at the quoted price and recognize the realized gain or loss for tax.

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
    proceeds = state["quotes"][symbol] * quantity
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


def _closing_price(state, symbol):
    price = state["quotes"][symbol]
    if state["sales_today"][symbol]:
        return (price * (100 + PRICE_INCREASE_PERCENT) + 50) // 100
    return price


def _daily_dividend(price, owned):
    """Round the dividend for the entire position to a whole game dollar."""
    return (price * owned * DAILY_DIVIDEND_PERCENT + 50) // 100


def settle_exchange(town, day, *, pay_daily_dividends=True):
    """Pay holders and apply sale-triggered price increases once per market close."""
    if not _quantity(day):
        return 0
    state = _state(town)
    if day <= state["last_settlement"]:
        return 0
    statement = _statement()
    statement["day"] = day
    state["previous_quotes"] = dict(state["quotes"])
    for asset in ASSETS:
        symbol = asset.symbol
        closing_price = _closing_price(state, symbol)
        payout = state["legacy_dividends"][symbol]
        if pay_daily_dividends:
            payout += _daily_dividend(closing_price, state["holdings"][symbol])
        statement["by_asset"][symbol] = payout
        state["legacy_dividends"][symbol] = 0
        state["total_dividends"][symbol] += payout
        state["quotes"][symbol] = closing_price
        state["sales_today"][symbol] = 0
    statement["paid"] = sum(statement["by_asset"].values())
    state["last_settlement"] = day
    state["last_statement"] = statement
    if statement["paid"]:
        town.add_cash(statement["paid"])
    return statement["paid"]


def portfolio_rows(town):
    """Read-only rows for the exchange panel; dollar values are whole integers."""
    state = getattr(town, "exchange", None)
    if not isinstance(state, dict) or state.get("version") != SCHEMA_VERSION:
        state = normalize_state(state)
    rows = []
    for asset in ASSETS:
        symbol = asset.symbol
        price = state["quotes"][symbol]
        previous = state.get("previous_quotes", {}).get(symbol) or price
        change = price - previous
        closing_price = _closing_price(state, symbol)
        owned = state["holdings"][symbol]
        rows.append({
            "symbol": symbol, "name": asset.name, "price": price, "owned": owned,
            "previous_close": previous, "day_change": change, "day_change_percent": change / previous * 100,
            "cost_basis": state["cost_basis"][symbol], "value": owned * price,
            "next_dividend": _daily_dividend(closing_price, owned) + state["legacy_dividends"][symbol],
            "next_price": closing_price,
            "last_payout": state["last_statement"]["by_asset"][symbol],
            "total_dividends": state["total_dividends"][symbol],
        })
    return tuple(rows)


def summary(town):
    """Read-only portfolio totals at current share prices."""
    rows = portfolio_rows(town)
    state = getattr(town, "exchange", None)
    if not isinstance(state, dict) or state.get("version") != SCHEMA_VERSION:
        state = normalize_state(state)
    return {
        "cash": town.cash, "owned": sum(row["owned"] for row in rows),
        "cost_basis": sum(row["cost_basis"] for row in rows),
        "value": sum(row["value"] for row in rows),
        "next_dividend": sum(row["next_dividend"] for row in rows),
        "total_dividends": sum(row["total_dividends"] for row in rows),
        "last_settlement": state["last_settlement"],
        "last_payout": state["last_statement"]["paid"],
        "last_statement": deepcopy(state["last_statement"]),
    }
