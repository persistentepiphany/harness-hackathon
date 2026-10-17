"""Web UI layer: adapts run directories to the UI record and adds the /ui routes to the API.

`install_ui(app, profile, jobs)` is called by `pah.interfaces.api.create_app`. It mounts every
router module that exists (`routes_read`, `routes_write`, `routes_agent`, each exposing
`build_router(profile, jobs)`) under /ui and installs an error handler that answers /ui requests
with `{"error": {"code", "message"}}`. Native routes keep FastAPI's default error bodies.
"""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import APIRouter, FastAPI, HTTPException, Request
    from fastapi.responses import Response

    from pah.config import Profile
    from pah.interfaces.api import JobStore

log = logging.getLogger(__name__)

PREFIX = "/ui"
ROUTER_MODULES = ("routes_read", "routes_write", "routes_agent")
CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    500: "internal_error",
    503: "unavailable",
}


def ui_error(status: int, code: str, message: str) -> HTTPException:
    """An HTTPException that /ui routes raise; rendered as {"error": {"code", "message"}}."""
    from fastapi import HTTPException

    return HTTPException(status, detail={"code": code, "message": message})


def ui_router(profile: Profile, jobs: JobStore) -> APIRouter:
    """Every available UI router under /ui. A missing or broken module only skips its routes."""
    from fastapi import APIRouter

    router = APIRouter(prefix=PREFIX)
    for name in ROUTER_MODULES:
        qualified = f"{__name__}.{name}"
        try:
            module = importlib.import_module(qualified)
            router.include_router(module.build_router(profile, jobs))
        except ModuleNotFoundError as exc:
            if exc.name == qualified:
                log.info("ui routes %s not present", name)
            else:
                log.warning("ui routes %s skipped: %s", name, exc)
        except Exception as exc:  # fail soft: one broken router never hides the others
            log.warning("ui routes %s skipped: %s: %s", name, type(exc).__name__, exc)
    return router


def _is_ui(request: Request) -> bool:
    path = str(request.scope.get("path", ""))
    root = str(request.scope.get("root_path", ""))
    if root and path.startswith(root):
        path = path[len(root) :]
    return path == PREFIX or path.startswith(PREFIX + "/")


def _body(status: int, detail: Any) -> dict[str, Any]:
    if isinstance(detail, dict) and "code" in detail:
        return {"error": {"code": str(detail["code"]), "message": str(detail.get("message", ""))}}
    return {"error": {"code": CODES.get(status, f"http_{status}"), "message": str(detail)}}


def install_error_handlers(app: FastAPI) -> None:
    from fastapi.exception_handlers import (
        http_exception_handler,
        request_validation_exception_handler,
    )
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse, PlainTextResponse
    from starlette.exceptions import HTTPException as StarletteHTTPException

    async def on_http(request: Request, exc: Exception) -> Response:
        assert isinstance(exc, StarletteHTTPException)
        if not _is_ui(request):
            return await http_exception_handler(request, exc)
        return JSONResponse(
            _body(exc.status_code, exc.detail),
            status_code=exc.status_code,
            headers=getattr(exc, "headers", None),
        )

    async def on_validation(request: Request, exc: Exception) -> Response:
        assert isinstance(exc, RequestValidationError)
        if not _is_ui(request):
            return await request_validation_exception_handler(request, exc)
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(x) for x in first.get("loc", ()))
        message = f"{where}: {first.get('msg', 'invalid request')}" if where else str(exc)
        return JSONResponse({"error": {"code": "validation_error", "message": message}}, 422)

    async def on_error(request: Request, exc: Exception) -> Response:
        if not _is_ui(request):
            return PlainTextResponse("Internal Server Error", status_code=500)
        log.exception("ui route failed: %s", request.url.path, exc_info=exc)
        message = f"{type(exc).__name__}: {exc}"
        return JSONResponse({"error": {"code": "internal_error", "message": message}}, 500)

    app.add_exception_handler(StarletteHTTPException, on_http)
    app.add_exception_handler(RequestValidationError, on_validation)
    app.add_exception_handler(Exception, on_error)


def install_ui(app: FastAPI, profile: Profile, jobs: JobStore) -> None:
    """Mounts the /ui routes and their error handler on the harness API app."""
    from pah.webui.settings import ApiSettings

    ApiSettings.from_profile_model(profile).ensure_dirs()
    app.include_router(ui_router(profile, jobs))
    install_error_handlers(app)
