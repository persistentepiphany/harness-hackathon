"""Shared helpers for layers 2 to 5: configured thresholds, the model registry, the reference
ligand, pocket residues, parsed predictions and the pose ensemble in one common frame.

Everything expensive is memoised on the check context, so several checks reading the ensemble
compute it once per run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

from pah.checks import resolve
from pah.config import load_yaml
from pah.core.check import CheckContext
from pah.core.models import ArtifactKind, Threshold

WATER = frozenset({"HOH", "WAT", "DOD", "H2O"})


class OutputUnavailableError(RuntimeError):
    """A prediction or reference needed by a check cannot be used; the message says why."""


@cache
def _thresholds() -> dict[str, Any]:
    return load_yaml("thresholds.yaml").get("checks", {})


@cache
def _models() -> dict[str, Any]:
    return load_yaml("models.yaml")


def rdkit_module(name: str) -> Any:
    """An RDKit Chem submodule typed as Any (the bundled stubs omit most generated functions)."""
    import importlib

    return importlib.import_module(f"rdkit.Chem.{name}")


def configured(check_id: str, name: str) -> Threshold:
    """Threshold from configs/thresholds.yaml with its origin and evidence level."""
    row = _thresholds()[check_id][name]
    return resolve.threshold(name, row["value"], row["comparator"], row["origin"], row["evidence"])


def value(check_id: str, name: str) -> Any:
    return _thresholds()[check_id][name]["value"]


def model_entry(executor: str | None) -> dict[str, Any] | None:
    if not executor:
        return None
    entry = _models().get("models", {}).get(executor)
    return dict(entry) if entry else None


def task_endpoint(task_id: str) -> str | None:
    endpoint = _models().get("task_endpoints", {}).get(task_id)
    return str(endpoint) if endpoint else None


def model_threshold(executor: str, name: str) -> Threshold | None:
    entry = model_entry(executor) or {}
    row = (entry.get("confidence") or {}).get(name)
    if not row:
        return None
    return resolve.threshold(
        f"{executor}.{name}", row["value"], row["comparator"], row["origin"], row["evidence"]
    )


def executors(ctx: CheckContext) -> list[str]:
    """Executors named by the run: the declared model and every prediction set."""
    names: list[str] = []
    if ctx.manifest.model and ctx.manifest.model.executor:
        names.append(ctx.manifest.model.executor)
    for p in ctx.manifest.predictions:
        if p.executor not in names:
            names.append(p.executor)
    return names


# ---------------------------------------------------------------------------------------------
# Reference structure and ligand


@dataclass(frozen=True)
class RefLigand:
    code: str
    chain: str
    seqid: str
    mol: Any  # RDKit Mol with the crystal coordinates, heavy atoms only
    coords: Any  # numpy (n, 3)
    source: str
    bond_orders: bool


def reference_ids(ctx: CheckContext) -> tuple[str | None, str | None]:
    """(PDB id, ligand CCD code) of the experimental reference, if one is declared."""
    m = ctx.manifest
    ref = m.reference
    pdb_id = (ref.pdb_id if ref else None) or (m.receptor.pdb_id if m.receptor else None)
    code = ref.ligand if ref and ref.ligand else next((x.ccd for x in m.ligands if x.ccd), None)
    return pdb_id, code


def receptor_path(ctx: CheckContext) -> Path | None:
    """Receptor structure as declared: the receptor file, else the reference entry mmCIF."""
    m = ctx.manifest
    if m.receptor and m.receptor.file:
        path = m.path(m.receptor.file)
        return path if path.is_file() else None
    pdb_id, _ = reference_ids(ctx)
    return resolve.mmcif_path(ctx, pdb_id) if pdb_id else None


def read_structure(path: Path) -> Any:
    import gemmi

    st = gemmi.read_structure(str(path))
    st.setup_entities()
    st.remove_hydrogens()
    return st


def _ligand_residues(st: Any, code: str, chain: str | None) -> list[tuple[str, Any]]:
    out = []
    for ch in st[0]:
        if chain and ch.name != chain:
            continue
        for res in ch:
            if res.name == code:
                out.append((ch.name, res))
    return out


def residue_mol(res: Any, smiles: str | None) -> tuple[Any, bool]:
    """RDKit molecule for one residue, bond orders from the SMILES template when it fits."""
    from rdkit import Chem, rdBase
    from rdkit.Chem import AllChem

    lines = []
    for i, atom in enumerate(res, start=1):
        if atom.element.name == "H":
            continue
        p = atom.pos
        lines.append(
            f"HETATM{i:5d} {atom.name:<4s} {res.name:>3s} L   1    "
            f"{p.x:8.3f}{p.y:8.3f}{p.z:8.3f}  1.00  0.00          {atom.element.name:>2s}"
        )
    block = "\n".join(lines) + "\nEND\n"
    with rdBase.BlockLogs():
        mol = Chem.MolFromPDBBlock(block, removeHs=True, sanitize=True)
        if mol is None:
            mol = Chem.MolFromPDBBlock(block, removeHs=True, sanitize=False)
        if mol is None:
            raise OutputUnavailableError(f"cannot build a molecule from residue {res.name}")
        if mol.NeedsUpdatePropertyCache():
            mol.UpdatePropertyCache(strict=False)
        Chem.FastFindRings(mol)
        if smiles:
            tmpl = Chem.MolFromSmiles(smiles)
            if tmpl is not None:
                try:
                    return AllChem.AssignBondOrdersFromTemplate(Chem.RemoveHs(tmpl), mol), True
                except (ValueError, RuntimeError):
                    pass
    return mol, False


def reference_ligand(ctx: CheckContext) -> RefLigand | None:
    """The crystal ligand of the reference entry, or None when no reference is declared."""
    pdb_id, code = reference_ids(ctx)
    ref = ctx.manifest.reference
    if not code or not (pdb_id or (ref and ref.file)):
        return None

    def build() -> RefLigand:
        import numpy as np

        if ref and ref.file:
            path = ctx.manifest.path(ref.file)
            label = str(ref.file)
        else:
            assert pdb_id is not None
            path = resolve.mmcif_path(ctx, pdb_id)
            label = pdb_id.upper()
        st = read_structure(path)
        hits = _ligand_residues(st, code, ref.chain if ref else None)
        if not hits:
            raise OutputUnavailableError(f"ligand {code} not found in {label}")
        chain, res = hits[0]
        smiles = None
        try:
            cc = resolve.chemcomp(ctx, code)
            smiles = cc.smiles_stereo or cc.smiles
        except Exception:  # bond orders then come from geometry only, recorded below
            smiles = None
        mol, ok = residue_mol(res, smiles)
        coords = np.array(mol.GetConformer().GetPositions())
        return RefLigand(code, chain, str(res.seqid), mol, coords, label, ok)

    return ctx.memo(f"ref_ligand:{pdb_id}:{code}", build)


@dataclass(frozen=True)
class PocketResidue:
    chain: str
    seqnum: int
    icode: str
    name: str
    min_distance: float

    @property
    def label(self) -> str:
        return f"{self.name}{self.seqnum}{self.icode.strip()}{self.chain}"


def pocket_residues(st: Any, coords: Any, cutoff: float) -> list[PocketResidue]:
    """Polymer residues with a heavy atom within `cutoff` Å of any of the given coordinates."""
    import gemmi
    import numpy as np

    ns = gemmi.NeighborSearch(st[0], st.cell, max(cutoff, 5.0) + 1).populate()
    best: dict[tuple[str, int, str], tuple[str, float]] = {}
    for xyz in np.asarray(coords):
        ref = gemmi.Position(*map(float, xyz))
        for mark in ns.find_atoms(ref, "\0", radius=cutoff):
            cra = mark.to_cra(st[0])
            if cra.residue.het_flag == "H" or cra.residue.name in WATER:
                continue
            if cra.atom.element.name == "H":
                continue
            d = cra.atom.pos.dist(ref)
            key = (cra.chain.name, int(cra.residue.seqid.num or 0), str(cra.residue.seqid.icode))
            if key not in best or d < best[key][1]:
                best[key] = (cra.residue.name, d)
    return sorted(
        (PocketResidue(c, n, i, name, round(d, 2)) for (c, n, i), (name, d) in best.items()),
        key=lambda r: (r.chain, r.seqnum, r.icode),
    )


# ---------------------------------------------------------------------------------------------
# Predictions


def prediction_sets(ctx: CheckContext) -> list[Any]:
    """Parses every declared prediction (and control) once. Failures are kept, not raised."""

    def build() -> tuple[list[Any], list[str]]:
        from pah.executors import ParseError, parse_prediction

        sets: list[Any] = []
        errors: list[str] = []
        specs = list(ctx.manifest.predictions)
        c = ctx.manifest.controls
        specs += [s.model_copy(update={"role": "control:redocking"}) for s in [c.redocking] if s]
        specs += [s.model_copy(update={"role": "control:decoy"}) for s in c.decoys]
        specs += [s.model_copy(update={"role": "control:active"}) for s in c.actives]
        for i, spec in enumerate(specs):
            workdir = ctx.run_dir / "predictions" / f"{i:02d}_{spec.executor}"
            try:
                pset = parse_prediction(spec, ctx.manifest, workdir)
            except (ParseError, OSError, ValueError, KeyError) as exc:
                errors.append(f"{spec.executor} {spec.path}: {type(exc).__name__}: {exc}")
                continue
            sets.append(pset)
            for pose in pset.poses:
                if pose.structure.is_file():
                    ctx.add_artifact(
                        pose.structure, ArtifactKind.PREDICTION_STRUCTURE, label=pose.id
                    )
                if pose.ligand and pose.ligand.is_file():
                    ctx.add_artifact(pose.ligand, ArtifactKind.DATA, label=f"{pose.id} ligand")
        return sets, errors

    sets, errors = ctx.memo("prediction_sets", build)
    ctx.state.setdefault("prediction_errors", errors)
    return list(sets)


def prediction_errors(ctx: CheckContext) -> list[str]:
    prediction_sets(ctx)
    return list(ctx.state.get("prediction_errors", []))


def assessed_sets(ctx: CheckContext) -> list[Any]:
    """Prediction sets that are not controls."""
    return [s for s in prediction_sets(ctx) if not s.role.startswith("control")]


def control_sets(ctx: CheckContext, kind: str) -> list[Any]:
    return [s for s in prediction_sets(ctx) if s.role == f"control:{kind}"]


def needs_predictions(ctx: CheckContext) -> str | None:
    """`applies()` helper: None when predictions exist; otherwise the reason the check skips."""
    if not ctx.manifest.predictions:
        return "no predictions declared (pre-run assessment)"
    return None


def require_sets(ctx: CheckContext) -> list[Any]:
    sets = assessed_sets(ctx)
    if not sets:
        raise OutputUnavailableError(
            "no prediction could be parsed: " + "; ".join(prediction_errors(ctx))
        )
    return sets


def ligand_poses(ctx: CheckContext) -> list[Any]:
    return [p for s in require_sets(ctx) for p in s.ranked() if p.ligand]


def pose_mol(pose: Any) -> Any:
    from rdkit import Chem, rdBase

    def load() -> Any:
        with rdBase.BlockLogs():
            mol = Chem.MolFromMolFile(str(pose.ligand), removeHs=False, sanitize=True)
        if mol is None:
            raise OutputUnavailableError(f"cannot read ligand of {pose.id}: {pose.ligand}")
        return mol

    return _pose_cache(("mol", pose.id, str(pose.ligand)), load)


_POSE_CACHE: dict[tuple[str, ...], Any] = {}


def _pose_cache(key: tuple[str, ...], fn: Any) -> Any:
    if key not in _POSE_CACHE:
        if len(_POSE_CACHE) > 512:
            _POSE_CACHE.clear()
        _POSE_CACHE[key] = fn()
    return _POSE_CACHE[key]


def heavy(mol: Any) -> Any:
    from rdkit import Chem

    out = Chem.RemoveHs(mol, sanitize=False)
    out.UpdatePropertyCache(strict=False)
    Chem.FastFindRings(out)
    return out


def receptor_of(pose: Any) -> Path:
    """Protein-only PDB of a pose's complex (written once next to the complex)."""
    out = pose.structure.with_name(pose.structure.stem + "_protein.pdb")
    if out.is_file():
        return Path(out)
    st = read_structure(pose.structure)
    st.remove_ligands_and_waters()
    st.remove_empty_chains()
    st.write_pdb(str(out))
    return Path(out)


