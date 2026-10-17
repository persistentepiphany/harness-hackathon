"""`stats` of the UI record (docs/UI.md, "Harness record to UI record"), from findings only.

Every value here is copied from a finding's measurements or evidence, from the executor outputs
the parsers reported (as the checks recorded them), or from the run manifest. Nothing is computed
from coordinates and nothing is filled in: a block whose source check skipped, or whose evidence
lacks the field, is left out, and the UI shows "not computed" for it.

Provenance: `stats.provenance` maps a block name (`seeds`) or a block field (`physics.strain`) to
`{check, tool, version?, unit?, n?, field?, pose?}`, so a hover can name the check and tool behind a
value. Object blocks (`pairwise`) also carry their `source` inline, and each `metrics` row names
its check and executor.

Ensemble members are the parsed poses the checks registered as `prediction_structure` artifacts
(`pah.checks.outputs.prediction_sets`), one row per pose or model, with the set they came from
resolved from the `predictions/<NN>_<executor>/` work directory. Per-pose values exist only for the
poses a check reported on (the independent samples of the primary set); other modes and control
poses carry their identity, file and any control measurement, and no tool values, because the run
directory does not hold their parsed scores.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

Json = dict[str, Any]

THIN = "\N{THIN SPACE}"
MINUS = "\N{MINUS SIGN}"

# Measurement and evidence names carry their unit as a suffix: `rmsd_A`, `volume_A3`, `strain_kcal`.
SUFFIX_UNITS = (("_A3", "Å³"), ("_A2", "Å²"), ("_A", "Å"), ("_kcal", "kcal/mol"))
# Keys that l5.confidence.local adds to a pose row next to the executor's own scores.
HARNESS_POSE_KEYS = frozenset({"pose", "global_plddt", "pocket_plddt", "pocket_residues", "pae"})
# Output kinds that read as confidence (the seed spread plots them); the rest are scores.
CONFIDENCE_KINDS = frozenset({"confidence", "interface", "plddt"})
# PLIP interaction types (pah.checks.layer4_validity.INTERACTION_TYPES) as the UI names them.
INTERACTION_LABELS = {
    "hbond": "H-bond",
    "salt_bridge": "Salt bridge",
    "pi_stack": "π stacking",
    "pi_cation": "π\N{EN DASH}cation",
    "hydrophobic": "Hydrophobic",
    "halogen": "Halogen bond",
    "water_bridge": "Water bridge",
    "metal": "Metal complex",
}

CLUSTERS = "l5.sampling.clusters"
CONFIDENCE = "l5.confidence.local"
AGREEMENT = "l5.agreement.cross_family"
REDOCKING = "l5.controls.redocking"
RMSD_CRYSTAL = "l5.rmsd_to_crystal"
ENRICHMENT = "l5.enrichment"
POSEBUSTERS = "l4.posebusters"
TORSIONS = "l4.torsion_strain"
POLARS = "l4.interactions.unsatisfied_polars"
FINGERPRINT = "l4.interactions.fingerprint"
KNOWN = "l4.interactions.known_binders"
DRIFT = "l4.minimisation_drift"
CLASHES = "l4.structure.clashes"
POCKET = "l2.pocket.resolved"
STATE = "l2.receptor.state"
COFACTORS = "l2.context.cofactors"
BOX = "l2.docking.box"

_SET_DIR = re.compile(r"^predictions/(?P<idx>\d+)_(?P<executor>[^/]+)/")
_POSE_ID = re.compile(
    r"^(?P<executor>[^/]+)(?:/seed(?P<seed>-?\d+))?/(?P<kind>[A-Za-z_]+?)(?P<index>\d+)$"
)
_CAPTION_SHA = re.compile(r"\bsha256 (?P<sha>[0-9a-f]{12,64})\b")


# ---------------------------------------------------------------- small helpers


def _d(value: Any) -> Json:
    return value if isinstance(value, dict) else {}


def _ds(value: Any) -> list[Json]:
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list | tuple) else []


def number(value: Any) -> float | int | None:
    """A finite int or float; bools, strings and NaN are not numbers here."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return value if math.isfinite(value) else None


def unit_of(name: str, unit: Any = None) -> str | None:
    """The unit a measurement states, else the one its name carries as a suffix."""
    if isinstance(unit, str) and unit:
        return unit
    for suffix, u in SUFFIX_UNITS:
        if name.endswith(suffix):
            return u
    return None


def fmt(value: Any, unit: str | None = None) -> str:
    """Display string in the UI's number style: true minus sign, unit after a thin space."""
    n = number(value)
    if n is None:
        text = str(value)
    else:
        text = str(n) if isinstance(n, int) else format(n, ".12g")
        if text.startswith("-"):
            text = MINUS + text[1:]
    return f"{text}{THIN}{unit}" if unit else text


def fraction(n: Any, d: Any) -> str | None:
    """`n/d` with the denominator kept; None unless both are numbers."""
    a, b = number(n), number(d)
    return f"{fmt(a)}/{fmt(b)}" if a is not None and b is not None else None


def file_url(run_id: str, rel: str) -> str:
    from urllib.parse import quote

    return f"/runs/{quote(run_id)}/files/{quote(rel)}"


def inside(run_dir: Path, path: str) -> str | None:
    """Run-relative posix path when `path` is inside the run directory, else None."""
    p = Path(path)
    if not p.is_absolute():
        return p.as_posix() if ".." not in p.parts else None
    try:
        return p.resolve().relative_to(run_dir.resolve()).as_posix()
    except ValueError:
        return None


class Findings:
    """Findings by check id. `get` returns only findings that ran (gate other than skip)."""

    def __init__(self, findings: Iterable[Mapping[str, Any]]) -> None:
        self.by_id: dict[str, Json] = {}
        for f in findings:
            if isinstance(f, dict) and f.get("check_id"):
                self.by_id[str(f["check_id"])] = f

    def get(self, cid: str) -> Json | None:
        f = self.by_id.get(cid)
        return f if f is not None and f.get("gate") != "skip" else None

    def evidence(self, cid: str) -> Json:
        return _d(_d(self.get(cid)).get("evidence"))

    def measures(self, cid: str) -> Json:
        return {
            str(m.get("name")): m.get("value") for m in _ds(_d(self.get(cid)).get("measurements"))
        }

    def unit(self, cid: str, name: str) -> str | None:
        for m in _ds(_d(self.get(cid)).get("measurements")):
            if m.get("name") == name:
                return unit_of(name, m.get("unit"))
        return unit_of(name)

    def threshold(self, cid: str, name: str) -> Json | None:
        return next(
            (t for t in _ds(_d(self.get(cid)).get("thresholds")) if t.get("name") == name), None
        )

    def ran(self, cid: str) -> bool:
        return self.get(cid) is not None

    def source(self, cid: str, **extra: Any) -> Json:
        tool = _d(_d(self.get(cid)).get("tool"))
        out: Json = {"check": cid, "tool": tool.get("name")}
        if tool.get("version"):
            out["version"] = tool["version"]
        out.update({k: v for k, v in extra.items() if v is not None})
        return out


