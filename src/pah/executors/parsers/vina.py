"""AutoDock Vina output (docs/EXECUTORS.md section 6).

`path` is a multi-model `_out.pdbqt` (`MODEL n` ... `ENDMDL`, best first) or a folder of them, one
per seed run. Each model carries `REMARK VINA RESULT: <energy> <rmsd_lb> <rmsd_ub>`. Ligand bond
orders come from the SMILES that Meeko stores in `REMARK SMILES` lines; without them the PDBQT
atoms are read by RDKit and bond orders assigned from the declared SMILES.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pah.core.manifest import Manifest, PredictionInput
from pah.executors.base import Family, ParseError, Pose, PredictionSet, parser
from pah.executors.parsers._common import ParseContext, pose_id, seed_from_name
from pah.executors.structure import mol_from_pdb_block, pdbqt_to_pdb_lines

_RESULT = re.compile(r"^REMARK VINA RESULT:\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)")
_GLOB = "<ligand>_out.pdbqt"


def _models(text: str) -> list[list[str]]:
    models: list[list[str]] = []
    current: list[str] | None = None
    for line in text.splitlines():
        if line.startswith("MODEL"):
            current = []
        elif line.startswith("ENDMDL"):
            if current is not None:
                models.append(current)
            current = None
        elif current is not None:
            current.append(line)
    if not models and any(ln.startswith(("ATOM", "HETATM")) for ln in text.splitlines()):
        models.append(text.splitlines())
    return models


def _scores(model: list[str]) -> dict[str, float]:
    for line in model:
        m = _RESULT.match(line)
        if m:
            return {
                "vina_affinity": float(m.group(1)),
                "rmsd_lb": float(m.group(2)),
                "rmsd_ub": float(m.group(3)),
            }
    return {}


def _meeko_mols(ctx: ParseContext, path: Path, n_models: int) -> list[Any] | None:
    """One RDKit molecule per pose from Meeko, or None when Meeko cannot rebuild them."""
    try:
        from meeko import PDBQTMolecule, RDKitMolCreate
        from rdkit import Chem
    except ImportError:
        ctx.issues.append("meeko not importable; ligand read from PDBQT atoms")
        return None
    try:
        pdbqt = PDBQTMolecule.from_file(str(path), skip_typing=True)
        mols = [m for m in RDKitMolCreate.from_pdbqt_mol(pdbqt) if m is not None]
    except Exception as exc:
        ctx.issues.append(f"{path.name}: meeko could not rebuild the ligand ({exc})")
        return None
    if len(mols) != 1 or mols[0].GetNumConformers() != n_models:
        ctx.issues.append(
            f"{path.name}: meeko returned {len(mols)} molecule(s); ligand read from PDBQT atoms"
        )
        return None
    mol = mols[0]
    out = []
    for conf in mol.GetConformers():
        one = Chem.Mol(mol)
        one.RemoveAllConformers()
        one.AddConformer(Chem.Conformer(conf), assignId=True)
        out.append(one)
    return out


def _files(ctx: ParseContext, root: Path) -> list[tuple[int | None, Path]]:
    if root.is_file():
        files = [root]
    else:
        files = sorted(root.glob("*.pdbqt"))
        out_files = [f for f in files if f.name.endswith("_out.pdbqt")]
        files = out_files or files
    if not files:
        raise ParseError(f"vina: no {_GLOB} at {root}")
    named = [seed_from_name(f.name) for f in files]
    if all(s is not None for s in named):
        return list(zip(named, files, strict=True))
    if any(s is not None for s in named):
        ctx.issues.append("seed tokens found on some PDBQT names only; seeds from declaration")
    return list(zip(ctx.seeds_for(len(files)), files, strict=True))


@parser("vina", family=Family.DOCKING)
def parse_vina(spec: PredictionInput, manifest: Manifest, workdir: Path) -> PredictionSet:
    ctx = ParseContext(spec, manifest, workdir, Family.DOCKING)
    root = ctx.require(ctx.source, "Vina output")
    receptor = ctx.receptor()
    poses: list[Pose] = []
    for seed, path in _files(ctx, root):
        models = _models(path.read_text(encoding="utf-8", errors="replace"))
        if not models:
            raise ParseError(f"vina: {path} holds no MODEL/ENDMDL blocks or atoms")
        mols = _meeko_mols(ctx, path, len(models))
        for i, model in enumerate(models):
            pid = pose_id(ctx.executor, seed, "mode", i)
            scores = _scores(model)
            if not scores:
                ctx.issues.append(f"{pid}: no REMARK VINA RESULT line")
            if mols is not None:
                mol, assign = mols[i], False
            else:
                mol = mol_from_pdb_block("\n".join([*pdbqt_to_pdb_lines(model), "END", ""]))
                assign = True
                if mol is None:
                    ctx.issues.append(f"{pid}: RDKit could not read the PDBQT atoms")
                    continue
            poses.append(
                ctx.docking_pose(
                    pid=pid,
                    mol=mol,
                    receptor=receptor,
                    seed=seed,
                    sample=i,
                    rank=i,
                    scores=scores,
                    files=[path],
                    bond_orders=assign,
                )
            )
    return ctx.result(poses)
