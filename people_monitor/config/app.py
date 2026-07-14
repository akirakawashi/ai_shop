"""Сборка секционных настроек в единую конфигурацию приложения."""

from __future__ import annotations

from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field

from people_monitor.config._base import DEFAULT_ENV_FILE
from people_monitor.config.camera import CameraConfig
from people_monitor.config.enums import CameraSourceKind
from people_monitor.config.event import EventConfig
from people_monitor.config.model import ModelConfig
from people_monitor.config.notifications import NotificationConfig, TelegramConfig
from people_monitor.config.output import OutputConfig
from people_monitor.config.roi import RoiConfig
from people_monitor.config.runtime import RuntimeConfig
from people_monitor.config.visualization import VisualizationConfig


class AppConfig(BaseModel):
    """Не читает env самостоятельно, а объединяет независимые секции."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_default=True,
    )

    camera: CameraConfig = Field(description="Источник видеокадров")
    model: ModelConfig = Field(description="Модель детекции и трекер")
    roi: RoiConfig = Field(description="Область интереса")
    event: EventConfig = Field(description="Правила формирования событий")
    notification: NotificationConfig = Field(description="Очередь уведомлений")
    telegram: TelegramConfig = Field(description="Канал Telegram Bot API")
    output: OutputConfig = Field(description="Файловые результаты")
    visualization: VisualizationConfig = Field(description="Отрисовка кадров")
    runtime: RuntimeConfig = Field(description="Параметры процесса")

    @classmethod
    def from_env(
        cls,
        env_file: str | Path | None = DEFAULT_ENV_FILE,
        source_kind: CameraSourceKind | None = None,
    ) -> Self:
        """Загрузить все секции из одного env-файла и окружения процесса.

        ``source_kind`` переопределяет ``camera.source_kind`` из env, позволяя
        быстро переключать сценарий (камера/экран) без правки файлов.
        """
        camera_overrides: dict[str, CameraSourceKind] = (
            {"source_kind": source_kind} if source_kind is not None else {}
        )
        return cls(
            camera=CameraConfig(_env_file=env_file, **camera_overrides),
            model=ModelConfig(_env_file=env_file),
            roi=RoiConfig(_env_file=env_file),
            event=EventConfig(_env_file=env_file),
            notification=NotificationConfig(_env_file=env_file),
            telegram=TelegramConfig(_env_file=env_file),
            output=OutputConfig(_env_file=env_file),
            visualization=VisualizationConfig(_env_file=env_file),
            runtime=RuntimeConfig(_env_file=env_file),
        )
