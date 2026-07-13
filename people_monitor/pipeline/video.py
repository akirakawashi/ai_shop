"""Упорядоченная обработка файла, камеры или RTSP-потока."""

from __future__ import annotations

import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from time import monotonic
from typing import Final

import cv2

from people_monitor.config import AppConfig
from people_monitor.detection import PeopleTracker
from people_monitor.domain import Frame, QueueFullEvent
from people_monitor.events import QueueOccupancyMonitor
from people_monitor.notifications import AsyncNotificationWorker
from people_monitor.storage import EventStore
from people_monitor.visualization import FrameRenderer
from people_monitor.video import FrameSource

_UNSAFE_FILENAME_CHARS: Final = re.compile(r"[^a-zA-Z0-9_.-]")
_VISION_EXECUTOR_WORKERS: Final = 1
_VISION_THREAD_PREFIX: Final = "vision-pipeline"


class VideoPipeline:
    """Сохраняет строгий порядок кадров и уступает loop между кадрами."""

    def __init__(
        self,
        settings: AppConfig,
        tracker: PeopleTracker,
        monitor: QueueOccupancyMonitor,
        renderer: FrameRenderer,
        frame_source: FrameSource,
        event_store: EventStore,
        notification_worker: AsyncNotificationWorker,
        notification_snapshots_enabled: bool,
        logger: logging.Logger | None = None,
    ) -> None:
        self._settings = settings
        self._tracker = tracker
        self._monitor = monitor
        self._renderer = renderer
        self._frame_source = frame_source
        self._event_store = event_store
        self._notification_worker = notification_worker
        self._notification_snapshots_enabled = notification_snapshots_enabled
        self._logger = logger or logging.getLogger(__name__)

    async def run(self) -> None:
        writer: cv2.VideoWriter | None = None
        frame_index = 0
        event_loop = asyncio.get_running_loop()
        vision_executor = ThreadPoolExecutor(
            max_workers=_VISION_EXECUTOR_WORKERS,
            thread_name_prefix=_VISION_THREAD_PREFIX,
        )

        try:
            source_generation = await event_loop.run_in_executor(
                vision_executor,
                self._open_frame_source,
            )
            while True:
                frame, video_time_seconds, generation = await event_loop.run_in_executor(
                    vision_executor,
                    self._read_frame,
                    frame_index,
                )
                if frame is None:
                    break

                if generation != source_generation:
                    self._logger.warning(
                        "Обнаружен новый участок потока камеры %s; "
                        "сбрасываю tracker и состояния событий",
                        self._settings.camera.id,
                    )
                    self._monitor.reset()
                    await event_loop.run_in_executor(
                        vision_executor,
                        self._tracker.reset,
                    )
                    source_generation = generation

                height, width = frame.shape[:2]
                if writer is None and self._settings.output.save_annotated_video:
                    writer = self._create_writer(
                        width=width,
                        height=height,
                        fps=self._frame_source.fps,
                    )

                detections = await event_loop.run_in_executor(
                    vision_executor,
                    self._tracker.track,
                    frame,
                )
                analysis = self._monitor.analyze(
                    detections=detections,
                    frame_index=frame_index,
                    frame_width=width,
                    frame_height=height,
                    video_time_seconds=video_time_seconds,
                    observed_at_seconds=monotonic(),
                )
                rendered_frame = self._renderer.draw(frame.copy(), analysis)

                if writer is not None:
                    writer.write(rendered_frame)

                snapshot = self._snapshot_if_needed(
                    rendered_frame,
                    has_events=bool(analysis.events),
                )
                for event in analysis.events:
                    self._publish_event(event, snapshot)

                frame_index += 1
                # Детекция остаётся синхронной и последовательной; здесь сеть получает
                # возможность продолжить уже запущенные async-запросы.
                await asyncio.sleep(0)
        finally:
            self._frame_source.request_stop()
            try:
                await event_loop.run_in_executor(
                    vision_executor,
                    self._frame_source.close,
                )
            finally:
                try:
                    # join может ждать незавершённый backend-вызов, поэтому не
                    # блокируем им event loop во время graceful shutdown.
                    await asyncio.to_thread(
                        vision_executor.shutdown,
                        wait=True,
                        cancel_futures=True,
                    )
                finally:
                    if writer is not None:
                        writer.release()

        self._logger.info("Обработка завершена, кадров: %s", frame_index)

    def _open_frame_source(self) -> int:
        self._frame_source.open()
        return self._frame_source.generation

    def _read_frame(self, frame_index: int) -> tuple[Frame | None, float, int]:
        frame = self._frame_source.read()
        if frame is None:
            return None, 0.0, self._frame_source.generation
        return (
            frame,
            self._frame_source.video_time(frame_index),
            self._frame_source.generation,
        )

    def _publish_event(
        self,
        event: QueueFullEvent,
        snapshot: bytes | None,
    ) -> None:
        self._event_store.append(event)
        if snapshot is not None and self._settings.output.save_snapshots:
            self._save_snapshot(event, snapshot)
        notification_snapshot = (
            snapshot if self._notification_snapshots_enabled else None
        )
        self._notification_worker.submit(event, notification_snapshot)

    def _snapshot_if_needed(self, frame: Frame, has_events: bool) -> bytes | None:
        if not has_events:
            return None
        if (
            not self._settings.output.save_snapshots
            and not self._notification_snapshots_enabled
        ):
            return None
        return self._renderer.encode_jpeg(
            frame,
            extension=self._settings.output.jpeg_extension.value,
            quality=self._settings.output.jpeg_quality,
        )

    def _create_writer(
        self,
        width: int,
        height: int,
        fps: float,
    ) -> cv2.VideoWriter:
        path = self._settings.output.annotated_video
        path.parent.mkdir(parents=True, exist_ok=True)
        codec = self._settings.output.video_codec.value
        writer = cv2.VideoWriter(
            str(path),
            cv2.VideoWriter_fourcc(*codec),
            fps,
            (width, height),
        )
        if not writer.isOpened():
            writer.release()
            raise RuntimeError(f"Не удалось создать выходное видео: {path}")
        return writer

    def _save_snapshot(self, event: QueueFullEvent, snapshot: bytes) -> None:
        directory = self._settings.output.snapshots_dir
        directory.mkdir(parents=True, exist_ok=True)
        safe_camera_id = _UNSAFE_FILENAME_CHARS.sub(
            "_",
            self._settings.camera.id,
        )
        filename = (
            f"{safe_camera_id}_event-{event.event_id}"
            f"{self._settings.output.jpeg_extension.value}"
        )
        (directory / filename).write_bytes(snapshot)
