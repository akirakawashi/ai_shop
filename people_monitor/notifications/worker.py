"""Асинхронная очередь доставки, изолирующая видеоконвейер от сети."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from people_monitor.domain import QueueFullEvent
from people_monitor.notifications.base import Notifier

_STOP: Final = object()


class _WorkerState(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    CLOSING = "closing"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class _NotificationJob:
    event: QueueFullEvent
    snapshot: bytes | None


class AsyncNotificationWorker:
    """Одноразовый worker с явным жизненным циклом и bounded queue."""

    def __init__(
        self,
        notifier: Notifier,
        queue_size: int,
        drain_timeout_seconds: float,
        notifier_close_timeout_seconds: float,
        drain_on_shutdown: bool,
        logger: logging.Logger | None = None,
    ) -> None:
        if queue_size <= 0:
            raise ValueError("queue_size должен быть положительным")
        if drain_timeout_seconds <= 0:
            raise ValueError("drain_timeout_seconds должен быть положительным")
        if notifier_close_timeout_seconds <= 0:
            raise ValueError(
                "notifier_close_timeout_seconds должен быть положительным"
            )
        self._notifier = notifier
        self._queue: asyncio.Queue[_NotificationJob | object] = asyncio.Queue(
            maxsize=queue_size
        )
        self._drain_timeout_seconds = drain_timeout_seconds
        self._notifier_close_timeout_seconds = notifier_close_timeout_seconds
        self._drain_on_shutdown = drain_on_shutdown
        self._logger = logger or logging.getLogger(__name__)
        self._consumer_task: asyncio.Task[None] | None = None
        self._close_lock = asyncio.Lock()
        self._state = _WorkerState.CREATED

    def start(self) -> None:
        if self._state is not _WorkerState.CREATED:
            raise RuntimeError(f"Нельзя запустить worker в состоянии {self._state}")
        event_loop = asyncio.get_running_loop()
        consumer_task = event_loop.create_task(
            self._consume(),
            name="notification-worker",
        )
        self._consumer_task = consumer_task
        self._state = _WorkerState.RUNNING

    def submit(self, event: QueueFullEvent, snapshot: bytes | None = None) -> bool:
        if self._state is not _WorkerState.RUNNING:
            self._logger.error(
                "Worker не принимает события в состоянии %s; event_id=%s пропущен",
                self._state,
                event.event_id,
            )
            return False
        try:
            self._queue.put_nowait(_NotificationJob(event=event, snapshot=snapshot))
        except asyncio.QueueFull:
            self._logger.error(
                "Очередь уведомлений переполнена; event_id=%s пропущен",
                event.event_id,
            )
            return False
        return True

    async def close(self) -> None:
        async with self._close_lock:
            await self._close_once()

    async def _close_once(self) -> None:
        if self._state is _WorkerState.CLOSED:
            return
        if self._state is _WorkerState.CREATED:
            self._state = _WorkerState.CLOSED
            await self._close_notifier_safely()
            return

        drain_deadline = (
            asyncio.get_running_loop().time() + self._drain_timeout_seconds
        )
        self._state = _WorkerState.CLOSING
        try:
            if self._drain_on_shutdown:
                await asyncio.wait_for(
                    self._drain_and_stop(),
                    timeout=self._remaining_drain_time(drain_deadline),
                )
            else:
                await self._cancel_consumer(drain_deadline)
        except TimeoutError:
            self._logger.warning(
                "Завершение очереди уведомлений превысило %.1f секунд",
                self._drain_timeout_seconds,
            )
            await self._cancel_consumer(drain_deadline)
        finally:
            self._discard_pending_jobs()
            try:
                await self._close_notifier_safely()
            finally:
                self._state = _WorkerState.CLOSED

    async def _drain_and_stop(self) -> None:
        await self._queue.put(_STOP)
        await self._queue.join()
        if self._consumer_task is not None:
            await self._consumer_task

    async def _cancel_consumer(self, drain_deadline: float) -> None:
        if self._consumer_task is None or self._consumer_task.done():
            return
        self._consumer_task.cancel()
        remaining_time = self._remaining_drain_time(drain_deadline)
        if remaining_time == 0:
            # Дать cooperative coroutine один цикл на обработку CancelledError.
            await asyncio.sleep(0)
            if self._consumer_task.done():
                with suppress(asyncio.CancelledError):
                    self._consumer_task.result()
                return
        done, pending = await asyncio.wait(
            {self._consumer_task},
            timeout=remaining_time,
        )
        if pending:
            self._logger.warning("Consumer уведомлений не завершился после отмены")
            return
        with suppress(asyncio.CancelledError):
            next(iter(done)).result()

    def _discard_pending_jobs(self) -> None:
        while not self._queue.empty():
            self._queue.get_nowait()
            self._queue.task_done()

    async def _close_notifier_safely(self) -> None:
        try:
            await asyncio.wait_for(
                self._notifier.close(),
                timeout=self._notifier_close_timeout_seconds,
            )
        except TimeoutError:
            self._logger.warning(
                "Закрытие канала уведомлений превысило %.1f секунд",
                self._notifier_close_timeout_seconds,
            )
        except Exception:
            # Cleanup канала не должен скрывать исходную ошибку pipeline.
            self._logger.exception("Не удалось корректно закрыть канал уведомлений")

    @staticmethod
    def _remaining_drain_time(drain_deadline: float) -> float:
        return max(0.0, drain_deadline - asyncio.get_running_loop().time())

    async def _consume(self) -> None:
        while True:
            job = await self._queue.get()
            try:
                if job is _STOP:
                    return
                if not isinstance(job, _NotificationJob):
                    raise TypeError("Неизвестный тип задания уведомления")
                await self._notifier.send(job.event, job.snapshot)
            except Exception:
                # Ошибка одного канала не должна останавливать обработку следующих событий.
                self._logger.exception("Не удалось доставить уведомление")
            finally:
                self._queue.task_done()
