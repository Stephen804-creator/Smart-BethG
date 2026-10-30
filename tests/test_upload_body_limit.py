import asyncio
import unittest

from middleware.upload_limits import UploadBodyLimitMiddleware


class TestUploadBodyLimitMiddleware(unittest.TestCase):
    def run_asgi(self, middleware, scope, messages):
        sent = []
        called = []

        async def receive():
            if messages:
                return messages.pop(0)
            return {"type": "http.disconnect"}

        async def send(message):
            sent.append(message)

        async def app(inner_scope, inner_receive, inner_send):
            called.append(True)
            first = await inner_receive()
            await inner_send({
                "type": "http.response.start",
                "status": 200,
                "headers": [],
            })
            await inner_send({
                "type": "http.response.body",
                "body": first.get("body", b""),
            })

        asyncio.run(middleware(scope, receive, send))
        return sent, called

    def test_rejects_declared_oversize_before_calling_multipart_parser(self):
        middleware = UploadBodyLimitMiddleware(lambda *_: None, max_body_bytes=10)
        sent, called = self.run_asgi(
            middleware,
            {
                "type": "http", "method": "POST", "path": "/api/v1/files",
                "headers": [(b"content-length", b"11")],
            },
            [],
        )
        self.assertFalse(called)
        self.assertEqual(sent[0]["status"], 413)

    def test_rejects_chunked_body_that_exceeds_limit(self):
        middleware = UploadBodyLimitMiddleware(lambda *_: None, max_body_bytes=5)
        sent, called = self.run_asgi(
            middleware,
            {"type": "http", "method": "POST", "path": "/api/v1/files", "headers": []},
            [
                {"type": "http.request", "body": b"123", "more_body": True},
                {"type": "http.request", "body": b"456", "more_body": False},
            ],
        )
        self.assertFalse(called)
        self.assertEqual(sent[0]["status"], 413)

    def test_allows_bounded_body_and_replays_it_to_the_application(self):
        middleware = UploadBodyLimitMiddleware(lambda *_: None, max_body_bytes=10)
        sent, called = self.run_asgi(
            middleware,
            {"type": "http", "method": "POST", "path": "/api/v1/files", "headers": []},
            [
                {"type": "http.request", "body": b"123", "more_body": True},
                {"type": "http.request", "body": b"45", "more_body": False},
            ],
        )
        self.assertTrue(called)
        self.assertEqual(sent[0]["status"], 200)
        self.assertEqual(sent[1]["body"], b"12345")

    def test_ignores_non_upload_routes(self):
        middleware = UploadBodyLimitMiddleware(lambda *_: None, max_body_bytes=2)
        sent, called = self.run_asgi(
            middleware,
            {"type": "http", "method": "POST", "path": "/api/v1/chat", "headers": []},
            [{"type": "http.request", "body": b"large body", "more_body": False}],
        )
        self.assertTrue(called)
        self.assertEqual(sent[0]["status"], 200)


if __name__ == "__main__":
    unittest.main()
