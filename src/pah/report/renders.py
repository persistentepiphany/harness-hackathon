"""Structure renders. Every prediction structure must have renders before a report is written."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from pah.core.engine import RunRecord
from pah.core.models import Artifact, ArtifactKind
from pah.report.model import FigureEntry

RENDERED_KINDS = (
    ArtifactKind.PREDICTION_STRUCTURE,
    ArtifactKind.SOURCE_STRUCTURE,
    ArtifactKind.INPUT_STRUCTURE,
)


class ReportError(Exception):
    """A report cannot be produced without violating a mandatory rule."""


@dataclass(frozen=True)
class RenderResult:
    structure: Artifact
    pngs: dict[str, Path] = field(default_factory=dict)
    session: Path | None = None
    organic: tuple[str, ...] = ()
    chains: tuple[str, ...] = ()
    error: str | None = None


class Renderer(Protocol):
    def render(self, structure: Path, ligands: list[Path], out_stem: Path) -> dict[str, object]: ...


class PymolRenderer:
    """Runs `pah.report.pymol_worker` in a subprocess so a PyMOL failure cannot end the run."""

    def __init__(self, timeout_s: float = 180.0, python: str = sys.executable) -> None:
        self.timeout_s = timeout_s
        self.python = python

    def render(self, structure: Path, ligands: list[Path], out_stem: Path) -> dict[str, object]:
        req = {
            "structure": str(structure),
            "ligands": [str(p) for p in ligands],
            "out_stem": str(out_stem),
        }
        proc = subprocess.run(
            [self.python, "-m", "pah.report.pymol_worker", json.dumps(req)],
            capture_output=True,
            text=True,
            timeout=self.timeout_s,
            check=False,
        )
        if proc.returncode != 0:
            tail = " ".join(proc.stderr.strip().splitlines()[-2:])[:300]
            raise RuntimeError(f"pymol worker exit {proc.returncode}: {tail}")
        result: dict[str, object] = json.loads(proc.stdout.strip().splitlines()[-1])
        return result


def _resolve(run_dir: Path, artifact: Artifact) -> Path:
    p = Path(artifact.path)
    return p if p.is_absolute() else run_dir / p


def render_stem(a: Artifact) -> str:
    """File stem for an artifact's renders. Predictions take their prediction set and pose id
    (several executors write every pose as `complex.pdb`, and a redocking control repeats the
    primary set's pose ids); other structures keep their file stem."""
    if a.kind is not ArtifactKind.PREDICTION_STRUCTURE:
        return Path(a.path).stem
    parts = Path(a.path).with_suffix("").parts
    if a.label:
        in_set = len(parts) > 2 and parts[0] == "predictions"
        name = f"{parts[1]}_{a.label}" if in_set else a.label
    else:
        name = "_".join(parts)
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_")


def render_structures(
    record: RunRecord,
    run_dir: Path,
    renderer: Renderer | None = None,
    on_result: Callable[[RenderResult], None] | None = None,
) -> list[RenderResult]:
    """Renders every structure artifact. `on_result` is called after each structure, so the
    files can be announced while later structures are still rendering."""
    renderer = renderer or PymolRenderer()
    out_dir = run_dir / "renders"
    out_dir.mkdir(parents=True, exist_ok=True)
    ligands = [
        _resolve(run_dir, a) for a in record.artifacts if a.kind is ArtifactKind.INPUT_LIGAND
    ]
    results = []
    for a in record.artifacts:
        if a.kind not in RENDERED_KINDS:
            continue
        overlay = ligands if a.kind is ArtifactKind.PREDICTION_STRUCTURE else []
        stem = out_dir / render_stem(a)
        try:
            raw = renderer.render(_resolve(run_dir, a), overlay, stem)
            pngs = raw.get("pngs", {})
            assert isinstance(pngs, dict)
            results.append(
                RenderResult(
                    structure=a,
                    pngs={k: Path(str(v)) for k, v in pngs.items()},
                    session=Path(str(raw["pse"])) if raw.get("pse") else None,
                    organic=tuple(map(str, raw.get("organic", []) or [])),  # type: ignore[call-overload]
                    chains=tuple(map(str, raw.get("chains", []) or [])),  # type: ignore[call-overload]
                )
            )
        except (RuntimeError, subprocess.TimeoutExpired, OSError, ValueError, KeyError) as exc:
            results.append(RenderResult(structure=a, error=f"{type(exc).__name__}: {exc}"))
        if on_result is not None:
            on_result(results[-1])
    return results


def require_renders(record: RunRecord, results: list[RenderResult]) -> None:
    """CLAUDE.md: a run whose prediction structures lack renders fails report generation."""
    done = {r.structure.path for r in results if r.pngs and r.session and not r.error}
    missing = [
        a.path
        for a in record.artifacts
        if a.kind is ArtifactKind.PREDICTION_STRUCTURE and a.path not in done
    ]
    if missing:
        raise ReportError(f"prediction structures without PyMOL renders: {missing}")


def figure_entries(results: list[RenderResult], rel_to: Path) -> list[FigureEntry]:
    entries = []
    for r in results:
        if r.error:
            continue
        name = r.structure.label or Path(r.structure.path).name
        for view, png in r.pngs.items():
            what = "whole structure" if view == "overview" else "ligand environment within 5 Å"
            organic = f"; organic components {', '.join(r.organic)}" if r.organic else ""
            entries.append(
                FigureEntry(
                    id=f"render_{render_stem(r.structure)}_{view}",
                    kind="render",
                    path=str(png.relative_to(rel_to)),
                    caption=(
                        f"{name} ({r.structure.kind.value}), {what}. Chains {', '.join(r.chains)}"
                        f"{organic}. sha256 {r.structure.sha256[:16]}."
                    ),
                    alt=(
                        f"PyMOL cartoon of {name} coloured by chain"
                        + (", ligands as sticks" if r.organic else "")
                        + "."
                    ),
                    session_path=str(r.session.relative_to(rel_to)) if r.session else None,
                )
            )
    return entries
