"""Scope of a run's verdict, derived from the run record (docs/UI.md, "Assessment scope").

The engine's verdict covers the layers it ran. A run without predictions (a pre-run check) runs
layers 4 and 5 as skips, and the engine then reports `pass`; the UI must not show that as a
supported claim. Everything here reads findings, the manifest, the task spec and the event
stream, so old records on the volume read the same way. No scientific value is computed.

- `assessment`: `pre-run` when the run holds no executor outputs, else `full`.
- `evaluated`: layers with at least one non-skip result.
- `pending`: output checks (layers 4-5) waiting for predictions.
- `outcome`: `not_assessed` when the task's claim needs output evidence and none was produced,
  unless a stop already happened (a pre-run refusal is real).
- `dimensions`: checks grouped by what they test (configs/catalog.yaml `dimensions`).
- `tool_versions`: declared tools and whether a non-skip finding used them.
- `execution`: execution events (`data.stage == "execute"`) aggregated per executor.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

OUTPUT_LAYERS = (4, 5)
PENDING_INPUT = "pending_input"
NOT_ASSESSED = "not_assessed"
PRE_RUN = "pre-run"
FULL = "full"
ASSESSED_PRE_RUN = "Inputs fit to run"
# Evidence of a layer 4-5 skip that waits for predictions (l4/l5 checks: "no predictions
# declared (pre-run assessment)").
_NO_PREDICTIONS = re.compile(r"no predictions|pre-run|no prediction structures?", re.I)
_ACTIVE_PHASES = frozenset({"queued", "building", "running", "done"})
_RESULT_RANK = {"na": 0, "pass": 1, "pending": 2, "warn": 3, "stop": 4}
_CERTAINTY_RANK = {"none": 3, "calibrated": 2, "published": 1, "uncalibrated": 0}
EXECUTE_STAGE = "execute"
_PHASE_RESULT = {"done": "pass", "failed": "stop", "skipped": "skip"}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list | tuple) else []


# ---------------------------------------------------------------- pending input


def is_pending_input(finding: Mapping[str, Any]) -> bool:
    """A layer 4-5 skip whose message says there are no predictions to check."""
    layer = finding.get("layer")
    if layer not in OUTPUT_LAYERS or finding.get("gate") != "skip":
        return False
    reason = str(_dict(finding.get("evidence")).get("skip_reason") or "")
    if reason == PENDING_INPUT:
        return True
    return bool(_NO_PREDICTIONS.search(str(finding.get("message", ""))))


def skip_reason(finding: Mapping[str, Any]) -> str | None:
    """The UI skip reason: `pending_input` for an output check waiting for predictions."""
    if finding.get("gate") != "skip":
        return None
    if is_pending_input(finding):
        return PENDING_INPUT
    reason = _dict(finding.get("evidence")).get("skip_reason")
    return str(reason) if reason else None


# ---------------------------------------------------------------- executor outputs


def execution_events(events: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Events written for executor progress (contract "Execution events")."""
    out: list[Mapping[str, Any]] = []
    for e in events:
        data = _dict(e.get("data"))
        stage = data.get("stage") or e.get("stage")
        if stage == EXECUTE_STAGE and data.get("executor"):
            out.append(e)
    return out


def has_outputs(
    manifest: Mapping[str, Any],
    artifacts: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    harness_executed: Iterable[str] = (),
) -> bool:
    """Whether the run holds (or is producing) executor outputs."""
    if _dicts(manifest.get("predictions")):
        return True
    if any(str(a.get("kind")) == "prediction_structure" for a in artifacts):
        return True
    if any(True for _ in harness_executed):
        return True
    for e in execution_events(events):
        if str(_dict(e.get("data")).get("phase")) in _ACTIVE_PHASES:
            return True
    return False


# ---------------------------------------------------------------- scope and outcome


def layer_span(layers: Iterable[int]) -> str:
    """`0-3`, `1`, `0-1,3`."""
    xs = sorted(set(layers))
    parts: list[str] = []
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[j + 1] == xs[j] + 1:
            j += 1
        parts.append(str(xs[i]) if i == j else f"{xs[i]}-{xs[j]}")
        i = j + 1
    return ",".join(parts)


def layers_phrase(layers: Iterable[int]) -> str:
    xs = sorted(set(layers))
    if not xs:
        return "no layer"
    return f"layer {xs[0]}" if len(xs) == 1 else f"layers {layer_span(xs)}"


