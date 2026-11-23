import pytest
from streamlit.testing.v1 import AppTest

from browser_game import entrance, street_input, visit
from tycoon import SITES, Town
from scene_buttons import click_scene, press


def click(app, label):
    next(button for button in app.button if button.label == label).click().run()
    assert not app.exception


def choose_place(app, name):
    # AppTest does not run keyboard movement. Stage arrival, then send the same E event.
    from browser_game import entrance, street_event
    site = next(site for site in SITES if site.name == name)
    app.selectbox(key="destination").select(name).run()
    app.session_state.town.x, app.session_state.town.y = entrance(site)
    app.session_state.inside = street_event(app.session_state.town,
        {"dx": 0, "dy": 0, "seconds": 0, "action": "interact"})
    app.run()
    assert not app.exception



def test_guest_can_resume_and_requires_confirmation_to_replace_progress():
    app = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    assert next(button for button in app.button if button.label == "Continue").disabled
    click(app, "New Game")
    click(app, "Skip")
    click(app, "Start playing")
    app.session_state.town.cash = 95
    click(app, "Start menu")
    click(app, "Continue")
    assert app.metric[0].value == "$95"
    click(app, "Start menu")
    click(app, "New Game")
    click(app, "Keep my progress")
    assert app.session_state.town.cash == 95
    click(app, "New Game")
    click(app, "Replace progress")
    assert app.metric[0].value == "$60"
    assert app.session_state.town.cash == 60
    assert app.session_state.revision == 0


def test_waterfront_video_is_muted_and_only_in_the_start_menu():
    app = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    video = app.get("video")[0].proto
    assert video.autoplay and video.loop and video.muted
    click(app, "New Game")
    assert not app.get("video")


def test_browser_trade_loop_rejection_and_guest_session_isolation():
    app = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    assert not app.exception
    click(app, "New Game")
    click(app, "Skip")
    click(app, "Start playing")
    choose_place(app, "Goldenfield Farm")
    click_scene(app, "Buy up to 4 Wheat")
    assert app.metric[0].value == "$44"
    choose_place(app, "Sunrise Bakery")
    click_scene(app, "Produce or collect")
    click_scene(app, "Produce or collect")
    assert "production" in app.info[0].value.lower()
    assert "Advance time" not in {button.label for button in app.button}
    assert not app.select_slider
    # AppTest does not run JavaScript. Simulate normal clock updates from the map.
    for _ in range(60):
        assert street_input(app.session_state.town, {"dx": 0, "dy": 0, "seconds": 0.25})
    click_scene(app, "Produce or collect")
    choose_place(app, "Daily Bread Market")
    click_scene(app, "Sell carried goods")
    assert app.metric[0].value == "$100"
    assert app.session_state.town.pending_level == 1
    click(app, "Continue to Level 2")
    assert app.session_state.town.level_notices == 1
    choose_place(app, "Cacilhas Dealership")  # The only garage is across the Tejo
    press(app, "1")  # The motorcycle card
    assert app.metric[0].value == "$100"
    assert app.metric[1].value == "0 / 12"
    assert "$120" in app.info[0].value
    click(app, "Start menu")
    click(app, "Continue")
    assert app.metric[0].value == "$100"
    assert app.session_state.town.elapsed == pytest.approx(15)
    assert app.session_state.town.nearby().name == "Cacilhas Dealership"
    separate = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    assert separate.metric[0].value == "$60"
    assert next(button for button in separate.button if button.label == "Continue").disabled
    assert app.session_state.town.cash == 100


def test_pages_and_service_controls():
    app = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    for place in ("Nova SBE · Carcavelos", "Bolsa de Lisboa", "Foundry Warehouse", "Foundry Casino"):
        choose_place(app, place)
        if place == "Bolsa de Lisboa":
            click(app, "Leave exchange")
    for page in ("Market & recipes", "Landmarks"):
        click(app, page)
        assert app.session_state.town_page == page
    # Contracts, deliveries and businesses were removed from the game's menus.
    assert not {"More", "Contracts", "Deliveries", "Businesses"} & {button.label for button in app.button}
    click(app, "Game")
    assert app.session_state.town_page == "Game"


def test_exchange_opens_trading_screen_and_can_buy_sell_and_leave():
    app = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    click(app, "New Game")
    click(app, "Skip")
    click(app, "Start playing")
    choose_place(app, "Bolsa de Lisboa")
    assert any(heading.value == "Bolsa de Lisboa" for heading in app.title)
    assert any(heading.value == "Trade shares" for heading in app.subheader)
    assert any(panel.label == "Share prices and holdings" for panel in app.expander)
    assert any("0 owned" in quote.value for quote in app.markdown)
    assert not app.get("component_instance")

    click(app, "Buy shares")
    assert app.metric[0].value == "$15"
    assert any("1 owned" in quote.value for quote in app.markdown)
    click(app, "Buy shares")
    assert app.metric[0].value == "$15"
    assert "You need $45" in app.session_state.town.message

    click(app, "Sell shares")
    assert app.metric[0].value == "$55"
    assert any("0 owned" in quote.value for quote in app.markdown)
    click(app, "Sell shares")
    assert app.metric[0].value == "$55"
    assert "You only own 0 shares" in app.session_state.town.message
    click(app, "Leave exchange")
    assert app.session_state.inside is None
    assert app.get("component_instance")


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


def test_visit_by_vehicle_rejects_unaffordable_toll():
    town = Town()
    mine = next(site for site in SITES if site.name == "Iron Hill Mine")
    town.vehicle = "car"
    town.x, town.y = entrance(mine)
    town.cash = 2
    visit(town, (480, 321), "Lisboa")
    assert (town.x, town.y, town.cash) == (*entrance(mine), 2)
    assert "portagem" in town.message.lower()


def test_a_removed_page_falls_back_to_the_game():
    app = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    app.session_state.town_page = "Contracts"
    app.run()
    assert not app.exception
    assert app.session_state.town_page == "Game"
