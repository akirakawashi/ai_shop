"""Общие ограничения и поведение конфигурации из окружения."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Final

from pydantic import Field, StringConstraints
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_ENV_FILE: Final = Path(".env")

PositiveInt = Annotated[int, Field(gt=0)]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveFloat = Annotated[float, Field(gt=0)]
NonNegativeFloat = Annotated[float, Field(ge=0)]
Probability = Annotated[float, Field(ge=0, le=1)]
JpegQuality = Annotated[int, Field(ge=1, le=100)]
ColorChannel = Annotated[int, Field(ge=0, le=255)]
NormalizedCoordinate = Annotated[float, Field(ge=0, le=1)]
SettingsNormalizedPoint = tuple[NormalizedCoordinate, NormalizedCoordinate]
BgrColor = tuple[ColorChannel, ColorChannel, ColorChannel]
NonBlankString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


class _BaseConfig(BaseSettings):
    """Единые правила чтения секционных настроек."""

    model_config = SettingsConfigDict(
        env_file=DEFAULT_ENV_FILE,
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        case_sensitive=False,
        extra="ignore",
        frozen=True,
        validate_default=True,
        allow_inf_nan=False,
    )
