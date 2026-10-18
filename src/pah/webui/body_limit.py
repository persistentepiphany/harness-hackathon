"""Request body limits for the /ui write routes.

Starlette spools multipart file parts to disk and `request.json()` buffers a JSON body in memory
before a route sees either, so a size check inside the route comes too late. This ASGI
middleware answers 413 `too_large` when Content-Length is over the limit, and counts the bytes of
bodies sent without a length (chunked, or behind a proxy that drops the header) as they arrive.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH"})
# JSON bodies of /ui routes (run settings, interpreter text, agent steps) are small
JSON_LIMIT = 4 * 1024 * 1024
# multipart framing around the file parts
MULTIPART_OVERHEAD = 1024 * 1024


class BodyTooLargeError(Exception):
    """Raised from `receive` once a body passes its limit."""


def upload_limit() -> int:
    from pah.webui.routes_write import MAX_UPLOAD_FILES
    from pah.webui.uploads import MAX_BYTES

    return MAX_UPLOAD_FILES * MAX_BYTES + MULTIPART_OVERHEAD


def _path(scope: Scope) -> str:
    path = str(scope.get("path", ""))
    root = str(scope.get("root_path", ""))
    return path[len(root) :] if root and path.startswith(root) else path


def limit_for(path: str) -> int | None:
    """Body limit in bytes for a write to `path`; None for routes outside /ui."""
    if path == "/ui/uploads":
        return upload_limit()
    if path.startswith("/ui/"):
        return JSON_LIMIT
    return None


def _content_length(scope: Scope) -> int | None:
    for key, value in scope.get("headers") or ():
        if key.lower() == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp, limit: Callable[[str], int | None] = limit_for) -> None:
        self.app = app
        self.limit = limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http" or str(scope.get("method", "")).upper() not in WRITE_METHODS:
            await self.app(scope, receive, send)
            return
        limit = self.limit(_path(scope))
        if limit is None:
            await self.app(scope, receive, send)
            return
        length = _content_length(scope)
        if length is not None and length > limit:
            await _too_large(send, limit, length)
            return
        seen = 0
        started = False

        async def counted() -> Message:
            nonlocal seen
            message = await receive()
            if message.get("type") == "http.request":
                seen += len(message.get("body", b""))
                if seen > limit:
                    raise BodyTooLargeError
            return message

        async def tracked(message: Message) -> None:
            nonlocal started
            if message.get("type") == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counted, tracked)
        except BodyTooLargeError:
            if not started:
                await _too_large(send, limit, None)


async def _too_large(send: Send, limit: int, length: int | None) -> None:
    size = f"{length:,} bytes" if length is not None else "the request body"
    body = json.dumps(
        {"error": {"code": "too_large", "message": f"{size} is over the {limit:,} byte limit"}}
    ).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
