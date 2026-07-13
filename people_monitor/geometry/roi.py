"""Площадь пересечения bbox с выпуклым полигоном ROI."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isclose, isfinite
from typing import Final

from people_monitor.domain import (
    Point,
    RoiAreaRelation,
    RoiEvaluation,
    TrackedDetection,
)

_GEOMETRY_EPSILON: Final = 1e-9


def _cross(origin: Point, first: Point, second: Point) -> float:
    return (first[0] - origin[0]) * (second[1] - origin[1]) - (
        first[1] - origin[1]
    ) * (second[0] - origin[0])


def _signed_area(points: Sequence[Point]) -> float:
    shifted_points = (*points[1:], points[0])
    return 0.5 * sum(
        x1 * y2 - x2 * y1
        for (x1, y1), (x2, y2) in zip(points, shifted_points, strict=True)
    )


def _polygon_area(points: Sequence[Point]) -> float:
    return abs(_signed_area(points)) if len(points) >= 3 else 0.0


def _orientation(first: Point, second: Point, third: Point) -> int:
    value = _cross(first, second, third)
    if isclose(value, 0.0, abs_tol=_GEOMETRY_EPSILON):
        return 0
    return 1 if value > 0 else -1


def _point_on_segment(point: Point, start: Point, end: Point) -> bool:
    return (
        min(start[0], end[0]) - _GEOMETRY_EPSILON
        <= point[0]
        <= max(start[0], end[0]) + _GEOMETRY_EPSILON
        and min(start[1], end[1]) - _GEOMETRY_EPSILON
        <= point[1]
        <= max(start[1], end[1]) + _GEOMETRY_EPSILON
    )


def _segments_intersect(
    first_start: Point,
    first_end: Point,
    second_start: Point,
    second_end: Point,
) -> bool:
    orientations = (
        _orientation(first_start, first_end, second_start),
        _orientation(first_start, first_end, second_end),
        _orientation(second_start, second_end, first_start),
        _orientation(second_start, second_end, first_end),
    )
    first_a, first_b, second_a, second_b = orientations
    if first_a * first_b < 0 and second_a * second_b < 0:
        return True
    return (
        (first_a == 0 and _point_on_segment(second_start, first_start, first_end))
        or (first_b == 0 and _point_on_segment(second_end, first_start, first_end))
        or (second_a == 0 and _point_on_segment(first_start, second_start, second_end))
        or (second_b == 0 and _point_on_segment(first_end, second_start, second_end))
    )


def _validate_simple_polygon(points: Sequence[Point]) -> None:
    if len(set(points)) != len(points):
        raise ValueError("ROI не должен содержать повторяющиеся вершины")

    edges = tuple(zip(points, (*points[1:], points[0]), strict=True))
    edge_count = len(edges)
    for first_index, first_edge in enumerate(edges):
        for second_index in range(first_index + 1, edge_count):
            are_adjacent = (
                second_index == first_index + 1
                or (first_index == 0 and second_index == edge_count - 1)
            )
            if are_adjacent:
                continue
            if _segments_intersect(*first_edge, *edges[second_index]):
                raise ValueError("Границы ROI не должны пересекаться")


def _validate_convex_polygon(points: Sequence[Point]) -> None:
    if len(points) < 3:
        raise ValueError("ROI должен содержать минимум три точки")
    _validate_simple_polygon(points)
    if isclose(_signed_area(points), 0.0, abs_tol=_GEOMETRY_EPSILON):
        raise ValueError("ROI имеет нулевую площадь")

    turn_directions: list[bool] = []
    point_count = len(points)
    for index in range(point_count):
        turn = _cross(
            points[index],
            points[(index + 1) % point_count],
            points[(index + 2) % point_count],
        )
        if not isclose(turn, 0.0, abs_tol=_GEOMETRY_EPSILON):
            turn_directions.append(turn > 0)
    if not turn_directions or not all(
        direction == turn_directions[0] for direction in turn_directions
    ):
        raise ValueError("ROI должен быть выпуклым полигоном")


def _line_intersection(
    start: Point,
    end: Point,
    edge_start: Point,
    edge_end: Point,
) -> Point:
    segment = (end[0] - start[0], end[1] - start[1])
    edge = (edge_end[0] - edge_start[0], edge_end[1] - edge_start[1])
    denominator = segment[0] * edge[1] - segment[1] * edge[0]
    if isclose(denominator, 0.0, abs_tol=_GEOMETRY_EPSILON):
        return end
    offset = (edge_start[0] - start[0], edge_start[1] - start[1])
    factor = (offset[0] * edge[1] - offset[1] * edge[0]) / denominator
    return (start[0] + factor * segment[0], start[1] + factor * segment[1])


def _clip_by_convex_polygon(
    subject: Sequence[Point],
    clip: Sequence[Point],
) -> list[Point]:
    """Вернуть пересечение полигонов алгоритмом Sutherland–Hodgman."""
    output = list(subject)
    clip_edges = zip(clip, (*clip[1:], clip[0]), strict=True)
    for edge_start, edge_end in clip_edges:
        if not output:
            break
        input_points = output
        output = []
        start = input_points[-1]
        for end in input_points:
            end_inside = _cross(edge_start, edge_end, end) >= -_GEOMETRY_EPSILON
            start_inside = _cross(edge_start, edge_end, start) >= -_GEOMETRY_EPSILON
            if end_inside:
                if not start_inside:
                    output.append(_line_intersection(start, end, edge_start, edge_end))
                output.append(end)
            elif start_inside:
                output.append(_line_intersection(start, end, edge_start, edge_end))
            start = end
    return output


def _area_relation(inside_area: float, outside_area: float) -> RoiAreaRelation:
    if isclose(
        inside_area,
        outside_area,
        rel_tol=_GEOMETRY_EPSILON,
        abs_tol=_GEOMETRY_EPSILON,
    ):
        return RoiAreaRelation.BALANCED
    if outside_area > inside_area:
        return RoiAreaRelation.OUTSIDE_LARGER
    return RoiAreaRelation.INSIDE_LARGER


@dataclass(frozen=True, slots=True)
class ConvexPolygonRoi:
    """Выпуклый ROI с координатами относительно ширины и высоты кадра."""

    normalized_points: tuple[Point, ...]

    def __post_init__(self) -> None:
        if any(
            not isfinite(coordinate) or not 0.0 <= coordinate <= 1.0
            for point in self.normalized_points
            for coordinate in point
        ):
            raise ValueError("Координаты ROI должны находиться в диапазоне [0, 1]")
        _validate_convex_polygon(self.normalized_points)
        if _signed_area(self.normalized_points) < 0:
            object.__setattr__(
                self,
                "normalized_points",
                tuple(reversed(self.normalized_points)),
            )

    def pixel_points(self, frame_width: int, frame_height: int) -> tuple[Point, ...]:
        if frame_width <= 0 or frame_height <= 0:
            raise ValueError("Размеры кадра должны быть положительными")
        return tuple(
            (x * frame_width, y * frame_height) for x, y in self.normalized_points
        )

    def evaluate(
        self,
        detection: TrackedDetection,
        frame_width: int,
        frame_height: int,
    ) -> RoiEvaluation:
        bbox = detection.bbox
        bbox_polygon: tuple[Point, ...] = (
            (bbox.x1, bbox.y1),
            (bbox.x2, bbox.y1),
            (bbox.x2, bbox.y2),
            (bbox.x1, bbox.y2),
        )
        intersection = _clip_by_convex_polygon(
            bbox_polygon,
            self.pixel_points(frame_width, frame_height),
        )
        bbox_area = bbox.area
        inside_area = min(bbox_area, max(0.0, _polygon_area(intersection)))
        outside_area = max(0.0, bbox_area - inside_area)

        return RoiEvaluation(
            detection=detection,
            bbox_area=bbox_area,
            inside_area=inside_area,
            outside_area=outside_area,
            inside_ratio=inside_area / bbox_area,
            outside_ratio=outside_area / bbox_area,
            area_relation=_area_relation(inside_area, outside_area),
        )
