"""Layer 3: the tool operates inside the regime where its accuracy was established.

Training exposure is reported as context. It narrows what a result shows about generalisation
and does not by itself lower confidence in the result (specification, layer 3).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pah.checks import outputs, resolve
from pah.core.check import Check, CheckContext, register
from pah.core.models import Finding, Gate, Layer, ToolRef
from pah.sources import SourceUnavailableError

SPEC_L3 = "Specification, Layer 3 (applicability)"
AFFINITY_WORDS = re.compile(r"\b(affinity|kd|ki|ic50|ec50|binding free energy|delta ?g)\b", re.I)


def learned_models(ctx: CheckContext) -> list[tuple[str, dict[str, Any]]]:
    out = []
    for e in outputs.executors(ctx):
        entry = outputs.model_entry(e)
        if entry and entry.get("learned"):
            out.append((e, entry))
    return out


def earliest_cutoff(ctx: CheckContext) -> tuple[str, str] | None:
    """(cutoff date, executor) for the learned model with the earliest known cutoff."""
    known = [(m["training_cutoff"], e) for e, m in learned_models(ctx) if m.get("training_cutoff")]
    return min(known) if known else None


def _needs_learned(ctx: CheckContext) -> str | None:
    if not learned_models(ctx):
        return "no learned executor declared (physics or empirical scoring has no training set)"
    return (
        None if earliest_cutoff(ctx) else "training cutoff unknown (see l3.model.training_cutoff)"
    )


@register
class TrainingCutoff(Check):
    id = "l3.model.training_cutoff"
    layer = Layer.APPLICABILITY
    title = "Model training cutoff recorded"

    def applies(self, ctx: CheckContext) -> str | None:
        return None if outputs.executors(ctx) else "no executor declared"

    def run(self, ctx: CheckContext) -> Finding:
        rows: list[dict[str, Any]] = []
        for e in outputs.executors(ctx):
            entry = outputs.model_entry(e)
            if entry is None:
                rows.append({"executor": e, "registered": False})
                continue
            rows.append(
                {
                    "executor": e,
                    "registered": True,
                    "learned": bool(entry.get("learned")),
                    "training_cutoff": entry.get("training_cutoff"),
                    "origin": entry.get("cutoff_origin"),
                    "evidence": entry.get("cutoff_evidence"),
                }
            )
        pdb_id, _ = outputs.reference_ids(ctx)
        ref_date = None
        if pdb_id:
            try:
                ref_date = resolve.pdb_entry(ctx, pdb_id).initial_release_date
            except SourceUnavailableError:
                ref_date = None
        for r in rows:
            if r.get("training_cutoff") and ref_date:
                r["reference_before_cutoff"] = ref_date < r["training_cutoff"]
        unknown = [
            r["executor"]
            for r in rows
            if not r["registered"] or (r["learned"] and not r["training_cutoff"])
        ]
        th = (
            resolve.threshold(
                "training_cutoff", "recorded", "==", SPEC_L3 + ": stop when unknown", "published"
            ),
        )
        m: dict[str, Any] = {
            "executors": len(rows),
            "unknown": len(unknown),
            "reference_released": ref_date,
        }
        ev: dict[str, Any] = {"models": rows}
        if unknown:
            return self.finding(
                Gate.STOP,
                f"training cutoff unknown for {', '.join(unknown)}",
                measurements=m,
                thresholds=th,
                evidence=ev,
            )
        parts = [
            f"{r['executor']} {r['training_cutoff']}"
            if r["learned"]
            else f"{r['executor']} not learned"
            for r in rows
        ]
        if ref_date:
            inside = [r["executor"] for r in rows if r.get("reference_before_cutoff")]
            parts.append(
                f"reference {pdb_id} released {ref_date}"
                + (f", before the cutoff of {', '.join(inside)}" if inside else "")
            )
        return self.finding(Gate.PASS, "; ".join(parts), measurements=m, thresholds=th, evidence=ev)


def _parent(smiles: str) -> Any:
    """Neutral parent without explicit hydrogens, so charge states and [H] atoms do not count."""
    from rdkit import Chem, rdBase
    from rdkit.Chem.MolStandardize import rdMolStandardize

    with rdBase.BlockLogs():
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        Chem.RemoveStereochemistry(mol)
        return rdMolStandardize.Uncharger().uncharge(Chem.RemoveHs(mol))


def fingerprint_similarity(smiles_a: str, smiles_b: str) -> float | None:
    """Tanimoto similarity of RDKit topological fingerprints of the neutral parents."""
    from rdkit import Chem, DataStructs

    a, b = _parent(smiles_a), _parent(smiles_b)
    if a is None or b is None:
        return None
    return float(DataStructs.TanimotoSimilarity(Chem.RDKFingerprint(a), Chem.RDKFingerprint(b)))


def _query_smiles(ctx: CheckContext) -> list[tuple[str, str]]:
    out = []
    for lig in ctx.manifest.ligands:
        smiles, _ = resolve.ligand_smiles(ctx, lig)
        if smiles:
            out.append((lig.id, smiles))
    return out


def analogues(ctx: CheckContext, smiles: str, cutoff: str) -> dict[str, Any]:
    """CCD components above the Tanimoto threshold and the pre-cutoff entries that contain them."""

    def build() -> dict[str, Any]:
        tanimoto = float(outputs.value("l3.exposure.ligand_prevalence", "tanimoto"))
        hits = ctx.sources.rcsb_search.similar_components(smiles)
        ctx.record(hits.provenance)
        comps: list[dict[str, Any]] = []
        for code in hits.identifiers[:25]:
            try:
                cc = resolve.chemcomp(ctx, code)
            except SourceUnavailableError:
                continue
            ref = cc.smiles_stereo or cc.smiles
            sim = fingerprint_similarity(smiles, ref) if ref else None
            if sim is not None and sim > tanimoto:
                comps.append({"code": code, "tanimoto": round(sim, 3)})
        entries: set[str] = set()
        total = 0
        for c in comps:
            res = ctx.sources.rcsb_search.entries_with_component(c["code"], cutoff, rows=1000)
            ctx.record(res.provenance)
            c["entries"] = res.total
            total += res.total
            entries |= set(res.identifiers)
        systems = len(entries) if total <= 1000 else total
        return {"components": comps, "systems": systems, "entries": sorted(entries)}

    return ctx.memo(f"analogues:{smiles}:{cutoff}", build)


@register
class LigandPrevalence(Check):
    id = "l3.exposure.ligand_prevalence"
    layer = Layer.APPLICABILITY
    title = "Ligand analogues in pre-cutoff training systems"
    requires_modules = ("rdkit",)

    def applies(self, ctx: CheckContext) -> str | None:
        if not ctx.manifest.ligands:
            return "no ligand declared"
        return _needs_learned(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        cutoff, model = earliest_cutoff(ctx)  # type: ignore[misc]
        th = (outputs.configured(self.id, "tanimoto"), outputs.configured(self.id, "systems"))
        rows: list[dict[str, Any]] = []
        for lig_id, smiles in _query_smiles(ctx):
            a = analogues(ctx, smiles, cutoff)
            rows.append({"ligand": lig_id, "systems": a["systems"], "components": a["components"]})
        worst = max(rows, key=lambda r: r["systems"])
        m: dict[str, Any] = {
            "cutoff": cutoff,
            "systems": worst["systems"],
            "analogue_components": len(worst["components"]),
        }
        tool = ToolRef(name="RCSB search (chemical) + RDKit topological fingerprint")
        prevalent = [r["ligand"] for r in rows if r["systems"] > th[1].value]
        codes = ", ".join(c["code"] for c in worst["components"][:6]) or "none"
        msg = (
            f"{worst['systems']} PDB entries released before {cutoff} ({model} cutoff) "
            f"contain analogues of {worst['ligand']} above Tanimoto {th[0].value}: {codes}"
        )
        gate = Gate.WARN if prevalent else Gate.PASS
        return self.finding(
            gate, msg, measurements=m, thresholds=th, evidence={"ligands": rows}, tool=tool
        )


@register
class SequenceExposure(Check):
    id = "l3.exposure.sequence"
    layer = Layer.APPLICABILITY
    title = "Chain sequence identity to pre-cutoff entries (secondary measure)"

    def applies(self, ctx: CheckContext) -> str | None:
        if not any(p.sequence for p in ctx.manifest.proteins):
            return "no protein sequence declared"
        return _needs_learned(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        cutoff, model = earliest_cutoff(ctx)  # type: ignore[misc]
        rows: list[dict[str, Any]] = []
        for p in ctx.manifest.proteins:
            if not p.sequence:
                continue
            row: dict[str, Any] = {"protein": p.id}
            for ident in (0.95, 0.4):
                res = ctx.sources.rcsb_search.sequence_hits(p.sequence, ident, cutoff, rows=5)
                ctx.record(res.provenance)
                row[f"entries_{int(ident * 100)}"] = res.total
                row[f"examples_{int(ident * 100)}"] = list(res.identifiers)
            rows.append(row)
        th = (outputs.configured(self.id, "identity"),)
        m: dict[str, Any] = {
            "cutoff": cutoff,
            "entries_95": max(r["entries_95"] for r in rows),
            "entries_40": max(r["entries_40"] for r in rows),
        }
        parts = [
            f"{r['protein']}: {r['entries_95']} entries at 95 percent identity, "
            f"{r['entries_40']} at 40 percent, released before {cutoff}"
            for r in rows
        ]
        return self.finding(
            Gate.PASS,
            "; ".join(parts) + " (reported, not gating)",
            measurements=m,
            thresholds=th,
            evidence={"proteins": rows, "model": model, "gating": False},
            tool=ToolRef(name="RCSB search (sequence, MMseqs2)"),
        )


_FDEF: Any = None


def sucos(ref: Any, probe: Any) -> float:
    """SuCOS (Leung et al. 2019): feature-map overlap and shape protrusion, both in place."""

    from rdkit import RDConfig
    from rdkit.Chem import rdShapeHelpers

    allchem = outputs.rdkit_module("AllChem")
    from rdkit.Chem.FeatMaps import FeatMaps

    global _FDEF
    if _FDEF is None:
        _FDEF = allchem.BuildFeatureFactory(str(Path(RDConfig.RDDataDir) / "BaseFeatures.fdef"))
    keep = (
        "Donor",
        "Acceptor",
        "NegIonizable",
        "PosIonizable",
        "ZnBinder",
        "Aromatic",
        "Hydrophobe",
        "LumpedHydrophobe",
    )
    params = {k: FeatMaps.FeatMapParams() for k in _FDEF.GetFeatureFamilies()}
    feats = [[f for f in _FDEF.GetFeaturesForMol(m) if f.GetFamily() in keep] for m in (ref, probe)]
    if not feats[0] or not feats[1]:
        fm_score = 0.0
    else:
        fm = FeatMaps.FeatMap(feats=feats[0], weights=[1] * len(feats[0]), params=params)
        fm.scoreMode = FeatMaps.FeatMapScoreMode.All  # type: ignore[misc]
        fm_score = fm.ScoreFeats(feats[1]) / min(fm.GetNumFeatures(), len(feats[1]))
    protrude = rdShapeHelpers.ShapeProtrudeDist(ref, probe, allowReordering=False)
    return float(0.5 * min(fm_score, 1.0) + 0.5 * (1.0 - protrude))


def _with_coords(mol: Any, xyz: Any) -> Any:
    from rdkit import Chem
    from rdkit.Geometry import Point3D

    out = Chem.Mol(outputs.heavy(mol))
    conf = out.GetConformer()
    for i, p in enumerate(xyz):
        conf.SetAtomPosition(i, Point3D(*map(float, p)))
    return out


@register
class PocketExposure(Check):
    id = "l3.exposure.pocket"
    layer = Layer.APPLICABILITY
    title = "Pocket similarity to pre-cutoff complexes (SuCOS times pocket coverage)"
    requires_modules = ("rdkit", "gemmi", "numpy")

    def applies(self, ctx: CheckContext) -> str | None:
        if not ctx.manifest.ligands:
            return "no ligand declared"
        reason = _needs_learned(ctx)
        if reason:
            return reason
        if not ctx.manifest.predictions and outputs.reference_ligand(ctx) is None:
            return "no prediction and no reference ligand to define the query pocket"
        return None

    def _query(self, ctx: CheckContext) -> tuple[Any, Any, Any, str]:
        """(structure, ligand mol, ligand coords) of the pocket being asked about."""
        if ctx.manifest.predictions:
            pose = outputs.representative(ctx)
            mol = outputs.pose_mol(pose)
            return outputs.read_structure(pose.structure), mol, outputs.heavy_coords(mol), pose.id
        ref = outputs.reference_ligand(ctx)
        assert ref is not None
        pdb_id, _ = outputs.reference_ids(ctx)
        st = outputs.read_structure(resolve.mmcif_path(ctx, str(pdb_id)))
        return st, ref.mol, ref.coords, f"reference {ref.code} in {ref.source} (pre-run)"

    def run(self, ctx: CheckContext) -> Finding:
        cutoff, model = earliest_cutoff(ctx)  # type: ignore[misc]
        th = (outputs.configured(self.id, "similarity"), outputs.configured(self.id, "entries"))
        q_st, q_mol, q_xyz, q_label = self._query(ctx)
        q_pocket = outputs.pocket_residues(q_st, q_xyz, 6.0)
        smiles = _query_smiles(ctx)[0][1]
        seq = next((p.sequence for p in ctx.manifest.proteins if p.sequence), None)
        candidates = self._candidates(ctx, smiles, seq, cutoff, int(th[1].value))
        rows: list[dict[str, Any]] = []
        for pdb_id in candidates:
            try:
                rows.append(self._compare(ctx, pdb_id, q_st, q_mol, q_xyz, q_pocket))
            except (outputs.OutputUnavailableError, SourceUnavailableError, ValueError) as exc:
                rows.append({"entry": pdb_id, "error": str(exc)})
        scored = [r for r in rows if "similarity" in r]
        best = max(scored, key=lambda r: r["similarity"], default=None)
        m: dict[str, Any] = {
            "cutoff": cutoff,
            "entries_compared": len(scored),
            "max_similarity": best["similarity"] if best else None,
            "pocket_residues": len(q_pocket),
        }
        ev: dict[str, Any] = {"query": q_label, "model": model, "entries": rows}
        if best is None:
            return self.finding(
                Gate.PASS,
                f"no pre-cutoff holo entry with an analogue found (cutoff {cutoff})",
                measurements=m,
                thresholds=th,
                evidence=ev,
            )
        msg = (
            f"max similarity {best['similarity']} to {best['entry']} ({best['ligand']}, "
            f"SuCOS {best['sucos']}, coverage {best['coverage']}), released before {cutoff}"
        )
        gate = Gate.WARN if best["similarity"] > th[0].value else Gate.PASS
        return self.finding(gate, msg, measurements=m, thresholds=th, evidence=ev)

    def _candidates(
        self, ctx: CheckContext, smiles: str, seq: str | None, cutoff: str, limit: int
    ) -> list[str]:
        ligand_entries = set(analogues(ctx, smiles, cutoff)["entries"])
        same_target: list[str] = []
        if seq:
            res = ctx.sources.rcsb_search.sequence_hits(seq, 0.9, cutoff, rows=200)
            ctx.record(res.provenance)
            same_target = list(res.identifiers)
        pdb_id, _ = outputs.reference_ids(ctx)
        ordered = [e for e in same_target if e in ligand_entries]
        if pdb_id and pdb_id.upper() in ligand_entries | set(same_target):
            ordered = [pdb_id.upper()] + [e for e in ordered if e != pdb_id.upper()]
        if not ordered:
            ordered = same_target
        return ordered[:limit]

    def _compare(
        self, ctx: CheckContext, pdb_id: str, q_st: Any, q_mol: Any, q_xyz: Any, q_pocket: Any
    ) -> dict[str, Any]:
        import numpy as np

        e_st = outputs.read_structure(resolve.mmcif_path(ctx, pdb_id))
        sup = outputs.superposition(q_st, e_st)
        probe = _with_coords(q_mol, sup.apply(q_xyz))
        best: dict[str, Any] = {"entry": pdb_id, "similarity": 0.0}
        for ch in e_st[0]:
            for res in ch:
                heavy = [a for a in res if a.element.name != "H"]
                if res.het_flag != "H" or res.name in outputs.WATER or len(heavy) < 6:
                    continue
                lig_xyz = np.array([a.pos.tolist() for a in heavy])
                if (
                    np.linalg.norm(lig_xyz.mean(0) - probe.GetConformer().GetPositions().mean(0))
                    > 8
                ):
                    continue
                mol, _ = outputs.residue_mol(res, None)
                score = sucos(mol, probe)
                e_pocket = {
                    (p.chain, p.seqnum, p.icode)
                    for p in outputs.pocket_residues(e_st, lig_xyz, 6.0)
                }
                mapped = [sup.residue_map.get((p.chain, p.seqnum, p.icode)) for p in q_pocket]
                covered = sum(1 for k in mapped if k in e_pocket)
                coverage = covered / len(q_pocket) if q_pocket else 0.0
                sim = round(100 * score * coverage, 1)
                if sim >= best["similarity"]:
                    best = {
                        "entry": pdb_id,
                        "ligand": res.name,
                        "sucos": round(score, 3),
                        "coverage": round(coverage, 3),
                        "similarity": sim,
                        "ca_rmsd": round(sup.rmsd, 2),
                    }
        if "ligand" not in best:
            best["ligand"] = None
        return best


MODALITY_KEYWORDS = {
    "membrane": ("Transmembrane", "Membrane"),
    "antibody": ("Immunoglobulin domain", "Antibody"),
    "lipid": ("Lipid-binding",),
}


@register
class Modality(Check):
    id = "l3.regime.modality"
    layer = Layer.APPLICABILITY
    title = "Modality inside the validated set; token count against the training crop"

    def applies(self, ctx: CheckContext) -> str | None:
        return None if outputs.executors(ctx) else "no executor declared"

    def run(self, ctx: CheckContext) -> Finding:
        modalities = self._modalities(ctx)
        tokens = sum(len(p.sequence or "") * p.copies for p in ctx.manifest.proteins)
        for lig in ctx.manifest.ligands:
            prep = resolve.prepared_ligand(ctx, lig)
            if prep.mol is not None:
                tokens += prep.mol.GetNumHeavyAtoms() * lig.copies
        rows, outside, over_crop = [], [], []
        for e in outputs.executors(ctx):
            entry = outputs.model_entry(e) or {}
            valid = set(entry.get("validated_modalities", []))
            missing = sorted(m for m in modalities if m not in valid)
            crop = entry.get("training_crop_tokens")
            rows.append(
                {
                    "executor": e,
                    "validated": sorted(valid),
                    "outside": missing,
                    "crop_tokens": crop,
                    "crop_origin": entry.get("crop_origin"),
                }
            )
            if missing:
                outside.append(f"{e}: {', '.join(missing)}")
            if crop and tokens > crop:
                over_crop.append(f"{e}: {tokens} tokens above crop {crop}")
        m: dict[str, Any] = {
            "modalities": len(modalities),
            "tokens": tokens,
            "outside": len(outside),
        }
        ev: dict[str, Any] = {"modalities": sorted(modalities), "models": rows}
        problems = outside + over_crop
        if problems:
            return self.finding(Gate.WARN, "; ".join(problems), measurements=m, evidence=ev)
        return self.finding(
            Gate.PASS,
            f"modalities {', '.join(sorted(modalities))} inside the validated set; {tokens} tokens",
            measurements=m,
            evidence=ev,
        )

    def _modalities(self, ctx: CheckContext) -> set[str]:
        m = ctx.manifest
        found = {"protein"}
        if m.ligands:
            found.add("protein_ligand")
        if len(m.proteins) > 1 or any(p.copies > 1 for p in m.proteins):
            found.add("protein_protein")
        for lig in m.ligands:
            prep = resolve.prepared_ligand(ctx, lig)
            if prep.metal:
                found.add("metal_site")
        for p in m.proteins:
            if not p.uniprot:
                continue
            try:
                ann = resolve.uniprot_annotations(ctx, p.uniprot)
            except SourceUnavailableError:
                continue
            kws = set(ann.keywords) | {f.type for f in ann.features}
            for name, keys in MODALITY_KEYWORDS.items():
                if kws & set(keys):
                    found.add(name)
        if self._covalent(ctx):
            found.add("covalent")
        return found

    def _covalent(self, ctx: CheckContext) -> bool:
        pdb_id, code = outputs.reference_ids(ctx)
        if not (pdb_id and code):
            return False
        try:
            st = outputs.read_structure(resolve.mmcif_path(ctx, pdb_id))
        except SourceUnavailableError:
            return False
        for conn in st.connections:
            names = {conn.partner1.res_id.name, conn.partner2.res_id.name}
            if code in names and conn.type.name == "Covale":
                return True
        return False


@register
class Endpoint(Check):
    id = "l3.metric.endpoint"
    layer = Layer.APPLICABILITY
    title = "Endpoint fits the tool"

    def applies(self, ctx: CheckContext) -> str | None:
        return None if outputs.executors(ctx) else "no executor declared"

    def run(self, ctx: CheckContext) -> Finding:
        endpoint = outputs.task_endpoint(ctx.task.id)
        claim = ctx.manifest.claim or ctx.task.claim
        rows: list[dict[str, Any]] = []
        bad: list[str] = []
        for e in outputs.executors(ctx):
            entry = outputs.model_entry(e) or {}
            supports = list(entry.get("endpoints", []))
            ok = endpoint in supports
            rows.append({"executor": e, "endpoints": supports, "fits": ok})
            if not ok:
                bad.append(e)
        claims_affinity = bool(AFFINITY_WORDS.search(claim)) and endpoint != "affinity_series"
        th = (
            resolve.threshold(
                "endpoint",
                str(endpoint),
                "in",
                SPEC_L3 + ": no affinity from "
                "interface confidence, no protein-protein affinity from Boltz-2",
                "published",
            ),
        )
        m: dict[str, Any] = {"endpoint": endpoint, "executors": len(rows), "not_fitting": len(bad)}
        ev: dict[str, Any] = {
            "claim": claim,
            "models": rows,
            "claim_names_affinity": claims_affinity,
        }
        if bad or claims_affinity:
            parts = [f"{', '.join(bad)} does not produce {endpoint}"] if bad else []
            if claims_affinity:
                parts.append(f"claim names an affinity endpoint; task endpoint is {endpoint}")
            return self.finding(
                Gate.STOP, "; ".join(parts), measurements=m, thresholds=th, evidence=ev
            )
        return self.finding(
            Gate.PASS,
            f"endpoint {endpoint} produced by {', '.join(r['executor'] for r in rows)}",
            measurements=m,
            thresholds=th,
            evidence=ev,
        )


@register
class ChemotypeExposure(Check):
    id = "l3.exposure.chemotype"
    layer = Layer.APPLICABILITY
    title = "Series chemotype (Murcko scaffold) in pre-cutoff entries"
    requires_modules = ("rdkit",)

    def applies(self, ctx: CheckContext) -> str | None:
        if not ctx.manifest.ligands:
            return "no ligand declared"
        return _needs_learned(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        from rdkit import Chem
        from rdkit.Chem.Scaffolds import MurckoScaffold

        cutoff, _ = earliest_cutoff(ctx)  # type: ignore[misc]
        scaffolds: dict[str, list[str]] = {}
        for lig_id, smiles in _query_smiles(ctx):
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                continue
            scaffold = Chem.MolToSmiles(MurckoScaffold.GetScaffoldForMol(mol))
            scaffolds.setdefault(scaffold, []).append(lig_id)
        rows: list[dict[str, Any]] = []
        for scaffold, ligs in scaffolds.items():
            if not scaffold:
                rows.append({"scaffold": "", "ligands": ligs, "systems": 0})
                continue
            a = analogues(ctx, scaffold, cutoff)
            rows.append({"scaffold": scaffold, "ligands": ligs, "systems": a["systems"]})
        th = (outputs.configured("l3.exposure.ligand_prevalence", "systems"),)
        worst = max(rows, key=lambda r: r["systems"])
        m: dict[str, Any] = {
            "scaffolds": len(rows),
            "max_systems": worst["systems"],
            "cutoff": cutoff,
        }
        gate = Gate.WARN if worst["systems"] > th[0].value else Gate.PASS
        return self.finding(
            gate,
            f"{len(rows)} scaffolds; {worst['scaffold'] or 'acyclic'} in "
            f"{worst['systems']} entries before {cutoff}",
            measurements=m,
            thresholds=th,
            evidence={"scaffolds": rows},
        )
