import pytest
from streamlit.testing.v1 import AppTest

from browser_game import MONASTERY, entrance, street_event
from lisbon_landmarks import LANDMARKS
from navigation import clear_line, directions
from tycoon import SITES, Town, pack_save, roulette_color, ROULETTE_POCKETS, unpack_save


def test_monastery_e_visits_award_and_save_luck_once_per_entry(monkeypatch):
    town = Town()
    left, _, right, bottom = LANDMARKS[0].bounds
    event = {"dx": 0, "dy": 0, "seconds": 0, "action": "interact"}
    town.x, town.y = (left+right)/2, bottom+16
    assert street_event(town, {**event, "dx": 4}) is None
    assert town.casino_luck == 0
    for expected in (5, 10, 15, 20, 20):
        assert street_event(town, event) == MONASTERY
        assert town.casino_luck == expected
        town, _ = unpack_save(pack_save(town, 0))
        assert town.casino_luck == expected
    assert street_event(town, {**event, "action": None}) is None
    assert town.casino_luck == 20


@pytest.mark.parametrize("colour", ["red", "black", "green"])
def test_each_monastery_visit_adds_five_probability_points(colour, monkeypatch):
    import tycoon
    town = Town()
    base = sum(roulette_color(number) == colour for number in ROULETTE_POCKETS)/len(ROULETTE_POCKETS)
    monkeypatch.setattr(tycoon.random, "choice", lambda options: options[0])
    for visit in range(5):
        town.monastery_visits = visit
        monkeypatch.setattr(tycoon.random, "random", lambda: base+visit*.05-.001)
        assert roulette_color(ROULETTE_POCKETS[town.roulette_pocket(colour)]) == colour
        monkeypatch.setattr(tycoon.random, "random", lambda: base+visit*.05+.001)
        assert roulette_color(ROULETTE_POCKETS[town.roulette_pocket(colour)]) != colour


@pytest.mark.parametrize("driving", [False, True])
def test_routes_to_every_business_avoid_obstacles_and_do_not_change_state(driving):
    town = Town()
    town.vehicle = "car" if driving else None
    before = pack_save(town, 0)
    for site in SITES:
        route = directions(town, entrance(site))
        assert route["points"], site.name
        assert route["points"][0] == (town.x, town.y)
        for a, b in zip(route["points"], route["points"][1:]):
            assert clear_line(a, b, driving), (site.name, a, b)
    assert pack_save(town, 0) == before


def test_direction_selection_never_moves_or_opens_building(monkeypatch):
    monkeypatch.delenv("FOUNDRY_LOCAL_DB", raising=False)
    app = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    before = pack_save(app.session_state.town, 0)
    for destination in ("Goldenfield Farm", "Iron Hill Mine", MONASTERY):
        app.selectbox[0].select(destination).run()
        assert not app.exception
        assert pack_save(app.session_state.town, 0) == before
        assert app.session_state.get("inside") is None
        assert not any(button.label.startswith(("Visit ", "Enter ")) for button in app.button)


def test_monastery_scene_rerender_does_not_award_extra_luck(monkeypatch):
    monkeypatch.delenv("FOUNDRY_LOCAL_DB", raising=False)
    app = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    town = app.session_state.town
    left, _, right, bottom = LANDMARKS[0].bounds
    town.x, town.y = (left+right)/2, bottom+16
    app.session_state.inside = street_event(town, {"dx": 0, "dy": 0, "seconds": 0, "action": "interact"})
    app.run().run()
    assert not app.exception
    assert app.session_state.town.casino_luck == 5
    assert any("+5" in caption.value for caption in app.caption)


def test_contract_guidance_selects_client_without_moving_player(monkeypatch):
    import contracts
    monkeypatch.delenv("FOUNDRY_LOCAL_DB", raising=False)
    app = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    town = app.session_state.town
    town.cash = 1000
    town.accept_contract("tools_workshop")
    app.session_state.town_page = "Contracts"
    app.run()
    before = town.x, town.y, town.cash
    button = next(button for button in app.button if button.label == f"Show directions to {contracts.BRIDGE.name}")
    button.click().run()
    assert not app.exception
    assert app.session_state.town_page == "Game"
    assert app.selectbox[0].value == contracts.BRIDGE.name
    assert (app.session_state.town.x, app.session_state.town.y, app.session_state.town.cash) == before
