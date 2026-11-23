"""Public-space artwork stays inside its plot and agrees with movement rules."""
import xml.etree.ElementTree as ET

from browser_game import COLLISION_MAP
from city_art import city_svg
from city_layout import plot_bounds
from lisbon_scene import PARK_BOUNDS, SCENERY_BLOCKS, vehicle_park_blocked
from public_spaces import (
    EXPANDED_GARDENS, EXPANDED_SQUARE, LAKE, LAKE_PLOT,
    garden_bounds, square_bounds, fountain_bounds,
)
from tycoon import Town


def test_requested_gardens_and_square_fill_their_plots_without_covering_curbs():
    for position in EXPANDED_GARDENS | {EXPANDED_SQUARE}:
        left,top,right,bottom=plot_bounds(*position)
        bounds=(garden_bounds if position in EXPANDED_GARDENS else square_bounds)(*position)
        assert bounds == (left+10,top+10,right-10,bottom-10)
        assert bounds[2]-bounds[0] > 176
        assert bounds[3]-bounds[1] > 104
        if position in EXPANDED_GARDENS:
            assert bounds in PARK_BOUNDS
            assert list(bounds) in COLLISION_MAP["parks"]
            assert vehicle_park_blocked(bounds[0]+2,bounds[1]+2)
            assert Town().can_walk(bounds[0]+15,bounds[1]+15)


def test_lake_water_blocks_walking_but_the_surrounding_path_is_accessible():
    town=Town()
    assert COLLISION_MAP["lake"] == list(LAKE)
    assert LAKE_PLOT in PARK_BOUNDS
    assert not town.can_walk(905,1650)
    assert not town.can_walk(905,1699)
    for x,y in ((905,1585),(905,1715),(667,1650),(1143,1650)):
        assert town.can_walk(x,y)
        assert vehicle_park_blocked(x,y)
    assert town.can_walk(905,1750)


def test_larger_fountain_basin_matches_browser_and_python_collision():
    bounds=fountain_bounds(*EXPANDED_SQUARE)
    assert bounds in SCENERY_BLOCKS
    assert list(bounds) in COLLISION_MAP["boxes"]
    assert not Town().can_walk(1905,1420)
    assert Town().can_walk(1905,1490)


def test_day_and_night_art_has_six_lakeside_benches_and_no_public_space_labels():
    ns={"s":"http://www.w3.org/2000/svg"}
    for night in (False,True):
        doc=ET.fromstring(city_svg(night))
        lake=doc.find('.//s:g[@data-kind="lake-park"]',ns)
        assert lake is not None
        assert len(lake.findall('s:g[@data-kind="bench"]',ns)) == 6
        visible=[node.text for node in doc.findall('.//s:text',ns)]
        assert not any(text and ("GARDEN" in text or text=="SQUARE") for text in visible)
