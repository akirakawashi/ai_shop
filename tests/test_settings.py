from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from people_monitor.config import (
    AppConfig,
    CameraConfig,
    EventConfig,
    ModelConfig,
    NotificationConfig,
    OutputConfig,
    RoiConfig,
    RuntimeConfig,
    TelegramConfig,
    VisualizationConfig,
)

_CONFIG_TYPES = (
    AppConfig,
    CameraConfig,
    ModelConfig,
    RoiConfig,
    EventConfig,
    NotificationConfig,
    TelegramConfig,
    OutputConfig,
    VisualizationConfig,
    RuntimeConfig,
)


class AppConfigTest(unittest.TestCase):
    def test_every_config_field_has_description(self) -> None:
        for config_type in _CONFIG_TYPES:
            for field_name, field_info in config_type.model_fields.items():
                with self.subTest(config=config_type.__name__, field=field_name):
                    self.assertTrue(field_info.description)

    def test_env_example_is_valid(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = AppConfig.from_env(Path(".env.example"))

        self.assertEqual(settings.camera.id, "shop-entrance")
        self.assertEqual(settings.event.roi_capacity, 2)
        self.assertFalse(settings.telegram.enabled)
        self.assertIsNone(settings.telegram.bot_token)
        self.assertIsNone(settings.telegram.chat_id)
        self.assertIsNone(settings.telegram.proxy_url)

    def test_defaults_are_valid_without_environment(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = AppConfig.from_env(None)

        self.assertEqual(settings.camera.source, "test.mp4")
        self.assertEqual(settings.model.weights, "yolov8s.pt")
        self.assertEqual(settings.event.full_confirm_seconds, 20.0)
        self.assertFalse(settings.telegram.enabled)

    def test_prefixed_environment_overrides_defaults(self) -> None:
        environment = {
            "CAMERA_SOURCE": "rtsp://camera/live",
            "MODEL_CONFIDENCE": "0.61",
            "TELEGRAM_BOT_TOKEN": "secret-token",
            "TELEGRAM_PROXY_URL": "http://user:password@proxy.test:3128",
            "ROI_POINTS": "[[0.1,0.1],[0.9,0.1],[0.5,0.9]]",
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = AppConfig.from_env(None)

        self.assertEqual(settings.camera.source, "rtsp://camera/live")
        self.assertEqual(settings.model.confidence, 0.61)
        self.assertEqual(len(settings.roi.points), 3)
        self.assertNotIn("secret-token", repr(settings.telegram.bot_token))
        self.assertNotIn("password", repr(settings.telegram.proxy_url))

    def test_invalid_probability_is_rejected(self) -> None:
        environment = {"MODEL_CONFIDENCE": "1.5"}
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(ValidationError):
                AppConfig.from_env(None)

    def test_zero_roi_capacity_is_rejected(self) -> None:
        environment = {"EVENT_ROI_CAPACITY": "0"}
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(ValidationError):
                AppConfig.from_env(None)

    def test_non_jpeg_extension_is_rejected(self) -> None:
        environment = {"OUTPUT_JPEG_EXTENSION": ".png"}
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(ValidationError):
                AppConfig.from_env(None)

    def test_insecure_telegram_url_is_rejected(self) -> None:
        environment = {
            "TELEGRAM_API_BASE_URL": "http://api.telegram.test"
        }
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(ValidationError):
                AppConfig.from_env(None)

    def test_telegram_url_query_is_rejected(self) -> None:
        environment = {
            "TELEGRAM_API_BASE_URL": "https://api.telegram.test/proxy?token=unsafe"
        }
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(ValidationError):
                AppConfig.from_env(None)

    def test_non_http_telegram_proxy_is_rejected(self) -> None:
        environment = {"TELEGRAM_PROXY_URL": "socks5://proxy.test:1080"}
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(ValidationError):
                AppConfig.from_env(None)

    def test_dry_run_configuration_can_omit_telegram_credentials(self) -> None:
        environment = {"TELEGRAM_ENABLED": "true"}
        with patch.dict(os.environ, environment, clear=True):
            settings = AppConfig.from_env(None)

        self.assertTrue(settings.telegram.enabled)
        self.assertIsNone(settings.telegram.bot_token)
        self.assertIsNone(settings.telegram.chat_id)

    def test_notification_queue_settings_are_channel_independent(self) -> None:
        environment = {"NOTIFICATION_QUEUE_SIZE": "17"}
        with patch.dict(os.environ, environment, clear=True):
            settings = AppConfig.from_env(None)

        self.assertEqual(settings.notification.queue_size, 17)

    def test_nested_bbox_format_fields_are_rejected(self) -> None:
        environment = {
            "VISUALIZATION_BBOX_LABEL_TEMPLATE": "{roi_state:{track_id}}"
        }
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(ValidationError):
                AppConfig.from_env(None)

    def test_infinite_operational_value_is_rejected(self) -> None:
        environment = {"RUNTIME_FALLBACK_FPS": "inf"}
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(ValidationError):
                AppConfig.from_env(None)

    def test_reconnect_max_backoff_must_cover_initial_backoff(self) -> None:
        environment = {
            "CAMERA_RECONNECT_BACKOFF_SECONDS": "5",
            "CAMERA_RECONNECT_MAX_BACKOFF_SECONDS": "1",
        }
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(ValidationError):
                AppConfig.from_env(None)

    def test_custom_env_file_is_forwarded_to_every_section(self) -> None:
        content = "\n".join(
            (
                "CAMERA_ID=custom-camera",
                "MODEL_CONFIDENCE=0.52",
                "ROI_POINTS=[[0.1,0.1],[0.9,0.1],[0.5,0.9]]",
                "EVENT_ROI_CAPACITY=7",
                "NOTIFICATION_QUEUE_SIZE=23",
                "TELEGRAM_ENABLED=true",
                "OUTPUT_SAVE_SNAPSHOTS=false",
                "VISUALIZATION_ROI_LABEL_TEMPLATE=ZONE {people_count}",
                "RUNTIME_LOG_LEVEL=WARNING",
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / "camera.env"
            env_file.write_text(content, encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                settings = AppConfig.from_env(env_file)

        self.assertEqual(settings.camera.id, "custom-camera")
        self.assertEqual(settings.model.confidence, 0.52)
        self.assertEqual(len(settings.roi.points), 3)
        self.assertEqual(settings.event.roi_capacity, 7)
        self.assertEqual(settings.notification.queue_size, 23)
        self.assertTrue(settings.telegram.enabled)
        self.assertFalse(settings.output.save_snapshots)
        self.assertEqual(
            settings.visualization.roi_label_template,
            "ZONE {people_count}",
        )
        self.assertEqual(settings.runtime.log_level.value, "WARNING")

    def test_environment_has_priority_over_custom_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / "camera.env"
            env_file.write_text("CAMERA_SOURCE=file.mp4\n", encoding="utf-8")
            with patch.dict(
                os.environ,
                {"CAMERA_SOURCE": "rtsp://camera/live"},
                clear=True,
            ):
                settings = AppConfig.from_env(env_file)

        self.assertEqual(settings.camera.source, "rtsp://camera/live")

    def test_dotenv_can_reuse_https_proxy_for_telegram(self) -> None:
        content = "\n".join(
            (
                "HTTPS_PROXY=http://user:password@proxy.test:3128",
                "TELEGRAM_PROXY_URL=${HTTPS_PROXY}",
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / "camera.env"
            env_file.write_text(content, encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                settings = AppConfig.from_env(env_file)

        self.assertIsNotNone(settings.telegram.proxy_url)
        assert settings.telegram.proxy_url is not None
        self.assertEqual(
            settings.telegram.proxy_url.get_secret_value(),
            "http://user:password@proxy.test:3128",
        )


if __name__ == "__main__":
    unittest.main()
