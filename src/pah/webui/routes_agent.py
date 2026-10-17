"""`/ui/agent/...` routes: an agent under test reports its steps; the UI streams them."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import run_in_threadpool

from pah.config import Profile, resolve_path
from pah.webui.agent_log import (
    AgentLog,
    AgentLogError,
    AgentTaskFinishedError,
    AgentTaskNotFoundError,
)

PING_S = 15


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


def _mapped(exc: Exception) -> JSONResponse:
    if isinstance(exc, AgentTaskNotFoundError):
        return _error(404, "not_found", str(exc))
    if isinstance(exc, AgentTaskFinishedError):
        return _error(409, "task_finished", str(exc))
    return _error(422, "invalid", str(exc))


async def _body(request: Request) -> dict[str, Any] | JSONResponse:
    try:
        body = await request.json()
    except ValueError:
        return _error(422, "invalid", "body must be a JSON object")
    if not isinstance(body, dict):
        return _error(422, "invalid", "body must be a JSON object")
    return body


def _int(value: Any, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AgentLogError(f"{name} must be a number")
    return int(value)


def build_router(profile: Profile, jobs: Any = None) -> APIRouter:
    """Routes relative to /ui. `jobs` is accepted for a uniform signature and not used."""
    router = APIRouter()
    log = AgentLog(resolve_path(profile.runs_dir))
    errors = (AgentLogError, AgentTaskNotFoundError, AgentTaskFinishedError)

    @router.get("/agent/tasks")
    async def list_tasks() -> list[dict[str, Any]]:
        return await run_in_threadpool(log.list_tasks)

    @router.post("/agent/tasks", status_code=201, response_model=None)
    async def create_task(request: Request) -> dict[str, Any] | JSONResponse:
        body = await _body(request)
        if isinstance(body, JSONResponse):
            return body
        goal = body.get("goal")
        if not isinstance(goal, str) or not goal.strip():
            return _error(422, "invalid", "goal must be a non-empty string")
        try:
            return await run_in_threadpool(log.create, goal)
        except errors as exc:
            return _mapped(exc)

    @router.get("/agent/tasks/{task_id}", response_model=None)
    async def get_task(task_id: str) -> dict[str, Any] | JSONResponse:
        try:
            return await run_in_threadpool(log.get, task_id)
        except errors as exc:
            return _mapped(exc)

    @router.post("/agent/tasks/{task_id}/steps", status_code=201, response_model=None)
    async def add_step(task_id: str, request: Request) -> dict[str, Any] | JSONResponse:
        body = await _body(request)
        if isinstance(body, JSONResponse):
            return body
        kind, text = body.get("kind"), body.get("text")
        if not isinstance(kind, str) or not isinstance(text, str):
            return _error(422, "invalid", "kind and text must be strings")
        data = body.get("data")
        try:
            ms = _int(body.get("ms"), "ms")
            return await run_in_threadpool(log.append, task_id, kind, text, ms, data)
        except errors as exc:
            return _mapped(exc)

    @router.post("/agent/tasks/{task_id}/finish", response_model=None)
    async def finish_task(task_id: str, request: Request) -> dict[str, Any] | JSONResponse:
        body = await _body(request)
        if isinstance(body, JSONResponse):
            return body
        status = body.get("status")
        if not isinstance(status, str):
            return _error(422, "invalid", "status must be done or failed")
        try:
            return await run_in_threadpool(log.finish, task_id, status, body.get("outcome"))
        except errors as exc:
            return _mapped(exc)

    @router.get("/agent/tasks/{task_id}/steps", response_model=None)
    async def steps(
        task_id: str, request: Request, format: str = "sse", after: int = 0
    ) -> Response | list[dict[str, Any]]:
        last = request.headers.get("last-event-id")
        if last is not None:
            try:
                after = max(after, int(last))
            except ValueError:
                return _error(422, "invalid", "Last-Event-ID must be an integer")
        try:
            await run_in_threadpool(log.get, task_id)
        except errors as exc:
            return _mapped(exc)
        if format == "json":
            return await run_in_threadpool(log.steps, task_id, after)
        if format != "sse":
            return _error(422, "invalid", "format must be sse or json")

        async def frames() -> AsyncIterator[dict[str, str]]:
            async for step in log.tail(task_id, after):
                yield {"event": "step", "id": str(step["seq"]), "data": json.dumps(step)}
            task = await run_in_threadpool(log.get, task_id)
            yield {"event": "end", "data": json.dumps(task)}

        return EventSourceResponse(frames(), ping=PING_S)

    return router
