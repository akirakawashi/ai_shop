from __future__ import annotations

import unittest

from people_monitor.config import EventConfig
from people_monitor.domain import (
    BoundingBox,
    FrameAnalysis,
    QueueState,
    TrackedDetection,
)
from people_monitor.events import QueueOccupancyMonitor
from people_monitor.geometry import ConvexPolygonRoi


class QueueOccupancyMonitorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.roi = ConvexPolygonRoi(
            normalized_points=(
                (0.25, 0.25),
                (0.75, 0.25),
                (0.75, 0.75),
                (0.25, 0.75),
            )
        )
        self.monitor = self.make_monitor()
        self.inside_box = BoundingBox(30, 20, 60, 60)

    def make_monitor(
        self,
        *,
        capacity: int = 1,
        full_confirm_frames: int = 2,
        recovery_confirm_frames: int = 2,
        cooldown_seconds: float = 0.0,
    ) -> QueueOccupancyMonitor:
        return QueueOccupancyMonitor(
            camera_id="test-camera",
            roi=self.roi,
            settings=EventConfig(
                roi_capacity=capacity,
                full_confirm_frames=full_confirm_frames,
                recovery_confirm_frames=recovery_confirm_frames,
                cooldown_seconds=cooldown_seconds,
                _env_file=None,
            ),
        )

    @staticmethod
    def detection(
        box: BoundingBox,
        track_id: int | None,
        confidence: float = 0.9,
    ) -> TrackedDetection:
        return TrackedDetection(
            bbox=box,
            confidence=confidence,
            track_id=track_id,
        )

    def analyze(
        self,
        monitor: QueueOccupancyMonitor,
        detections: tuple[TrackedDetection, ...],
        frame: int,
        clock: float | None = None,
    ) -> FrameAnalysis:
        return monitor.analyze(
            detections=detections,
            frame_index=frame,
            frame_width=100,
            frame_height=100,
            video_time_seconds=float(frame),
            observed_at_seconds=float(frame) if clock is None else clock,
        )

    def test_capacity_is_confirmed_and_emits_zone_event_once(self) -> None:
        person = (self.detection(self.inside_box, 7),)

        first = self.analyze(self.monitor, person, 0)
        second = self.analyze(self.monitor, person, 1)
        third = self.analyze(self.monitor, person, 2)

        self.assertFalse(first.events)
        self.assertIs(first.queue_state, QueueState.CONFIRMING_FULL)
        self.assertEqual(len(second.events), 1)
        self.assertEqual(second.events[0].people_count, 1)
        self.assertEqual(second.events[0].capacity, 1)
        self.assertEqual(second.events[0].track_ids, (7,))
        self.assertIs(second.queue_state, QueueState.FULL)
        self.assertFalse(third.events)

    def test_recovery_rearms_monitor_for_next_queue(self) -> None:
        person = (self.detection(self.inside_box, 7),)
        self.analyze(self.monitor, person, 0)
        self.assertTrue(self.analyze(self.monitor, person, 1).events)

        self.assertIs(
            self.analyze(self.monitor, (), 2).queue_state,
            QueueState.RECOVERING,
        )
        self.assertIs(
            self.analyze(self.monitor, (), 3).queue_state,
            QueueState.AVAILABLE,
        )
        self.assertFalse(self.analyze(self.monitor, person, 4).events)
        self.assertTrue(self.analyze(self.monitor, person, 5).events)

    def test_partial_recovery_does_not_create_duplicate_event(self) -> None:
        person = (self.detection(self.inside_box, 7),)
        self.analyze(self.monitor, person, 0)
        self.assertTrue(self.analyze(self.monitor, person, 1).events)
        self.analyze(self.monitor, (), 2)

        result = self.analyze(self.monitor, person, 3)

        self.assertFalse(result.events)
        self.assertIs(result.queue_state, QueueState.FULL)

    def test_capacity_counts_unique_tracked_people(self) -> None:
        monitor = self.make_monitor(capacity=2, full_confirm_frames=1)
        one_person_twice = (
            self.detection(self.inside_box, 7, confidence=0.7),
            self.detection(self.inside_box, 7, confidence=0.9),
        )

        one = self.analyze(monitor, one_person_twice, 0)
        two = self.analyze(
            monitor,
            (
                self.detection(self.inside_box, 7),
                self.detection(BoundingBox(40, 20, 70, 65), 8),
            ),
            1,
        )

        self.assertEqual(one.people_count, 1)
        self.assertFalse(one.events)
        self.assertEqual(two.people_count, 2)
        self.assertTrue(two.events)

    def test_untracked_detection_is_visible_but_not_counted(self) -> None:
        result = self.analyze(
            self.monitor,
            (self.detection(self.inside_box, None),),
            0,
        )

        self.assertEqual(len(result.memberships), 1)
        self.assertTrue(result.memberships[0].intersects_roi)
        self.assertEqual(result.people_count, 0)
        self.assertFalse(result.events)

    def test_small_bbox_overlap_is_enough_for_test_mode(self) -> None:
        mostly_outside = BoundingBox(0, 0, 30, 30)
        result = self.analyze(
            self.monitor,
            (self.detection(mostly_outside, 7),),
            0,
        )

        self.assertTrue(result.memberships[0].intersects_roi)
        self.assertEqual(result.people_count, 1)

    def test_frame_gap_resets_unfinished_confirmation(self) -> None:
        person = (self.detection(self.inside_box, 7),)
        self.analyze(self.monitor, person, 0)

        after_gap = self.analyze(self.monitor, person, 2)
        confirmed = self.analyze(self.monitor, person, 3)

        self.assertFalse(after_gap.events)
        self.assertTrue(confirmed.events)

    def test_cooldown_delays_repeated_notification_without_losing_it(self) -> None:
        monitor = self.make_monitor(
            full_confirm_frames=1,
            recovery_confirm_frames=1,
            cooldown_seconds=10.0,
        )
        person = (self.detection(self.inside_box, 7),)

        self.assertTrue(self.analyze(monitor, person, 0, clock=0.0).events)
        self.analyze(monitor, (), 1, clock=1.0)
        self.assertFalse(self.analyze(monitor, person, 2, clock=5.0).events)
        self.assertTrue(self.analyze(monitor, person, 3, clock=10.0).events)

    def test_reset_requires_new_confirmation(self) -> None:
        person = (self.detection(self.inside_box, 7),)
        self.analyze(self.monitor, person, 0)
        self.monitor.reset()

        self.assertFalse(self.analyze(self.monitor, person, 1).events)
        self.assertTrue(self.analyze(self.monitor, person, 2).events)


if __name__ == "__main__":
    unittest.main()
