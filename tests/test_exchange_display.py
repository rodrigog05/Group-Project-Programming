from copy import deepcopy
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from browser_game import OPEN_SITES, entrance
from exchange import (ASSETS, buy_shares, sell_shares, normalize_state,
                      portfolio_rows, record_trade, settle_exchange)
from exchange_art import exchange_svg
from tycoon import Order, Town, pack_save, unpack_save


def test_day_changes_follow_each_previous_close_and_only_settle_once():
    town = Town()
    assert all(row["day_change"] == 0 for row in portfolio_rows(town))
    old = dict(town.exchange["quotes"])
    store = next(site for site in OPEN_SITES if site.name == "Daily Bread Market")
    assert record_trade(town, store, 2)
    settle_exchange(town, 1)
    rows = portfolio_rows(town)
    assert {row["name"]: row["day_change"] for row in rows if row["day_change"]} == {"Daily Bread Market": 5}
    for row in rows:
        assert row["previous_close"] == old[row["symbol"]]
        assert row["day_change"] == row["price"] - row["previous_close"]
        assert row["day_change_percent"] == pytest.approx(row["day_change"] / row["previous_close"] * 100)
    closed = deepcopy(town.exchange)
    settle_exchange(town, 1)
    assert town.exchange == closed
    old = dict(town.exchange["quotes"])
    settle_exchange(town, 2)
    assert all(row["previous_close"] == old[row["symbol"]] and row["day_change"] == 0
               for row in portfolio_rows(town))


def test_price_history_survives_save_and_legacy_saves_start_flat():
    town = Town()
    store = next(site for site in OPEN_SITES if site.name == "Daily Bread Market")
    assert record_trade(town, store, 1)
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
    assert town.cash == cash-row["price"]
    assert sell_shares(town, row["symbol"], 1)
    assert town.cash == cash
    assert town.exchange["previous_quotes"] == history


def test_exchange_shows_every_stock_and_holding_on_the_board():
    from streamlit.testing.v1 import AppTest
    from test_browser_game import click, choose_place
    app = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    for label in ("New Game", "Skip", "Start playing"):
        click(app, label)
    choose_place(app, "Bolsa de Lisboa")

    def board():
        markup = next(element.proto.body for element in app.get("html") if 'class="exchange-board"' in element.proto.body)
        rows = ET.fromstring(markup).findall("./tbody/tr")
        return {row[0].text: (row[1].text, row[2].text, row[3].text) for row in rows}

    assert "All stocks" in {heading.value for heading in app.subheader}
    assert set(board()) == {asset.name for asset in ASSETS}
    assert all(owned == "0" and change == "—" for _, owned, change in board().values())
    town = app.session_state.town
    assert buy_shares(town, "BELEM", 1)
    store = next(site for site in OPEN_SITES if site.name == "Daily Bread Market")
    assert record_trade(town, store, 1)
    settle_exchange(town, 1)
    app.run()
    assert not app.exception
    assert board()["Daily Bread Market"] == ("$50", "1", "+$5 (+11.1%)")
    assert board()["Tool Market"] == ("$60", "0", "—")
    click(app, "Leave")
    assert app.session_state.inside is None


@pytest.mark.parametrize("asset", ASSETS, ids=lambda asset: asset.name)
def test_each_stock_is_linked_to_the_open_business_where_the_player_sells(asset):
    town = Town()
    store = next(site for site in OPEN_SITES if site.name == asset.store)
    town.x, town.y = entrance(store)
    if store.role == "SHIPYARD":
        town.industry_orders["SHIPYARD"] = Order(1, 0)
        town.shipyard_quote = 30
    else:
        town.goods[store.trade] = 1
    town.interact()
    assert {symbol for symbol, sales in town.exchange["sales_today"].items() if sales} == {asset.symbol}
    settle_exchange(town, 1)
    assert {row["name"] for row in portfolio_rows(town) if row["day_change"] > 0} == {asset.name}


def test_exchange_background_is_a_reproducible_drawing():
    root = Path(__file__).resolve().parents[1] / "street" / "scenes"
    markup = exchange_svg()
    doc = ET.fromstring(markup)
    assert not doc.findall(".//{http://www.w3.org/2000/svg}image")
    assert (root / "lisbon_exchange.svg").read_text(encoding="utf-8") == markup
    assert (root / "lisbon_exchange.webp").is_file()
