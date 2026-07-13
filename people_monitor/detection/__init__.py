"""Детекторы и трекеры объектов."""

from people_monitor.detection.base import PeopleTracker
from people_monitor.detection.ultralytics_tracker import UltralyticsPeopleTracker

__all__ = ["PeopleTracker", "UltralyticsPeopleTracker"]
