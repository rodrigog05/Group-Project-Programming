from pathlib import Path

from streamlit.testing.v1 import AppTest

from browser_game import MONASTERY, building_at, entrance, greeting, scene_for
from ferry import FERRY_PIERS
from lisbon_landmarks import LANDMARKS
from tycoon import ROULETTE_POCKETS, SITES, Town, roulette_color
from scene_buttons import click_scene, press, scene, scene_labels

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


def new_app():
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
    assert plain == {"EXCHANGE"}  # Nova SBE now shows the team's presentation
    assert (SCENES / "ferry_day.webp").is_file() and (SCENES / "ferry_night.webp").is_file()


def test_monastery_luck_is_capped_at_twenty_points():
    town = Town()
    for _ in range(6):
        town.visit_monastery()
    assert town.casino_luck == 20


# ----- Inside buildings in the app -----


def test_nova_sbe_presentation_has_only_exit_and_preserves_progress():
    from copy import deepcopy
    app = new_app()
    town = app.session_state.town
    before = town.cash, list(town.supplies), list(town.goods), deepcopy(town.innovation)
    choose_place(app, "Nova SBE · Carcavelos")
    room = streamlit_interior(app)
    assert room["scene"] == "nova_presentation"
    assert room["size"] == [1448, 1086]
    assert room["bubble"] is None and room["board"] is None
    assert room["accepts"] == ["escape"]
    assert room["keys"] == [["escape", "Leave"]]
    assert not app.get("number_input")
    assert not any("research" in label.lower() or "craft" in label.lower() for label in labels(app))
    assert (town.cash, town.supplies, town.goods, town.innovation) == before
    press(app, "escape")
    assert app.session_state.inside is None


def test_english_names_are_visible_without_changing_saved_identifiers():
    import json
    from browser_game import OPEN_SITES
    from place_names import PLACE_NAMES, place_name
    app = new_app()
    options = app.selectbox[0].options
    assert {place_name(site.name) for site in OPEN_SITES} <= set(options)
    assert not {name for name, label in PLACE_NAMES.items() if name != label} & set(options)
    choose_place(app, "Goldenfield Farm")
    room = streamlit_interior(app)
    assert room["title"] == "Goldenfield Farm"
    assert app.session_state.inside == "Goldenfield Farm"
    assert not app.subheader  # The translated name stays in the scene, not repeated below it.
    component = next(iter(app.get("component_instance")))
    locations = json.loads(component.proto.json_args)["locations"]
    assert {item["name"] for item in locations} >= {place_name(site.name) for site in OPEN_SITES}


def test_browser_clock_leaves_retired_research_untouched():
    from copy import deepcopy
    from browser_game import advance_clock
    town = Town()
    town.cash = 10000
    town.start_research("metallurgy")
    before = deepcopy(town.innovation)
    advance_clock(town, 1)
    assert town.innovation == before


def test_visit_enters_the_building_and_leave_returns_to_the_street():
    app = new_app()
    choose_place(app, "Goldenfield Farm")
    assert {"Buy up to 4 Wheat", "Leave"} <= set(scene_labels(app))  # Buttons drawn in the scene
    assert not {"Buy up to 4 Wheat", "Leave"} & labels(app)  # Not repeated under the map
    assert not {"Buy 1 egg", "Buy up to 4 eggs"} & set(scene_labels(app))  # Eggs were removed from the game
    click_scene(app, "Buy up to 4 Wheat")
    assert app.metric[0].value == "$44"
    assert "Wheat" in app.session_state.reply  # The vendor answers inside the speech bubble
    click_scene(app, "Leave")
    assert app.session_state.inside is None and not scene(app)
    assert "Enter Goldenfield Farm" not in labels(app)
    choose_place(app, "Goldenfield Farm")
    assert "Buy up to 4 Wheat" in scene_labels(app)


def test_casino_spin_pays_by_colour_and_rejects_an_unaffordable_chip():
    app = new_app()
    choose_place(app, "Foundry Casino")
    assert not any("pays" in label for label in labels(app))  # The bets are only in the scene
    click_scene(app, "Red · pays 2×")
    spin = app.session_state.spin
    expected = 70 if roulette_color(spin["number"]) == "red" else 50
    assert app.session_state.town.cash == expected
    assert spin["number"] in ROULETTE_POCKETS and spin["id"] == 1
    click_scene(app, "Black · pays 2×")  # Rejected while the wheel is still turning
    assert app.session_state.town.cash == expected
    assert app.session_state.spin["id"] == 1

    app.session_state.spin["ends_at"] = 0
    app.session_state.town.cash = 4
    app.run()
    click_scene(app, "Green 0 · pays 36×")
    assert app.session_state.town.cash == 4
    assert app.session_state.spin["id"] == 1  # No new spin
    assert "need $10" in app.session_state.reply


