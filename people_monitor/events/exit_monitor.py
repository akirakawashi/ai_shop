"""Автомат состояний для подтверждения выхода bbox из ROI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Final
from uuid import uuid4

from people_monitor.config import EventConfig
from people_monitor.domain import (
    ExitEvent,
    FrameAnalysis,
    RoiAreaRelation,
    RoiEvaluation,
    TrackedDetection,
)
from people_monitor.geometry import ConvexPolygonRoi

EVENT_SCHEMA_VERSION: Final = 1


class _TrackPhase(StrEnum):
    OBSERVING = "observing"
    ARMED = "armed"
    NOTIFIED = "notified"


@dataclass(slots=True)
class _TrackState:
    """Закрытое изменяемое состояние одного track_id."""

    phase: _TrackPhase = _TrackPhase.OBSERVING
    inside_streak: int = 0
    outside_streak: int = 0
    last_seen_frame: int | None = None
    last_alert_clock: float | None = None

    def reset_streaks(self) -> None:
        self.inside_streak = 0
        self.outside_streak = 0


class BboxExitMonitor:
    """Создаёт событие после устойчивого перехода bbox изнутри наружу."""

    def __init__(
        self,
        camera_id: str,
        roi: ConvexPolygonRoi,
        settings: EventConfig,
    ) -> None:
        self._camera_id = camera_id
        self._roi = roi
        self._settings = settings
        self._tracks: dict[int, _TrackState] = {}

    def reset(self) -> None:
        """Забыть streak и phase всех track_id после разрыва потока."""
        self._tracks.clear()

    def analyze(
        self,
        detections: tuple[TrackedDetection, ...],
        frame_index: int,
        frame_width: int,
        frame_height: int,
        video_time_seconds: float,
        observed_at_seconds: float | None = None,
        occurred_at: datetime | None = None,
    ) -> FrameAnalysis:
        timestamp = occurred_at or datetime.now(timezone.utc)
        clock = video_time_seconds if observed_at_seconds is None else observed_at_seconds
        evaluations = tuple(
            self._roi.evaluate(
                detection=detection,
                frame_width=frame_width,
                frame_height=frame_height,
            )
            for detection in detections
        )

        events: list[ExitEvent] = []
        for evaluation in self._unique_tracked_evaluations(evaluations):
            track_id = evaluation.detection.track_id
            if track_id is None:
                continue
            state = self._tracks.setdefault(track_id, _TrackState())
            self._reset_after_frame_gap(state, frame_index)
            state.last_seen_frame = frame_index

            if evaluation.area_relation is RoiAreaRelation.OUTSIDE_LARGER:
                event = self._handle_outside(
                    state=state,
                    evaluation=evaluation,
                    track_id=track_id,
                    frame_index=frame_index,
                    video_time_seconds=video_time_seconds,
                    clock=clock,
                    occurred_at=timestamp,
                )
                if event is not None:
                    events.append(event)
            elif evaluation.area_relation is RoiAreaRelation.INSIDE_LARGER:
                self._handle_inside(state)
            else:
                # Равенство площадей не считается ни входом, ни выходом.
                state.reset_streaks()

        self._remove_stale_tracks(frame_index)
        return FrameAnalysis(evaluations=evaluations, events=tuple(events))

    @staticmethod
    def _unique_tracked_evaluations(
        evaluations: tuple[RoiEvaluation, ...],
    ) -> tuple[RoiEvaluation, ...]:
        """Для повторного track_id оставить наиболее уверенную детекцию."""
        selected: dict[int, RoiEvaluation] = {}
        for evaluation in evaluations:
            track_id = evaluation.detection.track_id
            if track_id is None:
                continue
            current = selected.get(track_id)
            if (
                current is None
                or evaluation.detection.confidence > current.detection.confidence
            ):
                selected[track_id] = evaluation
        return tuple(selected.values())

    def _reset_after_frame_gap(self, state: _TrackState, frame_index: int) -> None:
        if state.last_seen_frame is None:
            return
        frame_gap = frame_index - state.last_seen_frame
        if frame_gap != 1:
            state.reset_streaks()
        if frame_gap > self._settings.track_ttl_frames:
            # Долгий разрыв означает новый жизненный цикл даже при повторном ID.
            state.phase = _TrackPhase.OBSERVING
            state.last_alert_clock = None

    def _handle_inside(self, state: _TrackState) -> None:
        state.outside_streak = 0
        state.inside_streak += 1
        if state.inside_streak >= self._settings.inside_confirm_frames:
            state.phase = _TrackPhase.ARMED

    def _handle_outside(
        self,
        state: _TrackState,
        evaluation: RoiEvaluation,
        track_id: int,
        frame_index: int,
        video_time_seconds: float,
        clock: float,
        occurred_at: datetime,
    ) -> ExitEvent | None:
        state.inside_streak = 0
        state.outside_streak += 1
        if not self._should_alert(state, clock):
            return None

        state.phase = _TrackPhase.NOTIFIED
        state.last_alert_clock = clock
        detection = evaluation.detection
        return ExitEvent(
            event_id=uuid4(),
            schema_version=EVENT_SCHEMA_VERSION,
            camera_id=self._camera_id,
            track_id=track_id,
            frame_index=frame_index,
            video_time_seconds=video_time_seconds,
            occurred_at=occurred_at,
            confidence=detection.confidence,
            bbox=detection.bbox,
            inside_area=evaluation.inside_area,
            outside_area=evaluation.outside_area,
            outside_ratio=evaluation.outside_ratio,
        )

    def _should_alert(self, state: _TrackState, clock: float) -> bool:
        if state.phase is not _TrackPhase.ARMED:
            return False
        if state.outside_streak < self._settings.outside_confirm_frames:
            return False
        if state.last_alert_clock is None:
            return True
        return clock - state.last_alert_clock >= self._settings.cooldown_seconds

    def _remove_stale_tracks(self, frame_index: int) -> None:
        stale_ids = [
            track_id
            for track_id, state in self._tracks.items()
            if state.last_seen_frame is not None
            and frame_index - state.last_seen_frame > self._settings.track_ttl_frames
        ]
        for track_id in stale_ids:
            del self._tracks[track_id]
