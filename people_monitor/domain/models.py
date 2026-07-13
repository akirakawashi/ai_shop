"""Независимые от библиотек модели предметной области."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from math import isfinite
from typing import Any
from uuid import UUID

from people_monitor.domain.enums import QueueState


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """BBox в пиксельных координатах кадра."""

    x1: float
    y1: float
    x2: float
    y2: float

    def __post_init__(self) -> None:
        coordinates = (self.x1, self.y1, self.x2, self.y2)
        if not all(isfinite(value) for value in coordinates):
            raise ValueError("Координаты bbox должны быть конечными числами")
        if self.x2 <= self.x1 or self.y2 <= self.y1:
            raise ValueError("BBox должен иметь положительные ширину и высоту")

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def area(self) -> float:
        return self.width * self.height

@dataclass(frozen=True, slots=True)
class TrackedDetection:
    """Детекция человека с идентификатором трека."""

    bbox: BoundingBox
    confidence: float
    track_id: int | None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence должен находиться в диапазоне [0, 1]")
        if self.track_id is not None and self.track_id < 0:
            raise ValueError("track_id не может быть отрицательным")


@dataclass(frozen=True, slots=True)
class RoiMembership:
    """Результат проверки пересечения bbox с областью интереса."""

    detection: TrackedDetection
    intersects_roi: bool


@dataclass(frozen=True, slots=True)
class QueueFullEvent:
    """Подтверждённое заполнение очереди в ROI."""

    event_id: UUID
    schema_version: int
    camera_id: str
    frame_index: int
    video_time_seconds: float
    occurred_at: datetime
    people_count: int
    capacity: int
    track_ids: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.capacity <= 0:
            raise ValueError("Вместимость ROI должна быть положительной")
        if self.people_count < self.capacity:
            raise ValueError("Событие возможно только при заполненной ROI")
        if self.people_count != len(self.track_ids):
            raise ValueError("people_count должен совпадать с количеством track_ids")
        if len(set(self.track_ids)) != len(self.track_ids):
            raise ValueError("track_ids события не должны повторяться")
        if any(track_id < 0 for track_id in self.track_ids):
            raise ValueError("track_id не может быть отрицательным")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["event_id"] = str(self.event_id)
        data["occurred_at"] = self.occurred_at.isoformat()
        return data


@dataclass(frozen=True, slots=True)
class FrameAnalysis:
    """Полный результат анализа одного кадра."""

    memberships: tuple[RoiMembership, ...]
    events: tuple[QueueFullEvent, ...]
    people_count: int
    capacity: int
    queue_state: QueueState
