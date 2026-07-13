from __future__ import annotations

import unittest

from people_monitor.config import EventConfig
from people_monitor.domain import BoundingBox, TrackedDetection
from people_monitor.events import BboxExitMonitor
from people_monitor.geometry import ConvexPolygonRoi


class BboxExitMonitorTest(unittest.TestCase):
    def setUp(self) -> None:
        roi = ConvexPolygonRoi(
            normalized_points=(
                (0.25, 0.25),
                (0.75, 0.25),
                (0.75, 0.75),
                (0.25, 0.75),
            )
        )
        self.monitor = BboxExitMonitor(
            camera_id="test-camera",
            roi=roi,
            settings=EventConfig(
                outside_confirm_frames=2,
                inside_confirm_frames=2,
                cooldown_seconds=10.0,
                track_ttl_frames=10,
                _env_file=None,
            ),
        )

    @staticmethod
    def detection(
        box: BoundingBox,
        track_id: int | None = 7,
        confidence: float = 0.9,
    ) -> TrackedDetection:
        return TrackedDetection(
            bbox=box,
            confidence=confidence,
            track_id=track_id,
        )

    def analyze(
        self,
        box: BoundingBox,
        frame: int,
        track_id: int | None = 7,
    ):
        return self.monitor.analyze(
            detections=(self.detection(box, track_id),),
            frame_index=frame,
            frame_width=100,
            frame_height=100,
            video_time_seconds=float(frame),
            observed_at_seconds=float(frame),
        )

    def test_stable_inside_to_outside_transition_emits_one_event(self) -> None:
        inside = BoundingBox(30, 30, 60, 60)
        outside = BoundingBox(0, 40, 40, 60)

        self.assertFalse(self.analyze(inside, 0).events)
        self.assertFalse(self.analyze(inside, 1).events)
        self.assertFalse(self.analyze(outside, 2).events)
        events = self.analyze(outside, 3).events

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].track_id, 7)
        self.assertGreater(events[0].outside_area, events[0].inside_area)
        self.assertFalse(self.analyze(outside, 4).events)

    def test_balanced_bbox_does_not_arm_track(self) -> None:
        balanced = BoundingBox(5, 40, 45, 60)
        outside = BoundingBox(0, 40, 40, 60)

        for frame in range(3):
            self.assertFalse(self.analyze(balanced, frame).events)
        self.assertFalse(self.analyze(outside, 3).events)
        self.assertFalse(self.analyze(outside, 4).events)

    def test_frame_gap_breaks_outside_streak(self) -> None:
        inside = BoundingBox(30, 30, 60, 60)
        outside = BoundingBox(0, 40, 40, 60)

        self.analyze(inside, 0)
        self.analyze(inside, 1)
        self.assertFalse(self.analyze(outside, 2).events)
        self.assertFalse(self.analyze(outside, 4).events)
        self.assertEqual(len(self.analyze(outside, 5).events), 1)

    def test_duplicate_track_id_counts_once_per_frame(self) -> None:
        inside = BoundingBox(30, 30, 60, 60)
        outside = BoundingBox(0, 40, 40, 60)

        for frame, box in enumerate((inside, inside, outside)):
            result = self.monitor.analyze(
                detections=(
                    self.detection(box, confidence=0.7),
                    self.detection(box, confidence=0.9),
                ),
                frame_index=frame,
                frame_width=100,
                frame_height=100,
                video_time_seconds=float(frame),
                observed_at_seconds=float(frame),
            )
            self.assertFalse(result.events)
        self.assertEqual(len(self.analyze(outside, 3).events), 1)

    def test_cooldown_delays_but_does_not_lose_repeated_exit(self) -> None:
        inside = BoundingBox(30, 30, 60, 60)
        outside = BoundingBox(0, 40, 40, 60)

        for frame, box in enumerate((inside, inside, outside, outside)):
            first_events = self.analyze(box, frame).events
        self.assertEqual(len(first_events), 1)

        self.analyze(inside, 4)
        self.analyze(inside, 5)
        for frame in range(6, 13):
            self.assertFalse(self.analyze(outside, frame).events)
        self.assertEqual(len(self.analyze(outside, 13).events), 1)

    def test_object_first_seen_outside_does_not_emit_event(self) -> None:
        outside = BoundingBox(0, 40, 40, 60)
        for frame in range(5):
            self.assertFalse(self.analyze(outside, frame).events)

    def test_reset_requires_track_to_be_armed_again(self) -> None:
        inside = BoundingBox(30, 30, 60, 60)
        outside = BoundingBox(0, 40, 40, 60)

        self.analyze(inside, 0)
        self.analyze(inside, 1)
        self.monitor.reset()

        self.assertFalse(self.analyze(outside, 2).events)
        self.assertFalse(self.analyze(outside, 3).events)

    def test_untracked_detection_never_emits_event(self) -> None:
        inside = BoundingBox(30, 30, 60, 60)
        outside = BoundingBox(0, 40, 40, 60)
        for frame, box in enumerate((inside, inside, outside, outside)):
            self.assertFalse(self.analyze(box, frame, track_id=None).events)


if __name__ == "__main__":
    unittest.main()
