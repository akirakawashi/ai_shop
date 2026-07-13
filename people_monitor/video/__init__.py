"""Абстракции и реализации источников видеокадров."""

from people_monitor.video.base import FrameSource
from people_monitor.video.opencv_source import OpenCvFrameSource

__all__ = ["FrameSource", "OpenCvFrameSource"]
