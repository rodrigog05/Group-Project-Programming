import pytest

from browser_game import COLLISION_MAP, LocalSave, entrance, street_input
from ferry import FERRY_PIERS
from tycoon import COLLISION_BOUNDS, SITES, Town


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


def test_batched_turns_match_sequential_validation_and_save(tmp_path):
    batch, sequential = Town(), Town()
    segments = [input_event(dx=1, seconds=.2), input_event(dy=1, seconds=.15),
                input_event(dx=-1, seconds=.1)]
    for segment in segments:
        assert street_input(sequential, segment)
    assert street_input(batch, {"segments": segments, "action": None})
    assert (batch.x, batch.y, batch.elapsed) == (sequential.x, sequential.y, sequential.elapsed)
    store = LocalSave(tmp_path / "batch.sqlite3")
    store.load()
    store.save(batch, 0)
    restored, _ = store.load()
    assert (restored.x, restored.y) == (batch.x, batch.y)


@pytest.mark.parametrize("segments", [
    [], [input_event(seconds=.2), input_event(dx=9, seconds=.1)],
    [input_event(seconds=.25)] * 9, [input_event(seconds=float("nan"))],
    [input_event(seconds=.01)] * 121,
])
def test_invalid_batch_cannot_move_trade_or_advance_time(segments):
    town = Town()
    before = vars(town).copy()
    assert not street_input(town, {"segments": segments, "action": "bulk"})
    assert vars(town) == before


def test_batch_collision_precedes_trade():
    town = Town()
    farm = next(site for site in SITES if site.name == "Goldenfield Farm")
    town.x, town.y = entrance(farm)
    assert street_input(town, {"segments": [input_event(dy=-1, seconds=.25)] * 2,
                               "action": "bulk"})
    assert town.can_walk(town.x, town.y)
    assert town.supplies[3] == 4 and town.cash == 44


def test_browser_collision_map_matches_python_walls():
    # street.js predicts movement with these walls, so they must be Python's own.
    assert COLLISION_MAP["boxes"] == [list(box) for box in COLLISION_BOUNDS]
    left, top, right, bottom = COLLISION_MAP["tower"]
    town = Town()
    assert not town.can_walk((left + right) / 2, (top + bottom) / 2)
    assert town.can_walk(right + COLLISION_MAP["radius"] + 5, 760)


def test_street_life_cars_drive_on_roads_and_people_never_step_onto_one():
    from browser_game import PEDESTRIAN_BODY, STREET_LIFE
    from vehicles import on_road
    for start, y, end, *_ in STREET_LIFE["cars"]:
        assert on_road(start + 5, y) and on_road(end - 5, y)
    for x1, y, x2, _, *_ in STREET_LIFE["people"]:
        # Every point of the walk, head to feet, stays off the roads, so walkers never cross traffic.
        for x in range(x1, x2 + 1, 2):
            assert not any(on_road(x + dx, y + dy) for dx in (-5, 5) for dy in PEDESTRIAN_BODY), (x, y)
    assert len(STREET_LIFE["cars"]) == 24 and len(STREET_LIFE["people"]) == 45
