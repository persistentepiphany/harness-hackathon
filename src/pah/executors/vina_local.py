"""Local AutoDock Vina runs through the Python bindings, for CPU hosts and the sandbox.

Writes the layout the `vina` parser reads: one `<ligand>_seed<N>_out.pdbqt` per seed, plus the
prepared receptor (`receptor_H.pdb`, `receptor.pdbqt`) and `vina_run.json` with every setting.
Receptor hydrogens come from PDBFixer at the stated pH; the ligand is protonated with
Dimorphite-DL at that pH when it is installed, otherwise the declared SMILES is used and this is
recorded in the run file.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pah.core.manifest import Manifest


@dataclass
class VinaRun:
    receptor_pdb: Path
    receptor_pdbqt: Path
    outputs: list[Path]
    center: list[float]
    size: list[float]
    box_origin: str
    smiles_declared: str
    smiles_docked: str
    seeds: list[int]
    exhaustiveness: int
    num_modes: int
    scoring: str = "vina"
    vina_version: str | None = None
    notes: list[str] = field(default_factory=list)

    def settings(self) -> dict[str, str | int | float | bool]:
        c, s = self.center, self.size
        return {
            "center_x": c[0],
            "center_y": c[1],
            "center_z": c[2],
            "size_x": s[0],
            "size_y": s[1],
            "size_z": s[2],
            "exhaustiveness": self.exhaustiveness,
            "num_modes": self.num_modes,
            "scoring": self.scoring,
            "box_origin": self.box_origin,
        }


def prepare_receptor(source: Path, out_dir: Path, ph: float) -> tuple[Path, Path]:
    """Protein-only receptor with hydrogens at `ph` (PDB) and its rigid PDBQT."""
    import gemmi
    from meeko import MoleculePreparation, PDBQTWriterLegacy, Polymer, ResidueChemTemplates
    from openmm.app import PDBFile
    from pdbfixer import PDBFixer

    st = gemmi.read_structure(str(source))
    st.setup_entities()
    st.remove_ligands_and_waters()
    st.remove_hydrogens()
    st.remove_empty_chains()
    bare = out_dir / "receptor_noH.pdb"
    st.write_pdb(str(bare))
    fixer = PDBFixer(filename=str(bare))
    fixer.findMissingResidues()
    fixer.missingResidues = {}
    fixer.findMissingAtoms()
    fixer.addMissingAtoms()
    fixer.addMissingHydrogens(ph)
    pdb = out_dir / "receptor_H.pdb"
    with pdb.open("w") as fh:
        PDBFile.writeFile(fixer.topology, fixer.positions, fh, keepIds=True)
    templates = ResidueChemTemplates.create_from_defaults()
    poly = Polymer.from_pdb_string(pdb.read_text(), templates, MoleculePreparation())
    rigid, _flex = PDBQTWriterLegacy.write_from_polymer(poly)
    pdbqt = out_dir / "receptor.pdbqt"
    pdbqt.write_text(rigid)
    return pdb, pdbqt


def protonate(smiles: str, ph: float, notes: list[str]) -> str:
    try:
        from dimorphite_dl import protonate_smiles
    except ImportError:
        notes.append("dimorphite_dl not installed; declared SMILES docked as given")
        return smiles
    states = protonate_smiles(smiles, ph_min=ph, ph_max=ph, max_variants=1)
    if not states:
        notes.append("Dimorphite-DL returned no state; declared SMILES docked as given")
        return smiles
    return str(states[0])


def ligand_pdbqt(smiles: str, seed: int) -> str:
    from meeko import MoleculePreparation, PDBQTWriterLegacy
    from rdkit import Chem
    from rdkit.Chem import AllChem

    mol = Chem.AddHs(Chem.MolFromSmiles(smiles))
    params = AllChem.ETKDGv3()  # type: ignore[attr-defined]
    params.randomSeed = seed
    AllChem.EmbedMolecule(mol, params)  # type: ignore[attr-defined]
    setup = MoleculePreparation().prepare(mol)[0]
    text, ok, err = PDBQTWriterLegacy.write_string(setup)
    if not ok:
        raise ValueError(f"meeko could not write the ligand PDBQT: {err}")
    return str(text)


def box_from_reference(coords: Any, padding: float = 4.0) -> tuple[list[float], list[float]]:
    """Box around the crystal ligand extent plus `padding` Å on every side (Gnina autobox_add)."""
    lo, hi = coords.min(axis=0), coords.max(axis=0)
    return [round(float(x), 3) for x in (lo + hi) / 2], [
        round(float(x), 3) for x in (hi - lo) + 2 * padding
    ]


def run_vina(
    manifest: Manifest,
    receptor_source: Path,
    out_dir: Path,
    *,
    ligand_id: str | None = None,
    smiles: str | None = None,
    center: Sequence[float],
    size: Sequence[float],
    box_origin: str,
    seeds: Sequence[int] = (0, 1, 2, 3, 4),
    exhaustiveness: int = 8,
    num_modes: int = 9,
    log: Callable[[str], None] = lambda _: None,
) -> VinaRun:
    import importlib.metadata

    from vina import Vina

    out_dir.mkdir(parents=True, exist_ok=True)
    lig = next((x for x in manifest.ligands if ligand_id in (None, x.id)), None)
    declared = smiles or (lig.smiles if lig else None)
    if not declared:
        raise ValueError("no ligand SMILES to dock")
    ph = manifest.ph if manifest.ph is not None else 7.4
    notes: list[str] = [] if manifest.ph is not None else ["pH not stated; 7.4 used"]
    log(f"receptor: {receptor_source.name}, hydrogens at pH {ph}")
    rec_pdb, rec_pdbqt = prepare_receptor(receptor_source, out_dir, ph)
    docked = protonate(declared, ph, notes)
    log(f"ligand: {declared} docked as {docked}")
    name = lig.id if lig else "ligand"
    outputs: list[Path] = []
    for seed in seeds:
        v = Vina(sf_name="vina", seed=seed, verbosity=0)
        v.set_receptor(str(rec_pdbqt))
        v.set_ligand_from_string(ligand_pdbqt(docked, seed))
        v.compute_vina_maps(center=list(center), box_size=list(size))
        v.dock(exhaustiveness=exhaustiveness, n_poses=num_modes)
        out = out_dir / f"{name}_seed{seed}_out.pdbqt"
        v.write_poses(str(out), n_poses=num_modes, overwrite=True)
        outputs.append(out)
        best = float(v.energies(n_poses=1)[0][0])
        log(f"seed {seed}: {out.name}, best {best:.3f} kcal/mol")
    try:
        version = importlib.metadata.version("vina")
    except importlib.metadata.PackageNotFoundError:
        version = None
    run = VinaRun(
        receptor_pdb=rec_pdb,
        receptor_pdbqt=rec_pdbqt,
        outputs=outputs,
        center=[float(x) for x in center],
        size=[float(x) for x in size],
        box_origin=box_origin,
        smiles_declared=declared,
        smiles_docked=docked,
        seeds=list(seeds),
        exhaustiveness=exhaustiveness,
        num_modes=num_modes,
        vina_version=version,
        notes=notes,
    )

    def rel(p: Path) -> str:
        return str(p.relative_to(out_dir)) if p.is_relative_to(out_dir) else p.name

    record = {k: (rel(v) if isinstance(v, Path) else v) for k, v in asdict(run).items()}
    record["outputs"] = [rel(p) for p in outputs]
    (out_dir / "vina_run.json").write_text(json.dumps(record, indent=2))
    return run
