"""Layer 4: the result is physically and chemically sensible, whatever the tool's confidence.

Geometry and interaction chemistry are checked separately; a pose can pass every geometric test
and still place a charged group in a greasy pocket (specification, layer 4).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from pah.checks import outputs, resolve
from pah.core.check import Check, CheckContext, SkipReason, register
from pah.core.models import Finding, Gate, Layer, ToolRef

SPEC_L4 = "Specification, Layer 4 (output validity)"
MAX_POSES = 25
PB_VALUES = {
    "bond_lengths": ("number_long_outlier_bonds", "{:.0f} long outliers"),
    "bond_angles": ("number_outlier_angles", "{:.0f} outliers"),
    "internal_steric_clash": ("number_clashes", "{:.0f}"),
    "aromatic_ring_flatness": ("aromatic_ring_maximum_distance_from_plane", "{:.2f} Å"),
    "internal_energy": ("energy_ratio", "{:.1f} times the ensemble mean"),
    "minimum_distance_to_protein": ("smallest_distance_protein", "{:.2f} Å"),
    "volume_overlap_with_protein": ("volume_overlap_protein", "{:.3f}"),
    "protein-ligand_maximum_distance": ("smallest_distance_protein", "{:.2f} Å"),
}


def _ligand_outputs(ctx: CheckContext) -> str | None:
    reason = outputs.needs_predictions(ctx)
    if reason:
        return reason
    return None if ctx.manifest.ligands else "no ligand declared"


def _poses(ctx: CheckContext) -> list[Any]:
    poses = outputs.ensemble_poses(ctx)
    if not poses:
        raise outputs.OutputUnavailableError("no ligand poses in the primary prediction set")
    return poses[:MAX_POSES]


def _rep_id(ctx: CheckContext) -> str:
    return str(outputs.representative(ctx).id)


@register
class PoseBustersCheck(Check):
    id = "l4.posebusters"
    layer = Layer.VALIDITY
    title = "PoseBusters geometry, stereochemistry, clashes and protein contact"
    requires_modules = ("posebusters", "rdkit")

    def applies(self, ctx: CheckContext) -> str | None:
        return _ligand_outputs(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        import math

        from posebusters import PoseBusters

        poses = _poses(ctx)
        rep = _rep_id(ctx)
        ref = outputs.reference_ligand(ctx)
        rows: list[dict[str, Any]] = []
        rep_tests: list[dict[str, Any]] = []
        for pose in poses:
            df = PoseBusters(config="dock").bust(
                mol_pred=[str(pose.ligand)],
                mol_cond=str(outputs.receptor_of(pose)),
                full_report=True,
            )
            row = df.iloc[0].to_dict()
            tests = [
                k
                for k, v in row.items()
                if isinstance(v, bool) and not k.endswith("loaded") and k in _test_columns(df)
            ]
            failed = [t for t in tests if not row[t]]
            rows.append(
                {
                    "pose": pose.id,
                    "passed": len(tests) - len(failed),
                    "total": len(tests),
                    "failed": failed,
                }
            )
            if pose.id == rep:
                for t in tests:
                    col, fmt = PB_VALUES.get(t, (None, ""))
                    raw = row.get(col) if col else None
                    shown = (
                        fmt.format(raw)
                        if isinstance(raw, (int, float)) and not math.isnan(float(raw))
                        else ("pass" if row[t] else "fail")
                    )
                    rep_tests.append({"test": t, "pass": bool(row[t]), "value": shown})
        rep_row = next(r for r in rows if r["pose"] == rep)
        th = (
            resolve.threshold("tests_failed", 0, "==", SPEC_L4 + ": stop on failure", "published"),
        )
        m = {
            "poses": len(rows),
            "passed": rep_row["passed"],
            "total": rep_row["total"],
            "poses_all_pass": sum(1 for r in rows if not r["failed"]),
        }
        ev = {
            "representative": rep,
            "tests": rep_tests,
            "poses": rows,
            "reference": f"{ref.code} in {ref.source}" if ref else None,
        }
        tool = ToolRef(name="posebusters", version=_version("posebusters"))
        if rep_row["failed"]:
            return self.finding(
                Gate.STOP,
                f"representative pose {rep} fails {', '.join(rep_row['failed'])}",
                measurements=m,
                thresholds=th,
                evidence=ev,
                tool=tool,
            )
        return self.finding(
            Gate.PASS,
            f"{rep_row['passed']} of {rep_row['total']} tests pass for "
            f"{rep}; {m['poses_all_pass']} of {len(rows)} poses pass all",
            measurements=m,
            thresholds=th,
            evidence=ev,
            tool=tool,
        )


def _test_columns(df: Any) -> set[str]:
    """Boolean test columns of the short PoseBusters report (no per-test detail columns)."""
    short = {
        "sanitization",
        "inchi_convertible",
        "all_atoms_connected",
        "no_radicals",
        "bond_lengths",
        "bond_angles",
        "internal_steric_clash",
        "aromatic_ring_flatness",
        "non-aromatic_ring_non-flatness",
        "double_bond_flatness",
        "internal_energy",
        "protein-ligand_maximum_distance",
        "minimum_distance_to_protein",
        "minimum_distance_to_organic_cofactors",
        "minimum_distance_to_inorganic_cofactors",
        "minimum_distance_to_waters",
        "volume_overlap_with_protein",
        "volume_overlap_with_organic_cofactors",
        "volume_overlap_with_inorganic_cofactors",
        "volume_overlap_with_waters",
    }
    return short & set(df.columns)


def _version(module: str) -> str | None:
    import importlib.metadata

    try:
        return importlib.metadata.version(module)
    except importlib.metadata.PackageNotFoundError:
        return None


def _with_h(mol: Any) -> Any:
    from rdkit import Chem

    return Chem.AddHs(mol, addCoords=True)


LOCAL_RELAX_A = 0.3


def local_relax(mol: Any) -> tuple[Any, Any]:
    """Pose with hydrogens and MMFF properties, minimised with every heavy atom held within
    0.3 Å of its pose position, so bond lengths from the docking or co-folding geometry do not
    count as strain. Returns (molecule, MMFF properties)."""
    ffh = outputs.rdkit_module("rdForceFieldHelpers")
    molh = _with_h(mol)
    props = ffh.MMFFGetMoleculeProperties(molh)
    if props is None:
        raise outputs.OutputUnavailableError("MMFF cannot type the ligand")
    ff = ffh.MMFFGetMoleculeForceField(molh, props)
    for atom in molh.GetAtoms():
        if atom.GetAtomicNum() > 1:
            ff.MMFFAddPositionConstraint(atom.GetIdx(), LOCAL_RELAX_A, 100.0)
    ff.Minimize(maxIts=2000)
    flat = list(ff.Positions())
    conf = molh.GetConformer()
    for i in range(molh.GetNumAtoms()):
        conf.SetAtomPosition(i, flat[3 * i : 3 * i + 3])
    return molh, props


def torsion_profile(mol: Any, step: int = 10) -> list[dict[str, Any]]:
    """Rigid scan of every rotatable torsion with MMFF; energy of the pose angle above the scan
    minimum, in kcal/mol."""
    from rdkit import Chem
    from rdkit.Chem import rdMolTransforms

    ffh = outputs.rdkit_module("rdForceFieldHelpers")
    molh, props = local_relax(mol)
    patt = Chem.MolFromSmarts(
        "[!$([NH])&!$([NH2])&!$(C(F)(F)F)&!D1&!$(*#*)]-&!@"
        "[!$([NH])&!$([NH2])&!$(C(F)(F)F)&!D1&!$(*#*)]"
    )
    rows = []
    for b, c in molh.GetSubstructMatches(patt):
        a = next(n.GetIdx() for n in molh.GetAtomWithIdx(b).GetNeighbors() if n.GetIdx() != c)
        d = next(n.GetIdx() for n in molh.GetAtomWithIdx(c).GetNeighbors() if n.GetIdx() != b)
        conf = Chem.Conformer(molh.GetConformer())
        work = Chem.Mol(molh)
        work.RemoveAllConformers()
        cid = work.AddConformer(conf, assignId=True)
        ff = ffh.MMFFGetMoleculeForceField(work, props, confId=cid)
        pose_angle = rdMolTransforms.GetDihedralDeg(work.GetConformer(cid), a, b, c, d)
        e_pose = ff.CalcEnergy()
        energies = []
        for ang in range(-180, 180, step):
            rdMolTransforms.SetDihedralDeg(work.GetConformer(cid), a, b, c, d, float(ang))
            energies.append(ff.CalcEnergy(list(work.GetConformer(cid).GetPositions().ravel())))
        rows.append(
            {
                "atoms": [a, b, c, d],
                "angle": round(pose_angle, 1),
                "excess_kcal": round(e_pose - min(energies), 2),
            }
        )
    return rows


def strain_energy(mol: Any, n_conf: int = 20) -> float | None:
    """MMFF energy of the locally relaxed pose minus the lowest energy of `n_conf` relaxed ETKDG
    conformers, in kcal/mol."""
    from rdkit import Chem

    allchem = outputs.rdkit_module("AllChem")
    ffh = outputs.rdkit_module("rdForceFieldHelpers")
    molh, props = local_relax(mol)
    e_pose = ffh.MMFFGetMoleculeForceField(molh, props).CalcEnergy()
    free = Chem.Mol(molh)
    params = allchem.ETKDGv3()
    params.randomSeed = 0xF00D
    ids = allchem.EmbedMultipleConfs(free, numConfs=n_conf, params=params)
    if not ids:
        return None
    results = allchem.MMFFOptimizeMoleculeConfs(free, maxIters=2000)
    best = min(e for _, e in results)
    return round(float(e_pose - best), 2)


@register
class TorsionStrain(Check):
    id = "l4.torsion_strain"
    layer = Layer.VALIDITY
    title = "Torsional strain of the ligand pose"
    requires_modules = ("rdkit",)

    def applies(self, ctx: CheckContext) -> str | None:
        return _ligand_outputs(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        th = (outputs.configured(self.id, "torsion_energy"),)
        limit = float(th[0].value)
        rows = []
        for pose in _poses(ctx):
            mol = outputs.pose_mol(pose)
            prof = torsion_profile(mol)
            unlikely = [t for t in prof if t["excess_kcal"] > limit]
            rows.append(
                {
                    "pose": pose.id,
                    "torsions": len(prof),
                    "unlikely_torsions": len(unlikely),
                    "max_excess_kcal": max((t["excess_kcal"] for t in prof), default=0.0),
                    "strain_kcal": strain_energy(mol),
                    "detail": prof,
                }
            )
        rep = _rep_id(ctx)
        rep_row = next((r for r in rows if r["pose"] == rep), rows[0])
        m = {
            "poses": len(rows),
            "unlikely_torsions": rep_row["unlikely_torsions"],
            "torsions": rep_row["torsions"],
            "strain_kcal": rep_row["strain_kcal"],
            "poses_with_unlikely": sum(1 for r in rows if r["unlikely_torsions"]),
        }
        ev = {
            "representative": rep,
            "poses": rows,
            "method": "MMFF94 after relaxation with heavy "
            "atoms held within 0.3 Å; rigid torsion scan in 10° steps; strain against 20 "
            "relaxed ETKDG conformers",
        }
        tool = ToolRef(name="rdkit MMFF94")
        if rep_row["unlikely_torsions"]:
            return self.finding(
                Gate.WARN,
                f"{rep_row['unlikely_torsions']} of "
                f"{rep_row['torsions']} torsions above {limit} kcal/mol in {rep}",
                measurements=m,
                thresholds=th,
                evidence=ev,
                tool=tool,
            )
        return self.finding(
            Gate.PASS,
            f"0 of {rep_row['torsions']} torsions above {limit} "
            f"kcal/mol in {rep}; strain {rep_row['strain_kcal']} kcal/mol",
            measurements=m,
            thresholds=th,
            evidence=ev,
            tool=tool,
        )


INTERACTION_TYPES = {
    "hbonds_pdon": "hbond",
    "hbonds_ldon": "hbond",
    "saltbridge_lneg": "salt_bridge",
    "saltbridge_pneg": "salt_bridge",
    "pistacking": "pi_stack",
    "pication_laro": "pi_cation",
    "pication_paro": "pi_cation",
    "hydrophobic_contacts": "hydrophobic",
    "halogen_bonds": "halogen",
    "water_bridges": "water_bridge",
    "metal_complexes": "metal",
}


def plip_interactions(complex_pdb: Path) -> list[dict[str, Any]]:
    """PLIP interactions of the ligand residues in a complex, one row per interaction."""
    import shutil
    import tempfile

    # PLIP writes protonated copies next to its input; work in a temporary directory so source
    # and output folders stay untouched. PLIP reads PDB only; co-folding tools write mmCIF.
    tmp = Path(tempfile.mkdtemp(prefix="pah-plip-"))
    try:
        pdb = tmp / "complex.pdb"
        if complex_pdb.suffix.lower() == ".pdb":
            shutil.copyfile(complex_pdb, pdb)
        else:
            st = outputs.read_structure(complex_pdb)
            st.shorten_chain_names()
            st.write_pdb(str(pdb))
        return _plip_rows(pdb, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _plip_rows(pdb: Path, out_dir: Path) -> list[dict[str, Any]]:
    from plip.structure.preparation import PDBComplex

    cplx = PDBComplex()
    cplx.output_path = str(out_dir)
    cplx.load_pdb(str(pdb))
    cplx.analyze()
    rows = []
    for site in cplx.interaction_sets.values():
        for attr, kind in INTERACTION_TYPES.items():
            for i in getattr(site, attr, []):
                dist = next(
                    (
                        getattr(i, k)
                        for k in ("distance_ad", "distance", "distance_aw")
                        if hasattr(i, k)
                    ),
                    None,
                )
                rows.append(
                    {
                        "type": kind,
                        "residue": f"{i.restype}{i.resnr}{i.reschain}",
                        "distance_A": round(float(dist), 2) if dist else None,
                    }
                )
    return rows


def reference_numbering(ctx: CheckContext, pose: Any) -> dict[tuple[str, int], str]:
    """Maps (chain, residue number) in a pose's complex to the reference entry's residue label
    (number, insertion code, chain), so interactions compare across numbering schemes. Empty when
    no reference entry is declared."""
    pdb_id, _ = outputs.reference_ids(ctx)
    if not pdb_id:
        return {}

    def build() -> dict[tuple[str, int], str]:
        ref = outputs.read_structure(resolve.mmcif_path(ctx, pdb_id))
        mob = outputs.read_structure(pose.structure)
        sup = outputs.superposition(mob, ref)
        return {
            (c, n): f"{num}{ic.strip()}{rc}" for (c, n, _), (rc, num, ic) in sup.residue_map.items()
        }

    return ctx.memo(f"refnum:{pose.structure}", build)


def _renumber(
    rows: list[dict[str, Any]], mapping: dict[tuple[str, int], str]
) -> list[dict[str, Any]]:
    import re

    out = []
    for r in rows:
        m = re.fullmatch(r"([A-Z0-9]{1,3}?)(-?\d+)([A-Za-z0-9]*)", r["residue"])
        if mapping and m:
            key = (m.group(3), int(m.group(2)))
            if key in mapping:
                r = {**r, "residue": m.group(1) + mapping[key], "pose_residue": r["residue"]}
        out.append(r)
    return out


def pose_interactions(ctx: CheckContext, pose: Any) -> list[dict[str, Any]]:
    """PLIP interactions of a pose with residues in the reference entry's numbering."""
    try:
        mapping = reference_numbering(ctx, pose)
    except (outputs.OutputUnavailableError, ValueError):
        mapping = {}
    return _renumber(plip_interactions(pose.structure), mapping)


