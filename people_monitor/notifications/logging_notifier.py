"""Безопасный канал для локальной отладки без Telegram."""

from __future__ import annotations

import logging

from people_monitor.domain import ExitEvent
from people_monitor.notifications.base import Notifier, format_event_message


class LoggingNotifier(Notifier):
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger(__name__)

    async def send(self, event: ExitEvent, snapshot: bytes | None = None) -> None:
        self._logger.warning("Событие выхода:\n%s", format_event_message(event))
