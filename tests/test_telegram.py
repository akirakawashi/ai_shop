from __future__ import annotations

import unittest

import httpx

from people_monitor.notifications import NotificationError, TelegramNotifier
from tests.factories import make_event


class TelegramNotifierTest(unittest.IsolatedAsyncioTestCase):
    async def test_sends_text_via_async_client(self) -> None:
        requests: list[httpx.Request] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json={"ok": True})

        client = httpx.AsyncClient(
            base_url="https://telegram.test",
            transport=httpx.MockTransport(handler),
        )
        notifier = TelegramNotifier(
            bot_token="secret-token",
            chat_id="42",
            api_base_url="https://telegram.test",
            timeout_seconds=1.0,
            snapshot_filename="event.jpg",
            max_retries=0,
            retry_backoff_seconds=0.0,
            client=client,
        )
        try:
            with self.assertLogs("httpx", level="INFO") as captured_logs:
                await notifier.send(make_event())
        finally:
            await notifier.close()
            await client.aclose()

        self.assertEqual(len(requests), 1)
        self.assertTrue(requests[0].url.path.endswith("/sendMessage"))
        self.assertNotIn("secret-token", "\n".join(captured_logs.output))

    async def test_error_does_not_expose_bot_token(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(502, text="bad gateway")

        client = httpx.AsyncClient(
            base_url="https://telegram.test",
            transport=httpx.MockTransport(handler),
        )
        notifier = TelegramNotifier(
            bot_token="top-secret-token",
            chat_id="42",
            api_base_url="https://telegram.test",
            timeout_seconds=1.0,
            snapshot_filename="event.jpg",
            max_retries=0,
            retry_backoff_seconds=0.0,
            client=client,
        )
        try:
            with self.assertRaises(NotificationError) as error:
                await notifier.send(make_event())
        finally:
            await notifier.close()
            await client.aclose()

        self.assertNotIn("top-secret-token", str(error.exception))

    async def test_relative_method_path_preserves_proxy_base_path(self) -> None:
        requests: list[httpx.Request] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json={"ok": True})

        client = httpx.AsyncClient(
            base_url="https://telegram.test/proxy/",
            transport=httpx.MockTransport(handler),
        )
        notifier = TelegramNotifier(
            bot_token="secret-token",
            chat_id="42",
            api_base_url="https://telegram.test/proxy/",
            timeout_seconds=1.0,
            snapshot_filename="event.jpg",
            max_retries=0,
            retry_backoff_seconds=0.0,
            client=client,
        )
        try:
            await notifier.send(make_event())
        finally:
            await notifier.close()
            await client.aclose()

        self.assertEqual(requests[0].url.path, "/proxy/botsecret-token/sendMessage")


if __name__ == "__main__":
    unittest.main()
