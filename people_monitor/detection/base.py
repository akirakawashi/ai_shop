"""Контракт источника отслеживаемых детекций."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from people_monitor.domain import Frame, TrackedDetection


@runtime_checkable
class PeopleTracker(Protocol):
    """Позволяет заменить Ultralytics другим движком без изменения pipeline."""

    def track(self, frame: Frame) -> tuple[TrackedDetection, ...]:
        """Найти людей на кадре и вернуть стабильные идентификаторы треков."""
        ...

    def reset(self) -> None:
        """Сбросить внутреннее состояние после разрыва видеопотока."""
        ...
