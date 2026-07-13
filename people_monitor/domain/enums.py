"""Перечисления предметной области."""

from __future__ import annotations

from enum import IntEnum, StrEnum


class CocoClass(IntEnum):
    """Используемые идентификаторы классов датасета COCO."""

    PERSON = 0


class QueueState(StrEnum):
    """Состояние заполненности очереди в области интереса."""

    AVAILABLE = "available"
    CONFIRMING_FULL = "confirming_full"
    FULL = "full"
    RECOVERING = "recovering"