# ---------------------------------------------------------------------------------------------
# Superposition and the pose ensemble


def _ca_trace(st: Any) -> tuple[str, list[Any], list[tuple[str, int, str]]]:
    import gemmi

    seq: list[str] = []
    pos: list[Any] = []
    keys: list[tuple[str, int, str]] = []
    for ch in st[0]:
        for res in ch:
            info = gemmi.find_tabulated_residue(res.name)
            if not info or not info.is_amino_acid():
                continue
            ca = res.find_atom("CA", "*")
            if ca is None:
                continue
            seq.append(info.one_letter_code.upper())
            pos.append(ca.pos)
            keys.append((ch.name, res.seqid.num, res.seqid.icode))
    return "".join(seq), pos, keys


@dataclass(frozen=True)
class Superposition:
    rot: Any
    tran: Any
    rmsd: float
    pairs: int
    residue_map: dict[tuple[str, int, str], tuple[str, int, str]]

    def apply(self, xyz: Any) -> Any:
        import numpy as np

        return np.asarray(xyz) @ self.rot.T + self.tran


def superposition(mobile: Any, target: Any) -> Superposition:
    """Places structure `mobile` on `target` by CA atoms paired through a sequence alignment."""
    import gemmi
    import numpy as np

    sa, pa, ka = _ca_trace(mobile)
    sb, pb, kb = _ca_trace(target)
    if not sa or not sb:
        raise OutputUnavailableError("no CA atoms to superpose")
    aln = gemmi.align_string_sequences(list(sa), list(sb), [])
    i = j = 0
    pairs: list[tuple[int, int]] = []
    for op, n in ((c[-1], int(c[:-1])) for c in _cigar(aln.cigar_str())):
        for _ in range(n):
            if op == "M":
                if sa[i] == sb[j]:
                    pairs.append((i, j))
                i, j = i + 1, j + 1
            elif op == "I":
                i += 1
            else:
                j += 1
    if len(pairs) < 3:
        raise OutputUnavailableError(f"fewer than 3 matched CA atoms ({len(pairs)})")
    sup = gemmi.superpose_positions([pb[b] for _, b in pairs], [pa[a] for a, _ in pairs])
    return Superposition(
        rot=np.array(sup.transform.mat.tolist()),
        tran=np.array(sup.transform.vec.tolist()),
        rmsd=float(sup.rmsd),
        pairs=len(pairs),
        residue_map={ka[a]: kb[b] for a, b in pairs},
    )


