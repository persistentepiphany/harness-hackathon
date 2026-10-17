"""`GET /ui/glossary`: what each score and check measurement the UI shows, and its source.

Entries are read from configuration and the check registry only: executor outputs from
`configs/executors.yaml` (`outputs`: label, unit, kind, note), output checks (layers 4-5) from
the registry (title, modules) with their thresholds from `configs/thresholds.yaml`, and the per-pose
fields of the physics table (`pah.webui.stats.PHYSICS_FIELDS`). Where a source says nothing, the
entry says so instead of describing the score.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from pah.config import config_dir, load_yaml
from pah.webui import stats as ui_stats
from pah.webui.adapter import checks_registry, executor_rows, tool_outputs

log = logging.getLogger(__name__)

NO_NOTE = "configs/executors.yaml gives no note for this output"
_LOWER = {"<", "<="}
_HIGHER = {">", ">="}


def _thresholds() -> dict[str, Any]:
    try:
        raw = load_yaml("thresholds.yaml", Path(config_dir()))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        log.info("thresholds.yaml not readable: %s", exc)
        return {}
    checks = raw.get("checks") if isinstance(raw, dict) else None
    return checks if isinstance(checks, dict) else {}


def executor_scores() -> list[dict[str, Any]]:
    """One entry per output key, with every executor that reports it."""
    by_key: dict[str, dict[str, Any]] = {}
    for row in executor_rows():
        eid, name = str(row["id"]), str(row.get("name") or row["id"])
        for o in tool_outputs(row):
            key = str(o["key"])
            entry = by_key.get(key)
            note = o.get("note")
            if entry is None:
                entry = by_key[key] = {
                    "key": key,
                    "label": o.get("label") or key,
                    "unit": o.get("unit"),
                    "kind": o.get("kind"),
                    "scope": o.get("scope"),
                    "producedBy": [],
                    "what": str(note) if note else NO_NOTE,
                    "inputs": [],
                    "higherIsBetter": o.get("higherIsBetter"),
                    "source": "configs/executors.yaml",
                    "notes": {},
                }
                if o.get("rankingOnly"):
                    entry["rankingOnly"] = True
            entry["producedBy"].append(eid)
            entry["inputs"].append(f"{name} prediction output, parsed by the {eid} adapter")
            if note:
                entry["notes"][eid] = str(note)
    for entry in by_key.values():
        notes = set(entry["notes"].values())
        if len(notes) == 1:
            entry["what"] = notes.pop()
        elif notes:
            entry["what"] = f"{entry['label']}; the executor notes differ (see notes)"
        else:
            entry["what"] = NO_NOTE
    return list(by_key.values())


def _direction(rows: dict[str, Any]) -> bool | None:
    """Higher passes (True) or lower passes (False) when every threshold agrees."""
    seen = {str(r.get("comparator")) for r in rows.values() if isinstance(r, dict)}
    if seen and seen <= _LOWER:
        return False
    if seen and seen <= _HIGHER:
        return True
    return None


def check_scores() -> list[dict[str, Any]]:
    """Output checks (layers 4-5) with the thresholds they compare."""
    thresholds = _thresholds()
    out: list[dict[str, Any]] = []
    for cid, cls in sorted(checks_registry().items()):
        if not cid.startswith(("l4.", "l5.")):
            continue
        modules = [str(m) for m in getattr(cls, "requires_modules", ())]
        raw = thresholds.get(cid)
        rows: dict[str, Any] = raw if isinstance(raw, dict) else {}
        title = str(getattr(cls, "title", cid))
        doc = " ".join(str(cls.__doc__ or "").split())
        out.append(
            {
                "key": cid,
                "label": title,
                "unit": None,
                "kind": "check",
                "producedBy": [cid],
                "what": doc or f"{title} (check title; the check gives no description)",
                "inputs": [f"computed with {', '.join(modules)}"]
                if modules
                else ["computed by the harness; the check declares no external module"],
                "higherIsBetter": _direction(rows),
                "source": "check registry, configs/thresholds.yaml",
                "measurements": sorted(rows),
                "thresholds": [
                    {
                        "name": name,
                        "comparator": r.get("comparator"),
                        "value": r.get("value"),
                        "origin": r.get("origin"),
                        "evidence": r.get("evidence"),
                    }
                    for name, r in rows.items()
                    if isinstance(r, dict)
                ],
            }
        )
    return out


def physics_fields() -> list[dict[str, Any]]:
    """Per-pose fields of the physics table and the check evidence they are read from."""
    registry = checks_registry()
    out: list[dict[str, Any]] = []
    for cid, src, dst in ui_stats.PHYSICS_FIELDS:
        cls = registry.get(cid)
        title = str(getattr(cls, "title", cid)) if cls is not None else cid
        out.append(
            {
                "key": f"physics.{dst}",
                "label": dst,
                "unit": ui_stats.unit_of(src),
                "kind": "measurement",
                "producedBy": [cid],
                "what": f"evidence.poses[].{src} of {cid} ({title})",
                "inputs": [f"the pose as checked by {cid}"],
                "higherIsBetter": None,
                "source": "pah.webui.stats.PHYSICS_FIELDS",
            }
        )
    return out


def build_glossary() -> dict[str, Any]:
    return {"scores": executor_scores() + check_scores() + physics_fields()}
