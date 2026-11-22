"""The drawn buildings and browser collision rules must agree about the new yards."""
from pathlib import Path
import xml.etree.ElementTree as ET

from browser_game import COLLISION_MAP, building_at, entrance
from city_art import CLOSED, COMPACT_ROLES, city_svg, presentation_svg
from tycoon import COLLISION_BOUNDS, SITES, Town
from place_names import PLACE_NAMES, localize_place_names


def test_compact_buildings_have_walkable_yards_and_keep_their_entrances():
    town = Town()
    for site in SITES:
        if site.role not in COMPACT_ROLES or site.name in CLOSED:
            continue
        left, top, right, bottom = site.solid_bounds
        assert right-left == 128 and bottom-top == 80
        assert site.solid_bounds in COLLISION_BOUNDS
        assert list(site.solid_bounds) in COLLISION_MAP["boxes"]
        assert not town.can_walk((left+right)/2, (top+bottom)/2)
        assert town.can_walk(site.x+8, site.y+64), site.name
        assert town.can_walk(site.x+168, site.y+64), site.name
        town.x, town.y = entrance(site)
        assert town.can_walk(town.x, town.y), site.name
        assert building_at(town) == site.name
        assert site.door == (site.x+88, site.y+104)


def test_closed_apartments_keep_their_full_collision_footprint():
    for site in SITES:
        if site.name in CLOSED:
            assert site.solid_bounds == site.bounds


def test_shipped_vector_assets_match_their_sources_and_contain_no_photographs():
    root = Path(__file__).resolve().parents[1] / "street"
    ns = {"svg": "http://www.w3.org/2000/svg"}
    for night in (False, True):
        markup = city_svg(night)
        assert (root / f'city_{"night" if night else "day"}.svg').read_text(encoding="utf-8") == markup
        doc = ET.fromstring(markup)
        visible = " ".join(node.text or "" for node in doc.findall(".//svg:text", ns))
        assert not any(name in visible for name, label in PLACE_NAMES.items() if name != label)
        drawn = {group.attrib["data-site"] for group in doc.findall("svg:g", ns) if "data-site" in group.attrib}
        assert drawn == {s.name for s in SITES if s.role in COMPACT_ROLES and s.name not in CLOSED}
    markup = presentation_svg()
    doc = ET.fromstring(markup)
    assert not doc.findall(".//svg:image", ns)
    assert "Foundry Town" in markup and "CARCAVELOS" in markup
    assert (root / "scenes" / "nova_presentation.svg").read_text(encoding="utf-8") == markup


def test_overlapping_shop_names_translate_without_changing_identifiers():
    assert localize_place_names("Oriente Tool Market · Tool Market") == "Oriente Tool Market · Tool Market"
    assert localize_place_names("Mercado das Nações · Estaleiro do Tejo") == "Nations Market · Tagus Shipyard"
    assert localize_place_names("Nova SBE · Carcavelos") == "Nova SBE · Carcavelos"
