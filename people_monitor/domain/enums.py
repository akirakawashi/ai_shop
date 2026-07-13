"""Перечисления предметной области."""

from __future__ import annotations

from enum import IntEnum, StrEnum


class CocoClass(IntEnum):
    """Используемые идентификаторы классов датасета COCO."""

    PERSON = 0


class RoiAreaRelation(StrEnum):
    """Отношение площадей bbox внутри и снаружи ROI."""

    INSIDE_LARGER = "inside_larger"
    BALANCED = "balanced"
    OUTSIDE_LARGER = "outside_larger"
