"""Конфигурация процесса и журналирования."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from people_monitor.config._base import PositiveFloat, _BaseConfig
from people_monitor.config.enums import LogLevel


class RuntimeConfig(_BaseConfig):
    """Общие параметры выполнения приложения."""

    model_config = SettingsConfigDict(env_prefix="RUNTIME_")

    fallback_fps: PositiveFloat = Field(
        default=25.0,
        description="FPS при отсутствии корректного значения от источника",
    )
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Минимальный уровень журналирования",
    )
    log_format: str = Field(
        default="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        min_length=1,
        description="Формат записей стандартного logging",
    )
