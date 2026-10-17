"""Shared parser plumbing: declared ligand, seeds, pose ids and pose construction."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pah.core.manifest import LigandInput, Manifest, PredictionInput
from pah.executors.base import Family, ParseError, Pose, PredictionSet
from pah.executors.structure import (
    assemble_complex,
    assign_bond_orders,
    extract_ligand,
    residue_plddt,
    write_sdf,
)

_SEED_DIR = re.compile(r"^seed[_-]?(\d+)$")
_SEED_TOKEN = re.compile(r"(?:^|[_\-.])seed[_-]?(\d+)(?=$|[_\-.])")


def seed_from_name(name: str) -> int | None:
    """Seed from a `seed<N>` / `seed_<N>` / `seed-<N>` token in a file or directory name."""
    m = _SEED_TOKEN.search(name)
    return int(m.group(1)) if m else None


def seed_dirs(root: Path) -> list[tuple[int, Path]]:
    """`seed_<n>` subdirectories of `root`, sorted by seed."""
    if not root.is_dir():
        return []
    found = [
        (int(m.group(1)), p)
        for p in root.iterdir()
        if p.is_dir() and (m := _SEED_DIR.match(p.name))
    ]
    return sorted(found)


def floats(data: Mapping[str, Any], keys: Iterable[str] | None = None) -> dict[str, float]:
    """Numeric scalar entries of a mapping; nested `{str: number}` maps become `key.sub`."""
    out: dict[str, float] = {}
    for key in keys if keys is not None else data.keys():
        if key not in data:
            continue
        value = data[key]
        if isinstance(value, bool | int | float):
            out[key] = float(value)
        elif isinstance(value, Mapping) and keys is None:
            for sub, v in value.items():
                if isinstance(v, int | float) and not isinstance(v, bool):
                    out[f"{key}.{sub}"] = float(v)
    return out


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ParseError(f"{path}: unreadable JSON ({exc})") from exc


def pose_id(executor: str, seed: int | None, kind: str, index: int) -> str:
    parts = [executor]
    if seed is not None:
        parts.append(f"seed{seed}")
    parts.append(f"{kind}{index}")
    return "/".join(parts)


def _ligand_smiles(lig: LigandInput, manifest: Manifest) -> str | None:
    if lig.smiles:
        return lig.smiles
    if lig.file is not None:
        from rdkit import Chem

        path = manifest.path(lig.file)
        mol = None
        if path.suffix.lower() in (".sdf", ".mol"):
            mol = next(iter(Chem.SDMolSupplier(str(path))), None)
        if mol is not None:
            return str(Chem.MolToSmiles(mol))
    return None


@dataclass
class ParseContext:
    """One parse: the manifest entry, the declared ligand and the issues found so far."""

    spec: PredictionInput
    manifest: Manifest
    workdir: Path
    family: Family
    issues: list[str] = field(default_factory=list)
    with_ligand: bool = True

    def __post_init__(self) -> None:
        self.ligand = self._declared_ligand() if self.with_ligand else None
        self.smiles = (
            _ligand_smiles(self.ligand, self.manifest) if self.ligand is not None else None
        )
        if self.ligand is not None and self.smiles is None:
            self.issues.append(
                f"ligand {self.ligand.id}: no SMILES or readable SDF declared; "
                "bond orders from coordinates only"
            )

    @property
    def executor(self) -> str:
        return self.spec.executor

    @property
    def source(self) -> Path:
        return self.manifest.path(self.spec.path)

    def _declared_ligand(self) -> LigandInput | None:
        ligands = self.manifest.ligands
        if self.spec.ligand is not None:
            for lig in ligands:
                if lig.id == self.spec.ligand:
                    return lig
            self.issues.append(f"prediction ligand {self.spec.ligand!r} is not a manifest ligand")
            return None
        if len(ligands) == 1:
            return ligands[0]
        if len(ligands) > 1:
            self.issues.append(
                "several manifest ligands and no prediction ligand id; no ligand assigned"
            )
        return None

    def require(self, path: Path, what: str) -> Path:
        if not path.exists():
            raise ParseError(f"{self.executor}: {what} not found at {path}")
        return path

    def seeds_for(self, n_runs: int) -> list[int | None]:
        """Seeds for `n_runs` run directories that do not name their seed."""
        seeds = list(self.spec.seeds)
        if len(seeds) == n_runs:
            return list(seeds)
        if seeds:
            self.issues.append(
                f"{len(seeds)} seeds declared for {n_runs} run(s); seeds left unrecorded"
            )
        return [None] * n_runs

    def pose_dir(self, pid: str) -> Path:
        d = self.workdir.joinpath(*pid.split("/"))
        d.mkdir(parents=True, exist_ok=True)
        return d

    # Co-folding -------------------------------------------------------------------------------

    def cofolding_pose(
        self,
        *,
        pid: str,
        structure: Path,
        seed: int | None,
        sample: int,
        rank: int,
        scores: Mapping[str, float],
        files: Sequence[Path],
        plddt: tuple[tuple[float, ...], tuple[tuple[str, int], ...]] | None = None,
        pae: Path | None = None,
    ) -> Pose:
        """A co-folding pose; pLDDT from B-factors when not given, ligand SDF when declared."""
        if plddt is None:
            plddt = residue_plddt(structure)
        ligand_sdf: Path | None = None
        if self.ligand is not None:
            issues: list[str] = []
            ligand_sdf = extract_ligand(
                structure,
                self.smiles,
                self.pose_dir(pid) / "ligand.sdf",
                resname=self.ligand.ccd,
                issues=issues,
                name=self.ligand.id,
            )
            self.issues.extend(f"{pid}: {i}" for i in issues)
        return Pose(
            id=pid,
            executor=self.executor,
            family=self.family,
            structure=structure,
            seed=seed,
            sample=sample,
            rank=rank,
            ligand=ligand_sdf,
            ligand_id=self.ligand.id if self.ligand is not None else None,
            scores=dict(scores),
            plddt=plddt[0] if plddt[0] else None,
            plddt_residues=plddt[1] if plddt[0] else None,
            pae=pae,
            files=tuple(dict.fromkeys(files)),
        )

    def save_pae(self, pid: str, matrix: Any) -> Path:
        import numpy as np

        out = self.pose_dir(pid) / "pae.npy"
        np.save(out, np.asarray(matrix, dtype=np.float32))
        return out

    # Docking ----------------------------------------------------------------------------------

    def receptor(self) -> Path:
        rec = self.spec.receptor
        if rec is None and self.manifest.receptor is not None:
            rec = self.manifest.receptor.file
        if rec is None:
            raise ParseError(
                f"{self.executor}: docking output needs the receptor as docked "
                "(prediction receptor or manifest receptor.file)"
            )
        return self.require(self.manifest.path(rec), "receptor")

    def docking_pose(
        self,
        *,
        pid: str,
        mol: Any,
        receptor: Path,
        seed: int | None,
        sample: int,
        rank: int,
        scores: Mapping[str, float],
        files: Sequence[Path],
        bond_orders: bool = True,
    ) -> Pose:
        """A docking pose: ligand SDF (bond orders from the declared SMILES) and a complex PDB."""
        from rdkit import Chem

        issues: list[str] = []
        try:
            heavy = Chem.RemoveHs(mol)
        except Exception:
            heavy = Chem.RemoveHs(mol, sanitize=False)
        if bond_orders:
            heavy = assign_bond_orders(heavy, self.smiles, issues, "docked ligand")
        self.issues.extend(f"{pid}: {i}" for i in issues)
        d = self.pose_dir(pid)
        name = self.ligand.id if self.ligand is not None else None
        sdf = write_sdf(heavy, d / "ligand.sdf", name)
        complex_pdb = assemble_complex(receptor, sdf, d / "complex.pdb")
        return Pose(
            id=pid,
            executor=self.executor,
            family=self.family,
            structure=complex_pdb,
            seed=seed,
            sample=sample,
            rank=rank,
            ligand=sdf,
            ligand_id=name,
            scores=dict(scores),
            files=tuple(dict.fromkeys([*files, receptor])),
        )

    # Result -----------------------------------------------------------------------------------

    def result(
        self, poses: Sequence[Pose], settings: Mapping[str, Any] | None = None
    ) -> PredictionSet:
        if not poses:
            raise ParseError(f"{self.executor}: no poses under {self.source}")
        merged: dict[str, Any] = dict(self.spec.settings)
        merged.update(settings or {})
        return PredictionSet(
            executor=self.executor,
            family=self.family,
            role=self.spec.role,
            source=self.source,
            poses=tuple(poses),
            version=self.spec.version,
            settings=merged,
            issues=tuple(self.issues),
        )