def superpose(mobile: Path, target: Path) -> tuple[Any, Any, float, int]:
    """Rotation, translation, CA RMSD and pair count that place `mobile` on `target`."""
    sup = superposition(read_structure(mobile), read_structure(target))
    return sup.rot, sup.tran, sup.rmsd, sup.pairs


def _cigar(s: str) -> list[str]:
    import re

    return re.findall(r"\d+[MID]", s)


@dataclass
class Ensemble:
    """Ligand poses in one frame with symmetry-aware pairwise RMSD, clusters and medoid."""

    frame: str
    poses: list[Any]
    coords: list[Any]  # heavy-atom coordinates in the common frame
    rmsd: Any  # numpy (n, n)
    clusters: list[list[int]]
    medoid: int
    frame_rmsd: dict[str, float] = field(default_factory=dict)
    centroids: list[Any] = field(default_factory=list)


def symmetric_rmsd(mol_a: Any, coords_a: Any, mol_b: Any, coords_b: Any) -> float:
    """Symmetry-aware heavy-atom RMSD without superposition (spyrmsd)."""
    import numpy as np
    from rdkit import Chem
    from spyrmsd import rmsd as sr

    a, b = heavy(mol_a), heavy(mol_b)
    if a.GetNumAtoms() != b.GetNumAtoms():
        raise OutputUnavailableError(
            f"heavy-atom counts differ ({a.GetNumAtoms()} vs {b.GetNumAtoms()})"
        )
    an = np.array([x.GetAtomicNum() for x in a.GetAtoms()])
    bn = np.array([x.GetAtomicNum() for x in b.GetAtoms()])
    return float(
        sr.symmrmsd(
            np.asarray(coords_a),
            np.asarray(coords_b),
            an,
            bn,
            Chem.GetAdjacencyMatrix(a),
            Chem.GetAdjacencyMatrix(b),
            center=False,
            minimize=False,
        )
    )


