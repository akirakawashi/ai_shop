from __future__ import annotations

import asyncio
import unittest

from people_monitor.domain import QueueFullEvent
from people_monitor.notifications import AsyncNotificationWorker, Notifier
from tests.factories import make_event


class _RecordingNotifier(Notifier):
    def __init__(self) -> None:
        self.events: list[QueueFullEvent] = []
        self.closed = False
        self.close_calls = 0

    async def send(
        self,
        event: QueueFullEvent,
        snapshot: bytes | None = None,
    ) -> None:
        self.events.append(event)

    async def close(self) -> None:
        self.closed = True
        self.close_calls += 1


class _BlockingNotifier(_RecordingNotifier):
    def __init__(self) -> None:
        super().__init__()
        self.send_started = asyncio.Event()

    async def send(
        self,
        event: QueueFullEvent,
        snapshot: bytes | None = None,
    ) -> None:
        self.send_started.set()
        await asyncio.Event().wait()


class _BlockingCloseNotifier(_RecordingNotifier):
    async def close(self) -> None:
        await asyncio.Event().wait()


class AsyncNotificationWorkerTest(unittest.IsolatedAsyncioTestCase):
    async def test_close_drains_queue_and_closes_notifier(self) -> None:
        notifier = _RecordingNotifier()
        worker = AsyncNotificationWorker(
            notifier=notifier,
            queue_size=2,
            drain_timeout_seconds=1.0,
            notifier_close_timeout_seconds=1.0,
            drain_on_shutdown=True,
        )
        worker.start()

        self.assertTrue(worker.submit(make_event(1)))
        self.assertTrue(worker.submit(make_event(2)))
        await worker.close()

        self.assertEqual([event.people_count for event in notifier.events], [1, 2])
        self.assertTrue(notifier.closed)

    async def test_closed_worker_rejects_new_jobs_and_cannot_restart(self) -> None:
        worker = AsyncNotificationWorker(
            notifier=_RecordingNotifier(),
            queue_size=1,
            drain_timeout_seconds=1.0,
            notifier_close_timeout_seconds=1.0,
            drain_on_shutdown=True,
        )
        worker.start()
        await worker.close()

        self.assertFalse(worker.submit(make_event()))
        with self.assertRaises(RuntimeError):
            worker.start()

    async def test_drain_timeout_handles_full_queue_and_blocked_sender(self) -> None:
        notifier = _BlockingNotifier()
        worker = AsyncNotificationWorker(
            notifier=notifier,
            queue_size=1,
            drain_timeout_seconds=0.01,
            notifier_close_timeout_seconds=0.1,
            drain_on_shutdown=True,
        )
        worker.start()
        self.assertTrue(worker.submit(make_event(1)))
        await notifier.send_started.wait()
        self.assertTrue(worker.submit(make_event(2)))

        await asyncio.wait_for(worker.close(), timeout=0.5)

        self.assertTrue(notifier.closed)
        self.assertFalse(worker.submit(make_event(3)))

    async def test_concurrent_close_closes_notifier_once(self) -> None:
        notifier = _RecordingNotifier()
        worker = AsyncNotificationWorker(
            notifier=notifier,
            queue_size=1,
            drain_timeout_seconds=1.0,
            notifier_close_timeout_seconds=1.0,
            drain_on_shutdown=True,
        )
        worker.start()

        await asyncio.gather(worker.close(), worker.close())

        self.assertEqual(notifier.close_calls, 1)

    async def test_notifier_close_has_its_own_timeout(self) -> None:
        worker = AsyncNotificationWorker(
            notifier=_BlockingCloseNotifier(),
            queue_size=1,
            drain_timeout_seconds=0.01,
            notifier_close_timeout_seconds=0.01,
            drain_on_shutdown=True,
        )

        await asyncio.wait_for(worker.close(), timeout=0.5)


if __name__ == "__main__":
    unittest.main()
