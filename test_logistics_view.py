from copy import deepcopy
from types import SimpleNamespace
import unittest

from logistics_view import FleetView, MAX_VISIBLE_ROUTES


class Canvas:
    """Small retained-canvas double, recording allocations and transformed items."""

    def __init__(self):
        self.items, self.moves, self.deleted = {}, [], []
        self.next_id = 0

    def __getattr__(self, name):
        if name.startswith("create_"):
            return self.create
        raise AttributeError(name)

    def create(self, *coords, **options):
        self.next_id += 1
        self.items[self.next_id] = [list(coords), options.copy()]
        return self.next_id

    def selected(self, tag):
        return [item for key, item in self.items.items() if key == tag or item[1].get("tags") == tag]

    def itemconfigure(self, tag, **options):
        for item in self.selected(tag):
            item[1].update(options)

    def move(self, tag, dx, dy):
        self.moves.append((tag, dx, dy))
        for coords, _ in self.selected(tag):
            for i in range(0, len(coords), 2):
                coords[i], coords[i+1] = coords[i]+dx, coords[i+1]+dy

    def scale(self, tag, x, y, sx, sy):
        for coords, _ in self.selected(tag):
            for i in range(0, len(coords), 2):
                coords[i], coords[i+1] = x+(coords[i]-x)*sx, y+(coords[i+1]-y)*sy

    def delete(self, tag):
        self.deleted.append(tag)
        self.items = {key: item for key, item in self.items.items() if item[1].get("tags") != tag}


class FleetRenderingTest(unittest.TestCase):
    def setUp(self):
        self.canvas = Canvas()
        self.positions = []

        def position(route, sites):
            self.positions.append(route["id"])
            return route["test_position"]

        self.fleet = FleetView(self.canvas, (), zoom=1.25, position_fn=position)
        self.camera = SimpleNamespace(sees=lambda x, y, margin: 0 <= x <= 1000 and 104 <= y <= 800)

    def route(self, route_id=1, kind="van", position=(200, 300), load=2):
        return {"id": route_id, "kind": kind, "phase": "outbound", "load": load,
                "test_position": position}

    def test_empty_fleet_does_no_position_work_or_canvas_allocations(self):
        for _ in range(100):
            self.fleet.paint({"routes": []}, self.camera)
        self.assertEqual((self.positions, self.canvas.items, self.canvas.moves), ([], {}, []))

    def test_sprite_items_are_reused_and_only_changed_screen_pixels_move(self):
        route = self.route()
        ledger = {"routes": [route]}
        self.fleet.paint(ledger, self.camera)
        original_ids = tuple(self.canvas.items)
        original_position = self.fleet.sprites[1].position
        self.canvas.moves.clear()
        route["test_position"] = (200.1, 300.1)
        self.fleet.paint(ledger, self.camera)
        self.assertEqual(self.canvas.moves, [])
        route["test_position"] = (210, 320)
        self.fleet.paint(ledger, self.camera)
        self.assertEqual(tuple(self.canvas.items), original_ids)
        self.assertEqual(self.fleet.sprites[1].position, (262, 400))
        self.assertEqual(self.canvas.moves, [("delivery_1", 262-original_position[0], 400-original_position[1])])

    def test_offscreen_routes_allocate_only_when_visible_and_hide_without_moving(self):
        route = self.route(position=(1800, 1200))
        ledger = {"routes": [route]}
        self.fleet.paint(ledger, self.camera)
        self.assertEqual(self.canvas.items, {})
        route["test_position"] = (200, 300)
        self.fleet.paint(ledger, self.camera)
        original_ids = tuple(self.canvas.items)
        route["test_position"] = (1800, 1200)
        self.canvas.moves.clear()
        self.fleet.paint(ledger, self.camera)
        self.assertFalse(self.fleet.sprites[1].visible)
        self.assertTrue(all(item[1]["state"] == "hidden" for item in self.canvas.items.values()))
        self.assertEqual(self.canvas.moves, [])
        route["test_position"] = (400, 350)
        self.fleet.paint(ledger, self.camera)
        self.assertEqual(tuple(self.canvas.items), original_ids)
        self.assertEqual(self.fleet.sprites[1].position, (500, 438))

    def test_removed_routes_delete_groups_and_zoom_rebuilds_once(self):
        route = self.route(kind="drone")
        self.fleet.paint({"routes": [route]}, self.camera)
        old_ids = tuple(self.canvas.items)
        self.fleet.set_zoom(1.5)
        self.assertEqual(self.canvas.items, {})
        self.fleet.paint({"routes": [route]}, self.camera)
        self.assertNotEqual(tuple(self.canvas.items), old_ids)
        self.assertEqual(self.fleet.sprites[1].position, (300, 450))
        self.fleet.paint({"routes": []}, self.camera)
        self.assertEqual((self.canvas.items, self.fleet.sprites), ({}, {}))

    def test_load_and_night_changes_reuse_parts_and_do_not_mutate_the_route(self):
        route = self.route(kind="drone", load=0)
        ledger = {"routes": [route]}
        before = deepcopy(ledger)
        self.fleet.paint(ledger, self.camera)
        sprite = self.fleet.sprites[1]
        self.assertEqual(self.canvas.items[sprite.cargo_item][1]["state"], "hidden")
        original_ids = tuple(self.canvas.items)
        self.fleet.set_night(True)
        self.assertTrue(all(self.canvas.items[item][1]["fill"] == "#fff0ad" for item in sprite.light_items))
        self.assertEqual(ledger, before)
        route["load"] = 1
        self.fleet.paint(ledger, self.camera)
        self.assertEqual(self.canvas.items[sprite.cargo_item][1]["state"], "normal")
        self.assertEqual(tuple(self.canvas.items), original_ids)
        self.fleet.set_night(False)
        self.assertTrue(all(self.canvas.items[item][1]["fill"] == "#b4d8dc" for item in sprite.light_items))

    def test_render_work_is_bounded_to_eight_routes(self):
        ledger = {"routes": [self.route(route_id=i+1) for i in range(12)]}
        self.fleet.paint(ledger, self.camera)
        self.assertEqual(len(self.positions), MAX_VISIBLE_ROUTES)
        self.assertEqual(len(self.fleet.sprites), MAX_VISIBLE_ROUTES)


if __name__ == "__main__":
    unittest.main()
