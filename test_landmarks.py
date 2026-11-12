import unittest

from lisbon_landmarks import LANDMARKS, LANDMARK_SOLIDS
from lisbon_scene import RIVER_BOTTOM, RIVER_TOP, SCENERY_BLOCKS, bridge_center


def inside(x, y, bounds, margin=0):
    left, top, right, bottom = bounds
    return left-margin < x < right+margin and top-margin < y < bottom+margin


class LandmarkLayoutTest(unittest.TestCase):
    def test_all_four_landmarks_have_unique_names_and_map_locations(self):
        self.assertEqual(len(LANDMARKS), 4)
        self.assertEqual(len({landmark.name for landmark in LANDMARKS}), 4)
        for landmark in LANDMARKS:
            self.assertTrue(inside(*landmark.map_point, landmark.bounds))
            if landmark.kind == "tower":
                self.assertGreater(landmark.bounds[1], RIVER_TOP)
                self.assertLess(landmark.bounds[3], RIVER_BOTTOM)
            else:
                self.assertLess(landmark.bounds[3], RIVER_TOP)

    def test_square_courtyard_is_open_and_arcades_are_solid(self):
        for point in ((548, 580), (644, 580), (596, 620)):
            self.assertFalse(any(inside(*point, bounds, margin=10) for bounds in LANDMARK_SOLIDS), point)
        for point in ((520, 580), (672, 580), (596, 541)):
            self.assertTrue(any(inside(*point, bounds) for bounds in LANDMARK_SOLIDS), point)

    def test_landmarks_leave_both_bridge_corridors_clear(self):
        for y in range(RIVER_TOP-10, RIVER_BOTTOM+11, 4):
            for eastern in (False, True):
                x = bridge_center(y, eastern)
                self.assertFalse(any(inside(x, y, landmark.bounds, margin=15) for landmark in LANDMARKS))

    def test_relocated_business_plots_are_free_of_residential_scenery(self):
        for x, y in ((1280, 160), (2080, 160), (1540, 530)):
            self.assertNotIn((x, y, x+176, y+104), SCENERY_BLOCKS)


if __name__ == "__main__":
    unittest.main()
