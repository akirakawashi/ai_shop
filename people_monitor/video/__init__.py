"""Абстракции и реализации источников видеокадров."""

from people_monitor.video.base import FrameSource
from people_monitor.video.opencv_source import OpenCvFrameSource
from people_monitor.video.screen_source import ScreenFrameSource

__all__ = ["FrameSource", "OpenCvFrameSource", "ScreenFrameSource"]
