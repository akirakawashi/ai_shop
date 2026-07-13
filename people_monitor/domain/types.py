"""Общие точные типы, не содержащие поведения."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

Frame = NDArray[np.uint8]
Point = tuple[float, float]
NormalizedPoint = tuple[float, float]
