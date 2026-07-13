"""Сборка зависимостей приложения."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from people_monitor.config import AppConfig
from people_monitor.detection import UltralyticsPeopleTracker
from people_monitor.events import QueueOccupancyMonitor
from people_monitor.geometry import ConvexPolygonRoi
from people_monitor.notifications import (
    AsyncNotificationWorker,
    LoggingNotifier,
    Notifier,
    TelegramNotifier,
)
from people_monitor.pipeline import VideoPipeline
from people_monitor.storage import JsonlEventStore
from people_monitor.video import OpenCvFrameSource
from people_monitor.visualization import FrameRenderer


@dataclass(frozen=True, slots=True)
class _NotifierBinding:
    notifier: Notifier
    include_snapshot: bool


async def run(settings: AppConfig, dry_run: bool = False) -> None:
    """Собрать и запустить приложение для одной камеры."""
    notifier_binding = _build_notifier(settings, dry_run=dry_run)
    notification_worker: AsyncNotificationWorker | None = None
    try:
        notification_worker = AsyncNotificationWorker(
            notifier=notifier_binding.notifier,
            queue_size=settings.notification.queue_size,
            drain_timeout_seconds=settings.notification.drain_timeout_seconds,
            notifier_close_timeout_seconds=(
                settings.notification.notifier_close_timeout_seconds
            ),
            drain_on_shutdown=settings.notification.drain_on_shutdown,
        )
        notification_worker.start()
        roi = ConvexPolygonRoi(settings.roi.points)
        tracker = UltralyticsPeopleTracker(
            weights=settings.model.weights,
            confidence=settings.model.confidence,
            tracker=settings.model.tracker,
            class_id=settings.model.class_id,
            image_size=settings.model.image_size,
            iou_threshold=settings.model.iou_threshold,
            device=settings.model.device,
            verbose=settings.model.verbose,
        )
        monitor = QueueOccupancyMonitor(
            camera_id=settings.camera.id,
            roi=roi,
            settings=settings.event,
        )
        pipeline = VideoPipeline(
            settings=settings,
            tracker=tracker,
            monitor=monitor,
            renderer=FrameRenderer(roi=roi, settings=settings.visualization),
            frame_source=OpenCvFrameSource(
                settings=settings.camera,
                fallback_fps=settings.runtime.fallback_fps,
            ),
            event_store=JsonlEventStore(settings.output.events_file),
            notification_worker=notification_worker,
            notification_snapshots_enabled=notifier_binding.include_snapshot,
        )
        await pipeline.run()
    finally:
        if notification_worker is not None:
            await notification_worker.close()
        else:
            try:
                await notifier_binding.notifier.close()
            except Exception:
                logging.getLogger(__name__).exception(
                    "Не удалось закрыть канал после ошибки сборки приложения"
                )


def _build_notifier(settings: AppConfig, dry_run: bool) -> _NotifierBinding:
    telegram = settings.telegram
    if dry_run or not telegram.enabled:
        return _NotifierBinding(
            notifier=LoggingNotifier(
                alert_message=settings.notification.alert_message,
            ),
            include_snapshot=False,
        )

    if telegram.bot_token is None or telegram.chat_id is None:
        raise RuntimeError(
            "Telegram включён, но TELEGRAM_BOT_TOKEN или "
            "TELEGRAM_CHAT_ID не заданы"
        )
    notifier = TelegramNotifier(
        bot_token=telegram.bot_token.get_secret_value(),
        chat_id=telegram.chat_id,
        alert_message=settings.notification.alert_message,
        api_base_url=str(telegram.api_base_url),
        proxy_url=(
            telegram.proxy_url.get_secret_value()
            if telegram.proxy_url is not None
            else None
        ),
        timeout_seconds=telegram.timeout_seconds,
        snapshot_filename=telegram.snapshot_filename,
        max_retries=telegram.max_retries,
        retry_backoff_seconds=telegram.retry_backoff_seconds,
    )
    return _NotifierBinding(
        notifier=notifier,
        include_snapshot=telegram.send_snapshot,
    )
