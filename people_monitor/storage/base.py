"""Контракт хранилища событий."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from people_monitor.domain import QueueFullEvent


@runtime_checkable
class EventStore(Protocol):
    def append(self, event: QueueFullEvent) -> None:
        """Надёжно сохранить одно подтверждённое событие."""
        ...
