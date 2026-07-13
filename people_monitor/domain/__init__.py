"""Доменные модели приложения."""

from people_monitor.domain.enums import CocoClass, RoiAreaRelation
from people_monitor.domain.models import (
    BoundingBox,
    ExitEvent,
    FrameAnalysis,
    RoiEvaluation,
    TrackedDetection,
)
from people_monitor.domain.types import Frame, NormalizedPoint, Point

__all__ = [
    "BoundingBox",
    "CocoClass",
    "ExitEvent",
    "Frame",
    "FrameAnalysis",
    "NormalizedPoint",
    "Point",
    "RoiAreaRelation",
    "RoiEvaluation",
    "TrackedDetection",
]
