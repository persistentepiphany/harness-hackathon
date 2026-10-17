"""Write side of the `/ui` routes: start runs from UI settings, interpret a request, look up
entities, take uploads and list example manifests.

A run started here goes through the upstream pipeline: the settings become a manifest, and
`pah.service.run_manifest` runs on the shared `JobStore`, exactly as `POST /runs` does, so
checks, reports, PyMOL renders and the provenance graph are the same for every interface.

`runs/<id>/job.json` records what the UI needs before and around the run:
    {id, runId, status: queued|running|done|failed, name, task (UI id), pahTask, taskName,
     tools, executor, lookups, executors: "not run (checks only)", seeds, layers, halt,
     profile, serverProfile, settings, manifest, notes, createdAt, startedAt, finishedAt,
     verdict, reportError, error}
`events.jsonl` exists (empty) from submission. When the job starts, one log event with seq 0
states that executors are not run and lists the manifest decisions; the run's own events follow
from seq 1.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import yaml
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from pah.config import Profile, repo_root, resolve_path
from pah.core.events import Sink, new_run_id
from pah.core.models import Event, EventKind
from pah.webui import persistence
from pah.webui.manifest_builder import (
    EXECUTORS_NOT_RUN,
    RunPlan,
    RunSettings,
    SettingsError,
    complete_manifest,
    parse_settings,
    plan_run,
)

if TYPE_CHECKING:
    from pah.interfaces.api import JobStore

ClientFactory = Callable[[], httpx.Client]
MAX_UPLOAD_FILES = 20


def _default_client() -> httpx.Client:
    return httpx.Client(follow_redirects=True, timeout=30.0)


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


def _atomic_text(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        Path(tmp).replace(path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class JobFile:
    """`runs/<id>/job.json`, merged and replaced atomically on every change."""

    def __init__(self, path: Path, initial: dict[str, Any]) -> None:
        self.path = path
        self._data = dict(initial)
        self._lock = threading.Lock()
        self._flush()

    def update(self, **changes: Any) -> None:
        with self._lock:
            self._data.update(changes)
            self._flush()

    def _flush(self) -> None:
        _atomic_text(self.path, json.dumps(self._data, indent=2) + "\n")
        persistence.persist(f"job.json {self._data.get('id')} {self._data.get('status')}")


def _last_seq(events: Path) -> int | None:
    try:
        lines = events.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        try:
            seq = json.loads(line).get("seq")
        except (ValueError, AttributeError):
            continue
        if isinstance(seq, int):
            return seq
    return None


def append_event(run_dir: Path, run_id: str, message: str, **data: Any) -> Event:
    """Appends one log event after the last one in events.jsonl (seq 0 in an empty file)."""
    path = run_dir / "events.jsonl"
    last = _last_seq(path)
    event = Event(
        run_id=run_id,
        seq=0 if last is None else last + 1,
        kind=EventKind.LOG,
        stage="job",
        message=message,
        data=data,
    )
    with path.open("a", encoding="utf-8") as fh:
        fh.write(event.model_dump_json() + "\n")
    return event


class RunSubmitter:
    """Validates UI settings, prepares the run directory and starts the run on the JobStore."""

    def __init__(
        self, profile: Profile, jobs: JobStore, client_factory: ClientFactory | None = None
    ) -> None:
        self.profile = profile
        self.jobs = jobs
        self.client_factory = client_factory or _default_client
        root = repo_root()
        self.examples_dir = root / "examples" if root and (root / "examples").is_dir() else None

    def submit(self, settings: RunSettings) -> dict[str, str]:
        """Returns {jobId, runId} once job.json and an empty events.jsonl exist.

        Raises SettingsError for settings that cannot become a run.
        """
        from pah.core.manifest import Manifest
        from pah.interfaces.api import Job
        from pah.service import run_dir_for

        plan = plan_run(settings, server_profile=self.profile.name, examples_dir=self.examples_dir)
        run_id = new_run_id(plan.pah_task)
        run_dir = run_dir_for(self.profile, run_id)
        if plan.manifest is not None:
            try:
                Manifest.model_validate({**plan.manifest, "base_dir": run_dir})
            except ValueError as exc:
                raise SettingsError(f"manifest from settings does not validate: {exc}") from exc
        run_dir.mkdir(parents=True, exist_ok=False)
        (run_dir / "events.jsonl").touch()
        if plan.manifest is not None:
            self._write_manifest(run_dir, plan.manifest)
        job_file = JobFile(run_dir / "job.json", self._job_record(run_id, plan))
        self.jobs.start(
            Job(id=run_id, kind="run"),
            lambda sinks: self._work(plan, run_id, run_dir, job_file, sinks),
        )
        return {"jobId": run_id, "runId": run_id}

    def _job_record(self, run_id: str, plan: RunPlan) -> dict[str, Any]:
        manifest = "manifest.yaml"
        if plan.manifest_path is not None:
            root = repo_root()
            p = plan.manifest_path
            manifest = str(p.relative_to(root)) if root and p.is_relative_to(root) else str(p)
        return {
            "id": run_id,
            "runId": run_id,
            "status": "queued",
            "name": plan.name,
            "task": plan.ui_task,
            "pahTask": plan.pah_task,
            "taskName": plan.task_title,
            "tools": list(plan.tools),
            "executor": plan.executor,
            "lookups": list(plan.lookups),
            "executors": EXECUTORS_NOT_RUN,
            "seeds": plan.seeds,
            "layers": list(plan.layers),
            "halt": plan.halt,
            "profile": plan.profile,
            "serverProfile": self.profile.name,
            "settings": plan.settings.model_dump(mode="json", by_alias=True),
            "manifest": manifest,
            "notes": list(plan.notes),
            "createdAt": _now(),
            "startedAt": None,
            "finishedAt": None,
            "verdict": None,
            "reportError": None,
            "error": None,
        }

    @staticmethod
    def _write_manifest(run_dir: Path, manifest: dict[str, Any]) -> None:
        header = "# Built by pah.webui from run settings; see job.json for the decisions.\n"
        _atomic_text(run_dir / "manifest.yaml", header + yaml.safe_dump(manifest, sort_keys=False))

    def _work(
        self, plan: RunPlan, run_id: str, run_dir: Path, job: JobFile, sinks: Sequence[Sink]
    ) -> dict[str, Any]:
        from pah.service import RunOptions, run_manifest
        from pah.sources import CachedHttp, ContentCache, Sources

        job.update(status="running", startedAt=_now())
        notes = list(plan.notes)
        try:
            source: Any
            if plan.manifest is not None:
                cache = ContentCache(resolve_path(self.profile.cache_dir))
                with self.client_factory() as client:
                    sources = Sources(CachedHttp(client, cache, offline=self.profile.offline))
                    built = complete_manifest(plan.manifest, sources, notes.append)
                self._write_manifest(run_dir, built)
                source = built
            else:
                source = plan.manifest_path
            job.update(notes=notes)
            tools = ", ".join(plan.tools) or "none selected"
            append_event(
                run_dir,
                run_id,
                f"executors {EXECUTORS_NOT_RUN}: {tools}; layers "
                f"{','.join(map(str, plan.layers))} run as CPU checks"
                + (f". {'; '.join(notes)}" if notes else ""),
                executors=EXECUTORS_NOT_RUN,
                tools=list(plan.tools),
                notes=notes,
                job_profile=plan.profile,
            )
            options = RunOptions(layers=plan.layers, halt=plan.halt, report=True)
            result = run_manifest(
                source,
                self.profile,
                options,
                list(sinks),
                run_id=run_id,
                run_dir=run_dir,
                base_dir=run_dir,
            )
            summary = result.summary()
            job.update(
                status="done",
                finishedAt=_now(),
                verdict=summary.get("verdict"),
                reportError=result.report_error,
            )
            return summary
        except Exception as exc:  # recorded in the run and on the job; the server keeps serving
            message = f"{type(exc).__name__}: {exc}"
            try:
                append_event(run_dir, run_id, f"job failed: {message}", status="error")
            finally:
                job.update(status="failed", finishedAt=_now(), error=message, notes=notes)
            raise
        finally:
            persistence.persist(f"run {run_id} ended")


def _examples(examples_dir: Path | None) -> list[dict[str, Any]]:
    from pah.core.manifest import load_manifest
    from pah.core.task import load_task
    from pah.webui.catalog import load_catalog

    if examples_dir is None:
        return []
    catalog = load_catalog()
    root = examples_dir.parent
    out: list[dict[str, Any]] = []
    for path in sorted(examples_dir.rglob("manifest.yaml")):
        rel = path.relative_to(root).as_posix()
        row: dict[str, Any] = {"id": path.parent.relative_to(examples_dir).as_posix(), "path": rel}
        try:
            text = path.read_text(encoding="utf-8")
            comments = [ln.lstrip("# ").rstrip() for ln in text.splitlines() if ln.startswith("#")]
            man = load_manifest(path)
            spec = load_task(man.task)
        except (OSError, ValueError) as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
            out.append(row)
            continue
        row.update(
            task=catalog.ui_task_id(spec.id),
            pahTask=spec.id,
            taskName=spec.title,
            claim=man.claim or spec.claim,
            description=" ".join(comments),
            proteins=[p.uniprot or p.id for p in man.proteins],
            ligands=[lig.ccd or lig.smiles or lig.id for lig in man.ligands],
            executor=man.model.executor if man.model else None,
        )
        out.append(row)
    return out


def build_router(
    profile: Profile, jobs: JobStore, *, client_factory: ClientFactory | None = None
) -> APIRouter:
    """Routes relative to /ui."""
    router = APIRouter()
    submitter = RunSubmitter(profile, jobs, client_factory)
    factory = client_factory or _default_client
    runs_dir = resolve_path(profile.runs_dir)

    async def body_of(request: Request) -> Any:
        try:
            return await request.json()
        except ValueError:
            return None

    @router.post("/runs", status_code=202, response_model=None)
    async def create_run(request: Request) -> dict[str, str] | JSONResponse:
        body = await body_of(request)
        if not isinstance(body, dict):
            return _error(422, "invalid", "body must be a RunSettings object")
        try:
            settings = parse_settings(body)
            return await run_in_threadpool(submitter.submit, settings)
        except SettingsError as exc:
            return _error(422, "invalid_settings", str(exc))

    @router.post("/interpret", response_model=None)
    async def interpret(request: Request) -> dict[str, Any] | JSONResponse:
        from pah.webui.interpret import interpret_request

        body = await body_of(request)
        text = body.get("text") if isinstance(body, dict) else None
        if not isinstance(text, str) or not text.strip():
            return _error(422, "invalid", "body must be {text: string}")
        out = await run_in_threadpool(interpret_request, text)
        steps = out.pop("steps")
        return {"settings": out, "steps": steps, "interpreter": "rule-based"}

    @router.get("/entities")
    async def entities(q: str = "") -> list[dict[str, Any]]:
        from pah.sources import CachedHttp, ContentCache, Sources
        from pah.webui.entities import resolve_entities

        def run() -> list[dict[str, Any]]:
            cache = ContentCache(resolve_path(profile.cache_dir))
            with factory() as client:
                sources = Sources(CachedHttp(client, cache, offline=profile.offline))
                return resolve_entities(q, sources)

        return await run_in_threadpool(run)

    @router.post("/uploads", response_model=None)
    async def uploads(request: Request) -> dict[str, Any] | JSONResponse:
        from starlette.datastructures import UploadFile

        from pah.webui.body_limit import BodyTooLargeError
        from pah.webui.uploads import MAX_BYTES, UploadError, store_upload

        try:
            form = await request.form(max_files=MAX_UPLOAD_FILES)
        except BodyTooLargeError:  # answered 413 by BodyLimitMiddleware
            raise
        except Exception as exc:  # malformed multipart or python-multipart missing
            return _error(422, "invalid", f"multipart form expected: {exc}")
        files = [v for _, v in form.multi_items() if isinstance(v, UploadFile)]
        if not files:
            await form.close()
            return _error(422, "invalid", "no files in the form")
        rows: list[dict[str, Any]] = []
        try:
            for f in files:
                name = f.filename or "upload"
                data = await f.read(MAX_BYTES + 1)
                try:
                    rows.append(
                        await run_in_threadpool(store_upload, runs_dir / "uploads", name, data)
                    )
                except UploadError as exc:
                    size = f.size if isinstance(f.size, int) else len(data)
                    rows.append(
                        {"name": name, "size": size, "sha256": None, "kind": None,
                         "status": "error", "detail": str(exc)}
                    )  # fmt: skip
        finally:
            await form.close()
            persistence.persist("uploads")
        return {"files": rows}

    @router.get("/examples")
    async def examples() -> list[dict[str, Any]]:
        return await run_in_threadpool(_examples, submitter.examples_dir)

    @router.post("/tools", response_model=None)
    async def add_tool() -> JSONResponse:
        return _error(
            501,
            "not_implemented",
            "tool registry writes are not implemented; executors are declared in "
            "configs/executors.yaml and their runtimes in configs/runtimes.yaml",
        )

    return router
