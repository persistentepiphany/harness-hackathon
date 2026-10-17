"""JSON Schemas for the data contracts a frontend or agent consumes."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from pah.batch import BatchSpec
from pah.core.engine import RunRecord
from pah.core.manifest import Manifest
from pah.core.models import Event, Finding
from pah.report.model import BatchReport, RunReport

MODELS: dict[str, type[BaseModel]] = {
    "manifest": Manifest,
    "batch_spec": BatchSpec,
    "event": Event,
    "finding": Finding,
    "run_record": RunRecord,
    "run_report": RunReport,
    "batch_report": BatchReport,
}


def schema(name: str) -> dict[str, object]:
    model = MODELS[name]
    data = model.model_json_schema(mode="serialization")
    data["$id"] = f"https://github.com/persistentepiphany/harness-hackathon/schemas/{name}.json"
    return data


def write_schemas(out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in MODELS:
        path = out / f"{name}.json"
        path.write_text(json.dumps(schema(name), indent=2, sort_keys=True) + "\n")
        paths.append(path)
    return paths