@dataclass(frozen=True)
class Scope:
    assessment: str
    evaluated: tuple[int, ...]
    pending: tuple[str, ...]
    output_checks: tuple[str, ...]
    output_assessed: bool
    layer_of: Mapping[str, int]

    @property
    def pre_run(self) -> bool:
        return self.assessment == PRE_RUN

    @property
    def needs_outputs(self) -> bool:
        """The task lists output checks and none of them gave a non-skip result."""
        return bool(self.output_checks) and not self.output_assessed

    @property
    def pending_layers(self) -> tuple[int, ...]:
        evaluated = set(self.evaluated)
        layers = {self.layer_of[c] for c in self.output_checks if c in self.layer_of}
        return tuple(sorted(i for i in layers if i not in evaluated))

    def outcome(self, base: str | None, stops: Sequence[str]) -> str | None:
        """UI outcome. None while the run has no verdict."""
        if base is None:
            return None
        if self.needs_outputs:
            return "refused" if base == "refused" or stops else NOT_ASSESSED
        return base

    def assessed_claim(self, outcome: str | None) -> str | None:
        return ASSESSED_PRE_RUN if self.pre_run or outcome == NOT_ASSESSED else None


def scope(
    findings: Sequence[Mapping[str, Any]],
    task_layers: Mapping[int, Sequence[str]] | None,
    outputs: bool,
) -> Scope:
    """Scope of the verdict from the findings and the task's layer lists."""
    layer_of: dict[str, int] = {}
    for i, ids in (task_layers or {}).items():
        for cid in ids:
            layer_of.setdefault(str(cid), int(i))
    for f in findings:
        if isinstance(f.get("layer"), int):
            layer_of[str(f.get("check_id"))] = int(f["layer"])
    evaluated = tuple(
        sorted(
            {
                int(f["layer"])
                for f in findings
                if f.get("gate") != "skip" and isinstance(f.get("layer"), int)
            }
        )
    )
    if task_layers:
        output_checks = [str(c) for i in OUTPUT_LAYERS for c in task_layers.get(i, ())]
    else:
        output_checks = [
            str(f.get("check_id")) for f in findings if f.get("layer") in OUTPUT_LAYERS
        ]
    output_findings = [f for f in findings if f.get("layer") in OUTPUT_LAYERS]
    assessed = any(f.get("gate") != "skip" for f in output_findings)
    reported = {str(f.get("check_id")) for f in findings}
    pending = [str(f.get("check_id")) for f in output_findings if is_pending_input(f)]
    pending += [c for c in output_checks if c not in reported and c not in pending]
    return Scope(
        assessment=FULL if outputs else PRE_RUN,
        evaluated=evaluated,
        pending=tuple(dict.fromkeys(pending)),
        output_checks=tuple(dict.fromkeys(output_checks)),
        output_assessed=assessed,
        layer_of=layer_of,
    )


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _ids(ids: Sequence[str], limit: int = 4) -> str:
    head = ", ".join(ids[:limit])
    return head + (f" and {len(ids) - limit} more" if len(ids) > limit else "")


def scoped_statement(
    sc: Scope,
    outcome: str,
    claim: str,
    stops: Sequence[str],
    warnings: Sequence[str],
    incomplete: Sequence[str],
) -> str:
    """Verdict sentence of a run whose output layers gave no result. Facts only."""
    head = "Pre-run check: " if sc.pre_run else ""
    parts = [f"{head}{layers_phrase(sc.evaluated)} evaluated"]
    pending = sc.pending_layers
    if pending:
        why = "pending predictions" if sc.pre_run else "gave no result"
        parts.append(f"{layers_phrase(pending)} {why}")
    text = "; ".join(parts) + "."

    def at(ids: Sequence[str]) -> str:
        return layers_phrase(sc.layer_of[c] for c in ids if c in sc.layer_of)

    if stops:
        text += f" {_plural(len(stops), 'check')} stopped in {at(stops)}: {_ids(stops)}."
    if warnings:
        text += f" {_plural(len(warnings), 'check')} warned in {at(warnings)}: {_ids(warnings)}."
    if incomplete:
        text += f" {_plural(len(incomplete), 'check')} could not be evaluated: {_ids(incomplete)}."
    if outcome == "refused":
        text += f" The claim “{claim}” is not supported."
    elif sc.pre_run:
        text += f" The claim “{claim}” is not assessed until predictions are checked."
    else:
        text += f" The claim “{claim}” is not assessed: no output check gave a result."
    return text


