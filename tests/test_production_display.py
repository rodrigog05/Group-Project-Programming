import json

import pytest
from streamlit.testing.v1 import AppTest

from browser_game import OPEN_SITES, entrance, greeting, next_move
from tycoon import Order, Town, TRADES, pack_save, unpack_save
from scene_buttons import click_scene


def scene_data(app):
    return json.loads(app.get("component_instance")[0].proto.json_args)


def test_browser_inventory_and_routes_hide_retired_content_from_older_saves():
    town = Town()
    town.eggs = 1
    town.industry_goods["PASTELARIA"] = 1
    town.industry_orders["PASTELARIA"] = Order(1, 7)
    town.innovation["levels"]["metallurgy"] = 1
    town.innovation["goods"]["alloy_components"] = 1
    town.innovation["orders"]["alloy_components"] = {"quantity": 1, "remaining": 10}
    town.goods[3] = 2
    town.orders[3] = Order(1, 4)
    town.discovered_recipes = ["pasteis", "alloy_components", "bread", "boat_repair"]
    saved = pack_save(town, 0)
    restored, _ = unpack_save(saved)

    app = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    app.session_state.town = restored
    app.run()
    assert not app.exception
    assert {item.value for item in app.text} == {
        "Iron ore: 0", "Timber: 0", "Clay: 0", "Wheat: 0",
        "Tools: 0", "Furniture: 0", "Pottery: 0", "Bread: 2",
    }
    assert [batch["product"] for batch in scene_data(app)["production"]] == ["Bread"]
    assert any("Older save data occupies 3 bag slots" in caption.value for caption in app.caption)

    next(button for button in app.button if button.label == "Market & recipes").click().run()
    assert not app.exception
    assert set(app.dataframe[0].value["Product"]) == {"Tools", "Furniture", "Pottery", "Bread", "Boat repair"}
    descriptions = [element.value for element in app.markdown]
    assert any("**3 Sell** at Tool Market" in item for item in descriptions)
    assert any("**3 Sell** at The Pottery Shop" in item for item in descriptions)
    assert all(any(title in item for item in descriptions) for title in ("**Bread**", "**Boat repair**"))
    assert not any(name in item for item in descriptions
                   for name in ("Pastéis", "Eggs", "Alloy Components", "Oriente Tool Market", "Nations Market"))
    assert pack_save(app.session_state.town, 0) == saved


@pytest.mark.parametrize("trade", range(len(TRADES)))
@pytest.mark.parametrize("ready", [False, True])
@pytest.mark.parametrize("full", [False, True])
def test_factory_hint_is_collect_only_without_countdown(trade, ready, full):
    town = Town()
    site = next(site for site in OPEN_SITES if site.role == "FACTORY" and site.trade == trade)
    town.x, town.y = entrance(site)
    town.orders[trade] = Order(town.bag_size if full else 4, 0 if ready else 100)
    assert next_move(town, site.name)["text"] == f"Press E to collect your {TRADES[trade].product}."
    town.x, town.y = 480, 321
    hint = next_move(town)["text"]
    assert "ready" not in hint.lower()
    assert "being made" not in hint.lower()
    assert "100s" not in hint


def test_production_timer_is_separate_from_seller_recipe_and_hint():
    app = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    town = app.session_state.town
    bakery = next(site for site in OPEN_SITES if site.name == "Sunrise Bakery")
    town.x, town.y = entrance(bakery)
    town.supplies[3] = 4
    app.session_state.inside = bakery.name
    app.run()
    initial = scene_data(app)["interior"]
    click_scene(app, "Produce or collect")
    assert not app.exception
    making = scene_data(app)
    assert making["interior"]["timer"]["seconds"] > 0
    assert making["interior"]["board_text"] == initial["board_text"] == "Wheat → Bread"
    assert making["interior"]["speech"] == initial["speech"] == greeting(app.session_state.town, bakery)
    assert making["next_move"]["text"] == "Press E to collect your Bread."
    assert "Ready in" not in app.session_state.town.message
    app.session_state.town.elapsed += 5
    app.run()
    ready = scene_data(app)
    assert ready["interior"]["timer"]["seconds"] == 0
    assert ready["interior"]["board_text"] == initial["board_text"]
    assert ready["interior"]["speech"] == initial["speech"]
    assert ready["next_move"]["text"] == making["next_move"]["text"]
    click_scene(app, "Produce or collect")
    collected = scene_data(app)["interior"]
    assert "timer" not in collected
    assert app.session_state.town.goods[3] == 4
    assert "Collected 4" in collected["speech"]


@pytest.mark.parametrize("trade", range(len(TRADES)))
def test_batch_quantity_countdown_and_carried_inventory(trade):
    app = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    town = app.session_state.town
    factory = next(site for site in OPEN_SITES if site.role == "FACTORY" and site.trade == trade)
    town.x, town.y = entrance(factory)
    town.supplies[trade] = 4
    town.goods[trade] = 2
    app.session_state.inside = factory.name
    app.run()
    click_scene(app, "Produce or collect")
    town = app.session_state.town
    assert town.supplies[trade] == 0
    assert town.goods[trade] == 2
    assert app.metric[1].value == "2 / 12"
    assert f"{TRADES[trade].supply}: 0" in [item.value for item in app.text]
    assert f"{TRADES[trade].product}: 2" in [item.value for item in app.text]
    batch = scene_data(app)["production"][0]
    assert batch == {"product": TRADES[trade].product, "quantity": 4,
                     "seconds": TRADES[trade].seconds}
    # Leaving the building keeps all production visible.
    app.session_state.inside = None
    town.x, town.y = 480, 321
    town.elapsed += 1
    app.run()
    assert scene_data(app)["production"][0]["seconds"] == batch["seconds"] - 1
    assert scene_data(app)["interior"] is None
    town.elapsed = town.orders[trade].ready_at
    town.x, town.y = entrance(factory)
    app.session_state.inside = factory.name
    app.run()
    assert scene_data(app)["production"][0]["seconds"] == 0
    assert app.metric[1].value == "2 / 12"
    click_scene(app, "Produce or collect")
    assert scene_data(app)["production"] == []
    assert app.metric[1].value == "6 / 12"
    assert app.session_state.town.goods[trade] == 6
