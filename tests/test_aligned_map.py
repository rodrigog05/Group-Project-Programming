import xml.etree.ElementTree as ET

from browser_game import place_vehicle_on_road, entrance, building_at
from city_art import city_svg
from city_layout import (ROAD_COLOR, COMPACT_ROLES, CLOSED, plot_bounds, plot_center,
                         apartment_transform)
from lisbon_scene import SCENERY_PLOTS
from tycoon import SITES, Town
from vehicles import ROAD_SEGMENTS, on_road

NS={"svg":"http://www.w3.org/2000/svg"}


def test_plots_and_buildings_stay_inside_their_street_boundaries():
    town=Town()
    for site in SITES:
        left,top,right,bottom=plot_bounds(site.x,site.y)
        a,b,c,d=site.solid_bounds
        assert left <= a < c <= right,site.name
        assert top <= b < d <= bottom,site.name
        assert abs(site.door[0]-plot_center(site.x,site.y)[0]) < 1e-8
        for x,y in ((left+.1,top+.1),(right-.1,top+.1),(left+.1,bottom-.1),(right-.1,bottom-.1)):
            assert not on_road(x,y),(site.name,x,y)
        if site.name not in CLOSED:
            town.x,town.y=entrance(site)
            assert town.can_walk(town.x,town.y),site.name
            assert building_at(town)==site.name


def test_apartment_rooflines_and_facades_are_centered_with_equal_margins():
    positions=[pos for pos,kind in SCENERY_PLOTS if kind=="flats"]
    positions += [(site.x,site.y) for site in SITES if site.name in CLOSED]
    for x,y in positions:
        px,py,scale=apartment_transform(x,y)
        cx,cy=plot_center(x,y)
        assert abs((px+88*scale)-cx)<1e-8
        assert abs((py+(-17+106)/2*scale)-cy)<1e-8
        left,top,right,bottom=plot_bounds(x,y)
        assert left < px and px+176*scale < right
        assert top < py-17*scale and py+106*scale < bottom


def test_every_road_segment_uses_one_dark_asphalt_colour_in_day_and_night():
    for night in (False,True):
        doc=ET.fromstring(city_svg(night))
        layer=doc.find('.//svg:g[@data-road-layer="asphalt"]',NS)
        paths=layer.findall('svg:path',NS)
        assert len(paths)==len(ROAD_SEGMENTS)
        assert {path.attrib['stroke'] for path in paths} == {ROAD_COLOR}
        clips=doc.findall('.//svg:clipPath',NS)
        assert len([clip for clip in clips if clip.attrib['id'].startswith('plot-')]) >= len(SITES)


def test_old_position_inside_a_recentered_building_is_recovered_without_losing_progress():
    town=Town()
    site=next(site for site in SITES if site.role=="FACTORY")
    town.x,town.y=plot_center(site.x,site.y)
    cash,cargo=town.cash,town.cargo
    assert not town.can_walk(town.x,town.y)
    place_vehicle_on_road(town)
    assert town.can_walk(town.x,town.y)
    assert (town.cash,town.cargo)==(cash,cargo)