# ---------------------------------------------------------------- inputs and members


@dataclass(frozen=True)
class StatsInput:
    """What the mapping reads from one run directory (built by `pah.webui.adapter`)."""

    run_id: str
    run_dir: Path
    findings: Sequence[Mapping[str, Any]]
    manifest: Mapping[str, Any]
    artifacts: Sequence[Mapping[str, Any]]
    # Executor id -> Tool shape from configs/executors.yaml (name, family, outputs, dockingParams).
    tools: Mapping[str, Mapping[str, Any]]
    # Provenance source id -> display name, for the crystal reference row.
    source_names: Mapping[str, str] = field(default_factory=dict)

    def url(self, rel: str) -> str:
        return file_url(self.run_id, rel)

    def tool(self, executor: str) -> Mapping[str, Any]:
        return self.tools.get(executor) or {"id": executor, "name": executor, "outputs": []}

    def outputs(self, executor: str) -> list[Json]:
        return _ds(self.tool(executor).get("outputs"))

    def output(self, executor: str, key: str) -> Json | None:
        """The register entry for a parsed key. Parsers write a `{name: number}` map output as
        `<key>.<name>` (`pah.executors.parsers._common.floats`), e.g. `pdockq.A-B`, which is
        declared once as `pdockq`."""
        outputs = self.outputs(executor)
        hit = next((o for o in outputs if o.get("key") == key), None)
        if hit is None and "." in key:
            base = key.split(".", 1)[0]
            hit = next((o for o in outputs if o.get("key") == base), None)
        return hit


@dataclass
class Member:
    """One parsed pose or model the checks registered."""

    id: str
    pose: str
    executor: str
    role: str
    set_index: int | None
    family: str | None
    seed: int | None = None
    sample: int | None = None
    sample_kind: str | None = None
    structure: str | None = None  # run-relative structure file, when inside the run directory
    sha256: str | None = None
    ligand: str | None = None  # run-relative ligand SDF, when inside the run directory
    kind: str = "model"
    label: str = ""

    @property
    def assessed(self) -> bool:
        return not self.role.startswith("control")


def spec_roles(manifest: Mapping[str, Any]) -> list[tuple[str, str]]:
    """(executor, role) per parsed prediction in the order `prediction_sets` numbers its work
    directories: predictions, then controls.redocking, decoys and actives."""
    out = [
        (str(p.get("executor")), str(p.get("role") or "primary"))
        for p in _ds(manifest.get("predictions"))
    ]
    controls = _d(manifest.get("controls"))
    redock = _d(controls.get("redocking"))
    if redock:
        out.append((str(redock.get("executor")), "control:redocking"))
    out += [(str(p.get("executor")), "control:decoy") for p in _ds(controls.get("decoys"))]
    out += [(str(p.get("executor")), "control:active") for p in _ds(controls.get("actives"))]
    return out


def primary_index(roles: Sequence[tuple[str, str]], present: set[int]) -> int | None:
    """Work directory of the primary set (`outputs.primary_set`): first parsed set with role
    primary, else the first parsed set that is not a control."""
    parsed = [i for i in range(len(roles)) if i in present]
    hit = next((i for i in parsed if roles[i][1] == "primary"), None)
    if hit is None:
        hit = next((i for i in parsed if not roles[i][1].startswith("control")), None)
    return hit


def _set_index(rel: str | None) -> int | None:
    m = _SET_DIR.match(rel or "")
    return int(m.group("idx")) if m else None


def _label(pose: str, role: str) -> str:
    if role in {"primary", "unknown"}:
        return pose
    return f"{role.split(':', 1)[-1]} · {pose}"


def members(inp: StatsInput) -> list[Member]:
    """Parsed poses from the run's artifacts, with role, seed, sample and UI kind."""
    roles = spec_roles(inp.manifest)
    out: list[Member] = []
    seen: set[tuple[str, str]] = set()
    last: Member | None = None
    for a in inp.artifacts:
        kind = str(a.get("kind", ""))
        label = str(a.get("label") or "")
        rel = inside(inp.run_dir, str(a.get("path", "")))
        if kind == "prediction_structure" and label:
            on_disk = rel if rel and (inp.run_dir / rel).is_file() else None
            idx = _set_index(rel)
            key = (label, str(a.get("path", "")))
            if key in seen:
                last = None
                continue
            seen.add(key)
            m = _POSE_ID.match(label)
            executor = m.group("executor") if m else label.split("/", 1)[0]
            last = Member(
                id=Path(on_disk).with_suffix("").as_posix() if on_disk else "",
                pose=label,
                executor=executor,
                role="unknown",
                set_index=idx,
                family=None,
                seed=int(m.group("seed")) if m and m.group("seed") is not None else None,
                sample=int(m.group("index")) if m else None,
                sample_kind=m.group("kind") if m else None,
                structure=on_disk,
                sha256=str(a.get("sha256") or "") or None,
            )
            out.append(last)
        elif kind == "data" and last is not None and label == f"{last.pose} ligand":
            if rel and (inp.run_dir / rel).is_file():
                last.ligand = rel
                if last.set_index is None:
                    last.set_index = _set_index(rel)
            last = None
    for mem in out:
        idx = mem.set_index
        if idx is not None and idx < len(roles) and roles[idx][0] == mem.executor:
            mem.role = roles[idx][1]
        elif len({r for e, r in roles if e == mem.executor}) == 1:
            mem.role = next(r for e, r in roles if e == mem.executor)
        mem.family = _family(inp, mem.executor)
        if not mem.id:
            base = Path(mem.ligand).parent.as_posix() if mem.ligand else f"{mem.role}/{mem.pose}"
            mem.id = base
        mem.label = _label(mem.pose, mem.role)
    _assign_kinds(inp, out)
    return out


def _family(inp: StatsInput, executor: str) -> str | None:
    fam = inp.tool(executor).get("family")
    return str(fam) if fam else None


