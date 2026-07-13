"""Адаптер YOLO/ByteTrack к доменному контракту PeopleTracker."""

from __future__ import annotations

from typing import Final

from ultralytics import YOLO

from people_monitor.domain import BoundingBox, Frame, TrackedDetection

_PERSIST_TRACKS: Final = True


class UltralyticsPeopleTracker:
    def __init__(
        self,
        weights: str,
        confidence: float,
        tracker: str,
        class_id: int,
        image_size: int,
        iou_threshold: float,
        device: str | None,
        verbose: bool,
    ) -> None:
        self._weights = weights
        self._model: YOLO | None = None
        self._confidence = confidence
        self._tracker = tracker
        self._class_id = class_id
        self._image_size = image_size
        self._iou_threshold = iou_threshold
        self._device = device
        self._verbose = verbose

    def reset(self) -> None:
        # Публичный API Ultralytics не гарантирует стабильный способ очистки
        # ByteTrack, поэтому после discontinuity безопаснее пересоздать модель.
        self._model = None

    def track(self, frame: Frame) -> tuple[TrackedDetection, ...]:
        model = self._model
        if model is None:
            # Первый вызов приходит из vision executor. Так загрузка модели не
            # блокирует event loop, а создание и inference живут в одном потоке.
            model = YOLO(self._weights)
            self._model = model

        inference_options: dict[str, object] = {
            "source": frame,
            "persist": _PERSIST_TRACKS,
            "classes": [self._class_id],
            "conf": self._confidence,
            "iou": self._iou_threshold,
            "imgsz": self._image_size,
            "tracker": self._tracker,
            "verbose": self._verbose,
        }
        if self._device is not None:
            inference_options["device"] = self._device

        result = model.track(
            **inference_options,
        )[0]

        if result.boxes is None:
            return ()

        detections: list[TrackedDetection] = []
        for box in result.boxes:
            x1, y1, x2, y2 = (float(value) for value in box.xyxy[0].tolist())
            track_id = int(box.id[0].item()) if box.id is not None else None
            detections.append(
                TrackedDetection(
                    bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
                    confidence=float(box.conf[0].item()),
                    track_id=track_id,
                )
            )
        return tuple(detections)
