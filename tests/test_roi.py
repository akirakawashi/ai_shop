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

    def test_bbox_intersecting_roi_is_counted(self) -> None:
        membership = self.roi.evaluate(
            self.detection(BoundingBox(30, 10, 60, 60)),
            frame_width=100,
            frame_height=100,
        )

        self.assertTrue(membership.intersects_roi)

    def test_bbox_outside_roi_is_not_counted(self) -> None:
        membership = self.roi.evaluate(
            self.detection(BoundingBox(0, 10, 20, 40)),
            frame_width=100,
            frame_height=100,
        )

        self.assertFalse(membership.intersects_roi)

    def test_bbox_touching_roi_boundary_is_counted(self) -> None:
        self.assertTrue(
            self.roi.intersects_bbox(BoundingBox(5, 30, 25, 50), 100, 100)
        )

    def test_clockwise_roi_is_normalized_and_supported(self) -> None:
        clockwise = ConvexPolygonRoi(
            ((0.25, 0.25), (0.25, 0.75), (0.75, 0.75), (0.75, 0.25))
        )

        self.assertTrue(
            clockwise.intersects_bbox(BoundingBox(40, 40, 60, 60), 100, 100)
        )

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
