from __future__ import annotations

import unittest

import numpy as np

from people_monitor.app import _build_frame_source
from people_monitor.config import AppConfig, CameraConfig, CameraSourceKind
from people_monitor.video import OpenCvFrameSource, ScreenFrameSource


class _FakeGrabber:
    def __init__(self, width: int = 8, height: int = 4) -> None:
        # monitors[0] — общий bounding box, monitors[1] — основной монитор.
        self.monitors = [
            {"left": 0, "top": 0, "width": width, "height": height},
            {"left": 0, "top": 0, "width": width, "height": height},
        ]
        self._width = width
        self._height = height
        self.grabbed_regions: list[dict[str, int]] = []
        self.closed = False

    def grab(self, region: dict[str, int]) -> np.ndarray:
        self.grabbed_regions.append(region)
        # mss отдаёт BGRA; повторяем форму (H, W, 4).
        return np.zeros((region["height"], region["width"], 4), dtype=np.uint8)

    def close(self) -> None:
        self.closed = True


def _screen_settings(**overrides: object) -> CameraConfig:
    params: dict[str, object] = {
        "source_kind": CameraSourceKind.SCREEN,
        "screen_fps": 1000.0,  # без ощутимого троттлинга в тестах
        "_env_file": None,
    }
    params.update(overrides)
    return CameraConfig(**params)


class ScreenFrameSourceTest(unittest.TestCase):
    def test_read_returns_bgr_frame_of_full_monitor(self) -> None:
        grabber = _FakeGrabber(width=8, height=4)
        source = ScreenFrameSource(
            settings=_screen_settings(),
            grabber_factory=lambda: grabber,
        )
        source.open()
        frame = source.read()
        source.close()

        assert frame is not None
        self.assertEqual(frame.shape, (4, 8, 3))  # BGRA -> BGR
        self.assertEqual(frame.dtype, np.uint8)
        self.assertEqual(
            grabber.grabbed_regions[0],
            {"left": 0, "top": 0, "width": 8, "height": 4},
        )
        self.assertTrue(grabber.closed)
        self.assertEqual(source.generation, 0)
        self.assertEqual(source.fps, 1000.0)

    def test_custom_region_is_passed_to_grabber(self) -> None:
        grabber = _FakeGrabber(width=100, height=100)
        source = ScreenFrameSource(
            settings=_screen_settings(screen_region=(10, 20, 30, 40)),
            grabber_factory=lambda: grabber,
        )
        source.open()
        source.read()
        source.close()

        self.assertEqual(
            grabber.grabbed_regions[0],
            {"left": 10, "top": 20, "width": 30, "height": 40},
        )

    def test_stop_request_skips_grab(self) -> None:
        grabber = _FakeGrabber()
        source = ScreenFrameSource(
            settings=_screen_settings(),
            grabber_factory=lambda: grabber,
        )
        source.open()
        source.request_stop()
        frame = source.read()
        source.close()

        self.assertIsNone(frame)
        self.assertEqual(grabber.grabbed_regions, [])

    def test_missing_monitor_raises_on_open(self) -> None:
        source = ScreenFrameSource(
            settings=_screen_settings(screen_monitor=9),
            grabber_factory=_FakeGrabber,
        )
        with self.assertRaises(RuntimeError):
            source.open()


class FrameSourceSelectionTest(unittest.TestCase):
    def test_screen_kind_selects_screen_source(self) -> None:
        settings = AppConfig.from_env(
            env_file=None,
            source_kind=CameraSourceKind.SCREEN,
        )
        self.assertIsInstance(_build_frame_source(settings), ScreenFrameSource)

    def test_device_kind_selects_opencv_source(self) -> None:
        settings = AppConfig.from_env(
            env_file=None,
            source_kind=CameraSourceKind.DEVICE,
        )
        self.assertIsInstance(_build_frame_source(settings), OpenCvFrameSource)


if __name__ == "__main__":
    unittest.main()
