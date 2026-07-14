"""Асинхронный контракт канала уведомлений."""

from __future__ import annotations

from abc import ABC, abstractmethod
from people_monitor.domain import QueueFullEvent


class Notifier(ABC):
    """Номинальный контракт управляемого асинхронного канала доставки."""

    @abstractmethod
    async def send(
        self,
        event: QueueFullEvent,
        snapshot: bytes | None = None,
    ) -> None:
        """Доставить событие, опционально приложив JPEG-снимок."""

    async def close(self) -> None:
        """Освободить ресурсы канала, если они есть."""


def format_event_message(event: QueueFullEvent, alert_message: str) -> str:
    return (
        f"{alert_message}\n"
        f"Камера: {event.camera_id}\n"
        f"Людей в зоне: {event.people_count}"
    )
