"""Асинхронный контракт канала уведомлений."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Final

from people_monitor.domain import ExitEvent

_ALERT_TITLE: Final = "⚠️ Человек вышел за границу ROI"


class Notifier(ABC):
    """Номинальный контракт управляемого асинхронного канала доставки."""

    @abstractmethod
    async def send(self, event: ExitEvent, snapshot: bytes | None = None) -> None:
        """Доставить событие, опционально приложив JPEG-снимок."""

    async def close(self) -> None:
        """Освободить ресурсы канала, если они есть."""


def format_event_message(event: ExitEvent) -> str:
    outside_percent = event.outside_ratio * 100
    return (
        f"{_ALERT_TITLE}\n"
        f"Камера: {event.camera_id}\n"
        f"ID события: {event.event_id}\n"
        f"ID трека: {event.track_id}\n"
        f"Снаружи bbox: {outside_percent:.1f}%\n"
        f"Площадь снаружи: {event.outside_area:.1f} px²\n"
        f"Площадь внутри: {event.inside_area:.1f} px²\n"
        f"Время: {event.occurred_at.astimezone().isoformat(timespec='seconds')}"
    )
