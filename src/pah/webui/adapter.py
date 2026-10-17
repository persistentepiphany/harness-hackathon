"""Turns a run directory into the shapes the web UI renders (docs/UI.md, "Shapes").

Sources, in order of preference: `record.json` (written when the checks end), `report.json`
(written after it, with renders, figures and the provenance graph), `events.jsonl` (written as
the run goes), `provenance.json`, `findings/` and the files under the run directory. Nothing here
computes a scientific value: every number comes from a finding, an event timestamp or a file.
`stats` and the docking card are mapped in `pah.webui.stats`.

Gate on failure (`UiCheck.gate`), in this order:

1. `Stop` when the task lists the check under `escalate` (its warn becomes a stop);
2. the registered check's `gate_kind` (`pah.core.check.GateKind`: Stop, Warn or Reported);
3. `Stop` for a check id with no registered implementation.
"""

from __future__ import annotations

import logging
import re
import time
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from pah import __version__
from pah.config import config_dir, load_yaml, repo_root
from pah.core.task import TaskSpec, load_task
from pah.webui import stats as ui_stats
from pah.webui.store import EVENTS, read_events, read_json

log = logging.getLogger(__name__)

LAYERS: tuple[dict[str, Any], ...] = (
    {"i": 0, "key": "provenance", "name": "Provenance",
     "question": "Where did every input come from?"},
    {"i": 1, "key": "integrity", "name": "Input integrity",
     "question": "Did the run receive exactly what was declared?"},
    {"i": 2, "key": "adequacy", "name": "Input adequacy",
     "question": "Does the input carry enough information?"},
    {"i": 3, "key": "applicability", "name": "Applicability",
     "question": "Is the tool inside its validated regime?"},
    {"i": 4, "key": "validity", "name": "Output validity",
     "question": "Is the result physically and chemically sensible?"},
    {"i": 5, "key": "support", "name": "Output support",
     "question": "Is a valid result corroborated?"},
)  # fmt: skip

TASK_UI_IDS = {
    "monomer_structure": "monomer",
    "known_complex_assembly": "known_complex",
    "binding_site_identification": "binding_site",
}
OUTCOMES = {
    "pass": "supported",
    "pass_with_warnings": "narrowed",
    "stop": "refused",
    "incomplete": "incomplete",
}
OUTCOME_RESULT = {"refused": "stop", "narrowed": "warn", "supported": "pass"}
RESULTS = ("pass", "warn", "stop", "skip")
_RANK = {"skip": 0, "pass": 1, "reported": 2, "warn": 3, "stop": 4}
# Event status values of non-check stages (report) mapped to a LogLine result.
_STATUS_RESULT = {"ok": "pass", "pass": "pass", "warn": "warn", "stop": "stop", "skip": "skip",
                  "error": "stop", "failed": "stop"}  # fmt: skip
# Provenance source ids that differ from the ids in configs/sources.yaml.
SOURCE_ALIASES = {"rcsb": "rcsb_data", "sifts": "sifts_api", "afdb": "alphafold_db"}
STRUCTURE_FORMATS = {
    ".cif": "mmcif",
    ".mmcif": "mmcif",
    ".pdb": "pdb",
    ".ent": "pdb",
    ".sdf": "sdf",
}
STRUCTURE_KINDS = ("source_structure", "prediction_structure", "input_structure", "input_ligand")
WORK_DIR = "artifacts/work/"  # scratch files the checks write (PLIP, PROPKA inputs)
DERIVED_DIR = "derived/"  # per-pose files the checks compute (receptor-only PDBs), not members
STALE_AFTER_S = 600.0
MAX_FIGURES = 8
MAX_OUTPUTS = 500

_STAGE = re.compile(r"^L([0-5])$")
_N_CHECKS = re.compile(r":\s*(\d+)\s+checks?\b")
_MANIFEST = re.compile(r"\bmanifest=(\S+)")
_PROFILE = re.compile(r"\bprofile=(\S+)")
_RENDER_ID = re.compile(r"^render_(?P<stem>.+)_(?P<view>[A-Za-z0-9]+)$")


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list | tuple) else []


# ---------------------------------------------------------------- configuration lookups


def checks_registry() -> Mapping[str, Any]:
    """Registered checks. Importing `pah.checks` registers them; a broken module is logged."""
    try:
        import pah.checks  # noqa: F401
    except Exception as exc:  # fail soft: a check module mid-edit must not break the API
        log.warning("check library import failed: %s", exc)
    from pah.core.check import CHECKS

    return CHECKS


@lru_cache(maxsize=64)
def _task_cached(base: str, task_id: str) -> TaskSpec | None:
    try:
        return load_task(task_id, Path(base))
    except Exception as exc:
        log.info("task %s not loadable: %s", task_id, exc)
        return None


def task_spec(task_id: str | None) -> TaskSpec | None:
    return _task_cached(str(config_dir()), task_id) if task_id else None


def ui_task_id(task_id: str) -> str:
    return TASK_UI_IDS.get(task_id, task_id)


# ---------------------------------------------------------------- tool register


FAMILIES = {"cofolding": "co-folding", "co-folding": "co-folding", "docking": "docking"}
NOT_INSTALLED = "not installed on this host"


class ToolOutput(BaseModel):
    """One parsed field an executor reports (`outputs:` in configs/executors.yaml)."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    key: str
    label: str
    unit: str | None = None
    kind: Literal["confidence", "interface", "affinity", "score", "rmsd", "plddt", "pae", "other"]
    scope: Literal["global", "interface", "ligand", "pose", "residue"]
    range: tuple[float, float] | None = None
    higherIsBetter: bool | None = None  # noqa: N815 - wire name
    rankingOnly: bool | None = None  # noqa: N815 - wire name
    note: str | None = None


class DockingParam(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    label: str
    unit: str | None = None
    default: str | None = None


@lru_cache(maxsize=8)
def _rows_cached(base: str, name: str, key: str) -> tuple[dict[str, Any], ...]:
    try:
        rows = load_yaml(name, Path(base)).get(key) or []
    except (OSError, ValueError, yaml.YAMLError) as exc:
        log.info("%s not readable: %s", name, exc)
        return ()
    return tuple(r for r in rows if isinstance(r, dict) and "id" in r)


def executor_rows() -> list[dict[str, Any]]:
    """Rows of configs/executors.yaml in file order (copies; the cache is not mutated)."""
    return [dict(r) for r in _rows_cached(str(config_dir()), "executors.yaml", "executors")]


def sources_meta() -> dict[str, dict[str, Any]]:
    return {str(r["id"]): r for r in _rows_cached(str(config_dir()), "sources.yaml", "sources")}


def _valid(model: type[BaseModel], items: Any, where: str) -> list[dict[str, Any]]:
    """Entries that validate against `model`; the others are logged and left out."""
    out: list[dict[str, Any]] = []
    for item in items if isinstance(items, list) else ():
        try:
            out.append(model.model_validate(item).model_dump(exclude_none=True))
        except ValidationError as exc:
            log.warning("%s: entry skipped: %s", where, exc.errors()[0].get("msg"))
    return out


def tool_outputs(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    """`outputs` of an executor row; an entry without outputs gets an empty list."""
    return _valid(ToolOutput, row.get("outputs"), f"executors.yaml {row.get('id')} outputs")


def docking_params(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    return _valid(DockingParam, row.get("dockingParams"), f"executors.yaml {row.get('id')}")


@lru_cache(maxsize=4)
def _runtimes_cached(base: str) -> Any:
    from pah.runtimes.registry import load_runtimes

    try:
        return load_runtimes(Path(base))
    except Exception as exc:
        log.info("runtimes.yaml not loadable: %s", exc)
        return None


def runtime_info(executor_id: str) -> dict[str, Any] | None:
    """`runtime` block of a Tool, from configs/runtimes.yaml; None when it has no entry there."""
    reg = _runtimes_cached(str(config_dir()))
    rt = next((e for e in reg.executors if e.id == executor_id), None) if reg else None
    if rt is None:
        return None
    out: dict[str, Any] = {"profiles": sorted(reg.profiles), "accel": rt.accel is not None}
    if rt.gpu:
        out["gpu"] = "required"
    if rt.accel is not None:
        out["accelConfigs"] = list(rt.accel.configs)
    if rt.native is not None:
        out["nativeVersion"] = rt.native.version
    if rt.verified:
        out["verified"] = list(rt.verified)
    return out


def availability(executor_id: str, profile_name: str | None) -> tuple[bool, str]:
    """Whether the stock executor is installed for this profile's launcher, and where or why not.

    Only the host launcher is probed (binary or venv on disk, no subprocess). Docker and
    Apptainer images are not inspected from the API, so those report not available.
    """
    from pah.runtimes.launch import HostLauncher

    reg = _runtimes_cached(str(config_dir()))
    rt = next((e for e in reg.executors if e.id == executor_id), None) if reg else None
    if rt is None:
        return False, f"{NOT_INSTALLED}: no entry in configs/runtimes.yaml"
    rprof = reg.profiles.get(profile_name or "")
    if rprof is None:
        return False, f"{NOT_INSTALLED}: no runtime profile {profile_name!r}"
    if rprof.launcher != "host":
        return False, f"not checked from the API for launcher {rprof.launcher}"
    try:
        found = HostLauncher(reg, rprof).native_available(rt)
    except Exception as exc:
        return False, f"{NOT_INSTALLED}: {type(exc).__name__}: {exc}"
    return (True, found.where) if found.ok else (False, f"{NOT_INSTALLED}: {found.where}")


def record_tool(executor_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Tool shape without availability. An executor missing from the register keeps its id as
    the name and has no outputs (docs/UI.md, Tools drive the display)."""
    row = next((r for r in rows if str(r.get("id")) == executor_id), None)
    if row is None:
        return {"id": executor_id, "name": executor_id, "version": None, "outputs": []}
    rt = runtime_info(executor_id)
    out: dict[str, Any] = {
        "id": executor_id,
        "name": str(row.get("name") or executor_id),
        "version": rt.get("nativeVersion") if rt else None,
        "role": str(row.get("role") or "Executor"),
        "outputs": tool_outputs(row),
    }
    family = FAMILIES.get(str(row.get("family") or ""))
    if family:
        out["family"] = family
    params = docking_params(row)
    if params:
        out["dockingParams"] = params
    if row.get("outputs_note"):
        out["outputsNote"] = str(row["outputs_note"])
    return out


