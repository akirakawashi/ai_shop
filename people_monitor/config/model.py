"""Конфигурация модели детекции и трекера."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from people_monitor.config._base import (
    NonBlankString,
    NonNegativeInt,
    PositiveInt,
    Probability,
    _BaseConfig,
)
from people_monitor.domain import CocoClass


class ModelConfig(_BaseConfig):
    """Параметры Ultralytics YOLO и ByteTrack."""

    model_config = SettingsConfigDict(env_prefix="MODEL_")

    weights: NonBlankString = Field(
        default="yolov8s.pt",
        description="Путь или имя весов YOLO",
    )
    confidence: Probability = Field(
        default=0.35,
        description="Минимальная уверенность детекции",
    )
    tracker: NonBlankString = Field(
        default="bytetrack.yaml",
        description="Конфигурация трекера Ultralytics",
    )
    class_id: NonNegativeInt = Field(
        default=int(CocoClass.PERSON),
        description="Идентификатор отслеживаемого класса",
    )
    image_size: PositiveInt = Field(
        default=640,
        description="Размер изображения для inference",
    )
    iou_threshold: Probability = Field(
        default=0.7,
        description="IoU-порог подавления пересекающихся детекций",
    )
    device: NonBlankString | None = Field(
        default=None,
        description="Устройство inference, например cpu или cuda:0",
    )
    verbose: bool = Field(
        default=False,
        description="Включить подробный вывод Ultralytics",
    )
