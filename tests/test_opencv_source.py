from __future__ import annotations

import unittest
from collections.abc import Iterator
from unittest.mock import patch

import cv2
import numpy as np

from people_monitor.config import CameraConfig, CameraSourceKind
from people_monitor.video import OpenCvFrameSource


class _FakeCapture:
    def __init__(
        self,
        frames: tuple[tuple[bool, object], ...],
        *,
        opened: bool = True,
        fps: float = 25.0,
    ) -> None:
        self._frames: Iterator[tuple[bool, object]] = iter(frames)
        self._opened = opened
        self._fps = fps
        self.released = False
        self.read_calls = 0

    def isOpened(self) -> bool:
        return self._opened

    def read(self) -> tuple[bool, object]:
        self.read_calls += 1
        return next(self._frames)

    def get(self, property_id: int) -> float:
        if property_id == cv2.CAP_PROP_FPS:
            return self._fps
        return 0.0

    def release(self) -> None:
        self.released = True


class OpenCvFrameSourceTest(unittest.TestCase):
    def test_file_eof_does_not_reconnect(self) -> None:
        capture = _FakeCapture(((False, None),))
        settings = CameraConfig(
            source="video.mp4",
            source_kind=CameraSourceKind.FILE,
            _env_file=None,
        )

        with patch(
            "people_monitor.video.opencv_source.cv2.VideoCapture",
            return_value=capture,
        ) as capture_factory:
            source = OpenCvFrameSource(settings=settings, fallback_fps=30.0)
            source.open()
            frame = source.read()
            source.close()

        self.assertIsNone(frame)
        self.assertEqual(source.generation, 0)
        capture_factory.assert_called_once_with("video.mp4")

    def test_live_reconnect_increments_generation(self) -> None:
        first_capture = _FakeCapture(((False, None),))
        expected_frame = np.zeros((2, 2, 3), dtype=np.uint8)
        second_capture = _FakeCapture(((True, expected_frame),))
        settings = CameraConfig(
            source="rtsp://camera/live",
            source_kind=CameraSourceKind.STREAM,
            reconnect_attempts=1,
            reconnect_backoff_seconds=0.0,
            _env_file=None,
        )

        with patch(
            "people_monitor.video.opencv_source.cv2.VideoCapture",
            side_effect=(first_capture, second_capture),
        ):
            source = OpenCvFrameSource(settings=settings, fallback_fps=30.0)
            source.open()
            frame = source.read()
            source.close()

        self.assertIs(frame, expected_frame)
        self.assertEqual(source.generation, 1)
        self.assertTrue(first_capture.released)

    def test_stop_request_skips_capture_read(self) -> None:
        capture = _FakeCapture(((True, object()),))
        settings = CameraConfig(
            source="0",
            source_kind=CameraSourceKind.DEVICE,
            _env_file=None,
        )

        with patch(
            "people_monitor.video.opencv_source.cv2.VideoCapture",
            return_value=capture,
        ):
            source = OpenCvFrameSource(settings=settings, fallback_fps=30.0)
            source.open()
            source.request_stop()
            frame = source.read()
            source.close()

        self.assertIsNone(frame)
        self.assertEqual(capture.read_calls, 0)


if __name__ == "__main__":
    unittest.main()
