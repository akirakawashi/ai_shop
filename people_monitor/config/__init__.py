"""Типизированная конфигурация приложения из env и файла ``.env``."""

from people_monitor.config._base import BgrColor, DEFAULT_ENV_FILE
from people_monitor.config.camera import CameraConfig
from people_monitor.config.enums import (
    CameraSourceKind,
    JpegExtension,
    LogLevel,
    VideoCodec,
)
from people_monitor.config.event import EventConfig
from people_monitor.config.model import ModelConfig
from people_monitor.config.notifications import NotificationConfig, TelegramConfig
from people_monitor.config.output import OutputConfig
from people_monitor.config.roi import RoiConfig
from people_monitor.config.runtime import RuntimeConfig
from people_monitor.config.visualization import VisualizationConfig
from people_monitor.config.app import AppConfig

__all__ = [
    "AppConfig",
    "BgrColor",
    "CameraConfig",
    "CameraSourceKind",
    "DEFAULT_ENV_FILE",
    "EventConfig",
    "JpegExtension",
    "LogLevel",
    "ModelConfig",
    "NotificationConfig",
    "OutputConfig",
    "RoiConfig",
    "RuntimeConfig",
    "TelegramConfig",
    "VideoCodec",
    "VisualizationConfig",
]
