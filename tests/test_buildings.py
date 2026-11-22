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
    from browser_game import CLOSED_SITES
    town = Town()
    for site in SITES:
        town.x, town.y = entrance(site)
        assert building_at(town) == (None if site.name in CLOSED_SITES else site.name)
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
    assert plain == {"EXCHANGE", "RESEARCH"}  # The warehouse has its own scene now
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
    assert {"Buy up to 4 Wheat", "Leave"} <= labels(app)
    assert not {"Buy 1 egg", "Buy up to 4 eggs"} & labels(app)  # Eggs were removed from the game
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
    click(app, "Skip")  # Skip jumps to the last slide, it doesn't restart
    assert app.session_state.show_tutorial and app.session_state.tutorial_step == 4
    assert "Start playing" in labels(app)
    click(app, "Start playing")
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



# ----- Simplified town -----

def test_closed_buildings_cannot_be_entered_and_are_not_destinations(monkeypatch):
    from browser_game import CLOSED_SITES, OPEN_SITES, street_event
    assert CLOSED_SITES == {"Motorworks Garage", "Armazém do Seixal", "Pastéis de Belém"}
    assert [site.name for site in OPEN_SITES if site.role == "GARAGE"] == ["Cacilhas Garage"]
    assert [site.name for site in OPEN_SITES if site.role == "WAREHOUSE"] == ["Foundry Warehouse"]
    town = Town()
    garage = next(site for site in SITES if site.name == "Motorworks Garage")
    town.x, town.y = entrance(garage)
    assert street_event(town, {"dx": 0, "dy": 0, "seconds": 0, "action": "interact"}) is None
    assert "apartments" in town.message and town.cash == 60
    app = new_app(monkeypatch)
    options = set(app.selectbox[0].options)
    assert not CLOSED_SITES & options and {"Cacilhas Garage", "Foundry Warehouse"} <= options


def test_warehouse_has_a_scene_and_the_farm_sells_only_wheat():
    from browser_game import scene_for
    town = Town()
    warehouse = next(site for site in SITES if site.name == "Foundry Warehouse")
    assert scene_for(town, warehouse)[0] == "warehouse"
    assert "12 slots" in greeting(town, warehouse)
    farm = next(site for site in SITES if site.name == "Goldenfield Farm")
    assert "Egg" not in greeting(town, farm)


def test_market_shows_four_route_cards_and_the_goal_bar(monkeypatch):
    app = new_app(monkeypatch)
    assert "of the" in app.get("progress")[0].proto.text  # "$60 of the $500 goal"
    click(app, "Market & recipes")
    text = " ".join(markdown.value for markdown in app.markdown)
    for product in ("Tools", "Furniture", "Pottery", "Bread"):
        assert product in text
    assert "Profit \\$10 per bread" in text and "Goldenfield Farm" in text
    assert "Pastéis" not in text


# ----- Next-move hint and the production countdown -----

def test_hints_say_where_to_go_then_which_key_to_press_on_a_new_route():
    from browser_game import next_move
    named = lambda name: next(site for site in SITES if site.name == name)
    town = Town()
    assert next_move(town)["text"] == "Go to Goldenfield Farm and buy Wheat ($4 each)."
    town.x, town.y = entrance(named("Goldenfield Farm"))
    assert next_move(town)["text"].startswith("Press Q to buy up to 4 Wheat")  # At the farm: the key
    town.interact(bulk=True)
    assert next_move(town) == {"text": "Now go to Sunrise Bakery to turn your Wheat into Bread.",
                               "target": "Sunrise Bakery"}
    town.x, town.y = entrance(named("Sunrise Bakery"))
    assert next_move(town)["text"] == "Press E to drop off your Wheat and make Bread."
    town.interact()
    assert "ready in 4s" in next_move(town)["text"]
    town.elapsed += 5
    assert next_move(town)["text"] == "Press E to collect your Bread."
    town.interact()
    assert next_move(town)["text"] == "Sell your 4 Bread at Daily Bread Market."
    town.x, town.y = entrance(named("Daily Bread Market"))
    assert next_move(town)["text"] == "Press E to sell your Bread."
    town.interact()
    # Bread is learned: suggest exploring, and stay quiet while making bread again.
    assert next_move(town) == {
        "text": "Nice work! Now explore the other buildings: each coloured sign is a new way to earn.",
        "target": None}
    town.x, town.y = entrance(named("Goldenfield Farm"))
    town.interact(bulk=True)
    assert next_move(town) is None


def test_building_hints_and_no_hints_once_every_route_is_learned():
    from browser_game import MONASTERY, next_move
    town = Town()
    assert "1 (red)" in next_move(town, "Foundry Casino")["text"]
    assert "1–4" in next_move(town, "Cacilhas Garage")["text"]
    assert "12 storage slots" in next_move(town, "Foundry Warehouse")["text"]
    assert "casino luck" in next_move(town, MONASTERY)["text"]
    town.total_sold = [1, 1, 1, 1]
    assert next_move(town) is None


def test_hints_can_be_hidden_and_show_route_sets_the_destination(monkeypatch):
    def route_button(app):
        return next(button for button in app.button if button.label.startswith("Show route"))
    app = new_app(monkeypatch)
    app.selectbox[0].select("Tool Market").run()
    assert route_button(app).label == "Show route to Goldenfield Farm" and not route_button(app).disabled
    route_button(app).click().run()
    assert app.selectbox[0].value == "Goldenfield Farm"
    assert route_button(app).disabled  # Already the destination; the button stays, so nothing moves
    app.toggle[0].set_value(False).run()
    app.selectbox[0].select("Tool Market").run()
    assert route_button(app).disabled


def test_bakery_shows_a_countdown_while_bread_is_made(monkeypatch):
    app = new_app(monkeypatch)
    choose_place(app, "Goldenfield Farm")
    click(app, "Buy up to 4 Wheat")
    choose_place(app, "Sunrise Bakery")
    assert "timer" not in streamlit_interior(app)
    click(app, "Produce or collect")
    timer = streamlit_interior(app)["timer"]
    assert timer["product"] == "Bread" and timer["quantity"] == 4 and 0 < timer["seconds"] <= 4


def streamlit_interior(app):
    """The interior data the app sends to the game view (street.js draws it)."""
    import json
    component = next(iter(app.get("component_instance")))
    return json.loads(component.proto.json_args).get("interior") or {}
