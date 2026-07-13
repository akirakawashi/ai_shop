"""Конфигурация файловых результатов обработки."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import SettingsConfigDict

from people_monitor.config._base import JpegQuality, _BaseConfig
from people_monitor.config.enums import JpegExtension, VideoCodec


class OutputConfig(_BaseConfig):
    """Пути и форматы сохраняемых артефактов."""

    model_config = SettingsConfigDict(env_prefix="OUTPUT_")

    annotated_video: Path = Field(
        default=Path("output/roi_monitor.mp4"),
        description="Путь к видео с разметкой",
    )
    events_file: Path = Field(
        default=Path("output/events.jsonl"),
        description="Путь к JSONL-журналу событий",
    )
    snapshots_dir: Path = Field(
        default=Path("output/events"),
        description="Каталог JPEG-снимков событий",
    )
    save_annotated_video: bool = Field(
        default=True,
        description="Сохранять видео с ROI и bbox",
    )
    save_snapshots: bool = Field(
        default=True,
        description="Сохранять локальные снимки событий",
    )
    video_codec: VideoCodec = Field(
        default=VideoCodec.MP4V,
        description="FourCC кодек выходного видео",
    )
    jpeg_extension: JpegExtension = Field(
        default=JpegExtension.JPG,
        description="Расширение и формат JPEG-снимков",
    )
    jpeg_quality: JpegQuality = Field(
        default=90,
        description="Качество JPEG от 1 до 100",
    )

    @field_validator("annotated_video", "events_file", "snapshots_dir")
    @classmethod
    def expand_output_path(cls, value: Path) -> Path:
        return value.expanduser()
