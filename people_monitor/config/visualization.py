"""Конфигурация отрисовки ROI и bbox."""

from __future__ import annotations

from string import Formatter

from pydantic import Field, field_validator
from pydantic_settings import SettingsConfigDict

from people_monitor.config._base import (
    BgrColor,
    NonBlankString,
    NonNegativeInt,
    PositiveFloat,
    PositiveInt,
    _BaseConfig,
)


def _validate_template(
    value: str,
    allowed_fields: set[str],
    example_values: dict[str, object],
    field_name: str,
) -> str:
    parsed_fields = tuple(Formatter().parse(value))
    used_fields = {
        parsed_field
        for _, parsed_field, _, _ in parsed_fields
        if parsed_field is not None
    }
    if not used_fields <= allowed_fields:
        supported = ", ".join(sorted(allowed_fields))
        raise ValueError(f"{field_name} поддерживает только: {supported}")
    if any(
        "{" in format_spec or "}" in format_spec
        for _, _, format_spec, _ in parsed_fields
    ):
        raise ValueError(f"Вложенные поля формата в {field_name} запрещены")
    try:
        value.format(**example_values)
    except (AttributeError, IndexError, KeyError, ValueError) as error:
        raise ValueError(f"Некорректный {field_name}") from error
    return value


class VisualizationConfig(_BaseConfig):
    """Цвета, размеры и шаблоны подписей OpenCV."""

    model_config = SettingsConfigDict(env_prefix="VISUALIZATION_")

    roi_color: BgrColor = Field(
        default=(0, 215, 255),
        description="BGR-цвет границы ROI",
    )
    inside_color: BgrColor = Field(
        default=(0, 190, 0),
        description="BGR-цвет bbox, пересекающего ROI",
    )
    outside_color: BgrColor = Field(
        default=(128, 128, 128),
        description="BGR-цвет bbox, не пересекающего ROI",
    )
    roi_thickness: PositiveInt = Field(
        default=2,
        description="Толщина линии ROI",
    )
    bbox_thickness: PositiveInt = Field(
        default=2,
        description="Обычная толщина рамки bbox",
    )
    event_bbox_thickness: PositiveInt = Field(
        default=4,
        description="Толщина bbox в кадре события",
    )
    text_thickness: PositiveInt = Field(
        default=2,
        description="Толщина текста OpenCV",
    )
    roi_font_scale: PositiveFloat = Field(
        default=0.7,
        description="Масштаб подписи ROI",
    )
    bbox_font_scale: PositiveFloat = Field(
        default=0.55,
        description="Масштаб подписи bbox",
    )
    label_vertical_offset: NonNegativeInt = Field(
        default=8,
        description="Вертикальный отступ подписи от bbox",
    )
    minimum_label_y: NonNegativeInt = Field(
        default=20,
        description="Минимальная координата Y подписи",
    )
    roi_label_template: str = Field(
        default="QUEUE {people_count}/{capacity} | {queue_state}",
        min_length=1,
        description="Шаблон подписи заполненности ROI",
    )
    unknown_track_label: NonBlankString = Field(
        default="?",
        description="Подпись детекции без track_id",
    )
    inside_state_label: NonBlankString = Field(
        default="IN",
        description="Подпись bbox, пересекающего ROI",
    )
    outside_state_label: NonBlankString = Field(
        default="OUT",
        description="Подпись bbox, не пересекающего ROI",
    )
    bbox_label_template: str = Field(
        default="ID {track_id} | {roi_state}",
        min_length=1,
        description="Шаблон подписи bbox",
    )

    @field_validator("roi_label_template")
    @classmethod
    def validate_roi_label_template(cls, value: str) -> str:
        return _validate_template(
            value=value,
            allowed_fields={"people_count", "capacity", "queue_state"},
            example_values={
                "people_count": 1,
                "capacity": 1,
                "queue_state": "full",
            },
            field_name="roi_label_template",
        )

    @field_validator("bbox_label_template")
    @classmethod
    def validate_bbox_label_template(cls, value: str) -> str:
        return _validate_template(
            value=value,
            allowed_fields={"track_id", "roi_state"},
            example_values={"track_id": "1", "roi_state": "IN"},
            field_name="bbox_label_template",
        )