def tool_register(
    profile_name: str | None, aliases: Mapping[str, list[str]] | None = None
) -> list[dict[str, Any]]:
    """Every executor in configs/executors.yaml as a Tool (docs/UI.md), in file order."""
    rows = executor_rows()
    out: list[dict[str, Any]] = []
    for row in rows:
        eid = str(row["id"])
        tool = record_tool(eid, rows)
        ok, note = availability(eid, profile_name)
        tool["available"] = ok
        tool["note"] = note
        for key in ("licence", "repo"):
            if row.get(key):
                tool[key] = str(row[key])
        tool["mvp"] = bool(row.get("mvp", False))
        rt = runtime_info(eid)
        if rt is not None:
            tool["runtime"] = rt
        if aliases and aliases.get(eid):
            tool["aliases"] = list(aliases[eid])
        out.append(tool)
    return out


def failure_gate(check_id: str, task: TaskSpec | None) -> str:
    """What a failure of this check does to the claim: "Stop", "Warn" or "Reported"."""
    from pah.core.check import GateKind

    if task is not None and check_id in task.escalate:
        return GateKind.STOP.value
    cls = checks_registry().get(check_id)
    kind = getattr(cls, "gate_kind", None) if cls is not None else None
    return GateKind(kind).value if isinstance(kind, str) and kind in set(GateKind) else "Stop"


# ---------------------------------------------------------------- small formatting helpers


def parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def iso(ts: datetime | None) -> str | None:
    return ts.astimezone(UTC).isoformat().replace("+00:00", "Z") if ts else None


def _ms(a: datetime | None, b: datetime | None) -> int | None:
    return round((b - a).total_seconds() * 1000) if a and b else None


def fmt_duration(ms: float) -> str:
    """Below 1 s in ms, otherwise seconds to one decimal (docs/UI.md, Number display)."""
    return f"{round(ms)} ms" if ms < 1000 else f"{ms / 1000:.1f} s"


def fmt_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return str(value)


def _measure(m: Mapping[str, Any]) -> str:
    unit = m.get("unit")
    return f"{m.get('name')}={fmt_value(m.get('value'))}{' ' + str(unit) if unit else ''}"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _ids(ids: list[str], limit: int = 4) -> str:
    head = ", ".join(ids[:limit])
    return head + (f" and {len(ids) - limit} more" if len(ids) > limit else "")


def _sentence(text: str) -> str:
    text = text.strip()
    return text if text.endswith((".", "!", "?")) else text + "."


def _stage_layer(stage: str) -> int | None:
    m = _STAGE.match(stage)
    return int(m.group(1)) if m else None


def _layer_name(i: int) -> str:
    return str(LAYERS[i]["name"]) if 0 <= i < len(LAYERS) else f"layer {i}"


def _worst(results: Iterable[str]) -> str | None:
    ranked = [r for r in results if r in _RANK]
    return max(ranked, key=lambda r: _RANK[r]) if ranked else None


def file_url(run_id: str, rel: str) -> str:
    """URL of a run file on the native files route (the web client prefixes /api/harness)."""
    return f"/runs/{quote(run_id)}/files/{quote(rel)}"


# ---------------------------------------------------------------- run state


@dataclass
class RunState:
    """Everything the adapters need from one run directory, read once."""

    run_dir: Path
    events: list[dict[str, Any]]
    record: dict[str, Any] | None
    report: dict[str, Any] | None
    provenance: list[dict[str, Any]] | None
    manifest: dict[str, Any] | None
    task_id: str | None
    task: TaskSpec | None
    claim: str | None
    selected: tuple[int, ...]
    findings: list[dict[str, Any]]
    started_at: datetime | None
    last_ts: datetime | None
    run_end: dict[str, Any] | None
    verdict: dict[str, Any] | None
    status: str
    report_status: str = "none"
    report_error: str | None = None
    harness_run_id: str | None = None
    profile: str | None = None
    error: str | None = None
    stage_start: dict[int, datetime] = field(default_factory=dict)
    stage_end: dict[int, datetime] = field(default_factory=dict)
    stage_total: dict[int, int] = field(default_factory=dict)
    job: dict[str, Any] = field(default_factory=dict)

    @property
    def run_id(self) -> str:
        return self.run_dir.name

    @property
    def ended_at(self) -> datetime | None:
        if self.run_end is not None:
            return parse_ts(self.run_end.get("ts"))
        return parse_ts(self.record.get("finished_at")) if self.record else None

    def layer_status(self, i: int) -> str:
        if self.selected and i not in self.selected:
            return "not_run"
        if i in self.stage_end:
            return "done"
        if i in self.stage_start and self.status == "running":
            return "running"
        if not self.selected and self.status == "done":
            return "not_run"
        if self.status == "done" and self.record is not None:
            return "done"
        return "pending"

    def layer_findings(self, i: int) -> list[dict[str, Any]]:
        return [f for f in self.findings if f.get("layer") == i]

    def artifacts(self) -> list[dict[str, Any]]:
        """Artifacts from report.json (a superset), else record.json."""
        rows = _dicts(_dict(self.report).get("artifacts"))
        return rows or _dicts(_dict(self.record).get("artifacts"))


