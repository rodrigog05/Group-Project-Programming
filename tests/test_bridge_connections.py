import math

from browser_game import COLLISION_MAP
from lisbon_scene import RIVER_TOP, RIVER_BOTTOM, VASCO_NORTH_X, bridge_center, south
from tycoon import Town
from vehicles import ROAD_SEGMENTS, on_road


def test_vasco_approaches_meet_the_deck_endpoints_and_city_roads():
    deck = next(segment for segment in ROAD_SEGMENTS if segment[1] == RIVER_TOP-20 and segment[4] == 22.5)
    north = next(segment for segment in ROAD_SEGMENTS if segment[:2] == (VASCO_NORTH_X, 660) and segment[3] == RIVER_TOP-20)
    south_approach = next(segment for segment in ROAD_SEGMENTS if segment[1] == RIVER_BOTTOM+19 and segment[3] == south(1058))
    assert north[2:4] == deck[:2]
    assert south_approach[:2] == deck[2:4]
    assert south_approach[2:4] == (VASCO_NORTH_X, south(1058))
    assert tuple(COLLISION_MAP["roads"]) == ROAD_SEGMENTS


def test_vasco_can_be_driven_from_street_to_street_in_both_directions():
    route = ((VASCO_NORTH_X,650),(bridge_center(RIVER_TOP-20,True),RIVER_TOP-20),
             (bridge_center(RIVER_BOTTOM+19,True),RIVER_BOTTOM+19), (VASCO_NORTH_X,south(1058)))
    for points in (route, route[::-1]):
        town = Town()
        town.vehicle = "car"
        town.cash = 100
        town.x,town.y = points[0]
        for start,end in zip(points,points[1:]):
            steps=math.ceil(math.dist(start,end)/2)
            for step in range(1,steps+1):
                x=start[0]+(end[0]-start[0])*step/steps
                y=start[1]+(end[1]-start[1])*step/steps
                assert on_road(x,y), (x,y)
                assert town.can_walk(x,y,roads_only=True), (x,y)
                town.x,town.y=x,y
        assert math.dist((town.x,town.y),points[-1]) < .001
