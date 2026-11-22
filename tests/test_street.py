import pytest

from browser_game import COLLISION_MAP, LocalSave, entrance, place_vehicle_on_road, street_input
from ferry import FERRY_PIERS
from lisbon_scene import SOUTH_PARK_TUNNEL
from tycoon import COLLISION_BOUNDS, SITES, Town
from vehicles import on_road


def input_event(dx=0, dy=0, seconds=0, action=None):
    return {"dx": dx, "dy": dy, "seconds": seconds, "action": action}


def test_driving_stays_on_streets_but_players_can_walk_onto_sidewalks():
    town = Town()
    town.vehicle = "car"
    town.x, town.y = 360, 301
    assert street_input(town, input_event(dy=-1, seconds=0.25))
    curb = town.y
    assert 281.5 <= curb < 301 and on_road(town.x, curb)
    assert street_input(town, input_event(dy=-1, seconds=0.25))
    assert town.y == curb
    assert street_input(town, input_event(dx=1, seconds=0.125))
    assert town.x > 360 and on_road(town.x, town.y)
    assert street_input(town, input_event(action="vehicle"))
    assert street_input(town, input_event(dy=-1, seconds=0.05))
    assert town.y < 281.5 and not on_road(town.x, town.y)
    assert street_input(town, input_event(action="vehicle"))
    assert town.vehicle is None and town.stowed_vehicle == "car"


def test_driving_from_garage_starts_on_the_street():
    town = Town()
    town.vehicle = "car"
    garage = next(site for site in SITES if site.name == "Motorworks Garage")
    town.x, town.y = garage.door
    place_vehicle_on_road(town)
    assert town.can_walk(town.x, town.y, roads_only=True)
    assert abs(town.x - garage.door[0]) < 40 and abs(town.y - garage.door[1]) < 40


def test_drive_through_tunnel_and_put_away_vehicle_without_losing_it(tmp_path):
    town = Town()
    town.vehicle = "car"
    left, right, center, _ = SOUTH_PARK_TUNNEL
    town.x, town.y = left - 10, center
    assert street_input(town, input_event(dx=1, seconds=0.25))
    assert left < town.x < right
    assert street_input(town, input_event(action="vehicle"))
    assert town.vehicle == "car"
    for _ in range(12):
        assert street_input(town, input_event(dx=1, seconds=0.25))
        if town.x > right:
            break
    assert town.x > right and town.y == center
    town.supplies[0] = town.bag_size + 1
    assert street_input(town, input_event(action="vehicle"))
    assert town.vehicle == "car"
    town.supplies[0] = 0
    assert street_input(town, input_event(action="vehicle"))
    assert (town.vehicle, town.stowed_vehicle, town.carry_capacity) == (None, "car", town.bag_size)
    store = LocalSave(tmp_path / "vehicle.sqlite3")
    store.load()
    store.save(town, 0)
    restored, _ = store.load()
    assert street_input(restored, input_event(action="vehicle"))
    assert (restored.vehicle, restored.stowed_vehicle, restored.cash) == ("car", None, town.cash)


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


def test_traffic_uses_right_hand_lanes_in_both_directions():
    from browser_game import STREET_LIFE
    lanes = {}
    for _, y, _, _, _, direction, _ in STREET_LIFE["cars"]:
        lanes.setdefault(y, set()).add(direction)
    positions = list(lanes)
    for upper, lower in zip(positions[::2], positions[1::2]):
        assert upper < lower
        assert lanes[upper] == {-1}  # Facing west, the right side is north/above.
        assert lanes[lower] == {1}   # Facing east, the right side is south/below.
