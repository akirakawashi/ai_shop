"""Контракт упорядоченного источника кадров."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from people_monitor.domain import Frame


@runtime_checkable
class FrameSource(Protocol):
    @property
    def generation(self) -> int:
        """Номер непрерывного участка потока; меняется после reconnect."""
        ...

    @property
    def fps(self) -> float:
        """Эффективная частота кадров."""
        ...

    def open(self) -> None:
        """Открыть источник и подготовить чтение."""
        ...

    def read(self) -> Frame | None:
        """Вернуть следующий кадр или None при завершении источника."""
        ...

    def video_time(self, frame_index: int) -> float:
        """Вернуть временную позицию текущего кадра в секундах."""
        ...

    def request_stop(self) -> None:
        """Потокобезопасно прервать ожидание retry/backoff."""
        ...

    def close(self) -> None:
        """Освободить источник."""
        ...