def heavy_coords(mol: Any) -> Any:
    import numpy as np

    h = heavy(mol)
    return np.array(h.GetConformer().GetPositions())


def frame_target(ctx: CheckContext) -> tuple[Path, str]:
    rec = None
    try:
        rec = receptor_path(ctx)
    except Exception:  # the frame then falls back to the first pose
        rec = None
    if rec is not None:
        return rec, rec.name
    first = ligand_poses(ctx)[0]
    return first.structure, first.id


def ensemble(ctx: CheckContext) -> Ensemble:
    def build() -> Ensemble:
        import numpy as np

        poses = ligand_poses(ctx)
        if not poses:
            raise OutputUnavailableError("no ligand poses in the predictions")
        target, label = frame_target(ctx)
        coords, frame_rmsd = [], {}
        for pose in poses:
            xyz = heavy_coords(pose_mol(pose))
            if pose.structure != target:
                rot, tran, r, _ = superpose(pose.structure, target)
                xyz = xyz @ rot.T + tran
                frame_rmsd[pose.id] = round(r, 3)
            coords.append(xyz)
        n = len(poses)
        mat = np.zeros((n, n))
        for i in range(n):
            for j in range(i + 1, n):
                d = symmetric_rmsd(pose_mol(poses[i]), coords[i], pose_mol(poses[j]), coords[j])
                mat[i, j] = mat[j, i] = d
        clusters = cluster(mat, float(value("l5.sampling.clusters", "cluster_rmsd")))
        largest = clusters[0]
        medoid = min(largest, key=lambda i: float(mat[i, largest].sum()))
        return Ensemble(
            frame=label,
            poses=poses,
            coords=coords,
            rmsd=mat,
            clusters=clusters,
            medoid=medoid,
            frame_rmsd=frame_rmsd,
            centroids=[c.mean(axis=0) for c in coords],
        )

    return ctx.memo("ensemble", build)


