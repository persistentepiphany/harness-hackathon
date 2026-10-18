"""Harness run directory to the UI shapes in docs/UI.md: `UiRunRecord`, `Job` and `LogLine`.

Reads `record.json` when the run has finished, otherwise the event stream in `events.jsonl`,
plus `provenance.json`, `artifacts/` and `renders/`. Values are copied, never invented: a value the
harness did not produce is left out of the output.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from pah.api.stats import build_stats
from pah.core.check import CHECKS, GateKind
from pah.core.engine import RunRecord
from pah.core.models import ArtifactKind, Finding, Gate

TASK_IDS = {
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
LAYERS = (
    ("provenance", "Provenance", "Where did every input come from?"),
    ("integrity", "Input integrity", "Did the run receive exactly what was declared?"),
    ("adequacy", "Input adequacy", "Does the input carry enough information?"),
    ("applicability", "Applicability", "Is the tool inside its validated regime?"),
    ("validity", "Output validity", "Is the result physically and chemically sensible?"),
    ("support", "Output support", "Is a valid result corroborated?"),
)
RESULTS = ("pass", "warn", "stop", "skip", "reported", "pending")
SEVERITY = {"stop": 5, "warn": 4, "pass": 3, "reported": 2, "skip": 1, "pending": 0}
STRUCTURE_FORMATS = {".cif": "mmcif", ".mmcif": "mmcif", ".pdb": "pdb", ".sdf": "sdf"}
FAMILIES = {"cofolding": "co-folding", "docking": "docking"}
STAGE = re.compile(r"^L([0-5])$")
N_CHECKS = re.compile(r"(\d+) checks$")


def ui_task(task_id: str) -> str:
    return TASK_IDS.get(task_id, task_id)


def ui_outcome(outcome: str) -> str:
    return OUTCOMES.get(outcome, outcome)


def file_url(run_name: str, rel: str) -> str:
    return f"/runs/{run_name}/files/{rel}"


def _iso(ts: datetime | str) -> str:
    text = ts if isinstance(ts, str) else ts.isoformat()
    return text.replace("+00:00", "Z")


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value)


@lru_cache(maxsize=1)
def _executors() -> dict[str, dict[str, Any]]:
    from pah.config import load_yaml

    try:
        rows = load_yaml("executors.yaml").get("executors", [])
    except (OSError, ValueError):
        return {}
    out: dict[str, dict[str, Any]] = {
        str(r["id"]): r for r in rows if isinstance(r, dict) and "id" in r
    }
    return out


def executor_families() -> dict[str, str]:
    return {
        k: FAMILIES.get(str(v.get("family")), str(v.get("family"))) for k, v in _executors().items()
    }


def _task_spec(task_id: str) -> Any:
    from pah.core.task import load_task

    try:
        return load_task(task_id)
    except (OSError, ValueError):
        return None


@dataclass
class RunFiles:
    """Everything the adapter reads from one run directory, loaded once."""

    run_dir: Path
    record: RunRecord | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    provenance: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def load(cls, run_dir: Path) -> RunFiles:
        rf = cls(run_dir)
        rec = run_dir / "record.json"
        if rec.is_file():
            rf.record = RunRecord.model_validate_json(rec.read_text())
        rf.events = read_events(run_dir)
        prov = run_dir / "provenance.json"
        if prov.is_file():
            data = json.loads(prov.read_text())
            rf.provenance = [p for p in data if isinstance(p, dict)]
        elif rf.record is not None:
            rf.provenance = [p.model_dump(mode="json") for p in rf.record.provenance]
        return rf

    def first(self, kind: str) -> dict[str, Any] | None:
        return next((e for e in self.events if e.get("kind") == kind), None)

    @property
    def run_start(self) -> dict[str, Any]:
        data = (self.first("run_start") or {}).get("data")
        return data if isinstance(data, dict) else {}

    @property
    def finished(self) -> bool:
        return self.record is not None or self.first("run_end") is not None

    @property
    def run_id(self) -> str:
        if self.record:
            return self.record.run_id
        start = self.first("run_start")
        return str(start["run_id"]) if start else self.run_dir.name

    @property
    def task(self) -> str | None:
        if self.record:
            return self.record.task
        task = self.run_start.get("task")
        return str(task) if task else None

    @property
    def manifest(self) -> dict[str, Any]:
        if self.record:
            return self.record.manifest
        m = self.run_start.get("manifest")
        return m if isinstance(m, dict) else {}

    @property
    def selected_layers(self) -> tuple[int, ...]:
        if self.record:
            return self.record.layers
        return tuple(int(x) for x in self.run_start.get("layers", []))

    @property
    def findings(self) -> list[Finding]:
        if self.record:
            return list(self.record.findings)
        out = []
        for e in self.events:
            raw = e.get("data", {}).get("finding") if e.get("kind") == "finding" else None
            if isinstance(raw, dict):
                out.append(Finding.model_validate(raw))
        return out

    @property
    def verdict(self) -> dict[str, Any] | None:
        if self.record and self.record.verdict:
            return self.record.verdict.model_dump(mode="json")
        end = self.first("run_end")
        v = (end or {}).get("data", {}).get("verdict")
        return v if isinstance(v, dict) else None

    @property
    def created_at(self) -> str | None:
        if self.record:
            return _iso(self.record.started_at)
        start = self.first("run_start")
        return _iso(start["ts"]) if start else None

    def stage_times(self) -> dict[int, dict[str, Any]]:
        """Per layer: start and end timestamps and the check ids announced at stage start."""
        out: dict[int, dict[str, Any]] = {}
        for e in self.events:
            m = STAGE.match(str(e.get("stage", "")))
            if not m:
                continue
            slot = out.setdefault(int(m.group(1)), {})
            if e.get("kind") == "stage_start":
                slot["start"] = _ts(e["ts"])
                slot["checks"] = list(e.get("data", {}).get("checks", []))
                slot["count"] = _planned_count(e)
            elif e.get("kind") == "stage_end":
                slot["end"] = _ts(e["ts"])
        return out


def _planned_count(e: Mapping[str, Any]) -> int:
    """Number of checks announced at stage start (older streams carry it only in the message)."""
    ids = e.get("data", {}).get("checks")
    if isinstance(ids, list):
        return len(ids)
    m = N_CHECKS.search(str(e.get("message", "")))
    return int(m.group(1)) if m else 0


def read_events(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "events.jsonl"
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:  # a line being written; the next read picks it up
            continue
    return rows


# ---- checks -------------------------------------------------------------------------------


def _fmt_value(value: object, unit: str | None = None) -> str:
    text = f"{value:g}" if isinstance(value, float) else str(value)
    return f"{text}\u2009{unit}" if unit else text


def _gate_kind(check_id: str, escalate: Iterable[str]) -> str:
    if check_id in set(escalate):
        return GateKind.STOP.value
    cls = CHECKS.get(check_id)
    return (cls.gate_kind if cls else GateKind.STOP).value


def ui_check(f: Finding, escalate: Iterable[str] = ()) -> dict[str, Any]:
    cls = CHECKS.get(f.check_id)
    gate = _gate_kind(f.check_id, escalate)
    result = f.gate.value
    if gate == GateKind.REPORTED.value and f.gate in (Gate.PASS, Gate.WARN):
        result = "reported"
    row: dict[str, Any] = {
        "id": f.check_id,
        "name": cls.title if cls else f.check_id,
        "gate": gate,
        "result": result,
        "message": f.message,
    }
    if f.tool:
        row["tool"] = f.tool.name + (f" {f.tool.version}" if f.tool.version else "")
    values = ", ".join(f"{m.name}={_fmt_value(m.value, m.unit)}" for m in f.measurements[:3])
    row["evidence"] = f"{f.message} · {values}" if values else f.message
    if f.duration_s is not None:
        row["ms"] = round(f.duration_s * 1000)
    if f.thresholds:
        t = f.thresholds[0]
        row["threshold"] = {
            "value": f"{t.comparator} {_fmt_value(t.value)}",
            "origin": t.origin,
            "evidenceLevel": t.evidence_level.value,
        }
        row["thresholds"] = [
            {
                "name": t.name,
                "value": t.value,
                "comparator": t.comparator,
                "origin": t.origin,
                "evidenceLevel": t.evidence_level.value,
            }
            for t in f.thresholds
        ]
    if f.measurements:
        row["measurements"] = [
            {"name": m.name, "value": m.value, "unit": m.unit} for m in f.measurements
        ]
    reason = f.evidence.get("skip_reason")
    if f.gate is Gate.SKIP and reason:
        row["skipReason"] = str(reason)
    return row


def _pending(check_id: str, escalate: Iterable[str]) -> dict[str, Any]:
    cls = CHECKS.get(check_id)
    return {
        "id": check_id,
        "name": cls.title if cls else check_id,
        "gate": _gate_kind(check_id, escalate),
        "result": "pending",
    }


def worst(results: Iterable[str]) -> str | None:
    items = list(results)
    return max(items, key=lambda r: SEVERITY.get(r, 0)) if items else None


def _counts(checks: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    c = Counter(str(x["result"]) for x in checks)
    out = {r: c.get(r, 0) for r in ("pass", "warn", "stop", "skip")}
    out.update({r: c[r] for r in ("reported", "pending") if c.get(r)})
    return out


def _figures(findings: Sequence[Finding]) -> list[list[str]]:
    """Key figures for a layer: the measurements of checks that ran, first occurrence per name."""
    seen: dict[str, str] = {}
    for f in findings:
        if f.gate is Gate.SKIP:
            continue
        for m in f.measurements:
            label = m.name.replace("_", " ")
            if label not in seen and m.value is not None:
                seen[label] = _fmt_value(m.value, m.unit)
    return [[k, v] for k, v in list(seen.items())[:8]]


def _layers(
    rf: RunFiles, findings: Sequence[Finding], escalate: Sequence[str], task: Any
) -> list[dict[str, Any]]:
    times = rf.stage_times()
    selected = set(rf.selected_layers)
    out = []
    for i, (key, name, question) in enumerate(LAYERS):
        fs = [f for f in findings if int(f.layer) == i]
        checks = [ui_check(f, escalate) for f in fs]
        t = times.get(i, {})
        if i not in selected:
            status = "not_run"
        elif "end" in t or rf.record is not None:
            status = "done"
        elif "start" in t:
            status = "running"
        else:
            status = "pending"
        if status in ("running", "pending"):
            planned = t.get("checks") or (list(task.layers.get(i, ())) if task else [])
            have = {c["id"] for c in checks}
            checks += [_pending(c, escalate) for c in planned if c not in have]
        layer: dict[str, Any] = {
            "i": i,
            "key": key,
            "name": name,
            "question": question,
            "status": status,
            "counts": _counts(checks) if status != "not_run" else {},
            "checks": checks,
        }
        if "start" in t and "end" in t:
            layer["durationMs"] = round((t["end"] - t["start"]).total_seconds() * 1000)
        figures = _figures(fs)
        if figures:
            layer["figures"] = figures
        out.append(layer)
    return out


# ---- record -------------------------------------------------------------------------------


def _tools(manifest: Mapping[str, Any], tool_versions: Mapping[str, str]) -> list[dict[str, Any]]:
    entries: list[tuple[str, Any]] = []
    model = manifest.get("model")
    if isinstance(model, dict) and model.get("executor"):
        entries.append((str(model["executor"]), model.get("version")))
    for p in manifest.get("predictions") or []:
        if isinstance(p, dict) and p.get("executor"):
            entries.append((str(p["executor"]), p.get("version")))
    known = _executors()
    out: list[dict[str, Any]] = []
    for tid, version in entries:
        if any(t["id"] == tid for t in out):
            continue
        info = known.get(tid, {})
        row: dict[str, Any] = {"id": tid, "name": str(info.get("name", tid))}
        version = version or tool_versions.get(tid)
        if version:
            row["version"] = str(version)
        family = info.get("family")
        if family:
            row["family"] = FAMILIES.get(str(family), str(family))
        out.append(row)
    return out


def _inputs(manifest: Mapping[str, Any]) -> dict[str, Any]:
    proteins = [p for p in manifest.get("proteins") or [] if isinstance(p, dict)]
    ligands = [x for x in manifest.get("ligands") or [] if isinstance(x, dict)]
    out: dict[str, Any] = {}
    if proteins:
        first = proteins[0]
        target = first.get("uniprot") or first.get("pdb_id") or first.get("id")
        if target:
            out["target"] = target
    if len(proteins) > 1:
        second = proteins[1]
        out["partner"] = second.get("uniprot") or second.get("pdb_id") or second.get("id")
    if ligands:
        lig = ligands[0]
        out["ligand"] = lig.get("smiles") or lig.get("ccd") or lig.get("id")
    reference = manifest.get("reference") if isinstance(manifest.get("reference"), dict) else {}
    receptor = manifest.get("receptor") if isinstance(manifest.get("receptor"), dict) else {}
    ref = (reference or {}).get("pdb_id") or (receptor or {}).get("pdb_id")
    if ref:
        out["reference"] = ref
    if manifest.get("ph") is not None:
        out["ph"] = manifest["ph"]
    seeds = _seeds(manifest)
    if seeds:
        out["seeds"] = len(seeds)
    return out


def _seeds(manifest: Mapping[str, Any]) -> list[int]:
    seeds: list[int] = []
    model = manifest.get("model")
    if isinstance(model, dict):
        seeds += [int(s) for s in model.get("seeds") or []]
    for p in manifest.get("predictions") or []:
        if isinstance(p, dict):
            seeds += [int(s) for s in p.get("seeds") or [] if int(s) not in seeds]
    return seeds


def _sources(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for p in rows:
        extra = p.get("extra") or {}
        row: dict[str, Any] = {
            "source": p.get("source_id"),
            "accession": p.get("accession"),
            "release": p.get("release") or "n/a",
            "sha256": p.get("sha256"),
            "retrievedAt": _iso(str(p.get("retrieved_at", ""))),
        }
        if isinstance(extra, dict) and "cache" in extra:
            row["cached"] = extra["cache"] == "hit"
        if p.get("url"):
            row["url"] = p["url"]
        if p.get("size_bytes") is not None:
            row["sizeBytes"] = p["size_bytes"]
        out.append(row)
    return out


def _statement(outcome: str, scope: str, counts: Mapping[str, int], v: Mapping[str, Any]) -> str:
    label = {"supported": "Supported", "narrowed": "Narrowed", "refused": "Refused"}.get(
        outcome, "Incomplete"
    )
    parts = [
        f"{label} over {scope}: "
        + ", ".join(f"{counts.get(g, 0)} {g}" for g in ("pass", "warn", "stop", "skip"))
        + "."
    ]
    if v.get("stops"):
        parts.append(f"Stopped by {', '.join(v['stops'])}.")
    if v.get("warnings"):
        parts.append(f"Warnings from {', '.join(v['warnings'])}.")
    if v.get("incomplete"):
        parts.append(f"{len(v['incomplete'])} checks not verified.")
    return " ".join(parts)


def _verdict(rf: RunFiles, findings: Sequence[Finding], claim: str) -> dict[str, Any] | None:
    v = rf.verdict
    if v is None:
        return None
    outcome = ui_outcome(str(v.get("outcome")))
    counts = Counter(f.gate.value for f in findings)
    out: dict[str, Any] = {
        "claim": v.get("claim") or claim,
        "outcome": outcome,
        "statement": _statement(outcome, str(v.get("scope", "")), counts, v),
        "stops": list(v.get("stops", [])),
        "warnings": list(v.get("warnings", [])),
        "incomplete": list(v.get("incomplete", [])),
    }
    return out


def _controls(task: Any, findings: Sequence[Finding]) -> list[dict[str, Any]]:
    if task is None:
        return []
    by_id = {f.check_id: f for f in findings}
    status = {"pass": "sound", "warn": "incomplete", "stop": "incomplete"}
    out = []
    for name in task.controls:
        f = by_id.get(f"l5.controls.{name}")
        if f is None or f.gate is Gate.SKIP:
            row = {"name": name, "status": "missing"}
            if f is not None:
                row["note"] = f.message
        else:
            row = {"name": name, "status": status[f.gate.value], "note": f.message}
        out.append(row)
    return out


def _structures(rf: RunFiles, stats: Mapping[str, Any]) -> list[dict[str, Any]]:
    root = rf.run_dir / "artifacts"
    if not root.is_dir():
        return []
    labels: dict[str, tuple[str, ArtifactKind]] = {}
    for a in rf.record.artifacts if rf.record else []:
        labels[a.path] = (a.label, a.kind)
    ensemble = {str(e.get("id")): str(e.get("kind")) for e in stats.get("ensemble", [])}
    out = []
    for path in sorted(root.rglob("*")):
        fmt = STRUCTURE_FORMATS.get(path.suffix.lower())
        if fmt is None or not path.is_file():
            continue
        rel = str(path.relative_to(rf.run_dir))
        label, kind = labels.get(rel, (path.name, ArtifactKind.PREDICTION_STRUCTURE))
        ui_kind = "crystal" if kind is ArtifactKind.SOURCE_STRUCTURE else "model"
        ui_kind = ensemble.get(label, ui_kind)
        out.append(
            {
                "id": rel,
                "label": label or path.name,
                "kind": ui_kind,
                "url": file_url(rf.run_dir.name, rel),
                "format": fmt,
            }
        )
    return out


def _renders(rf: RunFiles) -> list[dict[str, Any]]:
    root = rf.run_dir / "renders"
    if not root.is_dir():
        return []
    out = []
    for pse in sorted(root.glob("*.pse")):
        stem = pse.stem
        for png in sorted(root.glob(f"{stem}_*.png")):
            out.append(
                {
                    "structure": stem,
                    "png": file_url(rf.run_dir.name, f"renders/{png.name}"),
                    "pse": file_url(rf.run_dir.name, f"renders/{pse.name}"),
                    "view": png.stem[len(stem) + 1 :],
                }
            )
    return out


def _outputs(rf: RunFiles, manifest: Mapping[str, Any]) -> list[str]:
    out = [
        a.path
        for a in (rf.record.artifacts if rf.record else [])
        if a.kind is ArtifactKind.PREDICTION_STRUCTURE
    ]
    for p in manifest.get("predictions") or []:
        if isinstance(p, dict) and p.get("path") and str(p["path"]) not in out:
            out.append(str(p["path"]))
    return out


def ui_record(run_dir: Path) -> dict[str, Any]:
    """`UiRunRecord` for one run directory (docs/UI.md, "Harness record to UI record")."""
    import pah.checks  # noqa: F401 - check titles and gate kinds

    rf = RunFiles.load(run_dir)
    task_id = rf.task or ""
    task = _task_spec(task_id) if task_id else None
    escalate = tuple(task.escalate) if task else ()
    findings = rf.findings
    manifest = rf.manifest
    claim = (
        rf.record.claim
        if rf.record
        else str(rf.run_start.get("claim") or (task.claim if task else ""))
    )
    tool_versions = rf.record.tool_versions if rf.record else {}
    stats = build_stats(findings, executor_families())
    out: dict[str, Any] = {
        "id": rf.run_id,
        "task": ui_task(task_id),
        "taskName": task.title if task else task_id,
        "claim": claim,
        "tools": _tools(manifest, tool_versions),
        "inputs": _inputs(manifest),
        "sources": _sources(rf.provenance),
        "layers": _layers(rf, findings, escalate, task),
        "stats": stats,
        "narrative": [],
        "controls": _controls(task, findings),
        "outputs": _outputs(rf, manifest),
        "record": {},
        "structures": _structures(rf, stats),
        "renders": _renders(rf),
        "source": "pah",
    }
    if rf.created_at:
        out["createdAt"] = rf.created_at
    verdict = _verdict(rf, findings, claim)
    if verdict:
        out["verdict"] = verdict
    record: dict[str, Any] = {}
    if rf.record:
        record["pahVersion"] = rf.record.pah_version
        if rf.record.tool_versions:
            record["toolVersions"] = dict(rf.record.tool_versions)
    seeds = _seeds(manifest)
    if seeds:
        record["seeds"] = seeds
    out["record"] = record
    return out


# ---- jobs and log lines -------------------------------------------------------------------


def ui_job(run_dir: Path) -> dict[str, Any]:
    """`Job` for one run directory: status, current layer, progress and worst result per layer."""
    import pah.checks  # noqa: F401

    rf = RunFiles.load(run_dir)
    task_id = rf.task or ""
    task = _task_spec(task_id) if task_id else None
    findings = rf.findings
    times = rf.stage_times()
    selected = rf.selected_layers
    done = rf.finished
    if done:
        status, layer_idx, progress = "done", 6, 1.0
    elif not rf.events:
        status, layer_idx, progress = "queued", 0, 0.0
    else:
        status = "running"
        running = [i for i, t in times.items() if "start" in t and "end" not in t]
        finished = [i for i, t in times.items() if "end" in t]
        layer_idx = running[0] if running else (max(finished) + 1 if finished else 0)
        planned = int(times.get(layer_idx, {}).get("count", 0))
        seen = sum(1 for f in findings if int(f.layer) == layer_idx)
        progress = round(min(1.0, seen / planned), 3) if planned else 0.0
    layers = []
    for i in range(6):
        results = [f.gate.value for f in findings if int(f.layer) == i]
        layer_done = "end" in times.get(i, {}) or (done and i in selected)
        layers.append({"i": i, "result": worst(results), "done": layer_done})
    manifest = rf.manifest
    events = rf.events
    elapsed = 0
    if len(events) >= 2:
        elapsed = round((_ts(events[-1]["ts"]) - _ts(events[0]["ts"])).total_seconds() * 1000)
    elif rf.record and rf.record.finished_at:
        elapsed = round((rf.record.finished_at - rf.record.started_at).total_seconds() * 1000)
    verdict = rf.verdict
    return {
        "id": run_dir.name,
        "runId": rf.run_id,
        "name": _job_name(manifest, run_dir.name),
        "task": ui_task(task_id),
        "taskName": task.title if task else task_id,
        "tools": [t["name"] for t in _tools(manifest, {})],
        "seeds": len(_seeds(manifest)),
        "status": status,
        "layerIdx": layer_idx,
        "progress": progress,
        "elapsedMs": elapsed,
        "createdAt": rf.created_at or "",
        "layers": layers,
        "verdict": ui_outcome(str(verdict["outcome"])) if verdict else None,
    }


def _job_name(manifest: Mapping[str, Any], fallback: str) -> str:
    parts = []
    for key in ("proteins", "ligands"):
        items = manifest.get(key) or []
        if items and isinstance(items[0], dict) and items[0].get("id"):
            parts.append(str(items[0]["id"]))
    return " · ".join(parts) or fallback


def _layer_of(stage: str) -> int | None:
    m = STAGE.match(stage)
    return int(m.group(1)) if m else None


def _plain(e: Mapping[str, Any], kind: str, layer: int | None) -> str:
    data = e.get("data", {})
    msg = str(e.get("message", "")).rstrip(".")
    name = LAYERS[layer][1] if layer is not None else ""
    ek = e.get("kind")
    if ek == "run_start":
        return f"Run started for task {data.get('task', '')}."
    if ek == "run_end":
        v = data.get("verdict") or {}
        outcome = ui_outcome(str(v.get("outcome", ""))) if isinstance(v, dict) else ""
        return f"Run finished with verdict {outcome}." if outcome else "Run finished."
    if ek == "stage_start" and layer is not None:
        n = _planned_count(e)
        return f"Layer {layer} ({name}) started with {n} checks."
    if ek == "stage_end" and layer is not None:
        counts = data.get("counts") or {}
        text = ", ".join(f"{counts.get(g, 0)} {g}" for g in ("pass", "warn", "stop", "skip"))
        return f"Layer {layer} ({name}) finished: {text}."
    if ek == "finding":
        f = data.get("finding") or {}
        cid = str(f.get("check_id", ""))
        cls = CHECKS.get(cid)
        title = cls.title if cls else cid
        gate = str(data.get("gate", ""))
        return f"{title}: {gate}, {str(f.get('message', '')).rstrip('.')}."
    if ek == "artifact":
        path = str(data.get("path") or msg)
        return f"Wrote {Path(path).name}."
    return f"{msg[:1].upper()}{msg[1:]}." if msg else ""


def _kind(e: Mapping[str, Any], layer: int | None) -> str:
    ek = str(e.get("kind", ""))
    data = e.get("data", {})
    if ek in ("run_start", "run_end"):
        return "run"
    if ek in ("stage_start", "stage_end"):
        return "layer" if layer is not None else "run"
    if ek == "finding":
        return "check"
    if ek == "artifact":
        return "artifact"
    if ek == "log" and layer == 0:
        cache = str(data.get("cache", "")).lower()
        return "cache" if cache == "hit" or "cache hit" in str(e.get("message", "")) else "fetch"
    if ek == "log" and str(e.get("stage", "")).startswith("exec"):
        return "exec"
    return "log"


def log_line(e: Mapping[str, Any], start: datetime | None) -> dict[str, Any]:
    stage = str(e.get("stage", ""))
    layer = _layer_of(stage)
    kind = _kind(e, layer)
    ts = _ts(str(e["ts"]))
    t = (ts - start).total_seconds() if start else 0.0
    row: dict[str, Any] = {
        "seq": e.get("seq"),
        "ts": _iso(str(e["ts"])),
        "t": f"{t:.1f}s",
        "layer": layer,
        "kind": kind,
        "text": f"{e.get('kind', '')} {stage} {e.get('message', '')}".strip(),
        "plain": _plain(e, kind, layer),
    }
    data = e.get("data", {})
    result = data.get("gate") if e.get("kind") == "finding" else None
    if result in RESULTS:
        row["result"] = result
    return row


def log_lines(run_dir: Path) -> list[dict[str, Any]]:
    """`LogLine` per event in `events.jsonl`, in sequence order."""
    import pah.checks  # noqa: F401

    events = read_events(run_dir)
    start = _ts(events[0]["ts"]) if events else None
    return [log_line(e, start) for e in events]
