"""Добавление событий в простой потоковый JSONL-журнал."""

from __future__ import annotations

import json
from pathlib import Path
from threading import Lock

from people_monitor.domain import QueueFullEvent

_PATH_LOCKS: dict[Path, Lock] = {}
_PATH_LOCKS_GUARD = Lock()


def _shared_path_lock(path: Path) -> Lock:
    normalized_path = path.expanduser().resolve()
    with _PATH_LOCKS_GUARD:
        return _PATH_LOCKS.setdefault(normalized_path, Lock())


class JsonlEventStore:
    def __init__(self, path: Path) -> None:
        self._path = path.expanduser().resolve()
        self._write_lock = _shared_path_lock(self._path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: QueueFullEvent) -> None:
        with self._write_lock, self._path.open("a", encoding="utf-8") as file:
            json.dump(event.to_dict(), file, ensure_ascii=False)
            file.write("\n")
