from copy import deepcopy
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from exchange import (ASSETS, advance_city, buy_shares, sell_shares, normalize_state,
                      portfolio_rows, settle_exchange)
from exchange_art import exchange_svg
from tycoon import Town, pack_save, unpack_save


def test_day_changes_follow_each_previous_close_and_only_settle_once():
    town = Town()
    assert all(row["day_change"] == 0 for row in portfolio_rows(town))
    old = dict(town.exchange["quotes"])
    settle_exchange(town, 1)  # A quiet day lowers quotes.
    rows = portfolio_rows(town)
    for row in rows:
        assert row["previous_close"] == old[row["symbol"]]
        assert row["day_change"] == row["ask"] - row["previous_close"] < 0
        assert row["day_change_percent"] == pytest.approx(row["day_change"] / row["previous_close"] * 100)
    closed = deepcopy(town.exchange)
    settle_exchange(town, 1)
    assert town.exchange == closed
    advance_city(town, 600)  # Busy next day raises quotes from that close.
    old = dict(town.exchange["quotes"])
    settle_exchange(town, 2)
    assert all(row["previous_close"] == old[row["symbol"]] and row["day_change"] > 0
               for row in portfolio_rows(town))


def test_price_history_survives_save_and_legacy_saves_start_flat():
    town = Town()
    settle_exchange(town, 1)
    saved = json.loads(json.dumps(pack_save(town, 1000)))
    restored, _ = unpack_save(saved)
    assert portfolio_rows(restored) == portfolio_rows(town)
    saved["state"]["exchange"].pop("previous_quotes")
    restored, _ = unpack_save(saved)
    assert all(row["day_change"] == row["day_change_percent"] == 0 for row in portfolio_rows(restored))
    malformed = deepcopy(town.exchange)
    malformed["previous_quotes"] = {"BELEM": 0, "TRAM": float("nan"), "ALFAMA": True}
    restored.exchange = normalize_state(malformed)
    assert all(row["previous_close"] > 0 for row in portfolio_rows(restored))


def test_displayed_quotes_are_the_actual_transaction_prices_and_read_only():
    town = Town()
    town.cash = 1000
    settle_exchange(town, 1)
    before = deepcopy(vars(town))
    row = portfolio_rows(town)[0]
    assert vars(town) == before
    history = dict(town.exchange["previous_quotes"])
    cash = town.cash
    assert buy_shares(town, row["symbol"], 1)
    assert town.cash == cash-row["ask"]
    assert sell_shares(town, row["symbol"], 1)
    assert town.cash == cash-row["ask"]+row["bid"]
    assert town.exchange["previous_quotes"] == history


def test_exchange_shows_every_stock_without_opening_the_portfolio_expander():
    from streamlit.testing.v1 import AppTest
    from test_browser_game import click, choose_place
    app = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    for label in ("New Game", "Skip", "Start playing"):
        click(app, label)
    choose_place(app, "Bolsa de Lisboa")

    def board():
        return next(table.value for table in app.dataframe if "Symbol" in table.value.columns)

    assert "All stocks" in {heading.value for heading in app.subheader}
    assert set(board()["Symbol"]) == {asset.symbol for asset in ASSETS}
    assert set(board()["Day change"]) == {"$+0"}
    town = app.session_state.town
    settle_exchange(town, 1)
    app.run()
    assert not app.exception
    for _, displayed in board().iterrows():
        row = next(row for row in portfolio_rows(town) if row["symbol"] == displayed["Symbol"])
        assert displayed["Buy"] == f"${row['ask']:,}"
        assert displayed["Sell"] == f"${row['bid']:,}"
        assert displayed["Day change"] == f"${row['day_change']:+d}"
    click(app, "Leave exchange")
    assert app.session_state.inside is None


def test_exchange_background_is_a_reproducible_drawing():
    root = Path(__file__).resolve().parents[1] / "street" / "scenes"
    markup = exchange_svg()
    doc = ET.fromstring(markup)
    assert not doc.findall(".//{http://www.w3.org/2000/svg}image")
    assert (root / "lisbon_exchange.svg").read_text(encoding="utf-8") == markup
    assert (root / "lisbon_exchange.webp").is_file()
