"""Отрисовка ROI, bbox, track_id и соотношения площадей."""

from __future__ import annotations

from typing import Final

import cv2
import numpy as np

from people_monitor.config import BgrColor, VisualizationConfig
from people_monitor.domain import Frame, FrameAnalysis, RoiAreaRelation, RoiEvaluation
from people_monitor.geometry import ConvexPolygonRoi

_FONT_FACE: Final = cv2.FONT_HERSHEY_SIMPLEX
_LINE_TYPE: Final = cv2.LINE_AA


class FrameRenderer:
    def __init__(
        self,
        roi: ConvexPolygonRoi,
        settings: VisualizationConfig,
    ) -> None:
        self._roi = roi
        self._settings = settings

    def draw(self, frame: Frame, analysis: FrameAnalysis) -> Frame:
        height, width = frame.shape[:2]
        roi_points = np.asarray(
            self._roi.pixel_points(width, height),
            dtype=np.int32,
        ).reshape((-1, 1, 2))
        cv2.polylines(
            frame,
            [roi_points],
            isClosed=True,
            color=self._settings.roi_color,
            thickness=self._settings.roi_thickness,
        )
        cv2.putText(
            frame,
            self._settings.roi_label,
            tuple(roi_points[0][0]),
            _FONT_FACE,
            self._settings.roi_font_scale,
            self._settings.roi_color,
            self._settings.text_thickness,
            _LINE_TYPE,
        )

        event_track_ids = {event.track_id for event in analysis.events}
        for evaluation in analysis.evaluations:
            self._draw_evaluation(frame, evaluation, event_track_ids)
        return frame

    def encode_jpeg(self, frame: Frame, extension: str, quality: int) -> bytes:
        ok, encoded = cv2.imencode(
            extension,
            frame,
            [cv2.IMWRITE_JPEG_QUALITY, quality],
        )
        if not ok:
            raise RuntimeError(f"Не удалось закодировать кадр в {extension}")
        return encoded.tobytes()

    def _draw_evaluation(
        self,
        frame: Frame,
        evaluation: RoiEvaluation,
        event_track_ids: set[int],
    ) -> None:
        detection = evaluation.detection
        bbox = detection.bbox
        track_id = detection.track_id
        is_event = track_id in event_track_ids
        color = self._color_for(evaluation.area_relation)
        thickness = (
            self._settings.event_bbox_thickness
            if is_event
            else self._settings.bbox_thickness
        )
        cv2.rectangle(
            frame,
            (round(bbox.x1), round(bbox.y1)),
            (round(bbox.x2), round(bbox.y2)),
            color,
            thickness,
        )
        identity = (
            str(track_id)
            if track_id is not None
            else self._settings.unknown_track_label
        )
        label = self._settings.bbox_label_template.format(
            track_id=identity,
            outside_ratio=evaluation.outside_ratio,
        )
        cv2.putText(
            frame,
            label,
            (
                round(bbox.x1),
                max(
                    self._settings.minimum_label_y,
                    round(bbox.y1) - self._settings.label_vertical_offset,
                ),
            ),
            _FONT_FACE,
            self._settings.bbox_font_scale,
            color,
            self._settings.text_thickness,
            _LINE_TYPE,
        )

    def _color_for(self, relation: RoiAreaRelation) -> BgrColor:
        if relation is RoiAreaRelation.OUTSIDE_LARGER:
            return self._settings.outside_color
        if relation is RoiAreaRelation.BALANCED:
            return self._settings.balanced_color
        return self._settings.inside_color
