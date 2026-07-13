"""Автомат состояний заполненности очереди в ROI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Final
from uuid import uuid4

from people_monitor.config import EventConfig
from people_monitor.domain import (
    FrameAnalysis,
    QueueFullEvent,
    QueueState,
    RoiMembership,
    TrackedDetection,
)
from people_monitor.geometry import ConvexPolygonRoi

EVENT_SCHEMA_VERSION: Final = 2


@dataclass(slots=True)
class _OccupancyState:
    """Закрытое изменяемое состояние одной ROI."""

    phase: QueueState = QueueState.AVAILABLE
    full_streak: int = 0
    recovery_streak: int = 0
    last_alert_clock: float | None = None
    last_frame_index: int | None = None


class QueueOccupancyMonitor:
    """Создаёт одно событие после устойчивого заполнения ROI."""

    def __init__(
        self,
        camera_id: str,
        roi: ConvexPolygonRoi,
        settings: EventConfig,
    ) -> None:
        self._camera_id = camera_id
        self._roi = roi
        self._settings = settings
        self._state = _OccupancyState()

    def reset(self) -> None:
        """Сбросить подтверждение после разрыва видеопотока."""
        self._state = _OccupancyState()

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
        if frame_index < 0:
            raise ValueError("frame_index не может быть отрицательным")
        self._handle_frame_sequence(frame_index)

        timestamp = occurred_at or datetime.now(timezone.utc)
        clock = video_time_seconds if observed_at_seconds is None else observed_at_seconds
        memberships = tuple(
            self._roi.evaluate(
                detection=detection,
                frame_width=frame_width,
                frame_height=frame_height,
            )
            for detection in self._unique_detections(detections)
        )
        track_ids = self._overlapping_track_ids(memberships)
        people_count = len(track_ids)

        event = self._advance_state(
            people_count=people_count,
            track_ids=track_ids,
            frame_index=frame_index,
            video_time_seconds=video_time_seconds,
            clock=clock,
            occurred_at=timestamp,
        )
        return FrameAnalysis(
            memberships=memberships,
            events=() if event is None else (event,),
            people_count=people_count,
            capacity=self._settings.roi_capacity,
            queue_state=self._state.phase,
        )

    def _handle_frame_sequence(self, frame_index: int) -> None:
        previous_frame = self._state.last_frame_index
        if previous_frame is not None and frame_index <= previous_frame:
            raise ValueError("frame_index должен строго возрастать")
        if previous_frame is not None and frame_index != previous_frame + 1:
            self._state.full_streak = 0
            self._state.recovery_streak = 0
            if self._state.phase is QueueState.CONFIRMING_FULL:
                self._state.phase = QueueState.AVAILABLE
            elif self._state.phase is QueueState.RECOVERING:
                # Разрыв не доказывает, что очередь действительно освободилась.
                self._state.phase = QueueState.FULL
        self._state.last_frame_index = frame_index

    @staticmethod
    def _unique_detections(
        detections: tuple[TrackedDetection, ...],
    ) -> tuple[TrackedDetection, ...]:
        """Оставить наиболее уверенную детекцию каждого track_id."""
        selected: dict[int, TrackedDetection] = {}
        untracked: list[TrackedDetection] = []
        for detection in detections:
            track_id = detection.track_id
            if track_id is None:
                untracked.append(detection)
                continue
            current = selected.get(track_id)
            if current is None or detection.confidence > current.confidence:
                selected[track_id] = detection
        return (*selected.values(), *untracked)

    @staticmethod
    def _overlapping_track_ids(
        memberships: tuple[RoiMembership, ...],
    ) -> tuple[int, ...]:
        return tuple(
            sorted(
                membership.detection.track_id
                for membership in memberships
                if membership.intersects_roi
                and membership.detection.track_id is not None
            )
        )

    def _advance_state(
        self,
        people_count: int,
        track_ids: tuple[int, ...],
        frame_index: int,
        video_time_seconds: float,
        clock: float,
        occurred_at: datetime,
    ) -> QueueFullEvent | None:
        if people_count < self._settings.roi_capacity:
            self._handle_available_capacity()
            return None
        return self._handle_full_capacity(
            people_count=people_count,
            track_ids=track_ids,
            frame_index=frame_index,
            video_time_seconds=video_time_seconds,
            clock=clock,
            occurred_at=occurred_at,
        )

    def _handle_available_capacity(self) -> None:
        self._state.full_streak = 0
        if self._state.phase in (
            QueueState.AVAILABLE,
            QueueState.CONFIRMING_FULL,
        ):
            self._state.phase = QueueState.AVAILABLE
            self._state.recovery_streak = 0
            return

        self._state.phase = QueueState.RECOVERING
        self._state.recovery_streak += 1
        if self._state.recovery_streak >= self._settings.recovery_confirm_frames:
            self._state.phase = QueueState.AVAILABLE
            self._state.recovery_streak = 0

    def _handle_full_capacity(
        self,
        people_count: int,
        track_ids: tuple[int, ...],
        frame_index: int,
        video_time_seconds: float,
        clock: float,
        occurred_at: datetime,
    ) -> QueueFullEvent | None:
        self._state.recovery_streak = 0
        if self._state.phase is QueueState.FULL:
            return None
        if self._state.phase is QueueState.RECOVERING:
            # Очередь снова заполнилась до завершения recovery: старое событие активно.
            self._state.phase = QueueState.FULL
            self._state.full_streak = 0
            return None
        if self._state.phase is QueueState.AVAILABLE:
            self._state.phase = QueueState.CONFIRMING_FULL
            self._state.full_streak = 0

        self._state.full_streak += 1
        if self._state.full_streak < self._settings.full_confirm_frames:
            return None
        if not self._cooldown_elapsed(clock):
            return None

        self._state.phase = QueueState.FULL
        self._state.full_streak = 0
        self._state.last_alert_clock = clock
        return QueueFullEvent(
            event_id=uuid4(),
            schema_version=EVENT_SCHEMA_VERSION,
            camera_id=self._camera_id,
            frame_index=frame_index,
            video_time_seconds=video_time_seconds,
            occurred_at=occurred_at,
            people_count=people_count,
            capacity=self._settings.roi_capacity,
            track_ids=track_ids,
        )

    def _cooldown_elapsed(self, clock: float) -> bool:
        last_alert_clock = self._state.last_alert_clock
        return (
            last_alert_clock is None
            or clock - last_alert_clock >= self._settings.cooldown_seconds
        )
