"""Небольшие фабрики доменных объектов для тестов."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from people_monitor.domain import BoundingBox, ExitEvent


def make_event(track_id: int = 1) -> ExitEvent:
    return ExitEvent(
        event_id=uuid4(),
        schema_version=1,
        camera_id="test-camera",
        track_id=track_id,
        frame_index=10,
        video_time_seconds=0.4,
        occurred_at=datetime.now(timezone.utc),
        confidence=0.9,
        bbox=BoundingBox(0, 0, 10, 10),
        inside_area=40.0,
        outside_area=60.0,
        outside_ratio=0.6,
    )
