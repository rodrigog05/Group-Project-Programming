import pytest

from browser_game import LocalSave, entrance, street_input
from ferry import FERRY_PIERS
from tycoon import SITES, Town


def input_event(dx=0, dy=0, seconds=0, action=None):
    return {"dx": dx, "dy": dy, "seconds": seconds, "action": action}


def test_street_movement_collision_and_reload(tmp_path):
    store = LocalSave(tmp_path / "street.sqlite3")
    town, revision = store.load()
    oak = next(site for site in SITES if site.name == "Oak Workshop")
    town.x, town.y = entrance(oak)
    assert street_input(town, input_event(dy=-1, seconds=0.25))
    assert oak.door[1] < town.y < entrance(oak)[1]
    assert town.nearby() == oak
    assert town.can_walk(town.x, town.y)
    assert town.elapsed == pytest.approx(0.25)
    store.save(town, revision)
    loaded, _ = store.load()
    assert (loaded.x, loaded.y, loaded.elapsed) == (town.x, town.y, town.elapsed)


def test_street_interactions_require_a_nearby_entrance_and_respect_capacity():
    town = Town()
    assert street_input(town, input_event(action="bulk"))
    assert (town.cash, town.cargo) == (60, 0)
    farm = next(site for site in SITES if site.name == "Goldenfield Farm")
    town.x, town.y = entrance(farm)
    assert street_input(town, input_event(action="egg"))
    assert (town.cash, town.eggs) == (58, 1)
    assert street_input(town, input_event(action="bulk"))
    assert (town.cash, town.supplies[3]) == (42, 4)
    town.bag_size = town.cargo
    assert street_input(town, input_event(action="interact"))
    assert (town.cash, town.supplies[3]) == (42, 4)


def test_street_ferry_and_invalid_input():
    town = Town()
    origin, destination = FERRY_PIERS
    town.x, town.y = origin.position
    assert not street_input(town, input_event(dy=-9, seconds=0.25, action="interact"))
    assert (town.x, town.y, town.cash) == (*origin.position, 60)
    assert street_input(town, input_event(action="interact"))
    assert (town.x, town.y, town.cash) == (*destination.position, 58)
