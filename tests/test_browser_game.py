import pytest
from streamlit.testing.v1 import AppTest

from browser_game import LocalSave, SaveConflict, advance_turn, entrance, visit
from tycoon import SITES, Town


def click(app, label):
    next(button for button in app.button if button.label == label).click().run()
    assert not app.exception


def choose_place(app, name):
    app.selectbox[0].select(name).run()
    assert not app.exception
    click(app, f"Visit {name}")


def test_browser_trade_loop_rejection_restart_and_session_isolation(tmp_path, monkeypatch):
    monkeypatch.setenv("FOUNDRY_LOCAL_DB", str(tmp_path / "game.sqlite3"))
    app = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    assert not app.exception
    choose_place(app, "Goldenfield Farm")
    click(app, "Buy up to 4 Wheat")
    assert app.metric[0].value == "$44"
    choose_place(app, "Sunrise Bakery")
    click(app, "Produce or collect")
    click(app, "Produce or collect")
    assert "production" in app.info[0].value.lower()
    click(app, "Advance time")
    click(app, "Produce or collect")
    choose_place(app, "Daily Bread Market")
    click(app, "Sell carried goods")
    assert app.metric[0].value == "$100"
    choose_place(app, "Motorworks Garage")
    click(app, "Buy Motorcycle · $120 · +6 slots")
    assert app.metric[0].value == "$100"
    assert app.metric[1].value == "0 / 12"
    assert "$120" in app.info[0].value
    reloaded = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    assert reloaded.metric[0].value == "$100"
    assert reloaded.session_state.town.elapsed == 15
    assert reloaded.session_state.town.nearby().name == "Motorworks Garage"
    monkeypatch.delenv("FOUNDRY_LOCAL_DB")
    separate = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    assert separate.metric[0].value == "$60"


def test_pages_and_service_controls(monkeypatch):
    monkeypatch.delenv("FOUNDRY_LOCAL_DB", raising=False)
    app = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    for place in ("Nova SBE · Carcavelos", "Bolsa de Lisboa", "Foundry Warehouse", "Foundry Casino"):
        choose_place(app, place)
    for page in ("Market & recipes", "Contracts", "Deliveries", "Businesses", "Landmarks"):
        app.radio[0].set_value(page).run()
        assert not app.exception


def test_crossing_rejects_unaffordable_ferry_and_charges_return_toll():
    town = Town()
    mine = next(site for site in SITES if site.name == "Iron Hill Mine")
    old_position = (town.x, town.y)
    town.cash = 1
    visit(town, entrance(mine), mine.name)
    assert (town.x, town.y) == old_position
    assert town.cash == 1
    town.cash = 60
    visit(town, entrance(mine), mine.name)
    assert (town.x, town.y) == entrance(mine)
    assert town.cash == 58
    town.vehicle = "motorcycle"
    visit(town, old_position, "Lisboa")
    assert (town.cash, town.tolls_today) == (55, 3)


def test_local_save_rejects_stale_write_and_restores_market_clock(tmp_path):
    store = LocalSave(tmp_path / "nested" / "game.sqlite3")
    first, revision = store.load()
    stale, stale_revision = store.load()
    advance_turn(first, 301)
    assert first.day == 2
    assert store.save(first, revision) == 1
    with pytest.raises(SaveConflict):
        store.save(stale, stale_revision)
    reloaded, revision = store.load()
    assert revision == 1
    assert reloaded.elapsed == reloaded.market_elapsed == 301
    assert reloaded.day == 2


def test_visit_by_vehicle_rejects_unaffordable_toll():
    town = Town()
    mine = next(site for site in SITES if site.name == "Iron Hill Mine")
    town.vehicle = "car"
    town.x, town.y = entrance(mine)
    town.cash = 2
    visit(town, (480, 321), "Lisboa")
    assert (town.x, town.y, town.cash) == (*entrance(mine), 2)
    assert "portagem" in town.message.lower()
