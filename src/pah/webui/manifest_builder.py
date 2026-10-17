"""Turns the UI's run settings into a harness manifest.

`plan_run` validates the settings without network access and returns a manifest skeleton.
`complete_manifest` then resolves what needs a source: the reference chain through SIFTS and the
sequence from UniProt. Nothing is invented. When a lookup fails the field stays unset, the
reason is recorded as a note, and the layer 0 and 1 checks report the gap.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from pydantic.alias_generators import to_camel

from pah.webui.catalog import (
    Catalog,
    CatalogProtein,
    Executor,
    UnknownToolError,
    load_catalog,
    load_executors,
    resolve_tools,
)

ALL_LAYERS = (0, 1, 2, 3, 4, 5)
EXECUTORS_NOT_RUN = "not run (checks only)"
UNIPROT = re.compile(r"[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}")
PDB_ID = re.compile(r"[0-9][A-Z0-9]{3}")
_CID = re.compile(r"(?:cid[:\s]*)?(\d{1,12})", re.IGNORECASE)
_CCD = re.compile(r"ccd[:\s]+([A-Za-z0-9]{1,5})", re.IGNORECASE)
_SLUG = re.compile(r"[^a-z0-9]+")

Note = Callable[[str], None]


class SettingsError(ValueError):
    """Settings that cannot become a run. The HTTP layer answers 422."""


class RunSettings(BaseModel):
    """What the New-run form submits. Wire keys are camelCase."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")

    task: str = "ligand_pose"
    tools: list[str] = Field(default_factory=list)
    target: str | None = None
    partner: str | None = None
    ligand: str | None = None
    reference: str | None = None
    ph: float | None = Field(None, ge=0, le=14)
    seeds: int = Field(5, ge=0, le=100)
    name: str | None = None
    claim: str | None = None
    layers: list[int] = Field(default_factory=lambda: list(ALL_LAYERS))
    halt: bool = False
    manifest: str | None = Field(None, description="Example manifest under examples/, run as-is")
    profile: str | None = Field(None, description="Profile recorded with the job")

    @field_validator(
        "task", "target", "partner", "ligand", "reference", "name", "claim", "manifest", "profile",
        mode="before",
    )  # fmt: skip
    @classmethod
    def _blank_is_none(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v

    @field_validator("target", "partner")
    @classmethod
    def _accession(cls, v: str | None) -> str | None:
        if v is None:
            return None
        acc = v.upper()
        if not UNIPROT.fullmatch(acc):
            raise ValueError(f"{v!r} is not a UniProt accession")
        return acc

    @field_validator("reference")
    @classmethod
    def _pdb(cls, v: str | None) -> str | None:
        if v is None:
            return None
        pid = v.upper()
        if not PDB_ID.fullmatch(pid):
            raise ValueError(f"{v!r} is not a PDB id")
        return pid

    @field_validator("layers")
    @classmethod
    def _layers(cls, v: list[int]) -> list[int]:
        out = sorted(set(v))
        if not out or any(x < 0 or x > 5 for x in out):
            raise ValueError("layers must be a non-empty list of integers 0-5")
        return out

    @field_validator("tools")
    @classmethod
    def _tools(cls, v: list[str]) -> list[str]:
        return [t.strip() for t in v if t and t.strip()]


def parse_settings(body: Any) -> RunSettings:
    try:
        return RunSettings.model_validate(body)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) or 'body'}: {e['msg']}" for e in exc.errors()
        )
        raise SettingsError(problems) from exc


@dataclass
class RunPlan:
    """A validated run: task, tools, display metadata and the manifest to run."""

    pah_task: str
    ui_task: str
    task_title: str
    tools: tuple[str, ...]
    executor: str | None
    lookups: tuple[str, ...]
    seeds: int
    layers: tuple[int, ...]
    halt: bool
    profile: str
    name: str
    settings: RunSettings
    manifest_path: Path | None = None
    manifest: dict[str, Any] | None = None
    notes: list[str] = field(default_factory=list)


