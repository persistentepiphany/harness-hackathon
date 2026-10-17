"""Write side of the `/ui` routes: start runs from UI settings, interpret a request, look up
entities, take uploads and list example manifests.

A run started here goes through the upstream pipeline: the settings become a manifest, and
`pah.service.run_manifest` runs on the shared `JobStore`, exactly as `POST /runs` does, so
checks, reports, PyMOL renders and the provenance graph are the same for every interface.

`runs/<id>/job.json` records what the UI needs before and around the run:
    {id, runId, status: queued|running|done|failed, name, task (UI id), pahTask, taskName,
     tools, executor, lookups, executors: "not run (checks only)" | "run (configs/dispatch.yaml)",
     execute, execution: UiExecution[], executionDenied, seeds, layers, halt, profile,
     serverProfile, settings, manifest, notes, createdAt, startedAt, finishedAt, verdict,
     reportError, error}
`events.jsonl` exists (empty) from submission. When the job starts, one log event with seq 0
states whether executors run and lists the manifest decisions. With `execute: true` the execute
stage (`pah.webui.execute`) follows with one event per phase change (`stage: execute`), writes
the outputs under `predictions/<executor>/` and adds them to the manifest's `predictions`; the
run's own events then continue the sequence. An executor that cannot run (not authorised, not
deployed, inputs missing) is recorded as `skipped` with the reason and the checks still run.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from collections.abc import Callable, Mapping, Sequence
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
    EXECUTORS_RUN,
    RunPlan,
    RunSettings,
    SettingsError,
    complete_manifest,
    parse_settings,
    plan_run,
)

if TYPE_CHECKING:
    from pah.interfaces.api import JobStore
    from pah.webui.execute import DispatchConfig, Dispatcher

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

    @property
    def data(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._data)

    def update(self, **changes: Any) -> None:
        with self._lock:
            self._data.update(changes)
            self._flush()

    def _flush(self) -> None:
        _atomic_text(self.path, json.dumps(self._data, indent=2) + "\n")
        persistence.persist(f"job.json {self._data.get('id')} {self._data.get('status')}")


DISPATCH_FILE = "dispatch.json"
_CALLS_LOCK = threading.Lock()


def write_calls(run_dir: Path, calls: Mapping[str, Mapping[str, Any]]) -> None:
    """`runs/<id>/dispatch.json`: every spawned executor call (Modal call id, app, seeds, status,
    the predictions entries once done), so a restarted server can follow the calls again."""
    with _CALLS_LOCK:
        body = {"version": 1, "updatedAt": _now(), "calls": {k: dict(v) for k, v in calls.items()}}
        _atomic_text(run_dir / DISPATCH_FILE, json.dumps(body, indent=2) + "\n")
    persistence.persist(f"dispatch.json {run_dir.name}")


def read_calls(run_dir: Path) -> dict[str, dict[str, Any]]:
    try:
        body = json.loads((run_dir / DISPATCH_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    calls = body.get("calls") if isinstance(body, dict) else None
    return {str(k): dict(v) for k, v in (calls or {}).items() if isinstance(v, dict)}


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


_EVENTS_LOCK = threading.Lock()


def append_event(run_dir: Path, run_id: str, message: str, **data: Any) -> Event:
    """Appends one log event after the last one in events.jsonl (seq 0 in an empty file)."""
    return write_event(run_dir, run_id, message, data)


def write_event(
    run_dir: Path, run_id: str, message: str, data: Mapping[str, Any], *, stage: str = "job"
) -> Event:
    """`append_event` with the data as a mapping (keys may include `message` or `stage`)."""
    path = run_dir / "events.jsonl"
    with _EVENTS_LOCK:
        last = _last_seq(path)
        event = Event(
            run_id=run_id,
            seq=0 if last is None else last + 1,
            kind=EventKind.LOG,
            stage=stage,
            message=message,
            data=dict(data),
        )
        with path.open("a", encoding="utf-8") as fh:
            fh.write(event.model_dump_json() + "\n")
    return event


class RunSubmitter:
    """Validates UI settings, prepares the run directory and starts the run on the JobStore."""

    def __init__(
        self,
        profile: Profile,
        jobs: JobStore,
        client_factory: ClientFactory | None = None,
        dispatchers: Mapping[str, Dispatcher] | None = None,
    ) -> None:
        self.profile = profile
        self.jobs = jobs
        self.client_factory = client_factory or _default_client
        self.dispatchers = dispatchers
        root = repo_root()
        self.examples_dir = root / "examples" if root and (root / "examples").is_dir() else None

    @staticmethod
    def dispatch_config() -> tuple[DispatchConfig | None, str | None]:
        from pah.webui.execute import load_dispatch

        try:
            return load_dispatch(), None
        except (OSError, ValueError, TypeError, KeyError) as exc:
            return None, f"configs/dispatch.yaml unusable: {type(exc).__name__}: {exc}"

    def _denied(self, plan: RunPlan, headers: Mapping[str, str]) -> str | None:
        """Why this run may not start executors, or None when it may (or does not ask to)."""
        from pah.webui.execute import ExecDeniedError, check_exec_token

        if not plan.execute:
            return None
        if plan.manifest is None:
            return "example manifests run as-is; executors are not dispatched for them"
        cfg, err = self.dispatch_config()
        if cfg is None:
            return err
        try:
            lower = {k.lower(): v for k, v in headers.items()}
            check_exec_token(cfg.guard, self.profile.name, lower.get(cfg.guard.header.lower()))
        except ExecDeniedError as exc:
            return str(exc)
        return None

    def submit(
        self, settings: RunSettings, headers: Mapping[str, str] | None = None
    ) -> dict[str, Any]:
        """Returns {jobId, runId} (plus {etaMs, eta} when executors run) once job.json and an
        empty events.jsonl exist; executors are spawned by the job, never by this request.

        Raises SettingsError for settings that cannot become a run.
        """
        from pah.core.manifest import Manifest
        from pah.interfaces.api import Job
        from pah.service import run_dir_for

        plan = plan_run(settings, server_profile=self.profile.name, examples_dir=self.examples_dir)
        denied = self._denied(plan, headers or {})
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
        eta = self.estimate(plan, denied)
        job_file = JobFile(run_dir / "job.json", self._job_record(run_id, plan, denied, eta))
        self.jobs.start(
            Job(id=run_id, kind="run"),
            lambda sinks: self._work(plan, run_id, run_dir, job_file, sinks, denied),
        )
        out: dict[str, Any] = {"jobId": run_id, "runId": run_id}
        if eta is not None:
            out["etaMs"], out["eta"] = eta.get("etaMs"), eta
        return out

    def estimate(self, plan: RunPlan, denied: str | None) -> dict[str, Any] | None:
        """Execute-stage estimate from configs/dispatch.yaml `eta` (None when nothing runs)."""
        from pah.webui.execute import estimate_run

        if not plan.execute or denied is not None or not plan.executors:
            return None
        cfg, _ = self.dispatch_config()
        if cfg is None:
            return None
        return estimate_run(cfg, plan.executors, list(range(max(1, plan.seeds))))

    def _job_record(
        self, run_id: str, plan: RunPlan, denied: str | None, eta: dict[str, Any] | None = None
    ) -> dict[str, Any]:
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
            "executors": EXECUTORS_RUN if plan.execute and denied is None else EXECUTORS_NOT_RUN,
            "execute": plan.execute,
            "etaMs": eta.get("etaMs") if eta else None,
            "eta": eta,
            "execution": [],
            "executionDenied": denied,
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

    def _execute(
        self,
        plan: RunPlan,
        manifest: dict[str, Any] | None,
        run_id: str,
        run_dir: Path,
        job: JobFile,
        denied: str | None,
    ) -> dict[str, Any] | None:
        """Runs the selected executors; returns the manifest with their predictions."""
        from pah.sources import CachedHttp, ContentCache, Sources
        from pah.webui.catalog import load_executors
        from pah.webui.execute import ExecuteStage

        def emit(message: str, data: Mapping[str, Any]) -> None:
            write_event(run_dir, run_id, message, data, stage="execute")

        names = {e.id: e.name for e in load_executors()}
        cfg, err = self.dispatch_config()
        if manifest is None or cfg is None or denied is not None:
            rows = []
            for eid in plan.executors:
                reason = denied or err or "execution unavailable"
                emit(f"execute {eid}: skipped ({reason})",
                     {"stage": "execute", "executor": eid, "phase": "skipped", "gpu": None,
                      "route": None, "routeNote": None, "seed": None, "elapsedMs": None,
                      "message": reason})  # fmt: skip
                rows.append({"executor": eid, "name": names.get(eid, eid), "phase": "skipped",
                             "seeds": [], "message": reason})  # fmt: skip
            job.update(execution=rows)
            return manifest
        stage = ExecuteStage(
            cfg,
            self._dispatchers(cfg),
            emit,
            on_change=lambda rows: job.update(execution=rows),
            on_call=lambda calls: write_calls(run_dir, calls),
            run_eta_ms=(job.data.get("eta") or {}).get("etaMs"),
        )
        cache = ContentCache(resolve_path(self.profile.cache_dir))
        with self.client_factory() as client:
            sources = Sources(CachedHttp(client, cache, offline=self.profile.offline))

            def structures(pdb_id: str) -> bytes:
                return bytes(sources.rcsb.mmcif(pdb_id).data)

            outcome = stage.run(
                manifest,
                plan.executors,
                run_id,
                run_dir,
                structures=structures,
                manifest_path=run_dir / "manifest.yaml",
                names=names,
            )
        job.update(execution=outcome.executions)
        self._write_manifest(run_dir, outcome.manifest)
        return outcome.manifest

    def _dispatchers(self, cfg: DispatchConfig) -> Mapping[str, Dispatcher]:
        from pah.webui.execute import LocalVinaDispatcher, ModalDispatcher, UnavailableDispatcher

        if self.dispatchers is not None:
            return self.dispatchers
        modal: Dispatcher = (
            UnavailableDispatcher(
                f"profile {self.profile.name} is offline; Modal dispatch needs the network"
            )
            if self.profile.offline
            else ModalDispatcher(cfg.modal, cfg.guard.poll_s)
        )
        return {"modal": modal, "local": LocalVinaDispatcher(self.profile)}

    def resume_pending(self) -> list[str]:
        """Takes up runs whose executor calls were spawned by a server process that has ended
        (job queued or running, calls `spawned` in dispatch.json): follows the calls to their
        end, then runs the checks. Returns the run ids taken up."""
        from pah.interfaces.api import Job

        runs_dir = resolve_path(self.profile.runs_dir)
        taken: list[str] = []
        if not runs_dir.is_dir():
            return taken
        for run_dir in sorted(p for p in runs_dir.iterdir() if (p / DISPATCH_FILE).is_file()):
            calls = read_calls(run_dir)
            if not any(c.get("status") == "spawned" for c in calls.values()):
                continue
            try:
                data = json.loads((run_dir / "job.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            run_id = run_dir.name
            if data.get("status") not in ("queued", "running") or self.jobs.get(run_id):
                continue
            job_file = JobFile(run_dir / "job.json", data)

            def work(
                sinks: Sequence[Sink],
                run_id: str = run_id,
                run_dir: Path = run_dir,
                job_file: JobFile = job_file,
                calls: dict[str, dict[str, Any]] = calls,
            ) -> dict[str, Any]:
                return self._resume_work(run_id, run_dir, job_file, calls, sinks)

            self.jobs.start(Job(id=run_id, kind="run"), work)
            taken.append(run_id)
        return taken

    def _resume_work(
        self,
        run_id: str,
        run_dir: Path,
        job: JobFile,
        calls: dict[str, dict[str, Any]],
        sinks: Sequence[Sink],
    ) -> dict[str, Any]:
        from pah.webui.execute import ExecuteStage

        data = job.data
        layers = tuple(int(x) for x in data.get("layers") or ())
        halt = bool(data.get("halt"))
        try:
            manifest = yaml.safe_load((run_dir / "manifest.yaml").read_text(encoding="utf-8"))
            cfg, err = self.dispatch_config()
            if cfg is None or not isinstance(manifest, dict):
                raise RuntimeError(err or "manifest.yaml unreadable")
            pending = sorted(k for k, c in calls.items() if c.get("status") == "spawned")
            append_event(
                run_dir,
                run_id,
                f"server restarted: following {len(pending)} spawned call(s) "
                f"({', '.join(pending)}) from dispatch.json",
                resumed=pending,
            )

            def emit(message: str, ev: Mapping[str, Any]) -> None:
                write_event(run_dir, run_id, message, ev, stage="execute")

            stage = ExecuteStage(
                cfg,
                self._dispatchers(cfg),
                emit,
                on_change=lambda rows: job.update(execution=rows),
                on_call=lambda c: write_calls(run_dir, c),
                run_eta_ms=data.get("etaMs"),
            )
            rows = [r for r in data.get("execution") or [] if isinstance(r, dict)]
            outcome = stage.resume(
                manifest, calls, run_id, run_dir, manifest_path=run_dir / "manifest.yaml",
                rows=rows,
            )  # fmt: skip
            job.update(execution=outcome.executions)
            self._write_manifest(run_dir, outcome.manifest)
            return self._check(outcome.manifest, layers, halt, run_id, run_dir, job, sinks)
        except Exception as exc:  # recorded in the run and on the job; the server keeps serving
            message = f"{type(exc).__name__}: {exc}"
            try:
                append_event(run_dir, run_id, f"job failed: {message}", status="error")
            finally:
                job.update(status="failed", finishedAt=_now(), error=message)
            raise
        finally:
            persistence.persist(f"run {run_id} ended")

    def _check(
        self,
        source: Any,
        layers: tuple[int, ...],
        halt: bool,
        run_id: str,
        run_dir: Path,
        job: JobFile,
        sinks: Sequence[Sink],
    ) -> dict[str, Any]:
        """Runs the checks on the (executed) manifest and records the verdict on the job."""
        from pah.service import RunOptions, run_manifest

        options = RunOptions(layers=layers, halt=halt, report=True)
        result = run_manifest(
            source,
            self.profile,
            options,
            list(sinks),
            run_id=run_id,
            run_dir=run_dir,
            base_dir=run_dir,
            seq_start=_last_seq(run_dir / "events.jsonl") or 0,
        )
        summary = result.summary()
        job.update(
            status="done",
            finishedAt=_now(),
            verdict=summary.get("verdict"),
            reportError=result.report_error,
        )
        return summary

    def _work(
        self,
        plan: RunPlan,
        run_id: str,
        run_dir: Path,
        job: JobFile,
        sinks: Sequence[Sink],
        denied: str | None = None,
    ) -> dict[str, Any]:
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
            executing = plan.execute and denied is None
            executors = EXECUTORS_RUN if executing else EXECUTORS_NOT_RUN
            append_event(
                run_dir,
                run_id,
                f"executors {executors}: {tools}; layers "
                f"{','.join(map(str, plan.layers))} run as checks"
                + (f". {'; '.join(notes)}" if notes else ""),
                executors=executors,
                tools=list(plan.tools),
                notes=notes,
                job_profile=plan.profile,
            )
            if plan.execute:
                executed = self._execute(
                    plan, source if isinstance(source, dict) else None, run_id, run_dir, job, denied
                )
                if executed is not None:
                    source = executed
            return self._check(source, plan.layers, plan.halt, run_id, run_dir, job, sinks)
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
    profile: Profile,
    jobs: JobStore,
    *,
    client_factory: ClientFactory | None = None,
    dispatchers: Mapping[str, Dispatcher] | None = None,
) -> APIRouter:
    """Routes relative to /ui. `dispatchers` replaces the executor dispatchers (tests)."""
    router = APIRouter()
    submitter = RunSubmitter(profile, jobs, client_factory, dispatchers)
    if os.environ.get("PAH_EXEC_RESUME", "1") != "0":
        # calls spawned before a restart are followed again in the background (dispatch.json)
        threading.Thread(
            target=submitter.resume_pending, name="pah-exec-resume", daemon=True
        ).start()
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
            return await run_in_threadpool(submitter.submit, settings, dict(request.headers))
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
        warnings = out.pop("warnings", [])
        return {"settings": out, "steps": steps, "warnings": warnings, "interpreter": "rule-based"}

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