# ---------------------------------------------------------------- dimensions


@dataclass(frozen=True)
class DimensionDef:
    id: str
    label: str
    layers: tuple[int, ...] = ()
    prefixes: tuple[str, ...] = ()


def dimension_defs(rows: Sequence[Mapping[str, Any]]) -> list[DimensionDef]:
    out: list[DimensionDef] = []
    for r in rows:
        if not r.get("id"):
            continue
        out.append(
            DimensionDef(
                id=str(r["id"]),
                label=str(r.get("label") or r["id"]),
                layers=tuple(int(x) for x in r.get("layers") or () if isinstance(x, int)),
                prefixes=tuple(str(x) for x in r.get("prefixes") or ()),
            )
        )
    return out


def dimension_of(check_id: str, layer: int | None, defs: Sequence[DimensionDef]) -> str | None:
    """Longest matching check id prefix, else the first dimension that lists the layer."""
    best: tuple[int, str] | None = None
    for d in defs:
        for p in d.prefixes:
            if check_id.startswith(p) and (best is None or len(p) > best[0]):
                best = (len(p), d.id)
    if best is not None:
        return best[1]
    return next((d.id for d in defs if layer is not None and layer in d.layers), None)


def certainty_of(levels: Iterable[str], table: Mapping[str, Sequence[str]]) -> str:
    """Weakest certainty among threshold evidence levels; `none` without thresholds."""
    lookup = {str(level): str(c) for c, ls in table.items() for level in ls}
    found = [lookup.get(str(level), "uncalibrated") for level in levels]
    if not found:
        return "none"
    return min(found, key=lambda c: _CERTAINTY_RANK.get(c, 0))


def dimensions(
    checks: Sequence[tuple[int, Mapping[str, Any]]],
    defs: Sequence[DimensionDef],
    certainty_table: Mapping[str, Sequence[str]],
) -> list[dict[str, Any]]:
    """UiDimension rows from (layer, UiCheck) pairs. A pending check is a `pending` result or
    a skip with skipReason `pending_input`."""
    groups: dict[str, list[Mapping[str, Any]]] = {d.id: [] for d in defs}
    for layer, c in checks:
        did = dimension_of(str(c.get("id")), layer, defs)
        if did is not None:
            groups[did].append(c)
    out: list[dict[str, Any]] = []
    for d in defs:
        rows = groups[d.id]
        passed = sum(1 for c in rows if c.get("result") in {"pass", "reported"})
        warned = sum(1 for c in rows if c.get("result") == "warn")
        stopped = sum(1 for c in rows if c.get("result") == "stop")
        pending = sum(
            1 for c in rows if c.get("result") == "pending" or c.get("skipReason") == PENDING_INPUT
        )
        if stopped:
            result = "stop"
        elif warned:
            result = "warn"
        elif pending:
            result = "pending"
        elif passed:
            result = "pass"
        else:
            result = "na"
        levels = [
            str(t.get("evidenceLevel") or "")
            for c in rows
            if c.get("result") not in {"skip", "pending"}
            for t in c.get("thresholds") or ()
            if isinstance(t, dict)
        ]
        out.append(
            {
                "id": d.id,
                "label": d.label,
                "result": result,
                "checks": len(rows),
                "passed": passed,
                "warned": warned,
                "stopped": stopped,
                "pending": pending,
                "certainty": certainty_of(levels, certainty_table),
                "checkIds": [str(c.get("id")) for c in rows],
            }
        )
    return out


# ---------------------------------------------------------------- tool versions


def _names(tool: str, text: str) -> bool:
    return bool(re.search(rf"(?<![A-Za-z0-9_]){re.escape(tool)}(?![A-Za-z0-9_])", text, re.I))


