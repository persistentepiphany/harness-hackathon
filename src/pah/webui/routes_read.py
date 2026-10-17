"""Read routes of the web UI under /ui: jobs, live logs, run records, tools, tasks, catalog.

Everything is read from disk (`runs/<id>/`), so runs started by the CLI, the MCP server, a batch,
an agent or `POST /ui/runs` appear and stream the same way. The upstream `JobStore` is consulted
only for jobs that failed before writing anything.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Header, Query, Request
from sse_starlette import EventSourceResponse, ServerSentEvent

from pah.config import Profile
from pah.webui import ui_error
from pah.webui.adapter import (
    LogLineConverter,
    checks_registry,
    load_state,
    loglines,
    task_spec,
    to_job,
    to_ui_record,
    tool_register,
    ui_task_id,
)
from pah.webui.settings import ApiSettings
from pah.webui.store import RunNotFoundError, RunStore, UnsafePathError, valid_run_id

if TYPE_CHECKING:
    from pah.interfaces.api import JobStore

log = logging.getLogger(__name__)

PING_S = 15
MAX_WAIT_S = 300.0


def _ping() -> ServerSentEvent:
    return ServerSentEvent(comment="ping")


def _after(last_event_id: str | None, after: int | None) -> int:
    if after is not None:
        return max(0, after)
    try:
        return max(0, int(last_event_id)) if last_event_id else 0
    except ValueError:
        return 0


def ui_tasks() -> list[dict[str, Any]]:
    """UI task ids (configs/catalog.yaml) joined with the task specs and implemented counts."""
    from pah.service import task_rows

    rows = {str(r["id"]): r for r in task_rows()}
    registry = checks_registry()
    try:
        from pah.webui.catalog import load_catalog

        catalog = load_catalog()
        entries = [(t.id, t.pah, t.name, t.long, list(t.default_tools)) for t in catalog.tasks]
        families = {t.id: t.family for t in catalog.tools}
    except Exception as exc:  # no catalog: one entry per task spec
        log.info("catalog not loadable, tasks from specs only: %s", exc)
        entries = [
            (ui_task_id(r["id"]), r["id"], r["title"], r["title"], []) for r in rows.values()
        ]
        families = {}
    out: list[dict[str, Any]] = []
    for uid, pah_id, name, long, default_tools in entries:
        row = rows.get(pah_id)
        spec = task_spec(pah_id)
        if row is None or spec is None:
            log.info("task %s: no specification %s", uid, pah_id)
            continue
        spec_families = [
            {"cofolding": "co-folding"}.get(str(f), str(f)) for f in row.get("families") or ()
        ]
        group = families.get(default_tools[0]) if default_tools else None
        out.append(
            {
                "id": uid,
                "pah": pah_id,
                "name": name,
                "long": long,
                "group": group or (spec_families[0] if spec_families else None),
                "families": spec_families,
                "defaultTools": default_tools,
                "claim": row.get("claim"),
                "status": row.get("status"),
                "controls": list(spec.controls),
                "requiredInputs": list(row.get("required_inputs") or ()),
                "checks": row.get("checks"),
                "implemented": row.get("implemented"),
                "layers": [
                    {
                        "i": int(layer),
                        "checks": len(ids),
                        "implemented": sum(c in registry for c in ids),
                    }
                    for layer, ids in sorted(spec.layers.items())
                ],
            }
        )
    return out


def ui_catalog() -> dict[str, Any]:
    from pah.webui.catalog import load_catalog

    try:
        catalog = load_catalog()
    except OSError:
        return {"proteins": [], "ligands": []}
    return {
        "proteins": [p.model_dump(by_alias=True) for p in catalog.proteins],
        "ligands": [x.model_dump(by_alias=True) for x in catalog.ligands],
        "defaults": catalog.defaults.model_dump(by_alias=True),
    }


def _aliases() -> dict[str, list[str]]:
    """Executor id -> UI tool ids that stand for it (configs/catalog.yaml `tools`)."""
    try:
        from pah.webui.catalog import load_catalog

        tools = load_catalog().tools
    except Exception:
        return {}
    out: dict[str, list[str]] = {}
    for t in tools:
        if t.executor and t.executor != t.id:
            out.setdefault(t.executor, []).append(t.id)
    return out


def build_router(profile: Profile, jobs: JobStore) -> APIRouter:
    """Read routes; paths are relative to the /ui prefix added by `pah.webui.ui_router`."""
    settings = ApiSettings.from_profile_model(profile)
    store = RunStore(settings.runs_dir)
    router = APIRouter()

    def run_dir_or_404(run_id: str) -> Any:
        try:
            return store.run_dir(run_id)
        except UnsafePathError as exc:
            raise ui_error(400, "invalid_run_id", str(exc)) from exc
        except RunNotFoundError as exc:
            raise ui_error(404, "run_not_found", f"no run {run_id!r}") from exc

    def memory_job(run_id: str) -> dict[str, Any] | None:
        job = jobs.get(run_id)
        if job is None:
            return None
        status = {"running": "queued"}.get(job.status, job.status)
        return {
            "id": run_id, "runId": run_id, "harnessRunId": run_id, "name": run_id,
            "task": None, "taskName": None, "tools": [], "seeds": 0, "status": status,
            "layerIdx": 0, "progress": 0.0, "elapsedMs": 0, "createdAt": None,
            "layers": [{"i": i, "result": None, "done": False} for i in range(6)],
            "verdict": None, "checksDone": 0, "checksTotal": 0, "reportStatus": "none",
            **({"error": job.error} if job.error else {}),
        }  # fmt: skip

    def job_view(run_id: str) -> dict[str, Any]:
        if not valid_run_id(run_id):
            raise ui_error(400, "invalid_run_id", f"invalid run id {run_id!r}")
        try:
            run_dir = store.run_dir(run_id)
        except (RunNotFoundError, UnsafePathError):
            pending = memory_job(run_id)
            if pending is not None:
                return pending
            raise ui_error(404, "run_not_found", f"no run {run_id!r}") from None
        view = to_job(run_dir)
        job = jobs.get(run_id)
        if job is not None and job.status == "failed" and view["status"] != "done":
            view["status"] = "failed"
            view["error"] = job.error
        return view

    @router.get("/jobs")
    def list_jobs() -> list[dict[str, Any]]:
        out = []
        for path in store.list_runs():
            try:
                out.append(job_view(path.name))
            except Exception as exc:  # one unreadable run never hides the others
                log.warning("job %s skipped: %s", path.name, exc)
        return out

    @router.get("/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, Any]:
        return job_view(job_id)

    @router.get("/jobs/{job_id}/log", response_model=None)
    async def job_log(
        job_id: str,
        request: Request,
        format: str | None = Query(None, description="json returns LogLine[] instead of SSE"),
        after: int | None = Query(None, description="Only lines with seq greater than this"),
        wait: float = Query(30.0, description="Seconds to wait for a run that has not started"),
        last_event_id: str | None = Header(None),
    ) -> Any:
        if not valid_run_id(job_id):
            raise ui_error(400, "invalid_run_id", f"invalid run id {job_id!r}")
        start = _after(last_event_id, after)
        if format == "json":
            run_dir = run_dir_or_404(job_id)
            return [line for line in loglines(store.events(job_id), run_dir) if line["seq"] > start]
        if format not in (None, "sse"):
            raise ui_error(400, "bad_format", "format must be json or sse")
        run_dir = store.path_for(job_id)

        async def stream() -> AsyncIterator[ServerSentEvent]:
            convert = LogLineConverter(run_dir)
            last, ended, seen = start, False, False
            async for event in store.tail(
                job_id,
                wait_for_file=min(max(wait, 0.0), MAX_WAIT_S),
                stop=request.is_disconnected,
            ):
                seen = True
                line = convert(event)
                ended = ended or event.get("kind") == "run_end"
                if line["seq"] <= start:
                    continue
                last = line["seq"]
                yield ServerSentEvent(data=json.dumps(line), event="line", id=str(line["seq"]))
            reason = "run_end" if ended else ("missing" if not seen else "stale")
            yield ServerSentEvent(
                data=json.dumps({"reason": reason, "lastSeq": last}), event="end", id=str(last)
            )

        return EventSourceResponse(stream(), ping=PING_S, ping_message_factory=_ping)

    @router.get("/runs/{run_id}/record")
    def run_record(run_id: str) -> dict[str, Any]:
        run_dir = run_dir_or_404(run_id)
        record = to_ui_record(run_dir, state=load_state(run_dir))
        job = jobs.get(run_id)
        if job is not None and job.status == "failed" and record["status"] != "done":
            record["status"] = "failed"
        return record

    @router.get("/tools")
    def tools() -> list[dict[str, Any]]:
        return tool_register(profile.name, _aliases())

    @router.get("/tasks")
    def tasks() -> list[dict[str, Any]]:
        return ui_tasks()

    @router.get("/catalog")
    def catalog() -> dict[str, Any]:
        return ui_catalog()

    return router
