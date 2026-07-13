"""Небольшие фабрики доменных объектов для тестов."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from people_monitor.domain import QueueFullEvent


def make_event(people_count: int = 1) -> QueueFullEvent:
    return QueueFullEvent(
        event_id=uuid4(),
        schema_version=2,
        camera_id="test-camera",
        frame_index=10,
        video_time_seconds=0.4,
        occurred_at=datetime.now(timezone.utc),
        people_count=people_count,
        capacity=1,
        track_ids=tuple(range(1, people_count + 1)),
    )
