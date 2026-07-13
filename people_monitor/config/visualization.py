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


class VisualizationConfig(_BaseConfig):
    """Цвета, размеры и шаблоны подписей OpenCV."""

    model_config = SettingsConfigDict(env_prefix="VISUALIZATION_")

    roi_color: BgrColor = Field(
        default=(0, 215, 255),
        description="BGR-цвет границы ROI",
    )
    inside_color: BgrColor = Field(
        default=(0, 190, 0),
        description="BGR-цвет bbox преимущественно внутри ROI",
    )
    outside_color: BgrColor = Field(
        default=(0, 0, 255),
        description="BGR-цвет bbox преимущественно снаружи ROI",
    )
    balanced_color: BgrColor = Field(
        default=(255, 180, 0),
        description="BGR-цвет bbox на равной границе площадей",
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
    roi_label: NonBlankString = Field(
        default="ROI",
        description="Текст подписи области интереса",
    )
    unknown_track_label: NonBlankString = Field(
        default="?",
        description="Подпись детекции без track_id",
    )
    bbox_label_template: str = Field(
        default="ID {track_id} | OUT {outside_ratio:.0%}",
        min_length=1,
        description="Шаблон подписи bbox",
    )

    @field_validator("bbox_label_template")
    @classmethod
    def validate_bbox_label_template(cls, value: str) -> str:
        allowed_fields = {"track_id", "outside_ratio"}
        parsed_fields = tuple(Formatter().parse(value))
        used_fields = {
            field_name
            for _, field_name, _, _ in parsed_fields
            if field_name is not None
        }
        if not used_fields <= allowed_fields:
            raise ValueError(
                "bbox_label_template поддерживает только track_id и outside_ratio"
            )
        if any(
            "{" in format_spec or "}" in format_spec
            for _, _, format_spec, _ in parsed_fields
        ):
            raise ValueError("Вложенные поля формата в bbox_label_template запрещены")
        try:
            value.format(track_id="1", outside_ratio=0.5)
        except (AttributeError, IndexError, KeyError, ValueError) as error:
            raise ValueError(
                "bbox_label_template поддерживает только track_id и outside_ratio"
            ) from error
        return value
