"""Конфигурация источника видеокадров."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import SettingsConfigDict

from people_monitor.config._base import (
    NonBlankString,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveFloat,
    PositiveInt,
    _BaseConfig,
)
from people_monitor.config.enums import CameraSourceKind


class CameraConfig(_BaseConfig):
    """Параметры файла, устройства или сетевого видеопотока."""

    model_config = SettingsConfigDict(env_prefix="CAMERA_")

    id: NonBlankString = Field(
        default="shop-entrance",
        description="Стабильный идентификатор камеры в событиях и логах",
    )
    source: NonBlankString = Field(
        default="test.mp4",
        description="Путь, URL или строковый индекс устройства",
    )
    source_kind: CameraSourceKind = Field(
        default=CameraSourceKind.AUTO,
        description="Явный способ интерпретации источника",
    )
    stream_open_timeout_milliseconds: PositiveInt = Field(
        default=10_000,
        description="Backend timeout открытия сетевого потока",
    )
    stream_read_timeout_milliseconds: PositiveInt = Field(
        default=10_000,
        description="Backend timeout чтения сетевого потока",
    )
    reconnect_attempts: NonNegativeInt = Field(
        default=5,
        description="Количество попыток восстановить live-источник",
    )
    reconnect_backoff_seconds: NonNegativeFloat = Field(
        default=1.0,
        description="Начальная задержка между попытками reconnect",
    )
    reconnect_max_backoff_seconds: PositiveFloat = Field(
        default=30.0,
        description="Максимальная задержка между попытками reconnect",
    )

    @model_validator(mode="after")
    def validate_reconnect_backoff(self) -> Self:
        if self.reconnect_max_backoff_seconds < self.reconnect_backoff_seconds:
            raise ValueError(
                "reconnect_max_backoff_seconds не может быть меньше "
                "reconnect_backoff_seconds"
            )
        return self
