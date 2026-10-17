"""Layer 4: protein geometry from MolProbity, run on the predicted structures.

MolProbity is the cctbx implementation (`molprobity.molprobity` from cctbx-base) in the conda
prefix of environment/conda.yml, with the Richardson lab reduce (hydrogens) and probe (all-atom
contacts) and the Top8000 reference data from `pah fetch --only molprobity_data`. Phenix's
`phenix.molprobity` is used when it is on PATH and the conda prefix has none. The values are the
program's own summary: Ramachandran outliers and favoured fraction, rotamer outliers, Cβ
deviations above 0.25 Å, clashscore, RMS bonds and angles, and the MolProbity score.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pah.checks import outputs
from pah.core.check import Check, CheckContext, GateKind, SkipReason, register
from pah.core.models import ArtifactKind, Finding, Gate, Layer, Threshold, ToolRef

MAX_STRUCTURES = 3
TIMEOUT_S = 1800
EXECUTABLES = ("molprobity.molprobity", "phenix.molprobity")
# Summary label in the MolProbity output -> (measurement, unit)
SUMMARY: dict[str, tuple[str, str | None]] = {
    "Ramachandran outliers": ("rama_outliers_pct", "%"),
    "favored": ("rama_favored_pct", "%"),
    "Rotamer outliers": ("rotamer_outliers_pct", "%"),
    "C-beta deviations": ("cbeta_deviations", None),
    "Clashscore": ("clashscore", None),
    "RMS(bonds)": ("rms_bonds_A", "Å"),
    "RMS(angles)": ("rms_angles_deg", "°"),
    "MolProbity score": ("molprobity_score", None),
}
LABELS = {
    "rama_outliers_pct": "Ramachandran outliers",
    "rama_favored_pct": "Ramachandran favoured",
    "rotamer_outliers_pct": "rotamer outliers",
    "cbeta_deviations": "Cβ deviations",
    "clashscore": "clashscore",
    "molprobity_score": "MolProbity score",
}
# Threshold rows (configs/thresholds.yaml) -> measurement they apply to
LIMITS = {
    "rama_outliers": "rama_outliers_pct",
    "rama_favored": "rama_favored_pct",
    "rotamer_outliers": "rotamer_outliers_pct",
    "cbeta_deviations": "cbeta_deviations",
    "clashscore": "clashscore",
}
SETUP_ERRORS = (
    "Rotamer and Ramachandran distributions not available",
    "Reduce and/or Probe not configured",
    "Can't find chem_data",
    "Cannot find CCP4 monomer library",
)
LINE = re.compile(r"^\s*(?P<label>[A-Za-z][A-Za-z() -]*?)\s*=\s*(?P<value>-?\d+(?:\.\d+)?)")


def parse_summary(text: str) -> dict[str, float]:
    """Values of the `Summary` block of MolProbity output, keyed by measurement name."""
    _, sep, block = text.partition("= Summary =")
    if not sep:
        return {}
    values: dict[str, float] = {}
    for line in block.splitlines():
        m = LINE.match(line)
        if m and m["label"] in SUMMARY:
            values[SUMMARY[m["label"]][0]] = float(m["value"])
    return values


@dataclass(frozen=True)
class Toolchain:
    executable: Path
    prefix: Path | None
    version: str | None
    components: dict[str, str]


def _conda_prefix() -> Path:
    return Path(os.environ.get("PAH_CONDA_PREFIX") or ".tools/conda-env")


def _first_line(argv: list[str]) -> str | None:
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (proc.stdout + proc.stderr).strip().splitlines()
    return text[0].strip() if text else None


def find_toolchain() -> Toolchain | None:
    """The MolProbity executable: the conda prefix first, then PATH (Phenix)."""
    prefix = _conda_prefix()
    for name in EXECUTABLES:
        cand = prefix / "bin" / name
        if cand.is_file():
            return _describe(cand, prefix)
    for name in EXECUTABLES:
        found = shutil.which(name)
        if found:
            return _describe(Path(found), None)
    return None


def _describe(exe: Path, prefix: Path | None) -> Toolchain:
    version = None
    components: dict[str, str] = {}
    if prefix is not None:
        vfile = prefix / "share" / "cctbx" / "cctbx_version.txt"
        if vfile.is_file():
            version = vfile.read_text().strip() or None
            components["cctbx"] = version or ""
        for tool in ("reduce", "probe"):
            line = _first_line([str(prefix / "bin" / tool), "-version"])
            if line:
                components[tool] = line
    return Toolchain(exe, prefix, version, components)


def _structures(ctx: CheckContext) -> list[Any]:
    """Distinct structure files of the primary set, in rank order (a rigid docking receptor is
    one structure however many poses share it)."""
    seen: set[str] = set()
    out = []
    for pose in outputs.primary_set(ctx).ranked():
        if not pose.structure.is_file():
            continue
        digest = hashlib.sha256(pose.structure.read_bytes()).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        out.append(pose)
        if len(out) == MAX_STRUCTURES:
            break
    return out


def run_molprobity(tool: Toolchain, structure: Path, workdir: Path, stem: str) -> dict[str, Any]:
    """Runs MolProbity on one structure; returns the parsed summary, output file and errors."""
    workdir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    if tool.prefix is not None:
        env["PATH"] = os.pathsep.join([str(tool.prefix / "bin"), env.get("PATH", "")])
    argv = [
        str(tool.executable),
        str(structure.resolve()),
        f"output.prefix={stem}",
        "output.coot=False",
        "output.probe_dots=False",
    ]
    proc = subprocess.run(
        argv, capture_output=True, text=True, timeout=TIMEOUT_S, cwd=str(workdir), env=env
    )
    text = proc.stdout + proc.stderr
    log = workdir / f"{stem}.log"
    log.write_text(text)
    values = parse_summary(text)
    error = None
    if proc.returncode != 0 or not values:
        tail = [ln for ln in text.strip().splitlines() if ln.strip()][-1:] or ["no output"]
        error = tail[0][:300]
    out = workdir / f"{stem}.out"
    return {
        "values": values,
        "error": error,
        "setup_error": next((e for e in SETUP_ERRORS if e in text), None),
        "output": out if out.is_file() else None,
        "log": log,
    }


def _breaches(values: dict[str, float], limits: dict[str, Threshold]) -> list[str]:
    out = []
    for name, th in limits.items():
        v = values.get(LIMITS[name.removesuffix("_severe")])
        if v is None:
            continue
        ok = v <= float(th.value) if th.comparator == "<=" else v >= float(th.value)
        if not ok:
            out.append(f"{LABELS[LIMITS[name.removesuffix('_severe')]]} {v:g} (limit {th.value})")
    return out


@register
class MolProbity(Check):
    id = "l4.molprobity"
    layer = Layer.VALIDITY
    # Not decisive under configs/standing.yaml (inherited tool criteria): the engine reports a
    # severe result (Gate.STOP below) as a narrowing warning with the original gate recorded.
    gate_kind = GateKind.WARN
    title = "Protein geometry (MolProbity: Ramachandran, rotamers, Cβ deviations, clashscore)"

    def applies(self, ctx: CheckContext) -> str | None:
        return outputs.needs_predictions(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        tool = find_toolchain()
        if tool is None:
            return self.finding(
                Gate.SKIP,
                "molprobity.molprobity not found in PAH_CONDA_PREFIX or on PATH; install "
                "environment/conda.yml and run pah fetch --only molprobity_data",
                evidence={"skip_reason": SkipReason.TOOL_MISSING.value},
                tool=ToolRef(name="molprobity"),
            )
        ref = ToolRef(name="molprobity", version=tool.version)
        warn = {n: outputs.configured(self.id, n, measurement=m) for n, m in LIMITS.items()}
        severe = {
            f"{n}_severe": outputs.configured(self.id, f"{n}_severe", measurement=m)
            for n, m in LIMITS.items()
        }
        rows: list[dict[str, Any]] = []
        artifacts: list[str] = []
        for pose in _structures(ctx):
            stem = re.sub(r"[^A-Za-z0-9_.-]", "_", str(pose.id))
            res = run_molprobity(tool, pose.structure, ctx.run_dir / "derived" / "molprobity", stem)
            if res["setup_error"]:
                return self.finding(
                    Gate.SKIP,
                    f"MolProbity installation incomplete: {res['setup_error']}; run pah fetch "
                    "--only molprobity_data",
                    evidence={"skip_reason": SkipReason.TOOL_MISSING.value, **tool.components},
                    tool=ref,
                )
            row: dict[str, Any] = {"pose": pose.id, "structure": pose.structure.name}
            row.update(res["values"])
            if res["error"]:
                row["error"] = res["error"]
            if res["output"] is not None:
                art = ctx.add_artifact(
                    res["output"], ArtifactKind.DATA, label=f"MolProbity summary {pose.id}"
                )
                artifacts.append(art.path)
                row["summary_file"] = art.path
            rows.append(row)
        done = [r for r in rows if "molprobity_score" in r]
        if not done:
            raise outputs.OutputUnavailableError(
                "MolProbity failed for every structure: "
                + "; ".join(str(r.get("error")) for r in rows[:3])
            )
        top = done[0]
        values = {k: v for k, v in top.items() if k in {m for m, _ in SUMMARY.values()}}
        hard = _breaches(values, severe)
        soft = _breaches(values, warn)
        units = {m: u for m, u in SUMMARY.values() if u}
        m: dict[str, Any] = {**values, "structures": len(done), "failed": len(rows) - len(done)}
        ev = {
            "structures": rows,
            "toolchain": tool.components,
            "executable": str(tool.executable),
            "severe": hard,
            "warnings": soft,
        }
        th = (*warn.values(), *severe.values())
        summary = ", ".join(
            f"{LABELS[name]} {values[name]:g}{' %' if unit == '%' else ''}"
            for name, unit in SUMMARY.values()
            if name in values and name in LABELS
        )
        if hard:
            gate, msg = Gate.STOP, f"{top['pose']}: severe geometry ({'; '.join(hard)}); {summary}"
        elif soft:
            gate, msg = Gate.WARN, f"{top['pose']}: {'; '.join(soft)}; {summary}"
        else:
            gate, msg = Gate.PASS, f"{top['pose']}: {summary}"
        return self.finding(
            gate,
            msg,
            measurements=m,
            units=units,
            thresholds=th,
            evidence=ev,
            tool=ref,
            artifacts=tuple(artifacts),
        )