def cluster(mat: Any, cutoff: float) -> list[list[int]]:
    """Complete-linkage clusters at `cutoff`, largest first (ties: lowest index first)."""
    import numpy as np

    n = mat.shape[0]
    if n == 1:
        return [[0]]
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import squareform

    labels = fcluster(linkage(squareform(mat, checks=False), "complete"), cutoff, "distance")
    groups: dict[int, list[int]] = {}
    for i, lab in enumerate(labels):
        groups.setdefault(int(lab), []).append(i)
    out = sorted(groups.values(), key=lambda g: (-len(g), g[0]))
    _ = np
    return out


def representative(ctx: CheckContext) -> Any:
    """Medoid of the largest cluster when the ensemble exists, else the top-ranked pose."""
    try:
        ens = ensemble(ctx)
        return ens.poses[ens.medoid]
    except OutputUnavailableError:
        return ligand_poses(ctx)[0]


def site_coords(ctx: CheckContext) -> tuple[Any, str] | None:
    """Coordinates defining the binding site: the crystal ligand, else the docking box centre."""
    import numpy as np

    try:
        ref = reference_ligand(ctx)
    except Exception:
        ref = None
    if ref is not None:
        return ref.coords, f"{ref.code} in {ref.source}"
    box = ctx.manifest.docking_box
    if box is not None:
        return np.array([box.center]), f"docking box centre ({box.origin})"
    return None
