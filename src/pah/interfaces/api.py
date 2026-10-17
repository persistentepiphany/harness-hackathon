"""HTTP API for a frontend or remote agents. FastAPI with a server-sent event stream per job.

    pah serve --port 8765      # binds 127.0.0.1 by default

Runs and batches execute on worker threads. Every event is kept in memory for the job and
written to events.jsonl, so `GET /runs/{id}/events` replays from the start and then follows.
"""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import AsyncIterator, Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from pah import __version__
from pah.api.routes import ui_router
from pah.config import Profile, resolve_path
from pah.core.events import CallbackSink, Sink, new_run_id
from pah.core.models import Event
from pah.service import (
    InputError,
    RunOptions,
    check_rows,
    load_run,
    manifest_from,
    run_dir_for,
    run_manifest,
    task_rows,
)


class RunRequest(BaseModel):
    manifest: dict[str, Any] | None = Field(
        None, description="Inline manifest (see /schemas/manifest)"
    )
    manifest_path: str | None = Field(None, description="Path to a manifest on the server")
    base_dir: str | None = Field(
        None, description="Server directory for files named in an inline manifest"
    )
    layers: list[int] = Field(default_factory=lambda: [0, 1])
    offline: bool | None = None
    report: bool = True


class BatchRequest(BaseModel):
    batch_path: str | None = None
    manifest_paths: list[str] | None = None
    name: str = "batch"
    layers: list[int] = Field(default_factory=lambda: [0, 1])
    halt: bool = True


@dataclass
class Job:
    id: str
    kind: Literal["run", "batch"]
    status: Literal["running", "done", "failed"] = "running"
    events: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] | None = None
    error: str | None = None

    def add(self, event: Event) -> None:
        self.events.append(json.loads(event.model_dump_json()))

    def view(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "events": len(self.events),
            "summary": self.summary,
            "error": self.error,
            "links": {
                "events": f"/runs/{self.id}/events",
                "report_md": f"/runs/{self.id}/report?format=md",
                "report_json": f"/runs/{self.id}/report?format=json",
                "report_html": f"/runs/{self.id}/report?format=html",
                "record": f"/runs/{self.id}/record",
                "log": f"/jobs/{self.id}/log",
            },
        }


class JobStore:
    def __init__(self, workers: int = 2) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="pah-job")

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def start(self, job: Job, work: Callable[[Sequence[Sink]], dict[str, Any]]) -> None:
        with self._lock:
            self._jobs[job.id] = job

        def run() -> None:
            try:
                job.summary = work([CallbackSink(job.add)])
                job.status = "done"
            except Exception as exc:  # recorded on the job; the server keeps serving
                job.error = f"{type(exc).__name__}: {exc}"
                job.status = "failed"

        self._pool.submit(run)


