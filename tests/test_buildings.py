from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.errors import AppTestError

from browser_game import MONASTERY, building_at, entrance, greeting, scene_for
from ferry import FERRY_PIERS
from lisbon_landmarks import LANDMARKS
from tycoon import ROULETTE_POCKETS, SITES, Town, roulette_color

SCENES = Path(__file__).resolve().parents[1] / "street" / "scenes"


def click(app, label):
    next(button for button in app.button if button.label == label).click().run()
    assert not app.exception


def choose_place(app, name):
    # AppTest does not run keyboard movement. Stage arrival, then send the same E event.
    from browser_game import entrance, street_event
    site = next(site for site in SITES if site.name == name)
    app.selectbox[0].select(name).run()
    app.session_state.town.x, app.session_state.town.y = entrance(site)
    app.session_state.inside = street_event(app.session_state.town,
        {"dx": 0, "dy": 0, "seconds": 0, "action": "interact"})
    app.run()
    assert not app.exception



def labels(app):
    return {button.label for button in app.button}


def new_app(monkeypatch):
    monkeypatch.delenv("FOUNDRY_LOCAL_DB", raising=False)
    app = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    assert not app.exception
    return app


# ----- Which building is at the door -----

def test_every_door_opens_its_own_building_and_piers_take_priority():
    town = Town()
    for site in SITES:
        town.x, town.y = entrance(site)
        assert building_at(town) == site.name
    for pier in FERRY_PIERS:
        town.x, town.y = pier.position
        assert building_at(town) is None  # E at a pier rides the ferry
    town.x, town.y = 1300, 380  # Open street
    assert building_at(town) is None
    left, _, right, bottom = LANDMARKS[0].bounds
    town.x, town.y = (left + right) / 2, bottom + 16
    assert building_at(town) == MONASTERY


def test_every_illustrated_scene_exists_and_every_building_greets_you():
    town = Town()
    for site in [*SITES, MONASTERY]:
        found = scene_for(town, site)
        if found:
            assert (SCENES / f"{found[0]}.webp").is_file(), found[0]
        assert greeting(town, site)
    plain = {site.role for site in SITES if scene_for(town, site) is None}
    assert plain == {"WAREHOUSE", "EXCHANGE", "RESEARCH"}
    assert (SCENES / "ferry_day.webp").is_file() and (SCENES / "ferry_night.webp").is_file()


def test_monastery_luck_is_capped_at_twenty_points():
    town = Town()
    for _ in range(6):
        town.visit_monastery()
    assert town.casino_luck == 20


# ----- Inside buildings in the app -----

def test_visit_enters_the_building_and_leave_returns_to_the_street(monkeypatch):
    app = new_app(monkeypatch)
    choose_place(app, "Goldenfield Farm")
    assert {"Buy up to 4 Wheat", "Buy 1 egg", "Leave"} <= labels(app)
    click(app, "Buy up to 4 Wheat")
    assert app.metric[0].value == "$44"
    assert "Wheat" in app.session_state.reply  # The vendor answers inside the speech bubble
    click(app, "Leave")
    assert "Enter Goldenfield Farm" not in labels(app) and "Buy up to 4 Wheat" not in labels(app)
    choose_place(app, "Goldenfield Farm")
    assert "Buy up to 4 Wheat" in labels(app)


def test_casino_spin_pays_by_colour_and_rejects_an_unaffordable_chip(monkeypatch):
    app = new_app(monkeypatch)
    choose_place(app, "Foundry Casino")
    click(app, "Red · pays 2×")
    spin = app.session_state.spin
    expected = 70 if roulette_color(spin["number"]) == "red" else 50
    assert app.session_state.town.cash == expected
    assert spin["number"] in ROULETTE_POCKETS and spin["id"] == 1
    black = next(button for button in app.button if button.label == "Black · pays 2×")
    assert black.proto.disabled
    with pytest.raises(AppTestError, match="Cannot update a disabled button"):
        black.click()
    assert app.session_state.town.cash == expected
    assert app.session_state.spin["id"] == 1

    app.session_state.spin["ends_at"] = 0
    app.session_state.town.cash = 4
    app.run()
    click(app, "Green 0 · pays 36×")
    assert app.session_state.town.cash == 4
    assert app.session_state.spin["id"] == 1  # No new spin
    assert "need $10" in app.session_state.reply