def primary_members(inp: StatsInput, ms: Sequence[Member]) -> dict[str, Member]:
    """Pose id -> member of the primary set, the set the per-pose findings report on."""
    roles = spec_roles(inp.manifest)
    present = {m.set_index for m in ms if m.set_index is not None}
    idx = primary_index(roles, present)
    out: dict[str, Member] = {}
    for m in ms:
        if idx is not None and m.set_index == idx:
            out[m.pose] = m
    if idx is None:  # set not resolvable from the work directory: unique assessed pose ids only
        counts: dict[str, int] = {}
        for m in ms:
            counts[m.pose] = counts.get(m.pose, 0) + 1
        out = {m.pose: m for m in ms if m.assessed and counts[m.pose] == 1}
    return out


def _assign_kinds(inp: StatsInput, ms: Sequence[Member]) -> None:
    f = Findings(inp.findings)
    ev = f.evidence(CLUSTERS)
    clustered = {str(p.get("pose")) for p in _ds(ev.get("poses"))}
    medoid = ev.get("medoid")
    primary = primary_members(inp, ms)
    for m in ms:
        if primary.get(m.pose) is m and m.pose == medoid:
            m.kind = "medoid"
        elif primary.get(m.pose) is m and m.pose in clustered:
            m.kind = "seed"
        else:
            m.kind = "docking" if m.family == "docking" else "model"


# ---------------------------------------------------------------- blocks


def per_residue_confidence(inp: StatsInput, executor: str) -> Json | None:
    """The executor's per-residue confidence output from the register (kind plddt, scope
    residue), or None when the register declares none."""
    return next(
        (
            o
            for o in inp.outputs(executor)
            if o.get("kind") == "plddt" and o.get("scope") == "residue"
        ),
        None,
    )


def tool_values(row: Mapping[str, Any]) -> dict[str, float | int]:
    """Executor outputs in one l5.confidence.local pose row (the harness keys removed)."""
    out: dict[str, float | int] = {}
    for k, v in row.items():
        n = number(v)
        if k not in HARNESS_POSE_KEYS and n is not None:
            out[str(k)] = n
    return out


def _confidence_rows(f: Findings) -> dict[str, Json]:
    return {str(r.get("pose")): r for r in _ds(f.evidence(CONFIDENCE).get("poses"))}


def _value_key(values: Mapping[str, Any], value: Any) -> str | None:
    """The single output key whose reported value equals `value`, else None."""
    hits = [k for k, v in values.items() if number(v) is not None and v == value]
    return hits[0] if len(hits) == 1 else None


def seeds_block(inp: StatsInput, f: Findings, prov: Json) -> list[Json] | None:
    ev = f.evidence(CLUSTERS)
    poses = _ds(ev.get("poses"))
    if not poses:
        return None
    conf = _confidence_rows(f)
    rows: list[Json] = []
    for p in poses:
        pid = str(p.get("pose"))
        row: Json = {"pose": pid}
        for src, dst in (("seed", "seed"), ("sample", "sample"), ("cluster", "cluster")):
            if number(p.get(src)) is not None:
                row[dst] = p[src]
        for src, dst in (("rmsd_to_medoid_A", "rmsdToMedoid"), ("site_distance_A", "siteDistance")):
            if number(p.get(src)) is not None:
                row[dst] = p[src]
        if p.get("executor"):
            row["toolId"] = str(p["executor"])
        c = number(p.get("confidence"))
        if c is not None:
            key = _value_key(tool_values(conf.get(pid, {})), c)
            out = inp.output(str(p.get("executor") or ""), key) if key else None
            is_conf = (
                out is not None
                and out.get("kind") in CONFIDENCE_KINDS
                and not out.get("rankingOnly")
            )
            row["confidence" if is_conf else "score"] = c
            if key:
                row["confidenceKey" if is_conf else "scoreKey"] = key
        rows.append(row)
    prov["seeds"] = f.source(CLUSTERS, field="evidence.poses", unit="Å", n=len(rows))
    return rows


def pairwise_block(f: Findings, prov: Json) -> Json | None:
    pw = _d(f.evidence(CLUSTERS).get("pairwise_rmsd_A"))
    med, q1, q3 = (number(pw.get(k)) for k in ("median", "q1", "q3"))
    if med is None:
        return None
    src = f.source(CLUSTERS, field="evidence.pairwise_rmsd_A", unit="Å", n=pw.get("n"))
    out: Json = {"median": med, "unit": "Å", "source": src}
    if q1 is not None and q3 is not None:
        out["iqr"] = [q1, q3]
    if number(pw.get("n")) is not None:
        out["n"] = pw["n"]
    poses = number(f.measures(CLUSTERS).get("poses"))
    if poses is not None:
        out["poses"] = poses
    prov["pairwise"] = src
    return out


def posebusters_block(f: Findings, prov: Json) -> list[Json] | None:
    ev = f.evidence(POSEBUSTERS)
    tests = [
        {"test": str(t.get("test")), "pass": bool(t.get("pass")), "value": str(t.get("value"))}
        for t in _ds(ev.get("tests"))
    ]
    if not tests:
        return None
    prov["posebusters"] = f.source(
        POSEBUSTERS, field="evidence.tests", n=len(tests), pose=ev.get("representative")
    )
    return tests


def _by_pose(f: Findings, cid: str, key: str = "poses") -> dict[str, Json]:
    return {str(r.get("pose")): r for r in _ds(f.evidence(cid).get(key)) if r.get("pose")}


# (check id, evidence field, UI field) for the per-pose physics table.
PHYSICS_FIELDS: tuple[tuple[str, str, str], ...] = (
    (DRIFT, "drift_A", "drift"),
    (TORSIONS, "unlikely_torsions", "torsions"),
    (TORSIONS, "torsions", "torsionsScanned"),
    (TORSIONS, "strain_kcal", "strain"),
    (TORSIONS, "max_excess_kcal", "maxTorsionExcess"),
    (POLARS, "unsatisfied", "unsatisfied"),
    (POLARS, "buried_polar", "buriedPolar"),
    (POLARS, "buried_charged", "buriedCharged"),
    (POSEBUSTERS, "passed", "pbPassed"),
    (POSEBUSTERS, "total", "pbTotal"),
    (CLASHES, "clashes", "clashes"),
    (CLASHES, "clashscore", "clashscore"),
)
# Per-pose fields that are not numbers: failed PoseBusters test names, minimisation convergence.
PHYSICS_FLAGS: tuple[tuple[str, str, str], ...] = (
    (POSEBUSTERS, "failed", "pbFailed"),
    (DRIFT, "converged", "converged"),
)


