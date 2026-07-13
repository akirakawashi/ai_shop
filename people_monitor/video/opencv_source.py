"""Синхронный источник кадров на базе OpenCV VideoCapture."""

from __future__ import annotations

import logging
from math import isfinite
from threading import Event
from typing import Final
from urllib.parse import urlparse

import cv2

from people_monitor.config import CameraConfig, CameraSourceKind
from people_monitor.domain import Frame

_STREAM_SCHEMES: Final = frozenset({"http", "https", "rtsp", "rtsps"})


class OpenCvFrameSource:
    """Различает EOF файла и временный сбой live-потока."""

    def __init__(
        self,
        settings: CameraConfig,
        fallback_fps: float,
        logger: logging.Logger | None = None,
    ) -> None:
        self._settings = settings
        self._fallback_fps = fallback_fps
        self._logger = logger or logging.getLogger(__name__)
        self._capture: cv2.VideoCapture | None = None
        self._fps: float | None = None
        self._generation = 0
        self._stop_requested = Event()

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def fps(self) -> float:
        if self._fps is None:
            raise RuntimeError("Источник кадров ещё не открыт")
        return self._fps

    def open(self) -> None:
        if self._capture is not None:
            raise RuntimeError("Источник кадров уже открыт")
        self._stop_requested.clear()
        self._generation = 0
        capture = self._open_with_retries()
        if capture is None:
            raise RuntimeError(
                f"Не удалось открыть источник камеры {self._settings.id}"
            )
        self._attach_capture(capture, increment_generation=False)

    def read(self) -> Frame | None:
        if self._stop_requested.is_set():
            return None
        capture = self._require_capture()
        ok, frame = capture.read()
        if self._stop_requested.is_set():
            return None
        if ok:
            return frame
        if not self._should_reconnect():
            return None

        self._logger.warning(
            "Поток камеры %s прерван; начинаю переподключение",
            self._settings.id,
        )
        self._release_capture()
        frame = self._reconnect_and_read()
        if frame is None:
            if self._stop_requested.is_set():
                return None
            raise RuntimeError(
                f"Не удалось восстановить поток камеры {self._settings.id}"
            )
        return frame

    def video_time(self, frame_index: int) -> float:
        capture = self._require_capture()
        position_ms = float(capture.get(cv2.CAP_PROP_POS_MSEC))
        if isfinite(position_ms) and position_ms > 0:
            return position_ms / 1_000.0
        return frame_index / self.fps

    def close(self) -> None:
        self.request_stop()
        self._release_capture()

    def request_stop(self) -> None:
        self._stop_requested.set()

    def _open_with_retries(self) -> cv2.VideoCapture | None:
        retry_count = self._settings.reconnect_attempts if self._should_reconnect() else 0
        for attempt in range(retry_count + 1):
            if self._stop_requested.is_set():
                return None
            if attempt > 0 and self._wait_before_retry(attempt - 1):
                return None
            capture = self._create_capture()
            if self._stop_requested.is_set():
                capture.release()
                return None
            if capture.isOpened():
                return capture
            capture.release()
        return None

    def _reconnect_and_read(self) -> Frame | None:
        for attempt in range(self._settings.reconnect_attempts):
            if self._wait_before_retry(attempt):
                return None
            capture = self._create_capture()
            if self._stop_requested.is_set():
                capture.release()
                return None
            if not capture.isOpened():
                capture.release()
                continue
            ok, frame = capture.read()
            if self._stop_requested.is_set():
                capture.release()
                return None
            if ok:
                self._attach_capture(capture, increment_generation=True)
                self._logger.info(
                    "Поток камеры %s восстановлен",
                    self._settings.id,
                )
                return frame
            capture.release()
        return None

    def _create_capture(self) -> cv2.VideoCapture:
        source = self._capture_source()
        if not self._uses_network_timeouts():
            return cv2.VideoCapture(source)
        timeout_parameters = [
            cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
            self._settings.stream_open_timeout_milliseconds,
            cv2.CAP_PROP_READ_TIMEOUT_MSEC,
            self._settings.stream_read_timeout_milliseconds,
        ]
        return cv2.VideoCapture(source, cv2.CAP_ANY, timeout_parameters)

    def _attach_capture(
        self,
        capture: cv2.VideoCapture,
        increment_generation: bool,
    ) -> None:
        detected_fps = float(capture.get(cv2.CAP_PROP_FPS))
        self._fps = (
            detected_fps
            if isfinite(detected_fps) and detected_fps > 0
            else self._fallback_fps
        )
        self._capture = capture
        if increment_generation:
            self._generation += 1

    def _release_capture(self) -> None:
        if self._capture is not None:
            self._capture.release()
        self._capture = None
        self._fps = None

    def _require_capture(self) -> cv2.VideoCapture:
        if self._capture is None:
            raise RuntimeError("Источник кадров ещё не открыт")
        return self._capture

    def _capture_source(self) -> str | int:
        source = self._settings.source
        kind = self._settings.source_kind
        if kind is CameraSourceKind.DEVICE:
            try:
                return int(source)
            except ValueError:
                raise ValueError(
                    "Для camera.source_kind=device источник должен быть целым числом"
                ) from None
        if kind is CameraSourceKind.FILE:
            return source
        return int(source) if kind is CameraSourceKind.AUTO and source.isdecimal() else source

    def _should_reconnect(self) -> bool:
        kind = self._settings.source_kind
        if kind in {
            CameraSourceKind.DEVICE,
            CameraSourceKind.STREAM,
        }:
            return True
        if kind is CameraSourceKind.FILE:
            return False
        source = self._settings.source
        return source.isdecimal() or urlparse(source).scheme.lower() in _STREAM_SCHEMES

    def _uses_network_timeouts(self) -> bool:
        kind = self._settings.source_kind
        if kind is CameraSourceKind.STREAM:
            return True
        if kind in {CameraSourceKind.DEVICE, CameraSourceKind.FILE}:
            return False
        return urlparse(self._settings.source).scheme.lower() in _STREAM_SCHEMES

    def _retry_delay(self, attempt: int) -> float:
        exponential_delay = self._settings.reconnect_backoff_seconds * (2**attempt)
        return min(exponential_delay, self._settings.reconnect_max_backoff_seconds)

    def _wait_before_retry(self, attempt: int) -> bool:
        """Вернуть True, если ожидание было прервано запросом остановки."""
        return self._stop_requested.wait(self._retry_delay(attempt))
