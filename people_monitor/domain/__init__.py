"""Доменные модели приложения."""

from people_monitor.domain.enums import CocoClass, QueueState
from people_monitor.domain.models import (
    BoundingBox,
    FrameAnalysis,
    QueueFullEvent,
    RoiMembership,
    TrackedDetection,
)
from people_monitor.domain.types import Frame, NormalizedPoint, Point

__all__ = [
    "BoundingBox",
    "CocoClass",
    "Frame",
    "FrameAnalysis",
    "NormalizedPoint",
    "Point",
    "QueueFullEvent",
    "QueueState",
    "RoiMembership",
    "TrackedDetection",
]