def physics_block(
    f: Findings, order: Sequence[str], primary: Mapping[str, Member], prov: Json
) -> list[Json] | None:
    tables = {cid: _by_pose(f, cid) for cid in {c for c, _, _ in PHYSICS_FIELDS + PHYSICS_FLAGS}}
    poses = list(order) or list(dict.fromkeys(p for t in tables.values() for p in t))
    rows: list[Json] = []
    used: set[tuple[str, str, str]] = set()
    for pid in poses:
        row: Json = {"pose": pid}
        m = primary.get(pid)
        if m is not None and m.seed is not None:
            row["seed"] = m.seed
        if m is not None and m.sample is not None:
            row["sample"] = m.sample
        filled = False
        for cid, src, dst in PHYSICS_FIELDS:
            n = number(tables[cid].get(pid, {}).get(src))
            if n is not None:
                row[dst] = n
                used.add((cid, src, dst))
                filled = True
        for cid, src, dst in PHYSICS_FLAGS:
            v = tables[cid].get(pid, {}).get(src)
            if isinstance(v, bool) or (isinstance(v, list) and all(isinstance(x, str) for x in v)):
                row[dst] = v
                used.add((cid, src, dst))
        if filled:
            rows.append(row)
    if not rows:
        return None
    for cid, src, dst in sorted(used):
        prov[f"physics.{dst}"] = f.source(cid, field=f"evidence.poses[].{src}", unit=unit_of(src))
    prov["physics"] = {"check": None, "checks": sorted({c for c, _, _ in used}), "tool": None}
    prov["physics"]["n"] = len(rows)
    return rows


def interactions_block(f: Findings, prov: Json) -> list[Json] | None:
    ev = f.evidence(FINGERPRINT)
    table = _ds(ev.get("interactions"))
    if not table:
        return None
    rep = str(ev.get("representative") or "")
    rep_keys = {
        (str(r.get("type")), str(r.get("residue"))) for r in _ds(_d(ev.get("per_pose")).get(rep))
    }
    ref_rows = _ds(f.evidence(KNOWN).get("reference_interactions"))
    known = {(str(r.get("type")), str(r.get("residue"))) for r in ref_rows}
    rows: list[Json] = []
    for r in table:
        t, res = str(r.get("type")), str(r.get("residue"))
        row: Json = {"residue": res, "type": INTERACTION_LABELS.get(t, t), "plipType": t}
        if number(r.get("distance_A")) is not None:
            row["distance"] = r["distance_A"]
        for k in ("poses", "of"):
            if number(r.get(k)) is not None:
                row[k] = r[k]
        if rep:
            row["inRepresentative"] = (t, res) in rep_keys
        if ref_rows:
            row["known"] = (t, res) in known
        rows.append(row)
    prov["interactions"] = f.source(
        FINGERPRINT, field="evidence.interactions", unit="Å", n=len(rows), pose=rep or None
    )
    if ref_rows:
        prov["interactions.known"] = f.source(
            KNOWN, field="evidence.reference_interactions", n=len(ref_rows)
        )
    return rows


def _row(
    rows: list[list[str]], prov: Json, block: str, label: str, value: str | None, source: Json
) -> None:
    if value is None:
        return
    rows.append([label, value])
    prov[f"{block}.{label}"] = source


def site_block(f: Findings, prov: Json) -> list[list[str]] | None:
    rows: list[list[str]] = []
    pocket = f.measures(POCKET)
    if f.ran(POCKET):
        src = f.source(POCKET, field="measurements")
        for name, label in (
            ("pocket_residues", "pocket residues"),
            ("incomplete", "incomplete pocket residues"),
            ("sequence_gaps", "sequence gaps"),
        ):
            if number(pocket.get(name)) is not None:
                _row(rows, prov, "site", label, fmt(pocket[name]), src)
    state = f.measures(STATE).get("state")
    if isinstance(state, str):
        _row(rows, prov, "site", "receptor state", state, f.source(STATE, field="measurements"))
    cof = f.measures(COFACTORS)
    if number(cof.get("near_site")) is not None:
        src = f.source(COFACTORS, field="measurements")
        _row(rows, prov, "site", "components near site", fmt(cof["near_site"]), src)
    box = f.measures(BOX)
    if f.ran(BOX):
        src = f.source(BOX, field="measurements")
        vol = number(box.get("volume_A3"))
        if vol is not None:
            _row(rows, prov, "site", "docking box volume", fmt(vol, f.unit(BOX, "volume_A3")), src)
        contacts = number(box.get("contact_residues"))
        outside = number(box.get("contact_residues_outside"))
        if contacts is not None and outside is not None:
            within = fraction(contacts - outside, contacts)
            _row(rows, prov, "site", "contact residues in box", within, src)
    cl = f.measures(CLUSTERS)
    th = f.threshold(CLUSTERS, "site_distance")
    placed = fraction(cl.get("in_site"), cl.get("poses"))
    if placed is not None:
        cut = f" ≤ {fmt(th.get('value'), 'Å')} of site" if th else ""
        src = f.source(CLUSTERS, field="measurements.in_site")
        _row(rows, prov, "site", "placement", f"{placed} poses{cut}", src)
    return rows or None


def _crystal_rmsd(f: Findings, executor: str | None, medoid: Any) -> tuple[float | None, Json]:
    """RMSD of the primary method's medoid to the crystal ligand, when the agreement check used
    the same medoid as the cluster check; else l5.rmsd_to_crystal for the representative."""
    ev = f.evidence(AGREEMENT)
    same = _d(ev.get("medoids")).get(executor or "") == medoid
    for c in _ds(ev.get("comparisons")):
        if c.get("weight") == "decisive" and c.get("method") == executor and same:
            v = number(c.get("value"))
            if v is not None:
                return v, f.source(AGREEMENT, field="evidence.comparisons", unit=c.get("unit"))
    v = number(f.measures(RMSD_CRYSTAL).get("rmsd_A"))
    return v, f.source(RMSD_CRYSTAL, field="measurements.rmsd_A", unit="Å")


