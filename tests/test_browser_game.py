import pytest
from streamlit.testing.v1 import AppTest

from browser_game import LocalSave, SaveConflict, advance_clock, entrance, street_input, visit
from tycoon import SITES, Town, pack_save, unpack_save
from scene_buttons import click_scene, press


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



def test_start_menu_can_resume_and_requires_confirmation_to_replace_save(tmp_path, monkeypatch):
    path = tmp_path / "game.sqlite3"
    monkeypatch.setenv("FOUNDRY_LOCAL_DB", str(path))
    store = LocalSave(path)
    town, revision = store.load()
    town.cash = 95
    store.save(town, revision)
    app = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    click(app, "Continue")
    assert app.metric[0].value == "$95"
    click(app, "Start menu")
    click(app, "New Game")
    click(app, "Keep my progress")
    assert store.load()[0].cash == 95
    click(app, "New Game")
    click(app, "Replace progress")
    assert app.metric[0].value == "$60"
    assert store.load()[0].cash == 60


def test_character_choice_edit_and_save(tmp_path, monkeypatch):
    path = tmp_path / "game.sqlite3"
    monkeypatch.setenv("FOUNDRY_LOCAL_DB", str(path))
    app = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    app.text_input[0].set_value("Rodrigo").run()
    next(box for box in app.selectbox if box.label == "Skin").select("Mint").run()
    next(box for box in app.selectbox if box.label == "Hair").select("Chestnut").run()
    next(box for box in app.selectbox if box.label == "Outfit").select("Wizard").run()
    click(app, "New Game")
    assert app.session_state.town.profile == store_profile(path, "Rodrigo", "Mint", "Wizard")
    click(app, "Skip")
    click(app, "Start playing")
    click(app, "Edit character")
    next(box for box in app.selectbox if box.label == "Skin").select("Amber").run()
    click(app, "Save character")
    assert app.session_state.town.profile["body"] == "Amber"
    assert LocalSave(path).load()[0].profile["body"] == "Amber"


def store_profile(path, name, body, costume):
    profile = LocalSave(path).load()[0].profile
    assert profile["name"] == name
    assert profile["body"] == body
    assert profile["costume"] == costume
    return profile


def test_character_save_validation_and_legacy_default():
    saved = pack_save(Town(), 1_000)
    saved["state"].pop("profile")
    assert unpack_save(saved)[0].profile == Town().profile
    saved["state"]["profile"] = {"name": "X", "body": [], "hair": "Chestnut", "costume": "Builder"}
    with pytest.raises(ValueError, match="Invalid character"):
        unpack_save(saved)


def test_level_dialogs_and_saved_progress(tmp_path, monkeypatch):
    path = tmp_path / "game.sqlite3"
    monkeypatch.setenv("FOUNDRY_LOCAL_DB", str(path))
    store = LocalSave(path)
    town, revision = store.load()
    town.total_sold[0] = 1
    town.cash = 500
    town.won = True
    store.save(town, revision)
    app = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    click(app, "Continue")
    assert "### Level 1 complete!" in [item.value for item in app.markdown]
    click(app, "Continue to Level 2")
    assert store.load()[0].first_trade_acknowledged
    assert "### Level 2 complete!" in [item.value for item in app.markdown]
    click(app, "Not now")
    assert not store.load()[0].milestone_acknowledged
    click(app, "Continue to Level 3")
    assert store.load()[0].milestone_acknowledged
    app.session_state.town.add_cash(1500)
    app.run()
    assert "### You successfully completed the game! Good job!" in [item.value for item in app.markdown]
    click(app, "Finish")
    assert store.load()[0].game_completed_acknowledged
    reloaded = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    click(reloaded, "Continue")
    assert "Game complete!" in [item.text for item in reloaded.progress]


def test_level_progress_defaults_for_old_saves_and_rejects_invalid_flags():
    old = pack_save(Town(), 1_000)
    for key in ("first_trade_acknowledged", "game_completed_acknowledged"):
        old["state"].pop(key)
    restored, _ = unpack_save(old)
    assert not restored.first_trade_acknowledged and not restored.game_completed_acknowledged
    old["state"]["first_trade_acknowledged"] = "yes"
    with pytest.raises(ValueError, match="Invalid level progress"):
        unpack_save(old)


def test_waterfront_video_is_muted_and_only_in_the_start_menu(monkeypatch):
    monkeypatch.delenv("FOUNDRY_LOCAL_DB", raising=False)
    app = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    video = app.get("video")[0].proto
    assert video.autoplay and video.loop and video.muted
    click(app, "New Game")
    assert not app.get("video")


def test_browser_trade_loop_rejection_restart_and_session_isolation(tmp_path, monkeypatch):
    monkeypatch.setenv("FOUNDRY_LOCAL_DB", str(tmp_path / "game.sqlite3"))
    app = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    assert not app.exception
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
    choose_place(app, "Cacilhas Dealership")  # The only garage is across the Tejo
    press(app, "1")  # The motorcycle card
    assert app.metric[0].value == "$100"
    assert app.metric[1].value == "0 / 12"
    assert "$120" in app.info[0].value
    reloaded = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    assert reloaded.metric[0].value == "$100"
    assert reloaded.session_state.town.elapsed == pytest.approx(15)
    assert reloaded.session_state.town.nearby().name == "Cacilhas Dealership"
    monkeypatch.delenv("FOUNDRY_LOCAL_DB")
    separate = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    assert separate.metric[0].value == "$60"


def test_pages_and_service_controls(monkeypatch):
    monkeypatch.delenv("FOUNDRY_LOCAL_DB", raising=False)
    app = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    for place in ("Nova SBE · Carcavelos", "Bolsa de Lisboa", "Foundry Warehouse", "Foundry Casino"):
        choose_place(app, place)
    for page in ("Market & recipes", "Landmarks"):
        click(app, page)
        assert app.session_state.town_page == page
    # Contracts, deliveries and businesses were removed from the game's menus.
    assert not {"More", "Contracts", "Deliveries", "Businesses"} & {button.label for button in app.button}
    click(app, "Game")
    assert app.session_state.town_page == "Game"


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
    for _ in range(121):
        advance_clock(first, 1)
    assert first.day == 2
    assert store.save(first, revision) == 1
    with pytest.raises(SaveConflict):
        store.save(stale, stale_revision)
    reloaded, revision = store.load()
    assert revision == 1
    assert reloaded.elapsed == reloaded.market_elapsed == 121
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


def test_a_removed_page_falls_back_to_the_game(monkeypatch):
    monkeypatch.delenv("FOUNDRY_LOCAL_DB", raising=False)
    app = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    app.session_state.town_page = "Contracts"
    app.run()
    assert not app.exception
    assert app.session_state.town_page == "Game"
