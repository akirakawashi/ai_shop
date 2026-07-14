"""Конфигурация автомата заполненности очереди."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from people_monitor.config._base import (
    NonNegativeFloat,
    PositiveFloat,
    PositiveInt,
    _BaseConfig,
)


class EventConfig(_BaseConfig):
    """Вместимость ROI и параметры устойчивого формирования события."""

    model_config = SettingsConfigDict(env_prefix="EVENT_")

    roi_capacity: PositiveInt = Field(
        default=2,
        description="Количество людей, при котором ROI считается заполненной",
    )
    full_confirm_seconds: PositiveFloat = Field(
        default=20.0,
        description=(
            "Непрерывное время выше или на вместимости до подтверждения заполнения"
        ),
    )
    recovery_confirm_frames: PositiveInt = Field(
        default=10,
        description="Кадры подряд ниже вместимости для повторного взведения",
    )
    cooldown_seconds: NonNegativeFloat = Field(
        default=60.0,
        description="Минимальный интервал между уведомлениями одной ROI",
    )