def _example_path(value: str, examples_dir: Path | None) -> Path:
    if examples_dir is None:
        raise SettingsError("no examples directory on this server; give run settings instead")
    root = examples_dir.resolve()
    raw = Path(value)
    candidates = [raw] if raw.is_absolute() else [root.parent / raw, root / raw]
    for c in candidates:
        path = c / "manifest.yaml" if c.is_dir() else c
        resolved = path.resolve()
        if resolved.is_relative_to(root) and resolved.is_file() and resolved.suffix == ".yaml":
            return resolved
    raise SettingsError(f"manifest {value!r} is not a manifest under {root}")


def _slug(text: str) -> str:
    return _SLUG.sub("_", text.lower()).strip("_") or "protein"


def _protein_id(acc: str, entry: CatalogProtein | None, taken: set[str]) -> str:
    base = _slug(entry.names[0]) if entry else acc.lower()
    pid, n = base, 2
    while pid in taken:
        pid, n = f"{base}_{n}", n + 1
    taken.add(pid)
    return pid


def _executor_version(executor: str) -> str | None:
    from pah.runtimes.registry import load_runtimes

    try:
        rt = load_runtimes().get(executor)
    except (KeyError, OSError, ValueError):
        return None
    return rt.native.version if rt.native else None


def _ligand(value: str, catalog: Catalog, notes: list[str]) -> dict[str, Any]:
    entry = catalog.ligand_for(value)
    if entry is not None:
        lig: dict[str, Any] = {"id": _slug(entry.names[0]), "smiles": entry.smiles}
        if entry.ccd:
            lig["ccd"] = entry.ccd
        if entry.pubchem_cid is not None:
            lig["pubchem_cid"] = entry.pubchem_cid
        ids = ", ".join(
            x
            for x in (
                f"CCD {entry.ccd}" if entry.ccd else "",
                f"PubChem {entry.cid}" if entry.cid else "",
            )
            if x
        )
        notes.append(f"ligand {entry.names[0]} from configs/catalog.yaml ({ids or 'SMILES only'})")
        return lig
    if m := _CCD.fullmatch(value):
        code = m.group(1).upper()
        notes.append(f"ligand given as CCD {code}; SMILES taken from the CCD record")
        return {"id": code.lower(), "ccd": code}
    if m := _CID.fullmatch(value):
        notes.append(f"ligand given as PubChem CID {m.group(1)}; SMILES taken from PubChem")
        return {"id": f"cid_{m.group(1)}", "pubchem_cid": int(m.group(1))}
    notes.append(
        "ligand SMILES is not in configs/catalog.yaml; no CCD or PubChem identifier declared, "
        "so the cross-source InChIKey check does not apply"
    )
    return {"id": "ligand", "smiles": value}


