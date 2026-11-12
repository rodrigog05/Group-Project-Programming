import math
import unittest

from living_world import AmbientActor, Camera, LivingWorld, WORLD_TOP
from lisbon_scene import WORLD_WIDTH, WORLD_BOTTOM, SCENERY_BLOCKS, bridge_center
from tycoon import SITES, Town, pack_save, unpack_save


class CameraTest(unittest.TestCase):
    def test_follow_centers_player_and_projected_coordinates_match(self):
        camera = Camera(1000, 700, 1.25)
        camera.follow(1700, 1300, snap=True)
        self.assertEqual(camera.project(1700, 1300), (500, 350))
        self.assertAlmostEqual(camera.x, 1300)

    def test_camera_clamps_at_all_world_edges(self):
        camera = Camera(1920, 900, 1.25)
        camera.follow(0, 0, snap=True)
        self.assertEqual((camera.x, camera.y), (0, WORLD_TOP))
        camera.follow(WORLD_WIDTH+500, WORLD_BOTTOM+500, snap=True)
        self.assertAlmostEqual(camera.x+camera.visible_width, WORLD_WIDTH)
        self.assertAlmostEqual(camera.y+camera.visible_height, WORLD_BOTTOM)

    def test_follow_is_smooth_and_culling_handles_offscreen_actors(self):
        camera = Camera(1000, 700, 1.25)
        camera.follow(1700, 1300, dt=.016)
        self.assertTrue(0 < camera.x < 1300)
        self.assertTrue(camera.sees(camera.x+100, camera.y+100))
        self.assertFalse(camera.sees(WORLD_WIDTH+200, WORLD_BOTTOM+200))

    def test_ambient_routes_are_deterministic_and_reverse_at_endpoints(self):
        actor = AmbientActor('test', (100, 800), (300, 800), 20, 0, 'car')
        self.assertEqual(actor.position(0), (100, 800))
        self.assertEqual(actor.position(10), (300, 800))
        self.assertEqual(actor.position(20), (100, 800))
        self.assertTrue(all(math.isfinite(v) for v in actor.position(1234)))


class ExpandedWorldTest(unittest.TestCase):
    def test_compact_world_keeps_businesses_in_all_new_neighborhoods(self):
        area = WORLD_WIDTH*(WORLD_BOTTOM-WORLD_TOP)
        original_area = 1200*(1080-WORLD_TOP)
        self.assertGreater(area, 2.5*original_area)
        self.assertLess(area, 3.5*original_area)
        self.assertGreaterEqual(sum(s.x > 1200 or s.y > 1080 for s in SITES), 6)

    def test_progress_in_new_district_survives_reload(self):
        town = Town()
        farm = next(s for s in SITES if s.name == 'Quinta de Palmela')
        town.x, town.y = farm.door[0], farm.door[1]+10
        town.cash = 123
        restored, _ = unpack_save(pack_save(town, 1000))
        self.assertEqual((restored.x, restored.y), (town.x, town.y))
        self.assertEqual(restored.cash, 123)
        self.assertEqual(restored.nearby().name, farm.name)

    def test_save_from_removed_outskirts_recovers_without_losing_progress(self):
        town = Town()
        town.x, town.y = 2800, 1850
        town.cash, town.supplies[0], town.goods[1] = 234, 3, 2
        restored, _ = unpack_save(pack_save(town, 1000))
        self.assertTrue(restored.can_walk(restored.x, restored.y))
        self.assertEqual((restored.cash, restored.supplies[0], restored.goods[1]), (234, 3, 2))

    def test_ambient_routes_fit_compact_world_and_land_routes_clear_buildings(self):
        actors = []

        class Collector:
            def actor(self, kind, start, end, speed, offset, color):
                actors.append(AmbientActor(str(len(actors)), start, end, speed, offset, kind))

        LivingWorld.create_actors(Collector())
        self.assertEqual(len(actors), 60)
        town = Town()
        for actor in actors:
            for step in range(21):
                x = actor.start[0]+(actor.end[0]-actor.start[0])*step/20
                y = actor.start[1]+(actor.end[1]-actor.start[1])*step/20
                self.assertTrue(0 <= x <= WORLD_WIDTH and WORLD_TOP <= y <= WORLD_BOTTOM, actor.tag)
                if actor.kind in ('pedestrian', 'car'):
                    self.assertTrue(town.can_walk(x, y), (actor.kind, x, y))
                elif actor.kind == 'boat':
                    for eastern in (False, True):
                        self.assertGreater(abs(x-bridge_center(y, eastern)), 62, (actor.tag, eastern, x, y))

    def test_scenery_and_outer_world_edges_block_walking(self):
        town = Town()
        left, top, right, bottom = SCENERY_BLOCKS[0]
        self.assertFalse(town.can_walk((left+right)/2, (top+bottom)/2))
        self.assertFalse(town.can_walk(WORLD_WIDTH+1, 400))
        self.assertFalse(town.can_walk(400, WORLD_BOTTOM+1))


if __name__ == '__main__':
    unittest.main()
