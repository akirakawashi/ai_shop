"""Конфигурация области интереса."""

from __future__ import annotations

from typing import Final

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from people_monitor.config._base import SettingsNormalizedPoint, _BaseConfig
from people_monitor.domain import NormalizedPoint

DEFAULT_ROI_POINTS: Final[tuple[NormalizedPoint, ...]] = (
    (0.10, 0.20),
    (0.90, 0.20),
    (0.90, 0.90),
    (0.10, 0.90),
)


class RoiConfig(_BaseConfig):
    """Нормализованные вершины выпуклого ROI."""

    model_config = SettingsConfigDict(env_prefix="ROI_")

    points: tuple[SettingsNormalizedPoint, ...] = Field(
        default=DEFAULT_ROI_POINTS,
        min_length=3,
        description="Вершины ROI в координатах от 0 до 1",
    )