def pose_block(f: Findings, primary_executor: str | None, prov: Json) -> list[list[str]] | None:
    rows: list[list[str]] = []
    cl_ev = f.evidence(CLUSTERS)
    cl = f.measures(CLUSTERS)
    medoid = cl_ev.get("medoid")
    if isinstance(medoid, str):
        _row(rows, prov, "pose", "medoid", medoid, f.source(CLUSTERS, field="evidence.medoid"))
    rmsd, src = _crystal_rmsd(f, primary_executor, medoid)
    if rmsd is not None:
        _row(rows, prov, "pose", "RMSD to crystal", fmt(rmsd, "Å"), src)
    if f.ran(CLUSTERS):
        src = f.source(CLUSTERS, field="measurements")
        if number(cl.get("clusters")) is not None:
            _row(rows, prov, "pose", "clusters", fmt(cl["clusters"]), src)
        lc = fraction(cl.get("largest_cluster"), cl.get("poses"))
        _row(rows, prov, "pose", "largest cluster", f"{lc} poses" if lc else None, src)
        th = f.threshold(CLUSTERS, "cluster_rmsd")
        if th is not None:
            within = fraction(cl.get("within_medoid"), cl.get("poses"))
            _row(rows, prov, "pose", f"within {fmt(th.get('value'), 'Å')} of medoid", within, src)
        best = number(cl.get("best_sampled_rmsd_to_reference_A"))
        if best is not None:
            _row(rows, prov, "pose", "best sampled RMSD to crystal", fmt(best, "Å"), src)
    fractions = (
        (POSEBUSTERS, "PoseBusters", "passed", "total"),
        (TORSIONS, "unlikely torsions", "unlikely_torsions", "torsions"),
        (POLARS, "unsatisfied buried polars", "unsatisfied", "buried_polar"),
        (KNOWN, "key interactions reproduced", "reproduced", "key_interactions"),
    )
    for cid, label, num, den in fractions:
        ms = f.measures(cid)
        src = f.source(cid, field=f"measurements.{num}")
        _row(rows, prov, "pose", label, fraction(ms.get(num), ms.get(den)), src)
    values = (
        (TORSIONS, "torsion strain", "strain_kcal", "kcal/mol"),
        (DRIFT, "minimisation drift", "drift_A", "Å"),
        (CLASHES, "clashscore", "clashscore", None),
        (REDOCKING, "redocking control RMSD", "rmsd_A", "Å"),
    )
    for cid, label, name, unit in values:
        v = number(f.measures(cid).get(name))
        if v is not None:
            _row(
                rows, prov, "pose", label, fmt(v, unit), f.source(cid, field=f"measurements.{name}")
            )
    return rows or None


def metrics_block(
    inp: StatsInput, f: Findings, primary: Mapping[str, Member], prov: Json
) -> list[Json] | None:
    """Executor outputs of the representative pose, labelled from the tool register."""
    ev = f.evidence(CONFIDENCE)
    rep = str(ev.get("representative") or "")
    row = _confidence_rows(f).get(rep)
    out: list[Json] = []
    if row is not None:
        m = primary.get(rep)
        executor = m.executor if m else rep.split("/", 1)[0]
        for key, value in tool_values(row).items():
            out.append(_metric(inp, executor, key, value, rep))
    for extra in _ds(ev.get("metrics")):
        name, reported = str(extra.get("name", "")), number(extra.get("value"))
        if not name or reported is None:
            continue
        executor = str(extra.get("tool") or "")
        metric = _metric(inp, executor, name, reported, None)
        metric["separate"] = metric["separate"] or bool(extra.get("separate"))
        if extra.get("read"):
            metric["read"] = str(extra["read"])
        out.append(metric)
    if not out:
        return None
    order = {
        (eid, str(o.get("key"))): i
        for eid in {str(m["toolId"]) for m in out}
        for i, o in enumerate(inp.outputs(eid))
    }
    out.sort(key=lambda m: (not m["declared"], order.get((m["toolId"], m["key"]), 1 << 20)))
    prov["metrics"] = f.source(CONFIDENCE, field="evidence.poses", pose=rep or None, n=len(out))
    return out


def _metric(inp: StatsInput, executor: str, key: str, value: float | int, pose: str | None) -> Json:
    o = inp.output(executor, key)
    unit = str(o["unit"]) if o and o.get("unit") else None
    tool = inp.tool(executor)
    label = str(o["label"]) if o else key
    if o is not None and o.get("key") != key:
        label = f"{label} {key.split('.', 1)[1]}"  # one entry of a map output, e.g. a chain pair
    metric: Json = {
        "name": label,
        "value": fmt(value, unit),
        "number": value,
        "key": key,
        "toolId": executor,
        "tool": str(tool.get("name") or executor),
        "declared": o is not None,
        # an output the register does not declare is never read as pose quality
        "separate": bool(o.get("rankingOnly")) if o else True,
        "check": CONFIDENCE,
    }
    if unit:
        metric["unit"] = unit
    if o and o.get("kind"):
        metric["kind"] = o["kind"]
    if o and o.get("note"):
        metric["note"] = o["note"]
    if pose:
        metric["pose"] = pose
    return metric


def clusters_block(f: Findings, prov: Json) -> list[Json] | None:
    rows: list[Json] = [
        {str(k): c[k] for k in ("id", "size", "medoid") if k in c}
        for c in _ds(f.evidence(CLUSTERS).get("clusters"))
    ]
    if not rows:
        return None
    prov["clusters"] = f.source(CLUSTERS, field="evidence.clusters", n=len(rows))
    return rows


def pae_block(inp: StatsInput, f: Findings, prov: Json) -> Json | None:
    """PAE matrix file of the top-ranked pose, when the parser saved it inside the run."""
    pae = f.evidence(CONFIDENCE).get("pae")
    rel = inside(inp.run_dir, str(_d(pae).get("path", ""))) if isinstance(pae, dict) else None
    if not rel or not (inp.run_dir / rel).is_file():
        return None
    out: Json = {"path": rel, "url": inp.url(rel), "format": "npy"}
    if _d(pae).get("pose"):
        out["pose"] = str(_d(pae)["pose"])
    out.update(_pae_matrix(inp.run_dir / rel))
    prov["pae"] = f.source(CONFIDENCE, field="evidence.pae")
    return out


# Largest matrix embedded as is; a larger one is shown as means of k x k token blocks.
MAX_PAE_TOKENS = 512


