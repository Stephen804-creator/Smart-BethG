"""Bound request bodies before multipart parsing or route handlers buffer them."""
import json


class RequestBodyLimitMiddleware:
    def __init__(self, app, max_body_bytes):
        self.app = app
        self.max_body_bytes = int(max_body_bytes)
        if self.max_body_bytes < 1:
            raise ValueError("max_body_bytes must be positive")

    @staticmethod
    async def _reject(scope, receive, send):
        body = json.dumps(
            {"detail": "Request body exceeds the configured size limit."}
        ).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"cache-control", b"no-store"),
                (b"x-content-type-options", b"nosniff"),
            ],
        })
        await send({"type": "http.response.body", "body": body, "more_body": False})

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        declared = headers.get(b"content-length")
        if declared:
            try:
                if int(declared) > self.max_body_bytes:
                    await self._reject(scope, receive, send)
                    return
            except ValueError:
                # Let the ASGI server/framework reject malformed lengths.
                pass

        total = 0
        too_large = False
        response_started = False

        async def limited_receive():
            nonlocal total, too_large
            message = await receive()
            if message.get("type") == "http.request":
                total += len(message.get("body", b""))
                if total > self.max_body_bytes:
                    too_large = True
                    return {"type": "http.request", "body": b"", "more_body": False}
            return message

        async def limited_send(message):
            nonlocal response_started
            if too_large:
                if not response_started and message.get("type") == "http.response.start":
                    response_started = True
                    await self._reject(scope, receive, send)
                return
            await send(message)

        try:
            await self.app(scope, limited_receive, limited_send)
        except Exception:
            if too_large and not response_started:
                await self._reject(scope, receive, send)
                return
            raise
