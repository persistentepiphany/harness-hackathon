"""UI endpoints from docs/UI.md: jobs, job log (SSE or JSON) and the UI run record.

Errors are `{"error": {"code", "message"}}`. Every run directory under the profile's `runs_dir`
that has an `events.jsonl` is a job, so a run started from any interface appears here and its log
streams while the engine writes it.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from pah.api.adapter import log_line, log_lines, ui_job, ui_record
from pah.config import Profile, resolve_path
from pah.service import InputError, run_dir_for


def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


class RunLookupError(Exception):
    def __init__(self, response: JSONResponse) -> None:
        self.response = response


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value)


def ui_router(
    profile: Profile, *, log_poll_s: float = 0.25, log_idle_s: float = 600.0
) -> APIRouter:
    router = APIRouter()

    def job_dir(job_id: str) -> Path:
        try:
            d = run_dir_for(profile, job_id)
        except InputError as exc:
            raise RunLookupError(error(400, "invalid_id", str(exc))) from exc
        if not (d / "events.jsonl").is_file() and not (d / "record.json").is_file():
            raise RunLookupError(error(404, "not_found", f"no run {job_id!r}"))
        return d

    @router.get("/jobs", response_model=None)
    def jobs() -> list[dict[str, Any]] | JSONResponse:
        root = resolve_path(profile.runs_dir)
        if not root.is_dir():
            return []
        rows = []
        for d in root.iterdir():
            if (d / "events.jsonl").is_file():
                try:
                    rows.append(ui_job(d))
                except (OSError, ValueError) as exc:  # one broken run never hides the others
                    rows.append({"id": d.name, "status": "failed", "error": str(exc)})
        rows.sort(key=lambda j: str(j.get("createdAt") or ""), reverse=True)
        return rows

    @router.get("/jobs/{job_id}", response_model=None)
    def job(job_id: str) -> dict[str, Any] | JSONResponse:
        try:
            return ui_job(job_dir(job_id))
        except RunLookupError as exc:
            return exc.response

    @router.get("/jobs/{job_id}/log", response_model=None)
    async def job_log(
        job_id: str, request: Request, format: str | None = None
    ) -> list[dict[str, Any]] | JSONResponse | EventSourceResponse:
        try:
            d = job_dir(job_id)
        except RunLookupError as exc:
            return exc.response
        if format == "json":
            return log_lines(d)
        if format not in (None, "sse"):
            return error(400, "bad_format", "format must be json or sse")
        after = request.headers.get("last-event-id")
        last = int(after) if after and after.isdigit() else 0
        return EventSourceResponse(_tail(d / "events.jsonl", last, log_poll_s, log_idle_s), ping=15)

    @router.get("/runs/{job_id}/record", response_model=None)
    def record(job_id: str) -> dict[str, Any] | JSONResponse:
        try:
            return ui_record(job_dir(job_id))
        except RunLookupError as exc:
            return exc.response

    return router


async def _tail(
    path: Path, after: int, poll_s: float, idle_s: float
) -> AsyncIterator[dict[str, str]]:
    """Replays events.jsonl as LogLine frames, then follows it until `run_end` or `idle_s`."""
    offset = 0
    start: datetime | None = None
    last = after
    idle = 0.0
    while True:
        rows, offset = _read_from(path, offset)
        for row in rows:
            if start is None:
                start = _ts(str(row["ts"]))
            seq = int(row.get("seq", 0))
            if seq > last:
                last = seq
                yield {"event": "line", "id": str(seq), "data": json.dumps(log_line(row, start))}
            if row.get("kind") == "run_end":
                yield {"event": "end", "id": str(last), "data": json.dumps({"seq": last})}
                return
        idle = 0.0 if rows else idle + poll_s
        if idle >= idle_s:
            yield {"event": "end", "id": str(last), "data": json.dumps({"seq": last})}
            return
        await asyncio.sleep(poll_s)


def _read_from(path: Path, offset: int) -> tuple[list[dict[str, Any]], int]:
    """Complete lines after `offset`; a line still being written is left for the next read."""
    with path.open("rb") as fh:
        fh.seek(offset)
        data = fh.read()
    end = data.rfind(b"\n") + 1
    rows = []
    for line in data[:end].splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows, offset + end
