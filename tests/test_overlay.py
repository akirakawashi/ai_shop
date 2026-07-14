from __future__ import annotations

import unittest

from people_monitor.app import run
from people_monitor.config import AppConfig, CameraSourceKind
from people_monitor.visualization.overlay import _bgr_to_hex, _font_pixels


class OverlayColorTest(unittest.TestCase):
    def test_bgr_to_hex_swaps_channels(self) -> None:
        # Цвет ROI по умолчанию задан как BGR и должен стать золотым в RGB.
        self.assertEqual(_bgr_to_hex((0, 215, 255)), "#ffd700")

    def test_bgr_to_hex_pads_single_digit_channels(self) -> None:
        self.assertEqual(_bgr_to_hex((1, 2, 3)), "#030201")

    def test_font_pixels_never_below_floor(self) -> None:
        self.assertEqual(_font_pixels(0.0), 8)
        self.assertEqual(_font_pixels(1.0), 22)


class OverlayRequiresScreenSourceTest(unittest.IsolatedAsyncioTestCase):
    async def test_overlay_with_camera_source_is_rejected(self) -> None:
        settings = AppConfig.from_env(
            env_file=None,
            source_kind=CameraSourceKind.DEVICE,
        )
        with self.assertRaises(RuntimeError) as error:
            await run(settings, dry_run=True, overlay=True)

        self.assertIn("screen", str(error.exception))


if __name__ == "__main__":
    unittest.main()