def _load_manifest(run_dir: Path, events: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The manifest from the run directory, else from the path the run logged at start."""
    from pah.core.manifest import load_manifest

    candidates = [run_dir / "manifest.yaml", run_dir / "manifest.yml"]
    for e in events[:5]:
        m = _MANIFEST.search(str(e.get("message", ""))) if e.get("kind") == "log" else None
        if m:
            p = Path(m.group(1))
            if p.is_absolute():
                candidates.append(p)
            else:
                root = repo_root()
                candidates += [*([root / p] if root else []), Path.cwd() / p]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            return load_manifest(path).model_dump(mode="json")
        except Exception as exc:
            log.info("manifest %s not loadable: %s", path, exc)
    return None


def _profile_from_events(events: list[dict[str, Any]]) -> str | None:
    for e in events[:5]:
        m = _PROFILE.search(str(e.get("message", ""))) if e.get("kind") == "log" else None
        if m:
            return m.group(1)
    return None


def _findings_dir(run_dir: Path) -> list[dict[str, Any]]:
    folder = run_dir / "findings"
    out: list[dict[str, Any]] = []
    for path in sorted(folder.glob("L*_*.json")) if folder.is_dir() else ():
        data = read_json(path)
        if isinstance(data, dict):
            out.append(data)
    return out


def _report_status(
    events: list[dict[str, Any]],
    report: dict[str, Any] | None,
    job: Mapping[str, Any] | None = None,
) -> tuple[str, str | None]:
    """none | running | done | failed | skipped, from the `report` stage events.

    A report stage that started and never ended in a job that job.json records as failed has
    failed (an exception in the report writer), not running.
    """
    status, error = ("done", None) if report is not None else ("none", None)
    for e in events:
        if e.get("stage") != "report":
            continue
        if e.get("kind") == "stage_start":
            status = "running"
        elif e.get("kind") == "stage_end":
            raw = str(_dict(e.get("data")).get("status", "ok"))
            status = {"ok": "done", "skip": "skipped"}.get(raw, "failed")
            error = None if status == "done" else str(e.get("message", ""))
    if status == "running" and job is not None and str(job.get("status", "")) == "failed":
        return "failed", str(job.get("error") or "job failed during the report stage")
    return status, error


def load_state(
    run_dir: Path, *, now: float | None = None, stale_after: float = STALE_AFTER_S
) -> RunState:
    """Reads a run directory. Works for finished runs, live runs and runs that have not begun."""
    events_path = run_dir / EVENTS
    events = read_events(events_path)
    raw_record = read_json(run_dir / "record.json")
    record = raw_record if isinstance(raw_record, dict) else None
    raw_report = read_json(run_dir / "report.json")
    report = raw_report if isinstance(raw_report, dict) else None
    raw_prov = read_json(run_dir / "provenance.json")
    provenance = _dicts(raw_prov) if isinstance(raw_prov, list) else None
    if provenance is None and record is not None and isinstance(record.get("provenance"), list):
        provenance = _dicts(record["provenance"])
    job = _dict(read_json(run_dir / "job.json"))

    run_start = next((e for e in events if e.get("kind") == "run_start"), None)
    run_end = next((e for e in events if e.get("kind") == "run_end"), None)
    start_data = _dict(_dict(run_start).get("data"))

    # record.json at the end; while the run is live, the manifest run_start carries (CLI, MCP and
    # native runs write no manifest.yaml into the run directory)
    manifest: dict[str, Any] | None = (
        _dict(_dict(record).get("manifest")) or _dict(start_data.get("manifest")) or None
    )
    if manifest is None:
        manifest = _load_manifest(run_dir, events)

    raw_task = (
        _dict(record).get("task")
        or start_data.get("task")
        or _dict(manifest).get("task")
        or job.get("task")
    )
    task_id = raw_task if isinstance(raw_task, str) else None
    task = task_spec(task_id)
    raw_claim = _dict(record).get("claim") or _dict(manifest).get("claim")
    claim = raw_claim if isinstance(raw_claim, str) else (task.claim if task else None)
    layers = _dict(record).get("layers") or start_data.get("layers") or ()
    selected = tuple(sorted({int(x) for x in layers if isinstance(x, int) and 0 <= x <= 5}))

    if record is not None and isinstance(record.get("findings"), list):
        findings = _dicts(record["findings"])
    else:
        findings = [
            _dict(e.get("data"))["finding"]
            for e in events
            if e.get("kind") == "finding" and isinstance(_dict(e.get("data")).get("finding"), dict)
        ]
        if not findings and not events:
            findings = _findings_dir(run_dir)

    stage_start: dict[int, datetime] = {}
    stage_end: dict[int, datetime] = {}
    stage_total: dict[int, int] = {}
    error: str | None = None
    for e in events:
        kind = e.get("kind")
        layer = _stage_layer(str(e.get("stage", "")))
        ts = parse_ts(e.get("ts"))
        if kind == "stage_start" and layer is not None and ts:
            stage_start[layer] = ts
            m = _N_CHECKS.search(str(e.get("message", "")))
            if m:
                stage_total[layer] = int(m.group(1))
        elif kind == "stage_end" and layer is not None and ts:
            stage_end[layer] = ts
        elif (
            kind == "log"
            and e.get("stage") == "run"
            and str(_dict(e.get("data")).get("status", "")) in {"error", "failed"}
        ):
            error = str(e.get("message", ""))

    verdict: dict[str, Any] | None = _dict(_dict(record).get("verdict")) or None
    if verdict is None and run_end is not None:
        verdict = _dict(_dict(run_end.get("data")).get("verdict")) or None

    job_status = str(job.get("status", ""))
    if record is not None or run_end is not None:
        status = "done"
    elif job_status == "failed":
        status, error = "failed", str(job.get("error") or error or "")
    elif not events:
        status = "queued"
    elif error is not None:
        status = "failed"
    else:
        try:
            quiet = (time.time() if now is None else now) - events_path.stat().st_mtime
        except OSError:
            quiet = 0.0
        status = "failed" if quiet > stale_after else "running"

    started_at = (
        parse_ts(_dict(run_start).get("ts"))
        or parse_ts(_dict(record).get("started_at"))
        or (parse_ts(events[0].get("ts")) if events else None)
        or parse_ts(job.get("createdAt"))
    )
    harness_id = _dict(record).get("run_id") or (events[0].get("run_id") if events else None)
    report_status, report_error = _report_status(events, report, job)
    return RunState(
        run_dir=run_dir,
        events=events,
        record=record,
        report=report,
        provenance=provenance,
        manifest=manifest,
        task_id=task_id,
        task=task,
        claim=claim,
        selected=selected,
        findings=findings,
        started_at=started_at,
        last_ts=parse_ts(events[-1].get("ts")) if events else None,
        run_end=run_end,
        verdict=verdict,
        status=status,
        report_status=report_status,
        report_error=report_error,
        harness_run_id=harness_id if isinstance(harness_id, str) else None,
        profile=_profile_from_events(events),
        error=error or None,
        stage_start=stage_start,
        stage_end=stage_end,
        stage_total=stage_total,
        job=job,
    )


# ---------------------------------------------------------------- checks and layers


def _evidence(f: Mapping[str, Any]) -> str:
    message = str(f.get("message", ""))
    ms = _dicts(f.get("measurements"))[:3]
    return f"{message} · {', '.join(_measure(m) for m in ms)}" if ms else message


def _tool(f: Mapping[str, Any], cls: Any) -> str | None:
    tool = _dict(f.get("tool"))
    if tool.get("name"):
        return str(tool["name"])
    if cls is None:
        return None
    modules = [m.split(".")[0] for m in getattr(cls, "requires_modules", ())]
    return " · ".join(modules) if modules else "pah"


def _title(cid: str) -> str:
    cls = checks_registry().get(cid)
    return str(getattr(cls, "title", cid)) if cls is not None else cid


def ui_check(f: Mapping[str, Any], task: TaskSpec | None) -> dict[str, Any]:
    """One finding as a UiCheck."""
    cid = str(f.get("check_id", ""))
    cls = checks_registry().get(cid)
    evidence = _dict(f.get("evidence"))
    out: dict[str, Any] = {
        "id": cid,
        "name": _title(cid),
        "gate": failure_gate(cid, task),
        "result": str(f.get("gate", "skip")),
        "evidence": _evidence(f),
        "message": str(f.get("message", "")),
    }
    tool = _tool(f, cls)
    if tool:
        out["tool"] = tool
    if isinstance(f.get("duration_s"), int | float):
        out["ms"] = round(float(f["duration_s"]) * 1000)
    thresholds = _dicts(f.get("thresholds"))
    if thresholds:
        t0 = thresholds[0]
        out["threshold"] = {
            "value": f"{t0.get('comparator')} {fmt_value(t0.get('value'))}",
            "origin": str(t0.get("origin", "")),
            "evidenceLevel": str(t0.get("evidence_level", "")),
        }
        out["thresholds"] = [
            {
                "name": t.get("name"),
                "value": t.get("value"),
                "comparator": t.get("comparator"),
                "origin": t.get("origin"),
                "evidenceLevel": t.get("evidence_level"),
                **({"measurement": str(t["measurement"])} if t.get("measurement") else {}),
            }
            for t in thresholds
        ]
    measurements = _dicts(f.get("measurements"))
    if measurements:
        out["measurements"] = [
            {"name": m.get("name"), "value": m.get("value"), "unit": m.get("unit")}
            for m in measurements
        ]
    if out["result"] == "skip" and evidence.get("skip_reason"):
        out["skipReason"] = str(evidence["skip_reason"])
    if evidence.get("escalated_by_task"):
        out["escalated"] = True
    artifacts = [str(a) for a in f.get("artifacts") or ()]
    if artifacts:
        out["artifacts"] = artifacts
    return out


def _pending_check(cid: str, task: TaskSpec | None) -> dict[str, Any]:
    return {"id": cid, "name": _title(cid), "gate": failure_gate(cid, task), "result": "pending"}


def _counts(checks: list[dict[str, Any]]) -> dict[str, int]:
    c = Counter(str(ch["result"]) for ch in checks)
    out = {r: c.get(r, 0) for r in RESULTS}
    for extra in ("reported", "pending"):
        if c.get(extra):
            out[extra] = c[extra]
    return out


def _not_implemented(checks: list[dict[str, Any]]) -> int:
    return sum(1 for c in checks if c.get("skipReason") == "unknown_check")


def _figures(findings: list[dict[str, Any]]) -> list[list[str]]:
    out: list[list[str]] = []
    seen: set[str] = set()
    for f in findings:
        if f.get("gate") == "skip":
            continue
        # the first measurement with a value; a missing value is not a figure (the UI shows a dash)
        m = next((x for x in _dicts(f.get("measurements")) if x.get("value") is not None), None)
        if m is None:
            continue
        name = str(m.get("name", ""))
        unit = ui_stats.unit_of(name, m.get("unit"))
        for suffix, _u in ui_stats.SUFFIX_UNITS:
            if not m.get("unit") and name.endswith(suffix):
                name = name[: -len(suffix)]
                break
        label = name.replace("_", " ")
        if label in seen:
            continue
        seen.add(label)
        value = m.get("value")
        out.append(
            [label, fmt_value(value) if isinstance(value, bool) else ui_stats.fmt(value, unit)]
        )
        if len(out) >= MAX_FIGURES:
            break
    return out


def _summary(
    state: RunState, i: int, checks: list[dict[str, Any]], sources: list[dict[str, Any]]
) -> list[str]:
    status = state.layer_status(i)
    if status in {"not_run", "pending"}:
        return []
    counts = _counts(checks)
    if status == "running":
        return [f"{len(checks) - counts.get('pending', 0)} of {len(checks)} checks"]
    out: list[str] = []
    if i == 0 and sources:
        out.append(_plural(len(sources), "object"))
        if any("cached" in s for s in sources):
            out.append(f"{sum(1 for s in sources if s.get('cached'))} cached")
    out.append(_plural(len(checks), "check"))
    if counts["stop"]:
        out.append(f"{counts['stop']} stop")
    if counts["warn"]:
        out.append(f"{counts['warn']} warn")
    missing = _not_implemented(checks)
    if missing:
        out.append(f"{missing} not implemented")
    return out


def ui_layers(state: RunState, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for meta in LAYERS:
        i = int(meta["i"])
        status = state.layer_status(i)
        found = state.layer_findings(i)
        checks = [ui_check(f, state.task) for f in found]
        if status in {"running", "pending"} and state.task is not None:
            seen = {c["id"] for c in checks}
            checks += [
                _pending_check(c, state.task) for c in state.task.layers.get(i, ()) if c not in seen
            ]
        layer: dict[str, Any] = {
            **meta,
            "status": status,
            "counts": {} if status == "not_run" else _counts(checks),
            "summary": _summary(state, i, checks, sources),
            "figures": _figures(found) if status in {"done", "running"} else [],
            "checks": checks,
        }
        duration = _ms(state.stage_start.get(i), state.stage_end.get(i))
        if duration is not None:
            layer["durationMs"] = duration
        out.append(layer)
    return out


# ---------------------------------------------------------------- record sections


def _source_meta(sid: str) -> dict[str, Any]:
    meta = sources_meta()
    return meta.get(sid) or meta.get(SOURCE_ALIASES.get(sid, ""), {})


def ui_sources(state: RunState) -> list[dict[str, Any]]:
    """Layer 0 provenance. While the run is going, the records listed by l0.sources.resolved."""
    rows: list[dict[str, Any]] = []
    usage = {
        str(k): [str(x) for x in v]
        for k, v in _dict(_dict(state.record).get("usage")).items()
        if isinstance(v, list)
    }
    if state.provenance is not None:
        for p in state.provenance:
            sid = str(p.get("source_id", ""))
            m = _source_meta(sid)
            extra = _dict(p.get("extra"))
            pid = f"{sid}:{p.get('accession', '')}:{str(p.get('sha256', ''))[:12]}"
            row: dict[str, Any] = {
                "id": pid,
                "source": str(m.get("name") or sid),
                "sourceId": sid,
                "accession": str(p.get("accession", "")),
                "release": str(p.get("release") or "n/a"),
                "sha256": str(p.get("sha256", "")),
                "retrievedAt": p.get("retrieved_at"),
                "url": p.get("url"),
                "sizeBytes": p.get("size_bytes"),
                "usedBy": sorted(c for c, ids in usage.items() if pid in ids),
            }
            if m.get("supplies"):
                row["supplies"] = str(m["supplies"])
            if "cache" in extra:
                row["cached"] = extra["cache"] == "hit"
            rows.append(row)
        return rows
    resolved = next((f for f in state.findings if f.get("check_id") == "l0.sources.resolved"), None)
    for r in _dicts(_dict(_dict(resolved).get("evidence")).get("records")):
        sid = str(r.get("source", ""))
        m = _source_meta(sid)
        row = {
            "source": str(m.get("name") or sid),
            "sourceId": sid,
            "accession": str(r.get("accession", "")),
            "release": str(r.get("release") or "n/a"),
            "sha256": str(r.get("sha256", "")),
            "url": r.get("url"),
        }
        if m.get("supplies"):
            row["supplies"] = str(m["supplies"])
        rows.append(row)
    return rows


def run_executors(state: RunState) -> list[str]:
    """Executors the run names: the declared model, then every prediction and control set."""
    m = _dict(state.manifest)
    names = [str(_dict(m.get("model")).get("executor") or "")]
    names += [str(e) for e, _ in ui_stats.spec_roles(m)]
    return [n for n in dict.fromkeys(names) if n and n != "None"]


def _harness_executed(state: RunState) -> set[str]:
    """Executors an `exec` stage of this run's event stream names (run inside the harness)."""
    out: set[str] = set()
    for e in state.events:
        data = _dict(e.get("data"))
        if (e.get("stage") == "exec" or data.get("kind") == "exec") and data.get("executor"):
            out.add(str(data["executor"]))
    return out


def ran_by(
    state: RunState, executor: str, members: list[ui_stats.Member] | None = None
) -> str | None:
    """How the executor's outputs reached the run: "harness" when this run executed it,
    "external" when its outputs were supplied (manifest predictions or parsed prediction
    structures), None when nothing of it ran (runs started from settings check inputs only)."""
    from pah.webui.manifest_builder import EXECUTORS_NOT_RUN

    if executor in _harness_executed(state):
        return "harness"
    if state.job.get("executors") == EXECUTORS_NOT_RUN:
        return None
    supplied = {e for e, _ in ui_stats.spec_roles(_dict(state.manifest))}
    supplied |= {m.executor for m in members or ()}
    return "external" if executor in supplied else None


def ui_tools(state: RunState, members: list[ui_stats.Member] | None = None) -> list[dict[str, Any]]:
    """The executors the manifest declares, with the outputs they report (self-describing
    record). `ran` is true when the executor's outputs are in the run; `ranBy` says whether
    the harness executed it or the outputs were supplied (`ran_by`)."""
    model = _dict(_dict(state.manifest).get("model"))
    rows = executor_rows()
    preds = {str(p.get("executor")): p for p in _dicts(_dict(state.manifest).get("predictions"))}
    out: list[dict[str, Any]] = []
    for executor in run_executors(state):
        row = record_tool(executor, rows)
        declared = model.get("version") if model.get("executor") == executor else None
        declared = declared or _dict(preds.get(executor)).get("version")
        row["version"] = declared if declared else row.get("version")
        row["declaredVersion"] = declared
        if model.get("executor") == executor and model.get("checkpoint"):
            row["checkpoint"] = model["checkpoint"]
        by = ran_by(state, executor, members)
        row["ran"] = by is not None
        row["ranBy"] = by
        out.append(row)
    return out


def stats_input(state: RunState) -> ui_stats.StatsInput:
    """What the stats mapping reads: findings, manifest, artifacts and the register rows."""
    rows = executor_rows()
    names = {sid: str(m.get("name") or sid) for sid, m in sources_meta().items()}
    names.update(
        {alias: names[target] for alias, target in SOURCE_ALIASES.items() if target in names}
    )
    return ui_stats.StatsInput(
        run_id=state.run_id,
        run_dir=state.run_dir,
        findings=state.findings,
        manifest=_dict(state.manifest),
        artifacts=state.artifacts(),
        tools={e: record_tool(e, rows) for e in run_executors(state)},
        source_names=names,
    )


def ui_inputs(state: RunState) -> dict[str, Any]:
    m = _dict(state.manifest)
    proteins = _dicts(m.get("proteins"))
    ligands = _dicts(m.get("ligands"))
    receptor = _dict(m.get("receptor"))
    out: dict[str, Any] = {
        "partner": (proteins[1].get("uniprot") or proteins[1].get("id"))
        if len(proteins) > 1
        else None,
        "ligand": (ligands[0].get("smiles") or ligands[0].get("ccd")) if ligands else None,
    }
    if proteins and (proteins[0].get("uniprot") or proteins[0].get("id")):
        out["target"] = proteins[0].get("uniprot") or proteins[0].get("id")
    reference = receptor.get("pdb_id") or next(
        (p.get("pdb_id") for p in proteins if p.get("pdb_id")), None
    )
    if reference:
        out["reference"] = reference
    if isinstance(m.get("ph"), int | float):
        out["ph"] = m["ph"]
    seeds = run_seeds(m)
    if seeds:
        out["seeds"] = len(seeds)
    return out


def run_seeds(manifest: Mapping[str, Any]) -> list[int]:
    """Seeds of the declared model, then any further seeds of the prediction entries."""
    seeds: list[int] = []
    sets = [_dict(manifest.get("model")), *_dicts(manifest.get("predictions"))]
    for entry in sets:
        for x in entry.get("seeds") or ():
            if isinstance(x, int) and not isinstance(x, bool) and x not in seeds:
                seeds.append(x)
    return seeds


def _structure_kind(artifact_kind: str, rel: str) -> str:
    """UI structure kind (crystal | medoid | seed | docking | model) for a structure file."""
    if artifact_kind == "source_structure" or rel.startswith("artifacts/sources/"):
        return "crystal"
    name = Path(rel).name.lower()
    if "medoid" in name:
        return "medoid"
    if "seed" in name:
        return "seed"
    if "dock" in name or "pose" in name:
        return "docking"
    return "model"


def _inside(run_dir: Path, path: str) -> str | None:
    """Run-relative posix path when `path` is inside the run directory, else None."""
    p = Path(path)
    if not p.is_absolute():
        return p.as_posix() if ".." not in p.parts else None
    try:
        return p.resolve().relative_to(run_dir.resolve()).as_posix()
    except ValueError:
        return None


def ui_artifacts(state: RunState) -> list[dict[str, Any]]:
    """Every registered artifact with its checksum; `url` only for files inside the run."""
    out: list[dict[str, Any]] = []
    for a in state.artifacts():
        rel = _inside(state.run_dir, str(a.get("path", "")))
        out.append(
            {
                "path": rel or str(a.get("path", "")),
                "kind": str(a.get("kind", "")),
                "label": str(a.get("label", "")),
                "sha256": str(a.get("sha256", "")),
                "sizeBytes": a.get("size_bytes"),
                "url": file_url(state.run_id, rel) if rel else None,
                "derivedFrom": [str(x) for x in a.get("derived_from") or ()],
            }
        )
    return out


def ui_structures(
    state: RunState, members: list[ui_stats.Member] | None = None
) -> list[dict[str, Any]]:
    """Structure files the browser can load: registered artifacts inside the run directory,
    plus any `.cif`/`.pdb`/`.sdf` under `artifacts/` not yet registered (live runs). Parsed
    predictions take the label and kind of their ensemble member. Files the checks write for
    themselves (`artifacts/work/`, `derived/`) are not structures of the run and are left out."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    by_path = {m.structure: m for m in members or () if m.structure}

    def add(rel: str, artifact_kind: str, label: str, a: Mapping[str, Any] | None) -> None:
        fmt = STRUCTURE_FORMATS.get(Path(rel).suffix.lower())
        if fmt is None or rel in seen or rel.startswith((WORK_DIR, DERIVED_DIR)):
            return
        seen.add(rel)
        member = by_path.get(rel) if artifact_kind == "prediction_structure" else None
        row: dict[str, Any] = {
            "id": Path(rel).with_suffix("").as_posix(),
            "label": member.label if member else (label or Path(rel).name),
            "kind": member.kind if member else _structure_kind(artifact_kind, rel),
            "url": file_url(state.run_id, rel),
            "format": fmt,
            "artifactKind": artifact_kind,
            "path": rel,
        }
        if a is not None and a.get("sha256"):
            row["sha256"] = str(a["sha256"])
        derived = [str(x) for x in (a or {}).get("derived_from") or ()]
        if derived:
            row["derivedFrom"] = derived
        if member is not None:
            row["pose"] = member.pose
            row["role"] = member.role
            row["toolId"] = member.executor
        out.append(row)

    for a in state.artifacts():
        kind = str(a.get("kind", ""))
        rel = _inside(state.run_dir, str(a.get("path", "")))
        if kind in STRUCTURE_KINDS and rel and (state.run_dir / rel).is_file():
            add(rel, kind, str(a.get("label", "")), a)
    base = state.run_dir / "artifacts"
    if base.is_dir():
        for path in sorted(base.rglob("*")):
            if path.is_file():
                rel = path.relative_to(state.run_dir).as_posix()
                kind = "source_structure" if rel.startswith("artifacts/sources/") else "file"
                add(rel, kind, "", None)
    return out


def _unique_stems(structures: list[dict[str, Any]]) -> dict[str, str]:
    """File stem -> structure id, for stems that name one structure only."""
    stems = Counter(Path(str(s["path"])).stem for s in structures)
    return {
        Path(str(s["path"])).stem: str(s["id"])
        for s in structures
        if stems[Path(str(s["path"])).stem] == 1
    }


def last_renders(figures: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Render figures whose PNG is still the one they describe, and how many were overwritten.

    The report names each render file after the structure's file stem, so structures that share
    a stem (every docking pose is `complex.pdb`) write the same PNG in turn; the file then shows
    the last structure rendered to it."""
    last: dict[str, dict[str, Any]] = {}
    for f in figures:
        last[str(f.get("path", ""))] = f
    kept = list(last.values())
    return kept, len(figures) - len(kept)


def ui_renders(state: RunState, structures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """PyMOL renders from report.json figures (kind `render`): one entry per PNG view, with the
    structure it shows and its `.pse` session. The structure is the one whose sha256 the caption
    names (`pah.report.renders.figure_entries`), else the one with the file's stem. Falls back to
    `renders/*.png` before the report."""
    by_stem = _unique_stems(structures)
    by_sha = [(str(s["sha256"]), str(s["id"])) for s in structures if s.get("sha256")]
    out: list[dict[str, Any]] = []
    figures = [f for f in _dicts(_dict(state.report).get("figures")) if f.get("kind") == "render"]
    linked: set[tuple[str, str]] = set()
    for f in last_renders(figures)[0]:
        m = _RENDER_ID.match(str(f.get("id", "")))
        stem = m.group("stem") if m else Path(str(f.get("path", ""))).stem
        view = m.group("view") if m else "default"
        session = f.get("session_path")
        sha = ui_stats.caption_sha(str(f.get("caption", "")))
        hits = [sid for full, sid in by_sha if sha and full.startswith(sha)]
        # byte-identical files share a sha256 and render alike: the first one not yet linked
        free = [sid for sid in hits if (sid, view) not in linked]
        structure = (free or hits or [by_stem.get(stem, stem)])[0]
        linked.add((structure, view))
        out.append(
            {
                "structure": structure,
                "png": file_url(state.run_id, str(f.get("path", ""))),
                "pse": file_url(state.run_id, str(session)) if session else None,
                "view": view,
                "caption": str(f.get("caption", "")),
                "alt": str(f.get("alt", "")),
            }
        )
    if out or state.report is not None:
        return out
    base = state.run_dir / "renders"
    if not base.is_dir():
        return out
    sessions = {p.stem: p for p in base.glob("*.pse")}
    for png in sorted(base.glob("*.png")):
        stem, _, view = png.stem.rpartition("_")
        stem = stem or png.stem
        pse = sessions.get(stem)
        out.append(
            {
                "structure": by_stem.get(stem, stem),
                "png": file_url(state.run_id, png.relative_to(state.run_dir).as_posix()),
                "pse": file_url(state.run_id, pse.relative_to(state.run_dir).as_posix())
                if pse
                else None,
                "view": view or "default",
            }
        )
    return out


def ui_report_files(state: RunState) -> dict[str, Any]:
    """Report, figures and provenance graph files written by the report stage."""
    rep = _dict(state.report)
    graph = {
        str(k): file_url(state.run_id, str(v))
        for k, v in _dict(rep.get("graph")).items()
        if (state.run_dir / str(v)).is_file()
    }
    reports = {
        key: file_url(state.run_id, name)
        for key, name in (("markdown", "report.md"), ("json", "report.json"))
        if (state.run_dir / name).is_file()
    }
    figures = [
        {
            "id": str(f.get("id", "")),
            "url": file_url(state.run_id, str(f.get("path", ""))),
            "caption": str(f.get("caption", "")),
            "alt": str(f.get("alt", "")),
            **({"data": file_url(state.run_id, str(f["data_path"]))} if f.get("data_path") else {}),
        }
        for f in _dicts(rep.get("figures"))
        if f.get("kind") != "render"
    ]
    out: dict[str, Any] = {
        "status": state.report_status,
        "reports": reports,
        "graph": graph,
        "figures": figures,
        "renderErrors": [str(x) for x in rep.get("render_errors") or ()],
        "rendersOverwritten": last_renders(
            [f for f in _dicts(rep.get("figures")) if f.get("kind") == "render"]
        )[1],
        "limitations": [str(x) for x in rep.get("limitations") or ()],
    }
    if state.report_error:
        out["error"] = state.report_error
    return out


def ui_outputs(state: RunState) -> list[str]:
    out: list[str] = []
    for path in sorted(state.run_dir.rglob("*")):
        rel = path.relative_to(state.run_dir)
        if path.is_file() and rel.parts[0] != "findings":
            out.append(rel.as_posix())
            if len(out) >= MAX_OUTPUTS:
                break
    return out


def ui_controls(state: RunState) -> list[dict[str, Any]]:
    task = state.task
    if task is None:
        return []
    by_id = {str(f.get("check_id")): f for f in state.findings}
    out: list[dict[str, Any]] = []
    for name in task.controls:
        cid, layer = next(
            (
                (c, i)
                for i, ids in task.layers.items()
                for c in ids
                if c.endswith(f"controls.{name}")
            ),
            (None, None),
        )
        f = by_id.get(cid) if cid else None
        if cid is None:
            out.append({"name": name, "status": "missing", "note": "no check in the task spec"})
        elif f is None:
            ran = layer in state.selected
            note = f"{cid} not reported yet" if ran else f"{cid}: layer {layer} not run"
            out.append({"name": name, "status": "missing", "note": note, "check": cid})
        else:
            gate = f.get("gate")
            status = "sound" if gate == "pass" else "missing" if gate == "skip" else "incomplete"
            note = str(f.get("message", ""))
            out.append({"name": name, "status": status, "note": note, "check": cid})
    return out


def _scope(state: RunState) -> str:
    if state.verdict and state.verdict.get("scope"):
        return str(state.verdict["scope"])
    return f"layers {','.join(map(str, state.selected))}" if state.selected else "no layers"


def statement(
    outcome: str | None,
    claim: str,
    scope: str,
    stops: list[str],
    warnings: list[str],
    incomplete: list[str],
    total: int,
) -> str:
    """Verdict sentence from the outcome, scope and check ids. Facts only."""
    if outcome is None:
        return f"Run in progress in {scope}; no verdict yet."
    if outcome == "refused":
        return (
            f"{_plural(len(stops), 'check')} stopped in {scope}: {_ids(stops)}. "
            f"The claim “{claim}” is not supported."
        )
    if outcome == "incomplete":
        tail = f" {_plural(len(warnings), 'check')} warned: {_ids(warnings)}." if warnings else ""
        return (
            f"{_plural(len(incomplete), 'check')} in {scope} could not be evaluated: "
            f"{_ids(incomplete)}. The claim “{claim}” is not assessed until they run."
            f"{tail}"
        )
    if outcome == "narrowed":
        return (
            f"{_plural(len(warnings), 'check')} warned in {scope}: {_ids(warnings)}. "
            f"The claim “{claim}” is reported with these warnings attached."
        )
    return (
        f"{_plural(total, 'check')} in {scope} passed or did not apply. "
        f"The claim “{claim}” is supported within {scope}."
    )


def ui_verdict(state: RunState) -> dict[str, Any]:
    claim = state.claim or ""
    scope = _scope(state)
    v = state.verdict
    if v is not None:
        outcome = OUTCOMES.get(str(v.get("outcome")))
        stops = [str(x) for x in v.get("stops") or ()]
        warnings = [str(x) for x in v.get("warnings") or ()]
        incomplete = [str(x) for x in v.get("incomplete") or ()]
        na = [str(x) for x in v.get("not_applicable") or ()]
    else:
        outcome = None
        stops = [str(f.get("check_id")) for f in state.findings if f.get("gate") == "stop"]
        warnings = [str(f.get("check_id")) for f in state.findings if f.get("gate") == "warn"]
        incomplete, na = [], []
    text = statement(outcome, claim, scope, stops, warnings, incomplete, len(state.findings))
    if v is None and state.status == "failed":
        text = f"Run ended without a verdict in {scope}." + (
            f" {state.error}" if state.error else ""
        )
    return {
        "claim": claim,
        "outcome": outcome,
        "statement": text,
        "scope": scope,
        "stops": stops,
        "warnings": warnings,
        "incomplete": incomplete,
        "notApplicable": na,
    }


def ui_narrative(
    state: RunState, layers: list[dict[str, Any]], verdict: dict[str, Any]
) -> list[str]:
    lines: list[str] = []
    for layer in layers:
        status = layer["status"]
        if status not in {"done", "running"}:
            continue
        checks = layer["checks"]
        c = layer["counts"]
        head = f"Layer {layer['i']}, {str(layer['name']).lower()}"
        if status == "running":
            done = len(checks) - c.get("pending", 0)
            lines.append(f"{head}: running, {done} of {len(checks)} checks reported.")
            continue
        parts = [f"{c['pass']} pass", f"{c['warn']} warn", f"{c['stop']} stop", f"{c['skip']} skip"]
        text = f"{head}: {_plural(len(checks), 'check')}; {', '.join(parts)}."
        stops = [ch["id"] for ch in checks if ch["result"] == "stop"]
        warns = [ch["id"] for ch in checks if ch["result"] == "warn"]
        if stops:
            text += f" Stopped: {_ids(stops)}."
        if warns:
            text += f" Warned: {_ids(warns)}."
        missing = _not_implemented(checks)
        if missing:
            text += f" {missing} not implemented."
        lines.append(text)
    if verdict.get("outcome"):
        lines.append(f"Verdict: {verdict['outcome']}. {verdict['statement']}")
    return lines


def ui_run_meta(state: RunState) -> dict[str, Any]:
    rec = _dict(state.record)
    out: dict[str, Any] = {
        "runId": state.harness_run_id,
        "pahVersion": rec.get("pah_version") or __version__,
        "toolVersions": _dict(rec.get("tool_versions")),
        "startedAt": iso(state.started_at),
        "finishedAt": iso(state.ended_at),
        "layersSelected": list(state.selected),
    }
    seeds = run_seeds(_dict(state.manifest))
    if seeds:
        out["seeds"] = seeds
    if state.profile:
        out["profile"] = state.profile
    return out


def to_ui_record(run_dir: Path, *, state: RunState | None = None) -> dict[str, Any]:
    """The UiRunRecord for a run directory (finished or still running)."""
    s = state or load_state(run_dir)
    sources = ui_sources(s)
    layers = ui_layers(s, sources)
    verdict = ui_verdict(s)
    inp = stats_input(s)
    members = ui_stats.members(inp)
    structures = ui_structures(s, members)
    renders = ui_renders(s, structures)
    computed = ui_stats.build(inp, members, structures, renders)
    out: dict[str, Any] = {
        "id": s.run_id,
        "createdAt": iso(s.started_at),
        "status": s.status,
        "task": ui_task_id(s.task_id) if s.task_id else None,
        "taskName": s.task.title if s.task else s.task_id,
        "claim": s.claim or "",
        "tools": ui_tools(s, members),
        "inputs": ui_inputs(s),
        "sources": sources,
        "layers": layers,
        "verdict": verdict,
        "stats": computed.stats,
        "narrative": ui_narrative(s, layers, verdict),
        "controls": ui_controls(s),
        "outputs": ui_outputs(s),
        "record": ui_run_meta(s),
        "structures": structures,
        "renders": renders,
        "report": ui_report_files(s),
        "artifacts": ui_artifacts(s),
        "source": "pah",
    }
    if computed.docking is not None:
        out["docking"] = computed.docking
    return out


# ---------------------------------------------------------------- jobs


def _job_name(state: RunState) -> str:
    if isinstance(state.job.get("name"), str) and state.job["name"]:
        return str(state.job["name"])
    m = _dict(state.manifest)
    ids = [str(p.get("id")) for p in _dicts(m.get("proteins")) if p.get("id")]
    ids += [str(x.get("id")) for x in _dicts(m.get("ligands")) if x.get("id")]
    return " · ".join(ids) if ids else state.run_id


def to_job(
    run_dir: Path, *, state: RunState | None = None, now: float | None = None
) -> dict[str, Any]:
    """The Job card for a run directory."""
    s = state or load_state(run_dir, now=now)
    from pah.core.check import INCOMPLETE_REASONS

    incomplete_reasons = {str(r) for r in INCOMPLETE_REASONS}
    layers: list[dict[str, Any]] = []
    for meta in LAYERS:
        i = int(meta["i"])
        found = s.layer_findings(i)
        entry: dict[str, Any] = {
            "i": i,
            "result": _worst(str(f.get("gate")) for f in found),
            "done": s.layer_status(i) == "done",
        }
        # a skip that leaves the verdict incomplete (tool missing, error, unknown check)
        missing = [
            str(f.get("check_id"))
            for f in found
            if f.get("gate") == "skip"
            and str(_dict(f.get("evidence")).get("skip_reason")) in incomplete_reasons
        ]
        if missing:
            entry["incomplete"] = missing
        layers.append(entry)
    running = [i for i in s.stage_start if i not in s.stage_end]
    progress = 0.0
    if s.status == "done":
        layer_idx, progress = 6, 1.0
    elif running:
        layer_idx = running[-1]
        total = s.stage_total.get(layer_idx)
        if total is None and s.task is not None:
            total = len(s.task.layers.get(layer_idx, ()))
        done = len(s.layer_findings(layer_idx))
        progress = min(1.0, done / total) if total else 0.0
    else:
        ended = max(s.stage_end) if s.stage_end else -1
        later = [i for i in s.selected if i > ended]
        layer_idx = (
            later[0] if later else (6 if s.stage_end else (s.selected[0] if s.selected else 0))
        )
    if s.status == "done":
        end = s.ended_at or s.last_ts
    elif s.status == "running":
        end = datetime.fromtimestamp(time.time() if now is None else now, UTC)
    else:
        end = s.last_ts
    elapsed = _ms(s.started_at, end)
    planned = sum(len(s.task.layers.get(i, ())) for i in s.selected) if s.task else None
    verdict = OUTCOMES.get(str(s.verdict.get("outcome"))) if s.verdict else None
    model = _dict(_dict(s.manifest).get("model"))
    executor = model.get("executor")
    tools = (
        [str(t) for t in s.job.get("tools") or ()] if isinstance(s.job.get("tools"), list) else []
    )
    out: dict[str, Any] = {
        "id": s.run_id,
        "runId": s.run_id,
        "harnessRunId": s.harness_run_id,
        "name": _job_name(s),
        "task": ui_task_id(s.task_id) if s.task_id else None,
        "taskName": s.task.title if s.task else s.task_id,
        "tools": tools or ([str(executor)] if executor else []),
        "seeds": len(model.get("seeds") or ()),
        "status": s.status,
        "layerIdx": layer_idx,
        "progress": round(progress, 3),
        "elapsedMs": max(0, elapsed) if elapsed is not None else 0,
        "createdAt": iso(s.started_at),
        "layers": layers,
        "verdict": verdict,
        "checksDone": len(s.findings),
        "checksTotal": planned if planned is not None else len(s.findings),
        "reportStatus": s.report_status,
    }
    if s.error:
        out["error"] = s.error
    return out


# ---------------------------------------------------------------- log lines


def _log_kind(event: Mapping[str, Any]) -> str:
    data = _dict(event.get("data"))
    tagged = str(data.get("kind", "")).lower()
    if tagged in {"fetch", "cache", "exec"}:
        return tagged
    stage = str(event.get("stage", "")).lower()
    if stage in {"fetch", "cache", "exec"}:
        return stage
    message = str(event.get("message", "")).lstrip().lower()
    if re.match(r"(get|fetch|fetched|download)\b", message):
        return "fetch"
    if re.match(r"cached?\b", message):
        return "cache"
    return "log"


def _rel_path(path: str, run_dir: Path | None) -> str | None:
    """Run-relative path of a file named in an event. Writers log absolute paths or paths
    relative to their own working directory (`runs/<id>/record.json`), so the run directory's
    name inside the path is used when the path does not resolve under it."""
    if run_dir is None:
        return None
    p = Path(path)
    if p.is_absolute():
        rel = _inside(run_dir, path)
        if rel:
            return rel
    parts = p.parts
    if run_dir.name in parts:
        idx = len(parts) - 1 - parts[::-1].index(run_dir.name)
        rest = parts[idx + 1 :]
        if rest and ".." not in rest:
            return "/".join(rest)
    return None


def _finding_line(line: dict[str, Any], event: Mapping[str, Any]) -> dict[str, Any]:
    data = _dict(event.get("data"))
    f = _dict(data.get("finding"))
    message = str(event.get("message", ""))
    cid = str(f.get("check_id") or message.split(":", 1)[0])
    gate = str(f.get("gate") or data.get("gate") or "skip")
    layer = line["layer"]
    if layer is None and isinstance(f.get("layer"), int):
        layer = int(f["layer"])
        line["layer"] = layer
    title = _title(cid)
    text_msg = str(f.get("message", message))
    values = ", ".join(_measure(m) for m in _dicts(f.get("measurements"))[:6])
    text = f"L{layer}  {cid}  {gate}  {text_msg}" + (f"  [{values}]" if values else "")
    if isinstance(f.get("duration_s"), int | float):
        text += f"  {fmt_duration(float(f['duration_s']) * 1000)}"
    reason = _dict(f.get("evidence")).get("skip_reason")
    if gate == "skip" and reason == "unknown_check":
        plain = f"{cid} is not implemented in this harness; skipped."
    elif gate == "skip":
        plain = _sentence(f"{title}: skipped, {text_msg}")
    else:
        plain = f"{_sentence(f'{title}: {text_msg}')[:-1]} ({gate})."
    line.update(kind="check", result=gate, text=text, plain=plain)
    return line


def event_to_logline(
    event: Mapping[str, Any],
    started_at: datetime | None,
    *,
    stage_started_at: datetime | None = None,
    run_dir: Path | None = None,
) -> dict[str, Any]:
    """One harness event as a LogLine. `stage_started_at` gives a stage's duration on stage_end."""
    kind = str(event.get("kind", "log"))
    stage = str(event.get("stage", ""))
    message = str(event.get("message", ""))
    data = _dict(event.get("data"))
    ts = parse_ts(event.get("ts"))
    t = max(0.0, (ts - started_at).total_seconds()) if ts and started_at else 0.0
    layer = _stage_layer(stage)
    line: dict[str, Any] = {
        "seq": int(event.get("seq") or 0),
        "ts": event.get("ts"),
        "t": f"{t:.1f}s",
        "layer": layer,
    }
    if kind == "finding":
        return _finding_line(line, event)
    if kind in {"stage_start", "stage_end"} and layer is not None:
        name = _layer_name(layer).lower()
        if kind == "stage_start":
            m = _N_CHECKS.search(message)
            n = f": {_plural(int(m.group(1)), 'check')}" if m else ""
            line.update(
                kind="layer",
                text=f"L{layer}  start  {message}",
                plain=f"Layer {layer}, {name}, started{n}.",
            )
            return line
        counts = {str(k): int(v) for k, v in _dict(data.get("counts")).items()}
        duration = _ms(stage_started_at, ts)
        dur = f" in {fmt_duration(duration)}" if duration is not None else ""
        parts = ", ".join(f"{counts.get(r, 0)} {r}" for r in RESULTS)
        text = f"L{layer}  end  {message}"
        if duration is not None:
            text += f"  {fmt_duration(duration)}"
        line.update(
            kind="layer",
            text=text,
            plain=f"Layer {layer}, {name}, finished{dur}: "
            f"{_plural(sum(counts.values()), 'check')}, {parts}.",
        )
        worst = _worst(counts)
        if worst:
            line["result"] = worst
        return line
    if kind in {"run_start", "run_end"}:
        line["kind"] = "run"
        if kind == "run_start":
            layers = ", ".join(str(x) for x in data.get("layers") or ())
            line.update(
                text=f"run  start  {message}",
                plain=_sentence(f"Run started: task {data.get('task')}, layers {layers}"),
            )
            return line
        v = _dict(data.get("verdict"))
        outcome = OUTCOMES.get(str(v.get("outcome")), str(v.get("outcome") or "unknown"))
        n_stop, n_warn = len(v.get("stops") or ()), len(v.get("warnings") or ())
        n_inc = len(v.get("incomplete") or ())
        line.update(
            text=f"run  end  {message}  {t:.1f} s",
            plain=(
                f"Run finished after {t:.1f} s with verdict {outcome}: {_plural(n_stop, 'stop')}, "
                f"{_plural(n_warn, 'warning')}, {n_inc} incomplete."
            ),
        )
        if outcome in OUTCOME_RESULT:
            line["result"] = OUTCOME_RESULT[outcome]
        return line
    if kind == "artifact":
        raw = str(data.get("path") or message)
        rel = _rel_path(raw, run_dir)
        akind = data.get("artifact_kind")
        tag = f" ({akind})" if akind else ""
        shown = rel or raw
        line.update(kind="artifact", text=f"artifact  {shown}{tag}", plain=f"Wrote {shown}.")
        if rel and run_dir is not None:
            line.update(path=rel, url=file_url(run_dir.name, rel))
        return line
    status = str(data.get("status") or "")
    if kind in {"stage_start", "stage_end"}:  # non-layer stage, e.g. the report
        word = "start" if kind == "stage_start" else "end"
        duration = _ms(stage_started_at, ts) if kind == "stage_end" else None
        text = f"{stage}  {word}  {message}"
        if duration is not None:
            text += f"  {fmt_duration(duration)}"
        verb = "started" if kind == "stage_start" else "finished"
        line.update(kind="log", text=text, plain=_sentence(f"Stage {stage} {verb}: {message}"))
    else:
        line.update(
            kind=_log_kind(event), text=f"{stage}  {message}".strip(), plain=_sentence(message)
        )
    if status in _STATUS_RESULT:
        line["result"] = _STATUS_RESULT[status]
    return line


class LogLineConverter:
    """Stateful conversion for a stream: tracks run_start and each stage's start time."""

    def __init__(
        self, run_dir: Path | None = None, events: Iterable[Mapping[str, Any]] = ()
    ) -> None:
        self.run_dir = run_dir
        self.started_at: datetime | None = None
        self.first_ts: datetime | None = None
        self.stage_start: dict[str, datetime] = {}
        for e in events:
            self.observe(e)

    def observe(self, event: Mapping[str, Any]) -> None:
        ts = parse_ts(event.get("ts"))
        if self.first_ts is None:
            self.first_ts = ts
        kind = event.get("kind")
        if kind == "run_start" and self.started_at is None:
            self.started_at = ts
        if kind == "stage_start" and ts:
            self.stage_start[str(event.get("stage", ""))] = ts

    def __call__(self, event: Mapping[str, Any]) -> dict[str, Any]:
        self.observe(event)
        return event_to_logline(
            event,
            self.started_at or self.first_ts,
            stage_started_at=self.stage_start.get(str(event.get("stage", ""))),
            run_dir=self.run_dir,
        )


def loglines(events: list[dict[str, Any]], run_dir: Path | None = None) -> list[dict[str, Any]]:
    """Every event as a LogLine, with times relative to run_start."""
    converter = LogLineConverter(run_dir)
    return [converter(e) for e in events]
