from __future__ import annotations

import unittest

from people_monitor.domain import BoundingBox, TrackedDetection
from people_monitor.geometry import ConvexPolygonRoi


class ConvexPolygonRoiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.roi = ConvexPolygonRoi(
            normalized_points=(
                (0.25, 0.25),
                (0.75, 0.25),
                (0.75, 0.75),
                (0.25, 0.75),
            )
        )

    @staticmethod
    def detection(box: BoundingBox) -> TrackedDetection:
        return TrackedDetection(bbox=box, confidence=0.9, track_id=1)

    def test_bottom_center_inside_roi_is_counted_inside(self) -> None:
        membership = self.roi.evaluate(
            self.detection(BoundingBox(30, 10, 60, 60)),
            frame_width=100,
            frame_height=100,
        )

        self.assertEqual(membership.anchor_point, (45.0, 60))
        self.assertTrue(membership.is_inside)

    def test_bottom_center_outside_roi_is_not_counted(self) -> None:
        membership = self.roi.evaluate(
            self.detection(BoundingBox(0, 10, 20, 40)),
            frame_width=100,
            frame_height=100,
        )

        self.assertFalse(membership.is_inside)

    def test_point_on_roi_boundary_is_counted_inside(self) -> None:
        self.assertTrue(self.roi.contains((25.0, 50.0), 100, 100))

    def test_clockwise_roi_is_normalized_and_supported(self) -> None:
        clockwise = ConvexPolygonRoi(
            ((0.25, 0.25), (0.25, 0.75), (0.75, 0.75), (0.75, 0.25))
        )

        self.assertTrue(clockwise.contains((50.0, 50.0), 100, 100))

    def test_zero_area_bbox_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            BoundingBox(10, 10, 10, 20)

    def test_repeated_roi_vertex_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ConvexPolygonRoi(((0.1, 0.1), (0.9, 0.1), (0.9, 0.1), (0.1, 0.9)))

    def test_concave_roi_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ConvexPolygonRoi(
                ((0.1, 0.1), (0.9, 0.1), (0.5, 0.5), (0.9, 0.9), (0.1, 0.9))
            )


if __name__ == "__main__":
    unittest.main()