def create_app(
    profile: Profile, allow_origins: Sequence[str] = (), *, log_idle_s: float = 600.0
) -> FastAPI:
    app = FastAPI(
        title="Prediction assurance harness",
        version=__version__,
        description="Run assurance checks on co-folding and docking inputs and read reports.",
    )
    if allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(allow_origins),
            allow_methods=["*"],
            allow_headers=["*"],
        )
    jobs = JobStore()
    app.include_router(ui_router(profile, log_idle_s=log_idle_s))

    def _run_dir(job_id: str) -> Path:
        try:
            return run_dir_for(profile, job_id)
        except InputError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "ok": True,
            "version": __version__,
            "profile": profile.name,
            "runs_dir": str(resolve_path(profile.runs_dir)),
            "mode": "live",
        }

    @app.get("/tasks")
    def tasks() -> list[dict[str, Any]]:
        return task_rows()

    @app.get("/checks")
    def checks() -> list[dict[str, Any]]:
        return check_rows()

    @app.get("/schemas/{name}")
    def schemas(name: str) -> dict[str, Any]:
        from pah.schemas import MODELS, schema

        if name not in MODELS:
            raise HTTPException(404, f"unknown schema; one of {sorted(MODELS)}")
        return schema(name)

    @app.post("/runs", status_code=202)
    def create_run(req: RunRequest) -> dict[str, Any]:
        from pah.core.task import load_task

        source: Any = req.manifest if req.manifest is not None else req.manifest_path
        if source is None:
            raise HTTPException(422, "give manifest or manifest_path")
        base = Path(req.base_dir) if req.base_dir else None
        try:
            manifest = manifest_from(source, base)
            task = load_task(manifest.task)
        except (InputError, OSError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc
        run_id = new_run_id(task.id)
        options = RunOptions(layers=tuple(req.layers), offline=req.offline, report=req.report)
        job = Job(id=run_id, kind="run")
        jobs.start(
            job,
            lambda sinks: run_manifest(manifest, profile, options, sinks, run_id=run_id).summary(),
        )
        return job.view()

    @app.post("/batches", status_code=202)
    def create_batch(req: BatchRequest) -> dict[str, Any]:
        from pah.batch import BatchSpec, load_batch_spec, run_batch

        try:
            if req.batch_path:
                spec = load_batch_spec(Path(req.batch_path))
            elif req.manifest_paths:
                spec = BatchSpec(
                    name=req.name,
                    targets=[Path(p) for p in req.manifest_paths],
                    layers=tuple(req.layers),
                    halt=req.halt,
                )
            else:
                raise HTTPException(422, "give batch_path or manifest_paths")
        except InputError as exc:
            raise HTTPException(422, str(exc)) from exc
        batch_id = new_run_id(f"batch-{spec.name}")
        job = Job(id=batch_id, kind="batch")
        jobs.start(job, lambda sinks: run_batch(spec, profile, sinks, batch_id=batch_id).summary())
        return job.view()

    @app.get("/runs/{job_id}")
    def get_run(job_id: str) -> dict[str, Any]:
        job = jobs.get(job_id)
        if job:
            return job.view()
        d = _run_dir(job_id)
        if (d / "record.json").is_file() or (d / "batch_report.json").is_file():
            return {"id": job_id, "status": "done", "summary": None, "error": None}
        raise HTTPException(404, f"no run {job_id!r}")

    @app.get("/runs/{job_id}/events")
    async def events(job_id: str) -> EventSourceResponse:
        job = jobs.get(job_id)
        if job is None:
            path = _run_dir(job_id) / "events.jsonl"
            if not path.is_file():
                raise HTTPException(404, f"no events for {job_id!r}")
            replay = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
            return EventSourceResponse(_replay(replay))
        return EventSourceResponse(_follow(job))

    @app.get("/runs/{job_id}/report", response_model=None)
    def report(
        job_id: str, format: Literal["md", "json", "html"] = "md"
    ) -> PlainTextResponse | JSONResponse | HTMLResponse:
        d = _run_dir(job_id)
        for name in (f"report.{format}", f"batch_report.{format}"):
            if (d / name).is_file():
                text = (d / name).read_text()
                if format == "html":
                    return HTMLResponse(text)
                if format == "json":
                    return JSONResponse(json.loads(text))
                return PlainTextResponse(text, media_type="text/markdown")
        raise HTTPException(404, "report not written (yet)")

    @app.get("/runs/{job_id}/findings")
    def findings(
        job_id: str, layer: int | None = None, gate: str | None = Query(None)
    ) -> list[dict[str, Any]]:
        try:
            record = load_run(profile, job_id)
        except InputError as exc:
            raise HTTPException(404, str(exc)) from exc
        return [
            f.model_dump(mode="json")
            for f in record.findings
            if (layer is None or int(f.layer) == layer) and (gate is None or f.gate.value == gate)
        ]

    @app.get("/runs/{job_id}/files/{rel:path}")
    def files(job_id: str, rel: str) -> FileResponse:
        root = _run_dir(job_id).resolve()
        target = (root / rel).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise HTTPException(404, "file not found in run directory")
        return FileResponse(target)

    return app


async def _replay(rows: list[dict[str, Any]]) -> AsyncIterator[dict[str, str]]:
    for row in rows:
        yield {
            "event": row.get("kind", "message"),
            "id": str(row.get("seq", "")),
            "data": json.dumps(row),
        }


async def _follow(job: Job, poll_s: float = 0.2) -> AsyncIterator[dict[str, str]]:
    sent = 0
    while True:
        while sent < len(job.events):
            row = job.events[sent]
            sent += 1
            yield {"event": row["kind"], "id": str(sent), "data": json.dumps(row)}
        if job.status != "running" and sent >= len(job.events):
            yield {"event": "job_end", "data": json.dumps(job.view())}
            return
        await asyncio.sleep(poll_s)
