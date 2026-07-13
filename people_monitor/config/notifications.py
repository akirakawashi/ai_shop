"""Конфигурация очереди уведомлений и Telegram Bot API."""

from __future__ import annotations

from pathlib import Path

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import SettingsConfigDict

from people_monitor.config._base import (
    NonBlankString,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveFloat,
    PositiveInt,
    _BaseConfig,
)
from people_monitor.config.enums import JpegExtension


class NotificationConfig(_BaseConfig):
    """Параметры доставки, не зависящие от конкретного канала."""

    model_config = SettingsConfigDict(env_prefix="NOTIFICATION_")

    queue_size: PositiveInt = Field(
        default=100,
        description="Максимальное количество ожидающих уведомлений",
    )
    drain_timeout_seconds: PositiveFloat = Field(
        default=15.0,
        description="Timeout опустошения очереди при завершении",
    )
    notifier_close_timeout_seconds: PositiveFloat = Field(
        default=5.0,
        description="Отдельный timeout закрытия канала доставки",
    )
    drain_on_shutdown: bool = Field(
        default=True,
        description="Доставить накопленные уведомления перед завершением",
    )


class TelegramConfig(_BaseConfig):
    """Доступ и политика повторов Telegram Bot API."""

    model_config = SettingsConfigDict(env_prefix="TELEGRAM_")

    enabled: bool = Field(
        default=False,
        description="Включить реальную доставку через Telegram",
    )
    bot_token: SecretStr | None = Field(
        default=None,
        description="Секретный токен Telegram-бота",
    )
    chat_id: NonBlankString | None = Field(
        default=None,
        description="Идентификатор получателя или канала",
    )
    api_base_url: AnyHttpUrl = Field(
        default="https://api.telegram.org",
        description="Базовый HTTPS URL Telegram API или reverse proxy",
    )
    timeout_seconds: PositiveFloat = Field(
        default=10.0,
        description="Timeout одного HTTP-запроса",
    )
    max_retries: NonNegativeInt = Field(
        default=2,
        description="Количество повторов после неуспешной отправки",
    )
    retry_backoff_seconds: NonNegativeFloat = Field(
        default=0.5,
        description="Начальная задержка exponential retry",
    )
    send_snapshot: bool = Field(
        default=True,
        description="Прикладывать JPEG кадра к уведомлению",
    )
    snapshot_filename: NonBlankString = Field(
        default="roi-event.jpg",
        description="Имя JPEG-файла в Telegram multipart-запросе",
    )

    @field_validator("bot_token")
    @classmethod
    def normalize_bot_token(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        token = value.get_secret_value().strip()
        return SecretStr(token) if token else None

    @field_validator("api_base_url")
    @classmethod
    def validate_https_api_url(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.scheme != "https":
            raise ValueError("Telegram API URL должен использовать HTTPS")
        if value.query is not None or value.fragment is not None:
            raise ValueError("Telegram API URL не должен содержать query или fragment")
        return value

    @field_validator("snapshot_filename")
    @classmethod
    def validate_snapshot_filename(cls, value: str) -> str:
        if (
            Path(value).name != value
            or "/" in value
            or "\\" in value
            or any(ord(character) < 32 for character in value)
        ):
            raise ValueError("snapshot_filename должен быть безопасным именем файла")
        allowed_extensions = {extension.value for extension in JpegExtension}
        if Path(value).suffix.lower() not in allowed_extensions:
            raise ValueError("snapshot_filename должен иметь расширение .jpg или .jpeg")
        return value
