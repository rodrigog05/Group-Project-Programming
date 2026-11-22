import pytest

from browser_game import LocalSave, entrance, street_input
from tycoon import Order, SITES, Town, pack_save, unpack_save
from vehicles import VEHICLES, WALK_SPEED


def driver(key="car"):
    town = Town()
    town.cash = 2000
    garage = next(site for site in SITES if site.name == "Motorworks Garage")
    town.x, town.y = entrance(garage)
    assert town.purchase_vehicle(key)
    return town


@pytest.mark.parametrize("key", VEHICLES)
def test_dismount_then_collect_owned_vehicle_without_cash(key, tmp_path):
    town = driver(key)
    cost = town.other_expenses_today
    town.cash = 0
    assert street_input(town, {"dx": 0, "dy": 0, "seconds": 0, "action": "dismount"})
    assert town.vehicle is None
    assert town.owned_vehicles == [key]
    assert town.movement_speed == WALK_SPEED
    store = LocalSave(tmp_path / "owned.sqlite3")
    _, revision = store.load()
    store.save(town, revision)
    restored, _ = store.load()
    assert restored.vehicle is None
    assert restored.purchase_vehicle(key)
    assert restored.vehicle == key
    assert (restored.cash, restored.other_expenses_today) == (0, cost)
    assert restored.owned_vehicles == [key]
    assert not restored.purchase_vehicle(key)
    assert restored.cash == 0


def test_switching_vehicles_retains_both_purchases():
    town = driver()
    assert town.purchase_vehicle("van")
    cash = town.cash
    assert town.purchase_vehicle("car")
    assert town.cash == cash
    assert town.owned_vehicles == ["car", "van"]


@pytest.mark.parametrize("reserved", [False, True])
def test_dismount_rejects_overfull_cargo_or_reservations_without_loss(reserved):
    town = driver()
    if reserved:
        town.orders[0] = Order(13, 100)
    else:
        town.goods[0] = 13
    before = pack_save(town, 0)
    assert not town.leave_vehicle()
    assert "walking bag" in town.message
    town.message = before["state"]["message"]
    assert pack_save(town, 0) == before


def test_dismount_accepts_exact_bag_capacity():
    town = driver()
    town.goods[0] = town.bag_size
    assert town.leave_vehicle()
    assert town.cargo == town.carry_capacity
    assert not town.leave_vehicle()


def test_dismount_on_bridge_is_rejected():
    town = driver()
    town.x, town.y = 300, 800
    before = town.cash, town.vehicle, town.owned_vehicles.copy(), town.x, town.y
    assert not town.leave_vehicle()
    assert (town.cash, town.vehicle, town.owned_vehicles, town.x, town.y) == before


def test_legacy_active_vehicle_is_retained_and_can_be_collected():
    town = Town()
    town.vehicle = "van"
    saved = pack_save(town, 0)
    del saved["state"]["owned_vehicles"]
    restored, _ = unpack_save(saved)
    assert restored.owned_vehicles == ["van"]
    assert restored.leave_vehicle()
    restored.cash = 0
    assert restored.purchase_vehicle("van")


def test_main_stowed_save_can_be_collected_at_garage_for_free():
    town = Town()
    town.stowed_vehicle = "car"
    saved = pack_save(town, 0)
    del saved["state"]["owned_vehicles"]
    restored, _ = unpack_save(saved)
    assert restored.owned_vehicles == ["car"]
    restored.cash = 0
    assert restored.purchase_vehicle("car")
    assert (restored.vehicle, restored.stowed_vehicle, restored.cash) == ("car", None, 0)
    assert unpack_save(pack_save(restored, 0))[0].vehicle == "car"


def test_v_toggle_and_x_dismount_share_ownership_and_tunnel_safety():
    from lisbon_scene import SOUTH_PARK_TUNNEL
    town = driver()
    left, _, center, _ = SOUTH_PARK_TUNNEL
    town.x, town.y = left + 25, center
    assert street_input(town, {"dx": 0, "dy": 0, "seconds": 0, "action": "dismount"})
    assert town.vehicle == "car" and town.stowed_vehicle is None
    assert "tunnel" in town.message
    town.x, town.y = 360, 301
    for action in ("vehicle", "vehicle", "dismount"):
        assert street_input(town, {"dx": 0, "dy": 0, "seconds": 0, "action": action})
    assert town.vehicle is None and town.stowed_vehicle == "car"
    assert town.owned_vehicles == ["car"]
    town.cash = 0
    assert town.purchase_vehicle("car")
    assert town.stowed_vehicle is None and town.cash == 0


@pytest.mark.parametrize("owned", [None, "car", ["car", "car"], ["spaceship"], [{}]])
def test_invalid_ownership_is_rejected(owned):
    saved = pack_save(Town(), 0)
    saved["state"]["owned_vehicles"] = owned
    with pytest.raises(ValueError, match="owned vehicles"):
        unpack_save(saved)


@pytest.mark.parametrize("key,offroad,road", [
    ("motorcycle", 420, 520), ("car", 510, 690), ("van", 430, 620), ("f1", 350, 900),
])
def test_every_drive_speed_is_reduced_by_thirty_percent(key, offroad, road):
    assert VEHICLES[key].offroad_speed == pytest.approx(offroad * .7)
    assert VEHICLES[key].road_speed == pytest.approx(road * .7)


def test_garage_free_collection_and_green_bet_controls(monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.delenv("FOUNDRY_LOCAL_DB", raising=False)
    app = AppTest.from_file("../streamlit_app.py", default_timeout=15).run()
    town = app.session_state.town
    town.cash = 1000
    garage = next(site for site in SITES if site.name == "Cacilhas Garage")  # The only open garage
    town.x, town.y = entrance(garage)
    app.session_state.inside = garage.name
    app.run()
    assert not app.exception
    next(b for b in app.button if b.key == "vehicle-car").click().run()
    assert app.session_state.town.vehicle == "car"
    assert app.session_state.town.cash == 760
    assert app.session_state.town.leave_vehicle()
    app.session_state.town.cash = 0
    # Getting off moves the walker onto the pavement; walk back to the garage door.
    app.session_state.town.x, app.session_state.town.y = entrance(garage)
    app.session_state.inside = garage.name
    app.run()
    retrieve = next(b for b in app.button if b.key == "vehicle-car")
    assert retrieve.label == "Drive Car · Free"
    assert not retrieve.disabled
    retrieve.click().run()
    assert not app.exception
    assert app.session_state.town.vehicle == "car"
    assert app.session_state.town.cash == 0
    casino = next(site for site in SITES if site.role == "CASINO")
    app.session_state.town.x, app.session_state.town.y = entrance(casino)
    app.session_state.inside = casino.name
    app.run()
    assert not app.exception
    green = next(b for b in app.button if b.key == "bet_green")
    assert green.label == "Green 0 · pays 36×"
    green.click().run()
    assert not app.exception
    assert "cash" in app.session_state.town.message
