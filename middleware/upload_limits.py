"""Bound multipart upload bodies before Starlette parses/spools UploadFile."""
import asyncio


class UploadBodyLimitMiddleware:
    """Pre-buffer a small bounded upload body and reject overflow before parsing.

    Only the file-upload POST route is handled. A small concurrency semaphore
    bounds aggregate memory use; the limit includes multipart framing overhead.
    """

    def __init__(self, app, max_body_bytes, max_concurrent=2, route_suffix="/files"):
        self.app = app
        self.max_body_bytes = int(max_body_bytes)
        self.semaphore = asyncio.Semaphore(max(1, int(max_concurrent)))
        self.route_suffix = route_suffix

    @staticmethod
    async def _reject(send, status, message):
        body = ('{"detail":"' + message + '"}').encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"cache-control", b"no-store"),
                (b"x-content-type-options", b"nosniff"),
            ],
        })
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "").rstrip("/")
        if scope.get("method") != "POST" or not path.endswith(self.route_suffix):
            await self.app(scope, receive, send)
            return

        headers = {
            key.lower(): value
            for key, value in scope.get("headers", [])
        }
        declared = headers.get(b"content-length")
        if declared is not None:
            try:
                declared_size = int(declared)
            except (TypeError, ValueError):
                await self._reject(send, 400, "Invalid Content-Length header.")
                return
            if declared_size < 0:
                await self._reject(send, 400, "Invalid Content-Length header.")
                return
            if declared_size > self.max_body_bytes:
                await self._reject(send, 413, "Upload request exceeds the configured size limit.")
                return

        async with self.semaphore:
            body = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                if message["type"] != "http.request":
                    continue
                chunk = message.get("body", b"")
                if len(body) + len(chunk) > self.max_body_bytes:
                    await self._reject(send, 413, "Upload request exceeds the configured size limit.")
                    return
                body.extend(chunk)
                if not message.get("more_body", False):
                    break

            replayed = False

            async def bounded_receive():
                nonlocal replayed
                if not replayed:
                    replayed = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return {"type": "http.disconnect"}

            await self.app(scope, bounded_receive, send)
