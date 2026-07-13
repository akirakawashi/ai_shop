"""Безопасный канал для локальной отладки без Telegram."""

from __future__ import annotations

import logging

from people_monitor.domain import QueueFullEvent
from people_monitor.notifications.base import Notifier, format_event_message


class LoggingNotifier(Notifier):
    def __init__(
        self,
        alert_message: str,
        logger: logging.Logger | None = None,
    ) -> None:
        self._alert_message = alert_message
        self._logger = logger or logging.getLogger(__name__)

    async def send(
        self,
        event: QueueFullEvent,
        snapshot: bytes | None = None,
    ) -> None:
        self._logger.warning(
            "Очередь заполнена:\n%s",
            format_event_message(event, self._alert_message),
        )
