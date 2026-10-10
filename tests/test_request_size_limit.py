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

    def test_accepts_body_at_limit(self):
        response = self.client.post("/", content=b"12345678")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["size"], 8)


if __name__ == "__main__":
    unittest.main()
