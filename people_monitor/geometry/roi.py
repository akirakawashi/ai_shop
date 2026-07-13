"""Быстрая проверка точки опоры человека внутри выпуклого ROI."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isclose, isfinite
from typing import Final

from people_monitor.domain import Point, RoiMembership, TrackedDetection

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
    first_a = _orientation(first_start, first_end, second_start)
    first_b = _orientation(first_start, first_end, second_end)
    second_a = _orientation(second_start, second_end, first_start)
    second_b = _orientation(second_start, second_end, first_end)
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
            if not are_adjacent and _segments_intersect(
                *first_edge,
                *edges[second_index],
            ):
                raise ValueError("Границы ROI не должны пересекаться")


def _validate_convex_polygon(points: Sequence[Point]) -> None:
    if len(points) < 3:
        raise ValueError("ROI должен содержать минимум три точки")
    _validate_simple_polygon(points)
    if isclose(_signed_area(points), 0.0, abs_tol=_GEOMETRY_EPSILON):
        raise ValueError("ROI имеет нулевую площадь")

    turn_directions: list[bool] = []
    for index in range(len(points)):
        turn = _cross(
            points[index],
            points[(index + 1) % len(points)],
            points[(index + 2) % len(points)],
        )
        if not isclose(turn, 0.0, abs_tol=_GEOMETRY_EPSILON):
            turn_directions.append(turn > 0)
    if not turn_directions or not all(
        direction == turn_directions[0] for direction in turn_directions
    ):
        raise ValueError("ROI должен быть выпуклым полигоном")


@dataclass(frozen=True, slots=True)
class ConvexPolygonRoi:
    """Выпуклый ROI в нормализованных координатах кадра."""

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

    def contains(
        self,
        point: Point,
        frame_width: int,
        frame_height: int,
    ) -> bool:
        """Вернуть True для точки внутри ROI или непосредственно на границе."""
        if not all(isfinite(coordinate) for coordinate in point):
            raise ValueError("Координаты проверяемой точки должны быть конечными")
        pixel_points = self.pixel_points(frame_width, frame_height)
        edges = zip(
            pixel_points,
            (*pixel_points[1:], pixel_points[0]),
            strict=True,
        )
        return all(
            _cross(edge_start, edge_end, point) >= -_GEOMETRY_EPSILON
            for edge_start, edge_end in edges
        )

    def evaluate(
        self,
        detection: TrackedDetection,
        frame_width: int,
        frame_height: int,
    ) -> RoiMembership:
        """Определить принадлежность человека по нижнему центру bbox."""
        anchor_point = detection.bbox.bottom_center
        return RoiMembership(
            detection=detection,
            anchor_point=anchor_point,
            is_inside=self.contains(anchor_point, frame_width, frame_height),
        )
