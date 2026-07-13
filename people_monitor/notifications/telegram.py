"""Асинхронный адаптер Telegram Bot API."""

from __future__ import annotations

import asyncio
import logging
from enum import StrEnum
from typing import Any, Final
from urllib.parse import urlparse

import httpx

from people_monitor.domain import QueueFullEvent
from people_monitor.notifications.base import Notifier, format_event_message

_JPEG_CONTENT_TYPE: Final = "image/jpeg"
_HTTP_LOGGER_NAMES: Final = (
    "httpx",
    "httpcore",
    "httpcore.connection",
    "httpcore.http11",
    "httpcore.http2",
    "httpcore.proxy",
)
_REDACTED_SECRET: Final = "[REDACTED]"


class NotificationError(RuntimeError):
    """Ошибка доставки без раскрытия токена и proxy credentials."""


class _TelegramMethod(StrEnum):
    SEND_MESSAGE = "sendMessage"
    SEND_PHOTO = "sendPhoto"


class _SecretRedactingFilter(logging.Filter):
    """Удаляет bot token и proxy URL из внутренних HTTPX LogRecord."""

    def __init__(self, secrets: tuple[str, ...]) -> None:
        super().__init__()
        self._secrets = tuple(secret for secret in secrets if secret)

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._redact(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(self._redact(value) for value in record.args)
        elif isinstance(record.args, dict):
            record.args = {
                key: self._redact(value) for key, value in record.args.items()
            }
        return True

    def _redact(self, value: object) -> object:
        rendered = str(value)
        redacted = rendered
        for secret in self._secrets:
            redacted = redacted.replace(secret, _REDACTED_SECRET)
        return value if redacted == rendered else redacted


class TelegramNotifier(Notifier):
    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        alert_message: str,
        api_base_url: str,
        proxy_url: str | None,
        timeout_seconds: float,
        snapshot_filename: str,
        max_retries: int,
        retry_backoff_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not bot_token or not chat_id:
            raise ValueError("Для Telegram нужны непустые bot_token и chat_id")
        if not alert_message.strip():
            raise ValueError("alert_message не может быть пустым")
        parsed_api_url = urlparse(api_base_url)
        if parsed_api_url.scheme.lower() != "https":
            raise ValueError("Telegram API URL должен использовать HTTPS")
        if parsed_api_url.query or parsed_api_url.fragment:
            raise ValueError("Telegram API URL не должен содержать query или fragment")
        if proxy_url is not None:
            parsed_proxy_url = urlparse(proxy_url)
            if (
                parsed_proxy_url.scheme.lower() != "http"
                or not parsed_proxy_url.hostname
            ):
                raise ValueError("Telegram proxy должен быть корректным HTTP URL")
            if parsed_proxy_url.query or parsed_proxy_url.fragment:
                raise ValueError(
                    "Telegram proxy не должен содержать query или fragment"
                )
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds должен быть положительным")
        if max_retries < 0:
            raise ValueError("max_retries не может быть отрицательным")
        if retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds не может быть отрицательным")
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._alert_message = alert_message.strip()
        self._snapshot_filename = snapshot_filename
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._redacting_filter = _SecretRedactingFilter(
            (bot_token, proxy_url or ""),
        )
        self._http_loggers = tuple(
            logging.getLogger(name) for name in _HTTP_LOGGER_NAMES
        )
        for logger in self._http_loggers:
            logger.addFilter(self._redacting_filter)
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=f"{api_base_url.rstrip('/')}/",
            proxy=proxy_url,
            timeout=timeout_seconds,
        )

    async def send(
        self,
        event: QueueFullEvent,
        snapshot: bytes | None = None,
    ) -> None:
        message = format_event_message(event, self._alert_message)
        if snapshot is None:
            await self._request(
                method=_TelegramMethod.SEND_MESSAGE,
                json_payload={"chat_id": self._chat_id, "text": message},
            )
            return
        await self._request(
            method=_TelegramMethod.SEND_PHOTO,
            form_data={"chat_id": self._chat_id, "caption": message},
            files={
                "photo": (
                    self._snapshot_filename,
                    snapshot,
                    _JPEG_CONTENT_TYPE,
                )
            },
        )

    async def close(self) -> None:
        try:
            if self._owns_client:
                await self._client.aclose()
        finally:
            for logger in self._http_loggers:
                logger.removeFilter(self._redacting_filter)

    async def _request(
        self,
        method: _TelegramMethod,
        json_payload: dict[str, Any] | None = None,
        form_data: dict[str, str] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
    ) -> None:
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.post(
                    f"bot{self._bot_token}/{method.value}",
                    json=json_payload,
                    data=form_data,
                    files=files,
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict) or payload.get("ok") is not True:
                    raise NotificationError("Telegram Bot API отклонил уведомление")
                return
            except NotificationError:
                if attempt >= self._max_retries:
                    raise
            except (httpx.HTTPError, ValueError):
                if attempt >= self._max_retries:
                    # Исходное исключение может содержать URL с bot token.
                    raise NotificationError(
                        "Telegram Bot API недоступен или вернул некорректный ответ"
                    ) from None

            retry_delay = self._retry_backoff_seconds * (2**attempt)
            if retry_delay > 0:
                await asyncio.sleep(retry_delay)