def test_monastery_visit_shows_the_prayer_and_adds_luck(monkeypatch):
    app = new_app(monkeypatch)
    left, _, right, bottom = LANDMARKS[0].bounds
    town = app.session_state.town
    town.x, town.y = (left + right) / 2, bottom + 16
    app.session_state.inside = MONASTERY
    app.run()
    assert not app.exception
    assert any("Casino luck" in caption.value for caption in app.caption)


# ----- Ferry crossings are animated -----

def test_crossbank_destination_gives_ferry_directions_without_travelling(monkeypatch):
    from navigation import directions
    from browser_game import street_event
    app = new_app(monkeypatch)
    before = app.session_state.town.x, app.session_state.town.y, app.session_state.town.cash
    app.selectbox[0].select("Iron Hill Mine").run()
    town = app.session_state.town
    assert (town.x, town.y, town.cash) == before
    assert "Enter Iron Hill Mine" not in labels(app)
    assert not any(label.startswith("Visit ") for label in labels(app))
    mine = next(site for site in SITES if site.name == "Iron Hill Mine")
    assert "ferry" in directions(town, entrance(mine))["instruction"]
    town.x, town.y = FERRY_PIERS[0].position
    street_event(town, {"dx": 0, "dy": 0, "seconds": 0, "action": "interact"})
    assert (town.x, town.y, town.cash) == (*FERRY_PIERS[1].position, before[2]-2)
    assert "ferry" not in directions(town, entrance(mine))["instruction"]


# ----- E on the street map -----

def test_e_at_a_door_opens_the_building_without_trading():
    from browser_game import street_event
    town = Town()
    farm = next(site for site in SITES if site.name == "Goldenfield Farm")
    town.x, town.y = entrance(farm)
    still = {"segments": [{"dx": 0, "dy": 0, "seconds": 0}], "action": "interact"}
    assert street_event(town, still) == "Goldenfield Farm"
    assert (town.cash, town.cargo) == (60, 0)  # Trading happens inside
    town.x, town.y = FERRY_PIERS[0].position
    assert street_event(town, still) is None  # At a pier, E rides the ferry
    assert (town.x, town.y) == FERRY_PIERS[1].position
    town.x, town.y = 1300, 380
    assert street_event(town, still) is None
    assert "entrance" in town.message.lower()
    bad = {"segments": [{"dx": 9, "dy": 0, "seconds": 0.1}], "action": "interact"}
    before = vars(town).copy()
    assert street_event(town, bad) is None and vars(town) == before


# ----- Basics tutorial -----

def test_new_game_opens_the_basics_and_the_slides_page_through(monkeypatch):
    monkeypatch.delenv("FOUNDRY_LOCAL_DB", raising=False)
    app = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    click(app, "New Game")
    assert app.session_state.show_tutorial and app.session_state.tutorial_step == 0
    assert "Back" in labels(app) and "Next" in labels(app)
    for step in range(1, 5):
        click(app, "Next")
        assert app.session_state.tutorial_step == step
    assert "Next" not in labels(app) and "Start playing" in labels(app)
    click(app, "Back")
    assert app.session_state.tutorial_step == 3
    click(app, "Skip")
    assert not app.session_state.show_tutorial
    assert "Back" not in labels(app)


def test_basics_can_be_replayed_from_the_start_menu_and_every_slide_exists(monkeypatch):
    monkeypatch.delenv("FOUNDRY_LOCAL_DB", raising=False)
    app = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    click(app, "Basics · how to play in 5 slides")
    assert app.session_state.show_tutorial and not app.session_state.show_menu
    slides = Path(__file__).resolve().parents[1] / "street" / "tutorial"
    for name in ("goal", "buy", "make", "sell", "garage"):
        assert (slides / f"{name}.webp").is_file(), name
