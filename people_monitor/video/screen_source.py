"""Источник кадров, захватывающий область экрана через mss."""

from __future__ import annotations

import logging
from threading import Event
from time import monotonic
from typing import Any, Callable, Final

import cv2
import numpy as np

from people_monitor.config import CameraConfig
from people_monitor.domain import Frame

# mss хранит пиксели в BGRA; приводим к BGR, как ожидают OpenCV и YOLO.
_BGRA_CHANNELS: Final = 4


class ScreenFrameSource:
    """Отдаёт кадры рабочего стола с тем же контрактом, что и камера."""

    def __init__(
        self,
        settings: CameraConfig,
        logger: logging.Logger | None = None,
        grabber_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._settings = settings
        self._logger = logger or logging.getLogger(__name__)
        # Ленивая фабрика: зависимость mss нужна только при реальном захвате.
        self._grabber_factory = grabber_factory
        self._grabber: Any | None = None
        self._region: dict[str, int] | None = None
        self._stop_requested = Event()
        self._last_grab_time: float | None = None

    @property
    def generation(self) -> int:
        # Экран не переподключается: непрерывный участок всегда один.
        return 0

    @property
    def fps(self) -> float:
        return self._settings.screen_fps

    def open(self) -> None:
        if self._grabber is not None:
            raise RuntimeError("Источник экрана уже открыт")
        self._stop_requested.clear()
        self._last_grab_time = None
        self._grabber = self._create_grabber()
        self._region = self._resolve_region(self._grabber)
        self._logger.info(
            "Захват экрана %s: регион %s",
            self._settings.id,
            self._region,
        )

    def read(self) -> Frame | None:
        if self._stop_requested.is_set():
            return None
        grabber = self._require_grabber()
        if self._throttle():
            return None
        shot = grabber.grab(self._region)
        if self._stop_requested.is_set():
            return None
        pixels = np.asarray(shot, dtype=np.uint8)
        if pixels.ndim == 3 and pixels.shape[2] == _BGRA_CHANNELS:
            return cv2.cvtColor(pixels, cv2.COLOR_BGRA2BGR)
        return np.ascontiguousarray(pixels)

    def video_time(self, frame_index: int) -> float:
        return frame_index / self.fps

    def request_stop(self) -> None:
        self._stop_requested.set()

    def close(self) -> None:
        self.request_stop()
        if self._grabber is not None:
            close = getattr(self._grabber, "close", None)
            if callable(close):
                close()
        self._grabber = None
        self._region = None

    def _create_grabber(self) -> Any:
        if self._grabber_factory is not None:
            return self._grabber_factory()
        try:
            import mss
        except ImportError as error:  # pragma: no cover - зависит от окружения
            raise RuntimeError(
                "Для source_kind=screen нужен пакет mss (uv add mss)"
            ) from error
        return mss.mss()

    def _resolve_region(self, grabber: Any) -> dict[str, int]:
        region = self._settings.screen_region
        if region is not None:
            left, top, width, height = region
            return {"left": left, "top": top, "width": width, "height": height}
        monitors = grabber.monitors
        index = self._settings.screen_monitor
        if index >= len(monitors):
            raise RuntimeError(
                f"Монитор {index} недоступен; найдено мониторов: "
                f"{len(monitors) - 1}"
            )
        monitor = monitors[index]
        return {
            "left": int(monitor["left"]),
            "top": int(monitor["top"]),
            "width": int(monitor["width"]),
            "height": int(monitor["height"]),
        }

    def _throttle(self) -> bool:
        """Выдержать целевой FPS; вернуть True, если запрошена остановка."""
        now = monotonic()
        if self._last_grab_time is not None:
            frame_period = 1.0 / self.fps
            delay = frame_period - (now - self._last_grab_time)
            if delay > 0 and self._stop_requested.wait(delay):
                return True
        self._last_grab_time = monotonic()
        return False

    def _require_grabber(self) -> Any:
        if self._grabber is None:
            raise RuntimeError("Источник экрана ещё не открыт")
        return self._grabber