def test_monastery_visit_shows_the_prayer_and_adds_luck():
    app = new_app()
    left, _, right, bottom = LANDMARKS[0].bounds
    town = app.session_state.town
    town.x, town.y = (left + right) / 2, bottom + 16
    app.session_state.inside = MONASTERY
    app.run()
    assert not app.exception
    assert any("Casino luck" in caption.value for caption in app.caption)


# ----- Ferry crossings are animated -----

def test_crossbank_destination_gives_ferry_directions_without_travelling():
    from navigation import directions
    from browser_game import street_event
    app = new_app()
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

def test_new_game_opens_the_basics_and_the_slides_page_through():
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


def test_basics_slide_assets_exist():
    slides = Path(__file__).resolve().parents[1] / "street" / "tutorial"
    for name in ("goal", "buy", "make", "sell", "garage"):
        assert (slides / f"{name}.webp").is_file(), name



# ----- Simplified town -----

def test_closed_buildings_cannot_be_entered_and_are_not_destinations():
    from browser_game import CLOSED_SITES, OPEN_SITES, street_event
    assert CLOSED_SITES == {"Motorworks Garage", "Armazém do Seixal", "Pastéis de Belém"}
    assert [site.name for site in OPEN_SITES if site.role == "GARAGE"] == ["Cacilhas Dealership"]
    assert [site.name for site in OPEN_SITES if site.role == "WAREHOUSE"] == ["Foundry Warehouse"]
    town = Town()
    garage = next(site for site in SITES if site.name == "Motorworks Garage")
    town.x, town.y = entrance(garage)
    assert street_event(town, {"dx": 0, "dy": 0, "seconds": 0, "action": "interact"}) is None
    assert "apartments" in town.message and town.cash == 60
    app = new_app()
    options = set(app.selectbox[0].options)
    from place_names import place_name
    assert not {place_name(name) for name in CLOSED_SITES} & options
    assert {"Cacilhas Dealership", "Foundry Warehouse", "Palmela Farm", "Tagus Shipyard", "Nations Market"} <= options


def test_warehouse_has_a_scene_and_the_farm_sells_only_wheat():
    from browser_game import scene_for
    town = Town()
    warehouse = next(site for site in SITES if site.name == "Foundry Warehouse")
    assert scene_for(town, warehouse)[0] == "warehouse"
    assert "12 slots" in greeting(town, warehouse)
    farm = next(site for site in SITES if site.name == "Goldenfield Farm")
    assert "Egg" not in greeting(town, farm)


def test_market_shows_four_route_cards_and_the_goal_bar():
    app = new_app()
    assert app.get("progress")[0].proto.text == "LEVEL 1/3 · Sell a product 0/1"
    assert app.get("progress")[0].proto.value == 0
    click(app, "Market & recipes")
    text = " ".join(markdown.value for markdown in app.markdown)
    for product in ("Tools", "Furniture", "Pottery", "Bread"):
        assert product in text
    assert "Profit \\$10 per bread" in text and "Goldenfield Farm" in text
    assert "Armazém de Cereais" not in text
    assert "Pastéis" not in text


# ----- Next-move hint and the production countdown -----