def plan_run(
    settings: RunSettings,
    *,
    server_profile: str,
    examples_dir: Path | None,
    catalog: Catalog | None = None,
    executors: tuple[Executor, ...] | None = None,
    known_profiles: tuple[str, ...] | None = None,
) -> RunPlan:
    """Validates settings and builds the manifest skeleton. No network access.

    Raises SettingsError for an unknown task, tool, profile or example manifest.
    """
    from pah.config import available_profiles
    from pah.core.manifest import load_manifest
    from pah.core.task import load_task

    cat = catalog or load_catalog()
    register = executors if executors is not None else load_executors()
    profiles = known_profiles if known_profiles is not None else tuple(available_profiles())
    profile = settings.profile or server_profile
    if profile not in profiles and profile != server_profile:
        raise SettingsError(f"unknown profile {profile!r}; known: {', '.join(profiles)}")
    notes: list[str] = []
    if profile != server_profile:
        notes.append(
            f"profile {profile} recorded; this server runs checks with profile {server_profile}"
        )
    try:
        choice = resolve_tools(settings.tools, cat, register)
    except UnknownToolError as exc:
        raise SettingsError(str(exc)) from exc

    if settings.manifest:
        path = _example_path(settings.manifest, examples_dir)
        try:
            man = load_manifest(path)
            spec = load_task(man.task)
        except (OSError, ValueError) as exc:
            raise SettingsError(f"{settings.manifest}: {exc}") from exc
        declared = man.model.executor if man.model else None
        tools = tuple(dict.fromkeys([*([declared] if declared else []), *choice.tools]))
        rel = path.parent.relative_to(examples_dir.resolve()) if examples_dir else path.parent
        return RunPlan(
            pah_task=spec.id,
            ui_task=cat.ui_task_id(spec.id),
            task_title=spec.title,
            tools=tools,
            executor=declared,
            lookups=choice.lookups,
            seeds=len(man.model.seeds) if man.model else 0,
            layers=tuple(settings.layers),
            halt=settings.halt,
            profile=profile,
            name=settings.name or f"example {rel.as_posix()} · {spec.title.lower()}",
            settings=settings,
            manifest_path=path,
            notes=notes,
        )

    task = cat.task(settings.task)
    pah_task = task.pah if task else settings.task
    try:
        spec = load_task(pah_task)
    except (OSError, ValueError) as exc:
        raise SettingsError(f"unknown task {settings.task!r}") from exc
    if settings.target is None:
        raise SettingsError("target: a UniProt accession is required")
    inputs = set(task.inputs) if task and task.inputs else None

    def takes(name: str) -> bool:
        return inputs is None or name in inputs

    tools, executor = choice.tools, choice.executor
    if not tools and task:
        defaults = resolve_tools(list(task.default_tools), cat, register)
        tools, executor = defaults.tools, defaults.executor
        notes.append(f"no tools selected; task defaults used: {', '.join(tools)}")
    target = cat.protein(settings.target)
    taken: set[str] = set()
    proteins: list[dict[str, Any]] = [
        {"id": _protein_id(settings.target, target, taken), "uniprot": settings.target}
    ]
    reference = settings.reference if takes("reference") else None
    if settings.reference and not reference:
        notes.append(f"reference {settings.reference} ignored: task {spec.id} takes no reference")
    if reference:
        proteins[0]["pdb_id"] = reference
    if settings.partner:
        if takes("partner"):
            partner = cat.protein(settings.partner)
            row = {"id": _protein_id(settings.partner, partner, taken), "uniprot": settings.partner}
            if reference:
                row["pdb_id"] = reference
            proteins.append(row)
        else:
            notes.append(f"partner {settings.partner} ignored: task {spec.id} takes no partner")
    manifest: dict[str, Any] = {"task": spec.id, "proteins": proteins}
    if settings.claim:
        manifest["claim"] = settings.claim
    if settings.ligand:
        if takes("ligand") or takes("series"):
            manifest["ligands"] = [_ligand(settings.ligand, cat, notes)]
        else:
            notes.append(f"ligand ignored: task {spec.id} takes no ligand")
    if reference:
        manifest["receptor"] = {"pdb_id": reference, "chains": []}
    if settings.ph is not None:
        if takes("ph"):
            manifest["ph"] = settings.ph
        else:
            notes.append(f"pH ignored: task {spec.id} takes no pH")
    model: dict[str, Any] = {"seeds": list(range(settings.seeds))}
    if executor:
        model["executor"] = executor
        version = _executor_version(executor)
        if version:
            model["version"] = version
            notes.append(f"model version {version} from configs/runtimes.yaml (pinned runtime)")
    manifest["model"] = model
    label = target.label if target else settings.target
    name = settings.name or f"{label} · {(task.name if task else spec.title).lower()}"
    return RunPlan(
        pah_task=spec.id,
        ui_task=task.id if task else cat.ui_task_id(spec.id),
        task_title=spec.title,
        tools=tools,
        executor=executor,
        lookups=choice.lookups,
        seeds=settings.seeds,
        layers=tuple(settings.layers),
        halt=settings.halt,
        profile=profile,
        name=name,
        settings=settings,
        manifest=manifest,
        notes=notes,
    )