def _pae_matrix(path: Path) -> Json:
    """`matrix` (Å, rounded to 0.01) read from the saved .npy, for the UI heatmap.

    Returns {} when the file is not a finite square 2-D array. Above MAX_PAE_TOKENS tokens the
    matrix is binned by block means and `lines` states the binning.
    """
    try:
        import numpy as np
    except ImportError:  # numpy comes with the checks extra; the file URL stays in the block
        return {}
    try:
        arr = np.load(path, allow_pickle=False)
    except (OSError, ValueError):
        return {}
    if arr.ndim != 2 or arr.shape[0] != arr.shape[1] or arr.shape[0] == 0:
        return {}
    arr = arr.astype(float)
    if not np.isfinite(arr).all():
        return {}
    n = int(arr.shape[0])
    out: Json = {}
    if n > MAX_PAE_TOKENS:
        k = -(-n // MAX_PAE_TOKENS)
        m = -(-n // k)
        padded = np.full((m * k, m * k), np.nan)
        padded[:n, :n] = arr
        arr = np.nanmean(padded.reshape(m, k, m, k), axis=(1, 3))
        x = "\N{MULTIPLICATION SIGN}"
        out["lines"] = [f"{n} tokens, shown as {m}{x}{m} means of {k}{x}{k} blocks"]
        out["binned"] = k
    out["matrix"] = np.round(arr, 2).tolist()
    out["tokens"] = n
    return out


def reference_block(f: Findings, prov: Json) -> Json | None:
    """Pose accuracy against the experimental reference: the redocking control and the
    per-pose RMSD to the crystal ligand."""
    out: Json = {}
    ev = f.evidence(REDOCKING)
    redock = {
        dst: ev[src]
        for src, dst in (("rmsd_A", "rmsd"), ("pose", "pose"), ("reference", "reference"))
        if src in ev and ev[src] is not None
    }
    if redock:
        out["redocking"] = {**redock, "unit": "Å"}
        prov["reference.redocking"] = f.source(REDOCKING, field="evidence", unit="Å")
    rows = [
        {"pose": str(r["pose"]), "rmsd": r["rmsd_A"]}
        for r in _ds(f.evidence(RMSD_CRYSTAL).get("poses"))
        if r.get("pose") and number(r.get("rmsd_A")) is not None
    ]
    if rows:
        out["rmsdToCrystal"] = rows
        prov["reference.rmsdToCrystal"] = f.source(RMSD_CRYSTAL, field="evidence.poses", unit="Å")
    return out or None


def agreement_block(f: Findings, prov: Json) -> list[Json] | None:
    comps = [c for c in _ds(f.evidence(AGREEMENT).get("comparisons")) if c.get("method")]
    if not comps:
        return None
    methods = list(dict.fromkeys(m for c in comps for m in (str(c["method"]), str(c.get("vs")))))
    pairs = {(str(c["method"]), str(c.get("vs"))): c for c in comps}
    unit = next((str(c["unit"]) for c in comps if c.get("unit")), None)
    rows: list[Json] = []
    for a in methods:
        cells: list[Json] = []
        for b in methods:
            cell: Json = {"vs": b}
            if unit:
                cell["unit"] = unit
            hit, mirror = pairs.get((a, b)), pairs.get((b, a))
            if a == b:
                cell.update(value=0, weight="—", self=True)  # a method against itself
            elif hit is not None or mirror is not None:
                c = hit if hit is not None else mirror
                assert c is not None
                cell.update(value=c.get("value"), weight=str(c.get("weight") or "—"))
                if hit is None:
                    cell["mirror"] = True  # symmetric RMSD, reported once by the check
            else:
                cell["weight"] = "—"  # not compared
            cells.append(cell)
        rows.append({"method": a, "cells": cells})
    prov["agreement"] = f.source(AGREEMENT, field="evidence.comparisons", unit=unit, n=len(comps))
    return rows


def ensemble_block(
    inp: StatsInput,
    f: Findings,
    ms: Sequence[Member],
    structures: Sequence[Mapping[str, Any]],
    renders: Sequence[Mapping[str, Any]],
    prov: Json,
) -> list[Json] | None:
    if not ms:
        return None
    primary = primary_members(inp, ms)
    clusters = _by_pose(f, CLUSTERS)
    conf = _confidence_rows(f)
    pb = _by_pose(f, POSEBUSTERS)
    to_ref = _by_pose(f, RMSD_CRYSTAL)
    redock = _by_pose(f, REDOCKING)
    redock_exec = str(f.evidence(REDOCKING).get("executor") or "")
    by_path = {str(s.get("path")): s for s in structures}
    render_of = _render_index(renders)
    rows: list[Json] = []
    for m in ms:
        row: Json = {
            "id": m.id,
            "label": m.label,
            "kind": m.kind,
            "source": str(inp.tool(m.executor).get("name") or m.executor),
            "toolId": m.executor,
            "role": m.role,
            "pose": m.pose,
        }
        if m.seed is not None:
            row["seed"] = m.seed
        if m.sample is not None:
            row["sample"] = m.sample
            if m.sample_kind and m.sample_kind != "sample":
                row[m.sample_kind] = m.sample  # e.g. `mode` for a docking mode
        s = by_path.get(m.structure or "")
        if s is not None:
            row["structureId"] = str(s["id"])
            if render_of.get(str(s["id"])):
                row["render"] = render_of[str(s["id"])]
        if m.ligand:
            row["ligand"] = {"url": inp.url(m.ligand), "format": "sdf", "path": m.ligand}
        prc = per_residue_confidence(inp, m.executor)
        row["perResidueConfidence"] = prc is not None
        if prc is not None:
            row["perResidueConfidenceKey"] = str(prc.get("key"))
            if prc.get("range"):
                row["perResidueConfidenceRange"] = list(prc["range"])
        if primary.get(m.pose) is m:
            c = clusters.get(m.pose, {})
            if number(c.get("rmsd_to_medoid_A")) is not None:
                row["rmsdToMedoid"] = c["rmsd_to_medoid_A"]
            if number(c.get("cluster")) is not None:
                row["cluster"] = c["cluster"]
            if number(c.get("site_distance_A")) is not None:
                row["siteDistance"] = c["site_distance_A"]
            cr = conf.get(m.pose)
            if cr is not None:
                vals = tool_values(cr)
                if vals:
                    row["values"] = vals
                if number(cr.get("pocket_plddt")) is not None:
                    row["pocketPlddt"] = cr["pocket_plddt"]
                if number(cr.get("global_plddt")) is not None:
                    row["globalPlddt"] = cr["global_plddt"]
            p = pb.get(m.pose, {})
            if number(p.get("passed")) is not None:
                row["posebusters"] = p["passed"]
                if number(p.get("total")) is not None:
                    row["posebustersTotal"] = p["total"]
            if number(to_ref.get(m.pose, {}).get("rmsd_A")) is not None:
                row["rmsdToReference"] = to_ref[m.pose]["rmsd_A"]
        elif m.role == "control:redocking" and m.executor == redock_exec:
            r = redock.get(m.pose, {})
            if number(r.get("rmsd_A")) is not None:
                row["rmsdToReference"] = r["rmsd_A"]
        rows.append(row)
    crystal, crystal_src = _crystal_rows(inp, f, primary, structures, render_of)
    if crystal_src is not None:
        prov["ensemble.rmsdToMedoid.crystal"] = crystal_src
    prov["ensemble"] = {
        "check": None,
        "tool": None,
        "field": "artifacts (prediction_structure)",
        "n": len(rows) + len(crystal),
    }
    fields = (
        ("rmsdToMedoid", CLUSTERS, "Å"),
        ("cluster", CLUSTERS, None),
        ("siteDistance", CLUSTERS, "Å"),
        ("values", CONFIDENCE, None),
        ("pocketPlddt", CONFIDENCE, None),
        ("globalPlddt", CONFIDENCE, None),
        ("posebusters", POSEBUSTERS, None),
        ("rmsdToReference", REDOCKING, "Å"),
    )
    for name, cid, unit in fields:
        if f.ran(cid) and any(name in r for r in rows):
            prov[f"ensemble.{name}"] = f.source(cid, field="evidence.poses", unit=unit)
    if any("rmsdToReference" in r and r["role"] == "primary" for r in rows):
        prov["ensemble.rmsdToReference.primary"] = f.source(RMSD_CRYSTAL, field="evidence.poses")
    prov["ensemble.perResidueConfidence"] = {
        "check": None,
        "tool": None,
        "field": "configs/executors.yaml outputs (kind plddt, scope residue)",
    }
    return crystal + rows


def _crystal_rows(
    inp: StatsInput,
    f: Findings,
    primary: Mapping[str, Member],
    structures: Sequence[Mapping[str, Any]],
    render_of: Mapping[str, str],
) -> tuple[list[Json], Json | None]:
    """The declared reference entry as an ensemble row, with the medoid's RMSD to its ligand.
    Other source entries (fetched for exposure checks) are not ensemble members."""
    medoid = f.evidence(CLUSTERS).get("medoid")
    pm = primary.get(str(medoid)) if isinstance(medoid, str) else None
    rmsd, src = _crystal_rmsd(f, pm.executor if pm else None, medoid)
    crystals = [s for s in structures if s.get("kind") == "crystal"]
    ref = reference_id(inp.manifest)
    if ref:
        crystals = [s for s in crystals if Path(str(s.get("path", ""))).stem.upper() == ref]
    elif len(crystals) != 1:
        crystals = []
    rows: list[Json] = []
    for s in crystals:
        derived = [str(x) for x in s.get("derivedFrom") or ()]
        sid = derived[0].split(":", 1)[0] if derived else ""
        row: Json = {
            "id": str(s["id"]),
            "structureId": str(s["id"]),
            "label": str(s.get("label") or s["id"]),
            "kind": "crystal",
            "source": inp.source_names.get(sid, sid or "reference"),
            "perResidueConfidence": False,
        }
        if rmsd is not None:
            row["rmsdToMedoid"] = rmsd
        if render_of.get(str(s["id"])):
            row["render"] = render_of[str(s["id"])]
        rows.append(row)
    return rows, (src if rmsd is not None else None)


def reference_id(manifest: Mapping[str, Any]) -> str | None:
    """PDB id of the experimental reference (`outputs.reference_ids`): reference, else receptor."""
    for block in ("reference", "receptor"):
        pdb = _d(manifest.get(block)).get("pdb_id")
        if isinstance(pdb, str) and pdb:
            return pdb.upper()
    return None


def _render_index(renders: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    """Structure id -> PNG URL, the overview view when there is one."""
    out: dict[str, str] = {}
    for r in renders:
        sid, png = str(r.get("structure") or ""), r.get("png")
        if not sid or not png:
            continue
        if sid not in out or r.get("view") == "overview":
            out[sid] = str(png)
    return out


def docking_card(inp: StatsInput, ms: Sequence[Member]) -> Json | None:
    """Settings of the first assessed docking prediction in the manifest: box centre and size,
    the remaining declared settings and the seeds, labelled by the register's dockingParams.
    A box the settings do not state comes from the l2.docking.box evidence (the box checked)."""
    for i, p in enumerate(_ds(inp.manifest.get("predictions"))):
        executor = str(p.get("executor") or "")
        if _family(inp, executor) != "docking" or str(p.get("role", "primary")).startswith(
            "control"
        ):
            continue
        tool = inp.tool(executor)
        params = {str(x.get("key")): x for x in _ds(tool.get("dockingParams"))}
        settings = _d(p.get("settings"))
        grouped: dict[str, Any] = {}
        triples = {
            k[:-2]
            for k in settings
            if k.endswith(("_x", "_y", "_z"))
            and all(f"{k[:-2]}{a}" in settings for a in ("_x", "_y", "_z"))
        }
        for k, v in settings.items():
            base = k[:-2] if k.endswith(("_x", "_y", "_z")) else None
            if base in triples:
                grouped.setdefault(base, [settings[f"{base}{a}"] for a in ("_x", "_y", "_z")])
            else:
                grouped[k] = v
        box = Findings(inp.findings).evidence(BOX)
        from_box: list[str] = []
        for key in ("center", "size"):
            vals = box.get(key)
            if (
                key not in grouped
                and isinstance(vals, list)
                and all(number(x) is not None for x in vals)
            ):
                grouped[key] = list(vals)
                from_box.append(key)
        if from_box and isinstance(box.get("origin"), str) and "box_origin" not in grouped:
            grouped["box_origin"] = box["origin"]
            from_box.append("box_origin")
        seeds = [s for s in p.get("seeds") or () if number(s) is not None]
        if seeds:
            grouped["seed"] = seeds
        rows: list[list[str]] = []
        out_params: list[Json] = []
        for k, v in grouped.items():
            meta = params.get(k, {})
            unit = str(meta["unit"]) if meta.get("unit") else None
            text = ", ".join(fmt(x) for x in v) if isinstance(v, list) else fmt(v)
            label = str(meta.get("label") or k.replace("_", " "))
            rows.append([label, f"{text}{THIN}{unit}" if unit else text])
            param: Json = {"key": k, "label": label, "value": text, "declared": bool(meta)}
            if k in from_box:
                param["check"] = BOX
            if unit:
                param["unit"] = unit
            out_params.append(param)
        if not rows:
            return None
        poses = sum(1 for m in ms if m.executor == executor and m.role == p.get("role", "primary"))
        if poses:
            rows.append(["poses parsed", fmt(poses)])
        return {
            "tool": str(tool.get("name") or executor),
            "toolId": executor,
            "rows": rows,
            "params": out_params,
            "source": {
                "check": None,
                "tool": executor,
                "field": f"manifest.predictions[{i}].settings",
            },
        }
    return None


# ---------------------------------------------------------------- entry points


@dataclass
class StatsResult:
    stats: Json
    docking: Json | None


def build(
    inp: StatsInput,
    ms: Sequence[Member],
    structures: Sequence[Mapping[str, Any]],
    renders: Sequence[Mapping[str, Any]],
) -> StatsResult:
    """The `stats` block and the record-level `docking` card. Keys only for computed blocks."""
    f = Findings(inp.findings)
    prov: Json = {}
    primary = primary_members(inp, ms)
    order = [str(p.get("pose")) for p in _ds(f.evidence(CLUSTERS).get("poses"))]
    primary_executor = next(iter(primary.values())).executor if primary else None
    stats: Json = {}
    blocks: list[tuple[str, Callable[[], Any]]] = [
        ("seeds", lambda: seeds_block(inp, f, prov)),
        ("pairwise", lambda: pairwise_block(f, prov)),
        ("posebusters", lambda: posebusters_block(f, prov)),
        ("physics", lambda: physics_block(f, order, primary, prov)),
        ("interactions", lambda: interactions_block(f, prov)),
        ("site", lambda: site_block(f, prov)),
        ("pose", lambda: pose_block(f, primary_executor, prov)),
        ("metrics", lambda: metrics_block(inp, f, primary, prov)),
        ("agreement", lambda: agreement_block(f, prov)),
        ("clusters", lambda: clusters_block(f, prov)),
        ("pae", lambda: pae_block(inp, f, prov)),
        ("reference", lambda: reference_block(f, prov)),
        ("ensemble", lambda: ensemble_block(inp, f, ms, structures, renders, prov)),
    ]
    for name, make in blocks:
        value = make()
        if value:
            stats[name] = value
    ev = f.evidence(CLUSTERS)
    for src, dst in (
        ("site_placement", "sitePlacement"),
        ("pose_accuracy", "poseAccuracy"),
        ("medoid", "medoid"),
    ):
        if isinstance(ev.get(src), str):
            stats[dst] = ev[src]
            prov[dst] = f.source(CLUSTERS, field=f"evidence.{src}")
    rep = f.evidence(FINGERPRINT).get("representative")
    if "interactions" in stats and isinstance(rep, str):
        stats["interactionsPose"] = rep
        prov["interactionsPose"] = f.source(FINGERPRINT, field="evidence.representative")
    auc = number(f.measures(ENRICHMENT).get("auc"))
    if auc is not None:
        stats["auc"] = auc
        prov["auc"] = f.source(ENRICHMENT, field="measurements.auc")
    if stats:
        kept = {k: v for k, v in prov.items() if _block_of(k) in stats}
        for block in [b for b in stats if b != "provenance"]:
            if block not in kept:
                named = {v.get("check") for k, v in kept.items() if _block_of(k) == block}
                kept[block] = {"check": None, "checks": sorted(str(c) for c in named if c)}
                kept[block]["tool"] = None
                if isinstance(stats[block], list):
                    kept[block]["n"] = len(stats[block])
        stats["provenance"] = kept
    return StatsResult(stats=stats, docking=docking_card(inp, ms))


def _block_of(key: str) -> str:
    return key.split(".", 1)[0]


def caption_sha(caption: str) -> str | None:
    """sha256 prefix that `pah.report.renders.figure_entries` writes into a render caption."""
    m = _CAPTION_SHA.search(caption)
    return m.group("sha") if m else None


# ---------------------------------------------------------------- absent blocks and per-pose checks


def add_status(stats: Json, inp: StatsInput, *, pre_run: bool) -> None:
    """`stats.status` for blocks the UI shows as absent: `na` when the run's executors cannot
    produce the block, `pending` when it is not computed yet. `stats.pae` carries the `na`
    status itself when no executor of the run declares a PAE output (configs/executors.yaml)."""
    status: Json = {}
    if not inp.tools:
        return
    names = [str(inp.tool(e).get("name") or e) for e in inp.tools]
    if "pae" not in stats:
        declares = [e for e in inp.tools if any(o.get("kind") == "pae" for o in inp.outputs(e))]
        if not inp.tools:
            status["pae"] = {"status": "na", "reason": "no executor declared"}
        elif not declares:
            who = ", ".join(names)
            status["pae"] = {
                "status": "na",
                "reason": f"{who} declares no PAE output (configs/executors.yaml)",
            }
        else:
            why = "pending predictions" if pre_run else f"not computed by {CONFIDENCE}"
            status["pae"] = {"status": "pending", "reason": why}
    if "agreement" not in stats:
        if len(inp.tools) <= 1:
            who = names[0] if names else "no executor"
            status["agreement"] = {
                "status": "na",
                "reason": f"one executor ({who}); method agreement needs two",
            }
        else:
            why = "pending predictions" if pre_run else f"not computed by {AGREEMENT}"
            status["agreement"] = {"status": "pending", "reason": why}
    for block in ("seeds", "posebusters", "physics", "interactions", "ensemble"):
        if block not in stats and pre_run:
            status[block] = {"status": "pending", "reason": "pending predictions"}
    if status:
        stats["status"] = status
        prov = stats.setdefault("provenance", {})
        prov["status"] = {"check": None, "checks": [], "tool": None, "source": "configs"}


def _pose_result(row: Mapping[str, Any], gate: str) -> str:
    """Per-pose result from the row's own flags: a `failed` list, `pass`/`ok` booleans or a
    `gate`. Without a flag the row is reported (values shown, no badge)."""
    if str(row.get("gate")) in {"pass", "warn", "stop"}:
        return str(row["gate"])
    failed = row.get("failed")
    flags = [row[k] for k in ("pass", "ok", "passed_all") if isinstance(row.get(k), bool)]
    flag: bool | None = flags[0] if flags else None
    if isinstance(failed, list):
        flag = not failed if flag is None else flag
    if flag is None:
        return "reported"
    if flag:
        return "pass"
    return gate if gate in {"warn", "stop"} else "warn"


def pose_checks(
    findings: Sequence[Mapping[str, Any]], title: Callable[[str], str]
) -> dict[str, list[Json]]:
    """Pose id -> output checks that reported a row for it (`evidence.poses[]`)."""
    out: dict[str, list[Json]] = {}
    for f in findings:
        if f.get("layer") not in (4, 5) or f.get("gate") == "skip":
            continue
        cid = str(f.get("check_id"))
        for row in _ds(_d(f.get("evidence")).get("poses")):
            pose = row.get("pose")
            if not pose:
                continue
            entry: Json = {
                "id": cid,
                "name": title(cid),
                "result": _pose_result(row, str(f.get("gate"))),
            }
            if isinstance(row.get("failed"), list) and row["failed"]:
                entry["failed"] = [str(x) for x in row["failed"]]
            out.setdefault(str(pose), []).append(entry)
    return out