def test_hints_say_where_to_go_then_go_in_then_which_key_to_press():
    from browser_game import next_move
    named = lambda name: next(site for site in SITES if site.name == name)
    town = Town()
    assert next_move(town)["text"] == "Go to Goldenfield Farm and buy Wheat ($4 each)."
    town.x, town.y = entrance(named("Goldenfield Farm"))
    # At the door, still outside: go in (Q on the street would buy without entering).
    assert next_move(town)["text"] == "Press E to go into Goldenfield Farm."
    assert next_move(town, "Goldenfield Farm")["text"].startswith("Press Q to buy up to 4 Wheat")
    town.interact(bulk=True)
    assert next_move(town, "Goldenfield Farm") == {"text": "Now go to Sunrise Bakery to turn your Wheat into Bread.",
                                                   "target": "Sunrise Bakery"}
    town.x, town.y = entrance(named("Sunrise Bakery"))
    assert next_move(town)["text"] == "Press E to go into Sunrise Bakery."
    assert next_move(town, "Sunrise Bakery")["text"] == "Press E to drop off your Wheat and make Bread."
    town.interact()
    assert next_move(town, "Sunrise Bakery")["text"] == "Press E to collect your Bread."
    town.elapsed += 5
    assert next_move(town, "Sunrise Bakery")["text"] == "Press E to collect your Bread."
    town.interact()
    assert next_move(town, "Sunrise Bakery")["text"] == "Sell your 4 Bread at Daily Bread Market."
    town.x, town.y = entrance(named("Daily Bread Market"))
    assert next_move(town, "Daily Bread Market")["text"] == "Press E to sell your Bread."
    town.interact()
    # Bread is learned: a general invitation to explore, and quiet while making bread again.
    assert next_move(town, "Daily Bread Market") == {
        "text": "Nice work! Now explore the other buildings: each coloured sign is a new way to earn.",
        "target": None}
    town.x, town.y = entrance(named("Goldenfield Farm"))
    town.interact(bulk=True)
    assert next_move(town, "Goldenfield Farm") is None


def test_hints_guide_a_new_route_from_whichever_of_its_stores_you_enter():
    from browser_game import next_move
    named = lambda name: next(site for site in SITES if site.name == name)
    town = Town()
    town.total_sold[3] = 4  # Bread already learned
    town.x, town.y = entrance(named("Redbank Clay Pit"))
    assert next_move(town)["text"] == "Press E to go into Redbank Clay Pit."
    assert next_move(town, "Redbank Clay Pit")["text"] == "Press Q to buy up to 4 Clay ($6 each)."
    town.interact(bulk=True)
    assert next_move(town, "Redbank Clay Pit")["text"] == "Now go to Ember Kiln to turn your Clay into Pottery."
    other = Town()
    other.total_sold[3] = 4
    other.x, other.y = entrance(named("Ember Kiln"))
    assert next_move(other, "Ember Kiln") == {
        "text": "Ember Kiln makes Pottery from Clay. Start by buying Clay at Redbank Clay Pit.",
        "target": "Redbank Clay Pit"}
    for supplier, supply in (("Pine Mill", "Timber"), ("Iron Hill Mine", "Iron ore")):
        other.x, other.y = entrance(named(supplier))
        assert next_move(other, supplier)["text"].startswith(f"Press Q to buy up to 4 {supply}")
    other.supplies[3] = 4  # Busy with bread, but a new route's store still explains itself
    other.x, other.y = entrance(named("Pine Mill"))
    assert next_move(other, "Pine Mill")["text"].startswith("Press Q to buy up to 4 Timber")


def test_building_hints_and_no_hints_once_every_route_is_learned():
    from browser_game import MONASTERY, next_move
    town = Town()
    assert "1 (red)" in next_move(town, "Foundry Casino")["text"]
    assert "1–4" in next_move(town, "Cacilhas Dealership")["text"]
    assert "12 storage slots" in next_move(town, "Foundry Warehouse")["text"]
    assert "casino luck" in next_move(town, MONASTERY)["text"]
    town.total_sold = [1, 1, 1, 1]
    assert next_move(town) is None


def test_hints_can_be_hidden_and_show_route_sets_the_destination():
    def route_button(app):
        return next(button for button in app.button if button.label.startswith("Show route"))
    app = new_app()
    app.selectbox[0].select("Tool Market").run()
    assert route_button(app).label == "Show route to Goldenfield Farm" and not route_button(app).disabled
    route_button(app).click().run()
    assert app.selectbox[0].value == "Goldenfield Farm"
    assert route_button(app).disabled  # Already the destination; the button stays, so nothing moves
    app.toggle[0].set_value(False).run()
    app.selectbox[0].select("Tool Market").run()
    assert route_button(app).disabled


def test_bakery_shows_a_countdown_while_bread_is_made():
    app = new_app()
    choose_place(app, "Goldenfield Farm")
    click_scene(app, "Buy up to 4 Wheat")
    choose_place(app, "Sunrise Bakery")
    assert "timer" not in streamlit_interior(app)
    click_scene(app, "Produce or collect")
    timer = streamlit_interior(app)["timer"]
    assert timer["product"] == "Bread" and timer["quantity"] == 4 and 0 < timer["seconds"] <= 4