def _crystal_complex(ctx: CheckContext) -> Path | None:
    """The reference entry as a PDB holding the protein and the reference ligand only."""
    ref = outputs.reference_ligand(ctx)
    pdb_id, _ = outputs.reference_ids(ctx)
    if ref is None or not pdb_id:
        return None
    out = ctx.artifact_path(f"work/{pdb_id.upper()}_{ref.code}_complex.pdb")
    if out.is_file():
        return out
    st = outputs.read_structure(resolve.mmcif_path(ctx, pdb_id))
    st.remove_waters()
    for ch in st[0]:
        for i in range(len(ch) - 1, -1, -1):
            res = ch[i]
            if res.het_flag == "H" and not (
                res.name == ref.code and ch.name == ref.chain and str(res.seqid) == ref.seqid
            ):
                del ch[i]
    st.remove_empty_chains()
    st.write_pdb(str(out))
    return out


@register
class InteractionFingerprint(Check):
    id = "l4.interactions.fingerprint"
    layer = Layer.VALIDITY
    title = "Interaction fingerprint (PLIP)"
    requires_modules = ("plip", "openbabel")

    def applies(self, ctx: CheckContext) -> str | None:
        return _ligand_outputs(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        poses = _poses(ctx)
        per_pose = {p.id: pose_interactions(ctx, p) for p in poses}
        ctx.state["plip"] = per_pose
        counts: dict[tuple[str, str], dict[str, Any]] = {}
        for pid, rows in per_pose.items():
            for r in rows:
                key = (r["type"], r["residue"])
                slot = counts.setdefault(
                    key,
                    {"type": r["type"], "residue": r["residue"], "poses": set(), "distances": []},
                )
                slot["poses"].add(pid)
                if r["distance_A"] is not None:
                    slot["distances"].append(r["distance_A"])
        table = sorted(
            (
                {
                    "type": v["type"],
                    "residue": v["residue"],
                    "poses": len(v["poses"]),
                    "of": len(poses),
                    "distance_A": round(min(v["distances"]), 2) if v["distances"] else None,
                }
                for v in counts.values()
            ),
            key=lambda r: (-r["poses"], r["type"], r["residue"]),
        )
        rep = _rep_id(ctx)
        m = {
            "poses": len(poses),
            "interactions_representative": len(per_pose.get(rep, [])),
            "distinct": len(table),
            "hbonds_representative": sum(1 for r in per_pose.get(rep, []) if r["type"] == "hbond"),
        }
        ev = {"representative": rep, "interactions": table, "per_pose": per_pose}
        types = sorted({r["type"] for r in per_pose.get(rep, [])})
        return self.finding(
            Gate.PASS,
            f"{m['interactions_representative']} interactions in {rep} "
            f"({', '.join(types) or 'none'}); {len(table)} distinct across "
            f"{len(poses)} poses (reported)",
            measurements=m,
            evidence=ev,
            tool=ToolRef(name="plip", version=_version("plip")),
        )


@register
class KnownBinders(Check):
    id = "l4.interactions.known_binders"
    layer = Layer.VALIDITY
    title = "Interactions of the crystal ligand reproduced by the pose"
    requires_modules = ("plip", "openbabel", "gemmi")

    def applies(self, ctx: CheckContext) -> str | None:
        reason = _ligand_outputs(ctx)
        if reason:
            return reason
        pdb_id, code = outputs.reference_ids(ctx)
        return None if pdb_id and code else "no reference complex declared"

    def run(self, ctx: CheckContext) -> Finding:
        crystal = _crystal_complex(ctx)
        if crystal is None:
            raise outputs.OutputUnavailableError("reference ligand not found")
        ref_rows = plip_interactions(crystal)
        key_set = {(r["type"], r["residue"]) for r in ref_rows if r["type"] != "hydrophobic"}
        if not key_set:
            key_set = {(r["type"], r["residue"]) for r in ref_rows}
        per_pose = ctx.state.get("plip") or {p.id: pose_interactions(ctx, p) for p in _poses(ctx)}
        rep = _rep_id(ctx)
        rows = []
        for pid, inter in per_pose.items():
            have = {(r["type"], r["residue"]) for r in inter}
            rows.append({"pose": pid, "reproduced": len(key_set & have), "of": len(key_set)})
        rep_have = {(r["type"], r["residue"]) for r in per_pose.get(rep, [])}
        reproduced = sorted(f"{t} {res}" for t, res in key_set & rep_have)
        missing = sorted(f"{t} {res}" for t, res in key_set - rep_have)
        th = (outputs.configured(self.id, "reproduced"),)
        m = {
            "key_interactions": len(key_set),
            "reproduced": len(reproduced),
            "poses_reproducing_all": sum(1 for r in rows if r["reproduced"] == r["of"]),
        }
        _, code = outputs.reference_ids(ctx)
        ev = {
            "reference": crystal.name,
            "reference_interactions": ref_rows,
            "reproduced": reproduced,
            "missing": missing,
            "poses": rows,
            "representative": rep,
        }
        tool = ToolRef(name="plip", version=_version("plip"))
        if len(reproduced) < float(th[0].value):
            return self.finding(
                Gate.WARN,
                f"{rep} reproduces none of {len(key_set)} {code} interactions",
                measurements=m,
                thresholds=th,
                evidence=ev,
                tool=tool,
            )
        return self.finding(
            Gate.PASS,
            f"{rep} reproduces {len(reproduced)} of {len(key_set)} "
            f"{code} interactions: {', '.join(reproduced)}",
            measurements=m,
            thresholds=th,
            evidence=ev,
            tool=tool,
        )


POLAR = {"N", "O"}


@register
class UnsatisfiedPolars(Check):
    id = "l4.interactions.unsatisfied_polars"
    layer = Layer.VALIDITY
    title = "Buried ligand polar atoms without a hydrogen-bond partner"
    requires_modules = ("freesasa", "gemmi", "rdkit")

    def applies(self, ctx: CheckContext) -> str | None:
        return _ligand_outputs(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        th = (
            outputs.configured(self.id, "relative_sasa"),
            outputs.configured(self.id, "hbond_distance"),
        )
        rows = [self._pose(p, float(th[0].value), float(th[1].value)) for p in _poses(ctx)]
        rep = _rep_id(ctx)
        rr = next((r for r in rows if r["pose"] == rep), rows[0])
        m = {
            "poses": len(rows),
            "unsatisfied": rr["unsatisfied"],
            "buried_charged": rr["buried_charged"],
            "buried_polar": rr["buried_polar"],
        }
        ev = {"representative": rep, "poses": rows}
        tool = ToolRef(name="freesasa", version=_version("freesasa"))
        if rr["buried_charged"]:
            return self.finding(
                Gate.STOP,
                f"{rr['buried_charged']} buried charged ligand atoms without a partner in {rep}",
                measurements=m,
                thresholds=th,
                evidence=ev,
                tool=tool,
            )
        if rr["unsatisfied"]:
            return self.finding(
                Gate.WARN,
                f"{rr['unsatisfied']} of {rr['buried_polar']} buried "
                f"polar ligand atoms without a partner in {rep}",
                measurements=m,
                thresholds=th,
                evidence=ev,
                tool=tool,
            )
        return self.finding(
            Gate.PASS,
            f"{rr['buried_polar']} buried polar ligand atoms, all with "
            f"a partner within {th[1].value} Å in {rep}",
            measurements=m,
            thresholds=th,
            evidence=ev,
            tool=tool,
        )

    def _pose(self, pose: Any, sasa_cut: float, hb_cut: float) -> dict[str, Any]:
        import freesasa
        import gemmi
        import numpy as np

        mol = outputs.heavy(outputs.pose_mol(pose))
        lig = np.array(mol.GetConformer().GetPositions())
        st = outputs.read_structure(outputs.receptor_of(pose))
        prot = [
            (a.pos.tolist(), a.element.name, a.element.vdw_r) for ch in st[0] for r in ch for a in r
        ]
        radii = [gemmi.Element(a.GetSymbol()).vdw_r for a in mol.GetAtoms()]
        coords = [c for c, _, _ in prot] + lig.tolist()
        flat = [x for c in coords for x in c]
        all_r = [r for _, _, r in prot] + radii
        bound = freesasa.calcCoord(flat, all_r)
        free = freesasa.calcCoord([x for c in lig.tolist() for x in c], radii)
        n_prot = len(prot)
        polar_xyz = np.array([c for c, e, _ in prot if e in POLAR]) if prot else np.zeros((0, 3))
        atoms = []
        for i, atom in enumerate(mol.GetAtoms()):
            if atom.GetSymbol() not in POLAR:
                continue
            a_free = free.atomArea(i)
            rel = bound.atomArea(n_prot + i) / a_free if a_free > 0 else 0.0
            if rel >= sasa_cut:
                continue
            d = float(np.min(np.linalg.norm(polar_xyz - lig[i], axis=1))) if len(polar_xyz) else 99
            atoms.append(
                {
                    "atom": i,
                    "element": atom.GetSymbol(),
                    "charge": atom.GetFormalCharge(),
                    "relative_sasa": round(rel, 3),
                    "nearest_polar_A": round(d, 2),
                    "satisfied": d <= hb_cut,
                }
            )
        unsat = [a for a in atoms if not a["satisfied"]]
        return {
            "pose": pose.id,
            "buried_polar": len(atoms),
            "unsatisfied": len(unsat),
            "buried_charged": sum(1 for a in unsat if a["charge"] != 0),
            "atoms": atoms,
        }


NONPOLAR = {"C", "S", "Cl", "Br", "I"}


@register
class HydrophobicComplementarity(Check):
    id = "l4.interactions.hydrophobic"
    layer = Layer.VALIDITY
    title = "Hydrophobic complementarity of buried ligand surface"
    requires_modules = ("freesasa", "gemmi", "rdkit")

    def applies(self, ctx: CheckContext) -> str | None:
        return _ligand_outputs(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        th = (
            outputs.configured(self.id, "fraction"),
            outputs.configured("l4.interactions.unsatisfied_polars", "relative_sasa"),
        )
        rows = [self._pose(p, float(th[1].value)) for p in _poses(ctx)]
        rep = _rep_id(ctx)
        rr = next((r for r in rows if r["pose"] == rep), rows[0])
        m = {
            "poses": len(rows),
            "complementarity": rr["complementarity"],
            "buried_nonpolar": rr["buried_nonpolar"],
        }
        ev = {
            "representative": rep,
            "poses": rows,
            "method": "mean, over buried ligand C, S and halogen atoms (relative SASA below "
            "0.1), of the fraction of protein heavy atoms within 4.5 Å that are C or S",
        }
        frac = rr["complementarity"]
        if frac is None:
            return self.finding(
                Gate.PASS,
                f"no buried nonpolar ligand atoms in {rep} (reported)",
                measurements=m,
                thresholds=th,
                evidence=ev,
            )
        gate = Gate.WARN if frac < float(th[0].value) else Gate.PASS
        return self.finding(
            gate,
            f"nonpolar fraction of protein contacts around {rr['buried_nonpolar']} buried "
            f"nonpolar ligand atoms in {rep}: {frac}",
            measurements=m,
            thresholds=th,
            evidence=ev,
            tool=ToolRef(name="freesasa"),
        )

    def _pose(self, pose: Any, sasa_cut: float) -> dict[str, Any]:
        import freesasa
        import gemmi
        import numpy as np

        mol = outputs.heavy(outputs.pose_mol(pose))
        lig = np.array(mol.GetConformer().GetPositions())
        st = outputs.read_structure(outputs.receptor_of(pose))
        prot = [
            (a.pos.tolist(), a.element.name, a.element.vdw_r) for ch in st[0] for r in ch for a in r
        ]
        radii = [gemmi.Element(a.GetSymbol()).vdw_r for a in mol.GetAtoms()]
        flat = [x for c, _, _ in prot for x in c] + [x for c in lig.tolist() for x in c]
        bound = freesasa.calcCoord(flat, [r for _, _, r in prot] + radii)
        free = freesasa.calcCoord([x for c in lig.tolist() for x in c], radii)
        pxyz = np.array([c for c, _, _ in prot])
        pel = [e for _, e, _ in prot]
        fractions = []
        for i, atom in enumerate(mol.GetAtoms()):
            if atom.GetSymbol() not in NONPOLAR:
                continue
            a_free = free.atomArea(i)
            if a_free <= 0 or bound.atomArea(len(prot) + i) / a_free >= sasa_cut:
                continue
            near = np.flatnonzero(np.linalg.norm(pxyz - lig[i], axis=1) <= 4.5)
            if len(near):
                fractions.append(sum(pel[j] in {"C", "S"} for j in near) / len(near))
        return {
            "pose": pose.id,
            "buried_nonpolar": len(fractions),
            "complementarity": round(float(np.mean(fractions)), 3) if fractions else None,
        }


def _worker_python() -> Path | None:
    prefix = os.environ.get("PAH_CONDA_PREFIX") or ".tools/conda-env"
    py = Path(prefix) / "bin" / "python"
    return py if py.is_file() else None


WORKER = Path(__file__).with_name("minimise_worker.py")


@register
class MinimisationDrift(Check):
    id = "l4.minimisation_drift"
    layer = Layer.VALIDITY
    title = "Pose stability under short restrained minimisation (OpenMM, AMBER14 and OpenFF)"
    requires_modules = ("rdkit",)

    def applies(self, ctx: CheckContext) -> str | None:
        return _ligand_outputs(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        py = _worker_python()
        if py is None:
            return self.skip(
                SkipReason.TOOL_MISSING,
                "conda environment with OpenMM and OpenFF not found (PAH_CONDA_PREFIX)",
            )
        th = (outputs.configured(self.id, "drift"),)
        limit = float(th[0].value)
        rows = []
        for pose in _poses(ctx)[:10]:
            out = pose.structure.with_name(pose.structure.stem + "_minimised.json")
            args = {
                "receptor": str(outputs.receptor_of(pose)),
                "ligand": str(pose.ligand),
                "ph": ctx.manifest.ph or 7.4,
                "out": str(out),
            }
            proc = subprocess.run(
                [str(py), "-I", str(WORKER), json.dumps(args)],
                capture_output=True,
                text=True,
                timeout=900,
            )
            if proc.returncode != 0:
                tail = (proc.stderr or proc.stdout).strip().splitlines()[-1:] or ["no output"]
                if "ModuleNotFoundError" in tail[0]:
                    return self.skip(SkipReason.TOOL_MISSING, f"minimisation worker: {tail[0]}")
                rows.append({"pose": pose.id, "error": tail[0]})
                continue
            rows.append({"pose": pose.id, **json.loads(out.read_text())})
        done = [r for r in rows if "drift_A" in r]
        if not done:
            raise outputs.OutputUnavailableError(
                "minimisation failed for every pose: " + "; ".join(r["error"] for r in rows[:3])
            )
        rep = _rep_id(ctx)
        rr = next((r for r in done if r["pose"] == rep), done[0])
        m = {
            "poses": len(done),
            "drift_A": rr["drift_A"],
            "max_drift_A": max(r["drift_A"] for r in done),
            "poses_over": sum(1 for r in done if r["drift_A"] > limit),
            "failed": len(rows) - len(done),
        }
        ev = {"representative": rep, "poses": rows, "method": rr.get("method")}
        tool = ToolRef(name="openmm", version=rr.get("openmm"))
        if rr["drift_A"] > limit:
            return self.finding(
                Gate.WARN,
                f"{rep} moves {rr['drift_A']} Å under restrained minimisation",
                measurements=m,
                thresholds=th,
                evidence=ev,
                tool=tool,
            )
        return self.finding(
            Gate.PASS,
            f"{rep} moves {rr['drift_A']} Å under restrained "
            f"minimisation; {m['poses_over']} of {len(done)} poses above "
            f"{limit} Å",
            measurements=m,
            thresholds=th,
            evidence=ev,
            tool=tool,
        )


# --------------------------------------------------------------------------------------------
# Structure-level checks (complexes, all structures)


def _structures(ctx: CheckContext) -> list[Any]:
    return [p for p in outputs.primary_set(ctx).ranked()][:MAX_POSES]


def heavy_atom_clashes(st: Any, overlap: float) -> tuple[int, int]:
    """(clashing pairs, heavy atoms): non-bonded pairs in different residues closer than the sum
    of van der Waals radii minus `overlap`."""
    import gemmi

    st.setup_entities()
    ns = gemmi.NeighborSearch(st[0], st.cell, 5).populate()
    cs = gemmi.ContactSearch(4.0)
    cs.ignore = gemmi.ContactSearch.Ignore.AdjacentResidues
    count = 0
    atoms = sum(1 for ch in st[0] for r in ch for a in r if a.element.name != "H")
    for c in cs.find_contacts(ns):
        a, b = c.partner1.atom, c.partner2.atom
        if a.element.name == "H" or b.element.name == "H":
            continue
        if c.dist < a.element.vdw_r + b.element.vdw_r - overlap and not _bonded(c):
            count += 1
    return count, atoms


def _bonded(c: Any) -> bool:
    """Disulfides and covalent links are not clashes."""
    a, b = c.partner1.atom, c.partner2.atom
    return bool(
        c.dist < 2.2
        and {a.element.name, b.element.name} <= {"S", "C", "N", "O"}
        and (a.element.name == "S" or c.dist < 1.9)
    )


@register
class StructureClashes(Check):
    id = "l4.structure.clashes"
    layer = Layer.VALIDITY
    title = "Steric clashes (heavy-atom clashscore approximation)"
    requires_modules = ("gemmi",)

    def applies(self, ctx: CheckContext) -> str | None:
        return outputs.needs_predictions(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        th = (outputs.configured(self.id, "clashscore"), outputs.configured(self.id, "overlap"))
        rows = []
        for pose in _structures(ctx):
            clashes, atoms = heavy_atom_clashes(
                outputs.read_structure(pose.structure), float(th[1].value)
            )
            rows.append(
                {
                    "pose": pose.id,
                    "clashes": clashes,
                    "clashscore": round(1000 * clashes / atoms, 2) if atoms else None,
                }
            )
        top = rows[0]
        m = {
            "poses": len(rows),
            "clashscore": top["clashscore"],
            "clashes": top["clashes"],
            "max_clashscore": max(r["clashscore"] or 0 for r in rows),
        }
        ev = {"poses": rows, "method": "gemmi ContactSearch, heavy atoms, vdW overlap >= 0.4 Å"}
        gate = Gate.WARN if (top["clashscore"] or 0) > float(th[0].value) else Gate.PASS
        return self.finding(
            gate,
            f"clashscore {top['clashscore']} ({top['clashes']} clashes) for {top['pose']}",
            measurements=m,
            thresholds=th,
            evidence=ev,
        )


def _ca_segments(st: Any) -> dict[str, Any]:
    import numpy as np

    out = {}
    for ch in st[0]:
        pts = [r.find_atom("CA", "*").pos.tolist() for r in ch if r.find_atom("CA", "*")]
        if len(pts) > 1:
            out[ch.name] = np.array(pts)
    return out


def _segment_distance(p: Any, q: Any) -> Any:
    """Minimum distance between every segment of trace p and every segment of trace q."""
    import numpy as np

    a0, a1 = p[:-1], p[1:]
    b0, b1 = q[:-1], q[1:]
    best = np.inf
    for t in np.linspace(0, 1, 5):
        pa = a0 + t * (a1 - a0)
        for s in np.linspace(0, 1, 5):
            pb = b0 + s * (b1 - b0)
            d = np.linalg.norm(pa[:, None, :] - pb[None, :, :], axis=2)
            best = min(best, float(d.min()))
    return best


@register
class StructureTopology(Check):
    id = "l4.structure.topology"
    layer = Layer.VALIDITY
    title = "Chains not topologically entangled"
    requires_modules = ("gemmi", "numpy")

    def applies(self, ctx: CheckContext) -> str | None:
        reason = outputs.needs_predictions(ctx)
        if reason:
            return reason
        return (
            None
            if len(ctx.manifest.proteins) > 1 or any(p.copies > 1 for p in ctx.manifest.proteins)
            else "single-chain input"
        )

    def run(self, ctx: CheckContext) -> Finding:
        th = (outputs.configured(self.id, "segment_distance"),)
        rows = []
        for pose in _structures(ctx):
            traces = _ca_segments(outputs.read_structure(pose.structure))
            names = sorted(traces)
            pairs = []
            for i, a in enumerate(names):
                for b in names[i + 1 :]:
                    pairs.append(
                        {
                            "chains": f"{a}-{b}",
                            "min_segment_A": round(_segment_distance(traces[a], traces[b]), 2),
                        }
                    )
            rows.append({"pose": pose.id, "pairs": pairs})
        flagged = [
            (r["pose"], p["chains"], p["min_segment_A"])
            for r in rows
            for p in r["pairs"]
            if p["min_segment_A"] < float(th[0].value)
        ]
        m = {"poses": len(rows), "entangled_pairs": len(flagged)}
        if flagged:
            pose, chains, d = flagged[0]
            return self.finding(
                Gate.STOP,
                f"{len(flagged)} chain pairs with CA traces closer "
                f"than {th[0].value} Å (first: {pose} {chains} {d} Å)",
                measurements=m,
                thresholds=th,
                evidence={"poses": rows},
            )
        return self.finding(
            Gate.PASS,
            f"no interpenetrating chain pairs in {len(rows)} models",
            measurements=m,
            thresholds=th,
            evidence={"poses": rows},
        )


@register
class InterfaceChemistry(Check):
    id = "l4.interface.chemistry"
    layer = Layer.VALIDITY
    title = "Interface buried area, contacts and salt bridges"
    requires_modules = ("freesasa", "gemmi")

    def applies(self, ctx: CheckContext) -> str | None:
        return StructureTopology().applies(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        th = (outputs.configured(self.id, "buried_area"),)
        rows = [self._interface(p) for p in _structures(ctx)[:5]]
        top = rows[0]
        m = {
            "buried_area_A2": top["buried_area_A2"],
            "contacts": top["contacts"],
            "salt_bridges": top["salt_bridges"],
            "models": len(rows),
        }
        gate = Gate.WARN if top["buried_area_A2"] < float(th[0].value) else Gate.PASS
        return self.finding(
            gate,
            f"{top['pose']}: buried area {top['buried_area_A2']} Å², "
            f"{top['contacts']} residue contacts, {top['salt_bridges']} salt "
            "bridges",
            measurements=m,
            thresholds=th,
            evidence={"models": rows},
            tool=ToolRef(name="freesasa"),
        )

    def _interface(self, pose: Any) -> dict[str, Any]:
        import freesasa
        import gemmi

        st = outputs.read_structure(pose.structure)
        st.remove_ligands_and_waters()
        chains = [ch.name for ch in st[0]]

        def area(names: set[str]) -> float:
            xyz, radii = [], []
            for ch in st[0]:
                if ch.name in names:
                    for r in ch:
                        for a in r:
                            xyz += a.pos.tolist()
                            radii.append(a.element.vdw_r)
            return float(freesasa.calcCoord(xyz, radii).totalArea()) if radii else 0.0

        first, rest = {chains[0]}, set(chains[1:])
        buried = area(first) + area(rest) - area(first | rest)
        ns = gemmi.NeighborSearch(st[0], st.cell, 5).populate()
        contacts: set[tuple[str, str]] = set()
        salt = set()
        cs = gemmi.ContactSearch(4.0)
        for c in cs.find_contacts(ns):
            ca, cb = c.partner1, c.partner2
            if (ca.chain.name in first) == (cb.chain.name in first):
                continue
            ka = f"{ca.residue.name}{ca.residue.seqid.num}{ca.chain.name}"
            kb = f"{cb.residue.name}{cb.residue.seqid.num}{cb.chain.name}"
            contacts.add(tuple(sorted((ka, kb))))  # type: ignore[arg-type]
            names = {(ca.residue.name, ca.atom.name), (cb.residue.name, cb.atom.name)}
            pos = any(
                n in {("LYS", "NZ"), ("ARG", "NH1"), ("ARG", "NH2"), ("ARG", "NE")} for n in names
            )
            neg = any(
                n in {("ASP", "OD1"), ("ASP", "OD2"), ("GLU", "OE1"), ("GLU", "OE2")} for n in names
            )
            if pos and neg and c.dist <= 4.0:
                salt.add(tuple(sorted((ka, kb))))
        return {
            "pose": pose.id,
            "buried_area_A2": round(buried, 1),
            "contacts": len(contacts),
            "salt_bridges": len(salt),
        }


@register
class MolProbity(Check):
    id = "l4.molprobity"
    layer = Layer.VALIDITY
    title = "MolProbity clashscore, Ramachandran and rotamer outliers"

    def applies(self, ctx: CheckContext) -> str | None:
        return outputs.needs_predictions(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        import shutil

        exe = shutil.which("phenix.molprobity") or shutil.which("molprobity.molprobity")
        if exe is None:
            return self.skip(
                SkipReason.TOOL_MISSING,
                "phenix.molprobity not on PATH; the "
                "heavy-atom clash approximation is l4.structure.clashes",
            )
        pose = _structures(ctx)[0]
        proc = subprocess.run(
            [exe, str(pose.structure)],
            capture_output=True,
            text=True,
            timeout=1800,
            cwd=str(pose.structure.parent),
        )
        values: dict[str, Any] = {}
        for line in proc.stdout.splitlines():
            for key in ("Clashscore", "Ramachandran outliers", "Rotamer outliers"):
                if line.strip().startswith(key):
                    values[key.lower().replace(" ", "_")] = line.split("=")[-1].strip()
        gate = Gate.PASS if proc.returncode == 0 else Gate.WARN
        return self.finding(
            gate,
            ", ".join(f"{k} {v}" for k, v in values.items()) or "no summary parsed",
            measurements=values,
            tool=ToolRef(name="molprobity"),
        )


SCORE_KEYS = (
    "vina_affinity",
    "minimizedAffinity",
    "CNNscore",
    "diffdock_confidence",
    "confidence_score",
    "ranking_score",
    "aggregate_score",
)


def _score_key(pose: Any) -> str | None:
    return next((k for k in SCORE_KEYS if k in pose.scores), None)


@register
class ScoreDistribution(Check):
    id = "l4.score.distribution"
    layer = Layer.VALIDITY
    title = "Score distribution of the screened library"

    def applies(self, ctx: CheckContext) -> str | None:
        return outputs.needs_predictions(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        import numpy as np

        by_ligand: dict[str, float] = {}
        key = None
        for pset in outputs.assessed_sets(ctx) + outputs.control_sets(ctx, "decoy"):
            for pose in pset.ranked():
                key = key or _score_key(pose)
                if key and key in pose.scores:
                    lig = pose.ligand_id or pset.source.name
                    val = float(pose.scores[key])
                    better = (
                        val < by_ligand.get(lig, np.inf)
                        if "ffinity" in key
                        else (val > by_ligand.get(lig, -np.inf))
                    )
                    if lig not in by_ligand or better:
                        by_ligand[lig] = val
        if not by_ligand:
            raise outputs.OutputUnavailableError("no scores in the predictions")
        vals = np.array(list(by_ligand.values()))
        m = {
            "ligands": len(vals),
            "score": key,
            "median": round(float(np.median(vals)), 3),
            "min": round(float(vals.min()), 3),
            "max": round(float(vals.max()), 3),
            "distinct": len(set(np.round(vals, 3))),
        }
        gate = Gate.WARN if len(vals) > 1 and m["distinct"] == 1 else Gate.PASS
        return self.finding(
            gate,
            f"{len(vals)} ligands, {key} median {m['median']} "
            f"(range {m['min']} to {m['max']}); scores rank within this run "
            "only",
            measurements=m,
            evidence={"scores": by_ligand},
        )


@register
class TopHitInteractions(Check):
    id = "l4.interactions.top_hits"
    layer = Layer.VALIDITY
    title = "Interactions of the top-ranked hits"
    requires_modules = ("plip", "openbabel")

    def applies(self, ctx: CheckContext) -> str | None:
        return outputs.needs_predictions(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        poses = [p for s in outputs.assessed_sets(ctx) for p in s.ranked() if p.rank == 0]
        key = _score_key(poses[0]) if poses else None
        if key:
            poses.sort(key=lambda p: p.scores.get(key, 0.0), reverse="ffinity" not in key)
        rows = []
        for pose in poses[:5]:
            inter = plip_interactions(pose.structure)
            rows.append(
                {
                    "pose": pose.id,
                    "ligand": pose.ligand_id,
                    "score": pose.scores.get(key) if key else None,
                    "interactions": len(inter),
                    "hbonds": sum(1 for r in inter if r["type"] == "hbond"),
                }
            )
        empty = [r["pose"] for r in rows if r["interactions"] == 0]
        m = {"hits": len(rows), "without_interactions": len(empty)}
        gate = Gate.WARN if empty else Gate.PASS
        return self.finding(
            gate,
            f"{len(rows)} top hits; {len(empty)} without any PLIP interaction",
            measurements=m,
            evidence={"hits": rows},
            tool=ToolRef(name="plip"),
        )