def _err(exc: Exception) -> str:
    reason = getattr(exc, "reason", None)
    detail = getattr(exc, "detail", None)
    if reason is not None and detail is not None:
        return f"{getattr(reason, 'value', reason)}: {detail}"
    return f"{type(exc).__name__}: {exc}"


def complete_manifest(skeleton: dict[str, Any], sources: Any, note: Note) -> dict[str, Any]:
    """Fills chain, receptor chains and sequence from SIFTS and UniProt.

    `sources` is a `pah.sources.Sources`. Every decision and every failed lookup is passed to
    `note`. Returns a new manifest dict; the skeleton is not changed.
    """
    from pah.sources import SourceUnavailableError

    man = copy.deepcopy(skeleton)
    proteins: list[dict[str, Any]] = man.get("proteins") or []
    receptor = man.get("receptor")
    sifts_segments: list[Any] | None = None
    sifts_error: str | None = None
    ref = next((p["pdb_id"] for p in proteins if p.get("pdb_id")), None)
    if ref:
        try:
            sifts_segments = list(sources.pdbe.sifts(ref).segments)
        except SourceUnavailableError as exc:
            sifts_error = _err(exc)
    chains: list[str] = []
    for i, p in enumerate(proteins):
        acc = p["uniprot"]
        span: tuple[int, int] | None = None
        if p.get("pdb_id"):
            pid = p["pdb_id"]
            if sifts_segments is None:
                if i == 0:
                    p["chain"] = "A"
                    chains.append("A")
                    note(f"SIFTS {pid.lower()} unavailable ({sifts_error}); chain A assumed")
                else:
                    note(f"SIFTS {pid.lower()} unavailable ({sifts_error}); no chain set for {acc}")
            else:
                segs = [s for s in sifts_segments if s.uniprot == acc]
                mapped = sorted({s.chain_id for s in segs})
                if mapped:
                    chain = mapped[0]
                    own = [s for s in segs if s.chain_id == chain]
                    span = (min(s.unp_start for s in own), max(s.unp_end for s in own))
                    p["chain"] = chain
                    chains.append(chain)
                    note(
                        f"chain {chain} of {pid} for {acc} via SIFTS "
                        f"(mapped chains: {', '.join(mapped)}; UniProt {span[0]}-{span[1]})"
                    )
                else:
                    others = sorted({s.uniprot for s in sifts_segments})
                    if i == 0:
                        p["chain"] = "A"
                        chains.append("A")
                        note(
                            f"SIFTS maps no chain of {pid} to {acc} "
                            f"(maps {', '.join(others) or 'none'}); chain A assumed"
                        )
                    else:
                        p.pop("pdb_id", None)
                        note(
                            f"{pid} has no chain mapped to {acc} by SIFTS; "
                            "reference not declared for it"
                        )
        try:
            entry = sources.uniprot.entry(acc)
        except SourceUnavailableError as exc:
            note(f"sequence for {acc} not set: uniprot unavailable ({_err(exc)})")
            continue
        if span is not None:
            p["sequence"] = entry.sequence[span[0] - 1 : span[1]]
            note(
                f"sequence for {acc}: UniProt residues {span[0]}-{span[1]} "
                f"(SIFTS range of chain {p['chain']}), length {len(p['sequence'])}"
            )
        else:
            p["sequence"] = entry.sequence
            note(f"sequence for {acc}: canonical UniProt sequence, length {len(entry.sequence)}")
    if isinstance(receptor, dict):
        receptor["chains"] = list(dict.fromkeys(chains))
    return man