def streamlit_interior(app):
    """The interior data the app sends to the game view (street.js draws it)."""
    import json
    component = next(iter(app.get("component_instance")))
    return json.loads(component.proto.json_args).get("interior") or {}


# ----- Full bag -----

def test_full_bag_hint_says_to_make_or_sell_on_any_route():
    from browser_game import bag_full, next_move
    named = lambda name: next(site for site in SITES if site.name == name)
    town = Town()
    town.cash, town.total_sold[3] = 500, 4  # Even on a learned route
    town.x, town.y = entrance(named("Goldenfield Farm"))
    for _ in range(3):
        town.interact(bulk=True)
    assert bag_full(town)
    assert next_move(town, "Goldenfield Farm") == {
        "text": "Your bag is full (12/12). Take your Wheat to Sunrise Bakery to make Bread.",
        "target": "Sunrise Bakery"}
    town.x, town.y = entrance(named("Sunrise Bakery"))
    assert next_move(town, "Sunrise Bakery")["text"] == "Press E to drop off your Wheat and make Bread."
    town.interact()
    town.elapsed += 5
    town.interact()
    assert next_move(town, "Sunrise Bakery")["text"] == "Your bag is full (12/12). Sell your 12 Bread at Daily Bread Market."


def test_buying_with_a_full_bag_raises_the_red_warning_only_then():
    app = new_app()
    app.session_state.town.cash = 500
    choose_place(app, "Goldenfield Farm")
    for _ in range(3):
        click_scene(app, "Buy up to 4 Wheat")
    assert app.metric[1].value == "12 / 12" and "alert" not in app.session_state  # Room until now
    click_scene(app, "Buy up to 4 Wheat")
    assert app.session_state.alert == {"id": 1, "text": "Your bag is full"}
    assert app.metric[1].value == "12 / 12"
    assert app.session_state.reply is None  # The farmer keeps his greeting; the banner explains



def test_full_bag_inside_a_new_routes_supplier_says_sell_not_buy():
    from browser_game import next_move
    named = lambda name: next(site for site in SITES if site.name == name)
    town = Town()
    town.total_sold[3] = 4  # Bread learned, as in the reported case
    town.goods[3] = 12      # A full bag of bread
    town.x, town.y = entrance(named("Redbank Clay Pit"))
    assert next_move(town, "Redbank Clay Pit") == {
        "text": "Your bag is full (12/12). Sell your 12 Bread at Daily Bread Market.",
        "target": "Daily Bread Market"}


def test_garage_sends_one_card_per_vehicle_with_its_status():
    app = new_app()
    town = app.session_state.town
    town.cash, town.owned_vehicles = 300, ["motorcycle"]
    garage = next(site for site in SITES if site.name == "Cacilhas Dealership")
    town.x, town.y = entrance(garage)
    app.session_state.inside = garage.name
    app.run()
    cards = streamlit_interior(app)["showroom"]
    assert [card["label"] for card in cards] == ["Motorcycle", "Car", "Delivery van", "F1 car"]
    assert [card["status"] for card in cards] == ["owned", "buy", "buy", "buy"]
    assert [card["affordable"] for card in cards] == [True, True, False, False]
    assert cards[1]["trunk"] == 48 and cards[1]["cargo"] == 60
    assert streamlit_interior(app)["keys"] == [["1–4", "Choose a vehicle"], ["escape", "Leave"]]


def test_drivers_enter_the_dealership_from_the_road_in_front():
    from browser_game import building_at, street_event
    dealer = next(site for site in SITES if site.name == "Cacilhas Dealership")
    door_x, _ = dealer.door
    driver = Town()
    driver.vehicle = "car"
    driver.x, driver.y = door_x + 20, 1550  # On the road lane in front of the forecourt
    assert building_at(driver) == "Cacilhas Dealership"
    assert street_event(driver, {"dx": 0, "dy": 0, "seconds": 0, "action": "interact"}) == "Cacilhas Dealership"
    driver.x = door_x + 90  # Further along the road: not in front of it any more
    assert building_at(driver) is None
    walker = Town()
    walker.x, walker.y = door_x, 1550  # On foot, use the door itself
    assert building_at(walker) is None
