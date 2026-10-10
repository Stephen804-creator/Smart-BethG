import asyncio
import json
import unittest

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from security.request_size_limit import RequestBodyLimitMiddleware


class TestRequestBodyLimitMiddleware(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.add_middleware(RequestBodyLimitMiddleware, max_body_bytes=8)

        @app.post("/")
        async def echo_body(request: Request):
            body = await request.body()
            return {"size": len(body)}

        self.client = TestClient(app)

    def test_rejects_declared_oversized_request_before_route(self):
        response = self.client.post("/", content=b"123456789")
        self.assertEqual(response.status_code, 413)
        self.assertEqual(
            response.json()["detail"],
            "Request body exceeds the configured size limit.",
        )

    def test_rejects_streamed_oversized_body_without_content_length(self):
        messages = [
            {"type": "http.request", "body": b"1234", "more_body": True},
            {"type": "http.request", "body": b"56789", "more_body": False},
        ]
        sent = []

        async def receive():
            return messages.pop(0)

        async def send(message):
            sent.append(message)

        async def app(_scope, receive_inner, send_inner):
            while True:
                message = await receive_inner()
                if not message.get("more_body"):
                    break
            await send_inner({"type": "http.response.start", "status": 200, "headers": []})
            await send_inner({"type": "http.response.body", "body": b"ok", "more_body": False})

        middleware = RequestBodyLimitMiddleware(app, max_body_bytes=8)
        asyncio.run(middleware({"type": "http", "headers": []}, receive, send))
        self.assertEqual(sent[0]["status"], 413)
        payload = json.loads(sent[1]["body"])
        self.assertIn("exceeds", payload["detail"])

    def test_accepts_body_at_limit(self):
        response = self.client.post("/", content=b"12345678")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["size"], 8)


if __name__ == "__main__":
    unittest.main()