def tool_versions(
    findings: Sequence[Mapping[str, Any]],
    declared: Mapping[str, Any],
    executors: Sequence[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Declared tool versions (record `tool_versions`, finding tools, executors) and whether a
    non-skip finding names the tool. An executor counts as exercised when its outputs ran."""
    rows: dict[str, dict[str, Any]] = {}
    for key, version in declared.items():
        rows[str(key)] = {"name": str(key), "version": str(version) if version else None}
    for f in findings:
        tool = _dict(f.get("tool"))
        tname = tool.get("name")
        if isinstance(tname, str) and tname and tname not in rows and len(tname) <= 40:
            tversion = tool.get("version")
            rows[tname] = {"name": tname, "version": str(tversion) if tversion else None}
    active = [f for f in findings if f.get("gate") != "skip"]
    out: list[dict[str, Any]] = []
    for name, row in rows.items():
        checks = [
            str(f.get("check_id"))
            for f in active
            if _names(name, str(_dict(f.get("tool")).get("name") or ""))
        ]
        out.append({**row, "exercised": bool(checks), "checks": checks, "kind": "library"})
    for t in executors:
        out.append(
            {
                "name": str(t.get("name") or t.get("id")),
                "version": t.get("version"),
                "exercised": bool(t.get("ran")),
                "checks": [],
                "kind": "executor",
                "id": t.get("id"),
            }
        )
    return out


# ---------------------------------------------------------------- execution


def _ts(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def execution(
    events: Sequence[Mapping[str, Any]], names: Mapping[str, str]
) -> list[dict[str, Any]]:
    """UiExecution per executor, in the order executors first appear."""
    out: dict[str, dict[str, Any]] = {}
    first_ts: dict[str, datetime] = {}
    for e in execution_events(events):
        data = _dict(e.get("data"))
        eid = str(data["executor"])
        row = out.setdefault(
            eid,
            {
                "executor": eid,
                "name": names.get(eid, eid),
                "phase": "queued",
                "gpu": None,
                "route": None,
                "routeNote": None,
                "startedAt": e.get("ts"),
                "elapsedMs": None,
                "seeds": [],
                "message": None,
            },
        )
        ts = _ts(e.get("ts"))
        if ts is not None and eid not in first_ts:
            first_ts[eid] = ts
        phase = str(data.get("phase") or "")
        seed = data.get("seed")
        elapsed = data.get("elapsedMs")
        elapsed_ms = int(elapsed) if isinstance(elapsed, int | float) else None
        if isinstance(seed, int) and not isinstance(seed, bool):
            seeds: list[dict[str, Any]] = row["seeds"]
            entry = next((s for s in seeds if s["seed"] == seed), None)
            if entry is None:
                entry = {"seed": seed, "phase": phase or "queued", "ms": None}
                seeds.append(entry)
            if phase:
                entry["phase"] = phase
            if elapsed_ms is not None:
                entry["ms"] = elapsed_ms
            if phase == "running" and row["phase"] in {"queued", "building"}:
                row["phase"] = "running"
        else:
            if phase:
                row["phase"] = phase
            if elapsed_ms is not None:
                row["elapsedMs"] = elapsed_ms
        for key in ("gpu", "route", "routeNote"):
            if data.get(key) is not None:
                row[key] = data[key]
        if data.get("message") or e.get("message"):
            row["message"] = str(data.get("message") or e.get("message"))
        if row["elapsedMs"] is None and ts is not None and phase in {"done", "failed"}:
            start = first_ts.get(eid)
            if start is not None:
                row["_end"] = round((ts - start).total_seconds() * 1000)
    rows = list(out.values())
    for row in rows:
        end = row.pop("_end", None)
        if row["elapsedMs"] is None and end is not None:
            row["elapsedMs"] = end
    return rows


def execution_line(event: Mapping[str, Any]) -> dict[str, Any] | None:
    """LogLine fields (kind, text, plain, result) of an execution event, else None."""
    data = _dict(event.get("data"))
    if (data.get("stage") or event.get("stage")) != EXECUTE_STAGE or not data.get("executor"):
        return None
    eid = str(data["executor"])
    phase = str(data.get("phase") or "")
    seed = data.get("seed")
    bits = [eid, phase]
    if isinstance(seed, int) and not isinstance(seed, bool):
        bits.append(f"seed {seed}")
    for key in ("gpu", "route"):
        if data.get(key):
            bits.append(str(data[key]))
    elapsed = data.get("elapsedMs")
    if isinstance(elapsed, int | float):
        bits.append(f"{elapsed / 1000:.1f} s" if elapsed >= 1000 else f"{round(elapsed)} ms")
    message = str(data.get("message") or event.get("message") or "").strip()
    plain = message or f"{eid} {phase}"
    if not plain.endswith((".", "!", "?")):
        plain += "."
    line: dict[str, Any] = {
        "kind": "exec",
        "text": "exec  " + "  ".join(bits) + (f"  {message}" if message else ""),
        "plain": plain,
        "executor": eid,
        "phase": phase,
    }
    if phase in _PHASE_RESULT:
        line["result"] = _PHASE_RESULT[phase]
    return line
