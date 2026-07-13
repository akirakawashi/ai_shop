"""Конфигурация автомата событий выхода."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import SettingsConfigDict

from people_monitor.config._base import (
    NonNegativeFloat,
    PositiveInt,
    _BaseConfig,
)


class EventConfig(_BaseConfig):
    """Пороговые параметры подтверждения переходов bbox."""

    model_config = SettingsConfigDict(env_prefix="EVENT_")

    outside_confirm_frames: PositiveInt = Field(
        default=5,
        description="Кадры подряд с преобладанием внешней площади",
    )
    inside_confirm_frames: PositiveInt = Field(
        default=3,
        description="Кадры подряд для подтверждения нахождения внутри ROI",
    )
    cooldown_seconds: NonNegativeFloat = Field(
        default=30.0,
        description="Минимальный интервал между повторными событиями трека",
    )
    track_ttl_frames: PositiveInt = Field(
        default=150,
        description="Срок хранения состояния пропавшего track_id в кадрах",
    )

    @model_validator(mode="after")
    def validate_track_ttl(self) -> Self:
        required_ttl = max(self.outside_confirm_frames, self.inside_confirm_frames)
        if self.track_ttl_frames < required_ttl:
            raise ValueError(
                "track_ttl_frames не может быть меньше количества кадров подтверждения"
            )
        return self
