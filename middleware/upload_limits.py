"""Bound multipart upload bodies before Starlette parses/spools UploadFile."""
import asyncio
import tempfile


class UploadBodyLimitMiddleware:
    """Pre-buffer a small bounded upload body and reject overflow before parsing.

    Only the file-upload POST route is handled. A small concurrency semaphore
    bounds aggregate memory use; the limit includes multipart framing overhead.
    """

    def __init__(self, app, max_body_bytes, max_concurrent=2, route_suffix="/files"):
        self.app = app
        self.max_body_bytes = int(max_body_bytes)
        self.semaphore = asyncio.Semaphore(max(1, int(max_concurrent)))
        self.route_suffix = str(route_suffix or "/files").rstrip("/")
        if self.route_suffix.startswith("/api/v1/"):
            self.upload_paths = {self.route_suffix, self.route_suffix.replace("/api/v1/", "/api/", 1)}
        elif self.route_suffix.startswith("/"):
            self.upload_paths = {"/api" + self.route_suffix, "/api/v1" + self.route_suffix}
        else:
            raise ValueError("Upload route suffix must be an absolute path.")

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
        if scope.get("method") != "POST" or path not in self.upload_paths:
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
            body = tempfile.SpooledTemporaryFile(max_size=1024 * 1024, mode="w+b")
            total = 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    body.close()
                    return
                if message["type"] != "http.request":
                    continue
                chunk = message.get("body", b"")
                if total + len(chunk) > self.max_body_bytes:
                    body.close()
                    await self._reject(send, 413, "Upload request exceeds the configured size limit.")
                    return
                body.write(chunk)
                total += len(chunk)
                if not message.get("more_body", False):
                    break

            body.seek(0)
            body_finished = False

            async def bounded_receive():
                nonlocal body_finished
                if body_finished:
                    return {"type": "http.disconnect"}
                chunk = body.read(64 * 1024)
                more_body = body.tell() < total
                if not more_body:
                    body_finished = True
                return {"type": "http.request", "body": chunk, "more_body": more_body}

            try:
                await self.app(scope, bounded_receive, send)
            finally:
                body.close()
