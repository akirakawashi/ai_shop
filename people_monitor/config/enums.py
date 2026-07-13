"""Перечисления допустимых значений конфигурации."""

from __future__ import annotations

from enum import StrEnum


class VideoCodec(StrEnum):
    """Поддерживаемые четырёхсимвольные коды OpenCV VideoWriter."""

    MP4V = "mp4v"
    AVC1 = "avc1"


class JpegExtension(StrEnum):
    JPG = ".jpg"
    JPEG = ".jpeg"


class CameraSourceKind(StrEnum):
    """Способ интерпретации источника кадров."""

    AUTO = "auto"
    DEVICE = "device"
    FILE = "file"
    STREAM = "stream"


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
