"""Layer 5: a valid result is corroborated.

Confidence is read locally and against per-model thresholds; samples are counted by independent
seed; the representative pose is the medoid of the largest cluster; agreement is weighted by how
independently the methods can fail; controls the claim requires must be present and sound.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pah.checks import outputs, resolve
from pah.core.check import Check, CheckContext, register
from pah.core.models import Finding, Gate, Layer, ToolRef

SPEC_L5 = "Specification, Layer 5 (output support)"
WEIGHTS = {
    ("seed", "seed"): "low",
    ("cofolding", "cofolding"): "moderate",
    ("cofolding", "docking"): "high",
    ("docking", "docking"): "moderate",
    ("crystal", "any"): "decisive",
}


def _ligand_outputs(ctx: CheckContext) -> str | None:
    reason = outputs.needs_predictions(ctx)
    if reason:
        return reason
    return None if ctx.manifest.ligands else "no ligand declared"


def _pose_frame(ctx: CheckContext, pose: Any) -> Any:
    """Heavy-atom ligand coordinates of `pose` in the ensemble frame."""
    target, _ = outputs.frame_target(ctx)
    xyz = outputs.heavy_coords(outputs.pose_mol(pose))
    if pose.structure != target:
        rot, tran, _, _ = outputs.superpose(pose.structure, target)
        xyz = xyz @ rot.T + tran
    return xyz


def _rmsd_to_reference(ctx: CheckContext, pose: Any) -> float | None:
    """Symmetry-aware RMSD of a pose to the crystal ligand; None when there is no reference or
    the predicted ligand is a different molecule (for example a modified analogue)."""
    ref = outputs.reference_ligand(ctx)
    if ref is None:
        return None
    target, _ = outputs.frame_target(ctx)
    pdb_id, _ = outputs.reference_ids(ctx)
    xyz = _pose_frame(ctx, pose)
    if pdb_id and target.name.upper() != f"{pdb_id.upper()}.CIF":
        # The frame is not the reference entry: place the pose on the reference first.
        ref_path = resolve.mmcif_path(ctx, pdb_id)
        rot, tran, _, _ = outputs.superpose(target, ref_path)
        xyz = xyz @ rot.T + tran
    try:
        value = outputs.symmetric_rmsd(outputs.pose_mol(pose), xyz, ref.mol, ref.coords)
    except (outputs.OutputUnavailableError, ValueError):
        return None
    return round(value, 3)


def _confidence(pose: Any) -> float | None:
    for key in (
        "confidence_score",
        "ranking_score",
        "aggregate_score",
        "CNNscore",
        "diffdock_confidence",
        "vina_affinity",
        "minimizedAffinity",
    ):
        if key in pose.scores:
            return round(float(pose.scores[key]), 3)
    return None


@register
class LocalConfidence(Check):
    id = "l5.confidence.local"
    layer = Layer.SUPPORT
    title = "Confidence restricted to the pocket; per-model thresholds"
    requires_modules = ("gemmi", "numpy")

    def applies(self, ctx: CheckContext) -> str | None:
        return outputs.needs_predictions(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        import numpy as np

        pset = outputs.primary_set(ctx)
        poses = outputs.ensemble_poses(ctx) if ctx.manifest.ligands else pset.ranked()
        rows: list[dict[str, Any]] = []
        for pose in poses[:25]:
            row: dict[str, Any] = {
                "pose": pose.id,
                **{k: round(float(v), 3) for k, v in pose.scores.items()},
            }
            if pose.plddt is not None:
                row["global_plddt"] = round(float(np.mean(pose.plddt)), 1)
                if pose.ligand and pose.plddt_residues:
                    st = outputs.read_structure(pose.structure)
                    pocket = {
                        (p.chain, p.seqnum)
                        for p in outputs.pocket_residues(
                            st, outputs.heavy_coords(outputs.pose_mol(pose)), 6.0
                        )
                    }
                    vals = [
                        v
                        for v, r in zip(pose.plddt, pose.plddt_residues, strict=False)
                        if tuple(r) in pocket
                    ]
                    if vals:
                        row["pocket_plddt"] = round(float(np.mean(vals)), 1)
                        row["pocket_residues"] = len(vals)
            if pose.pae is not None:
                row["pae"] = str(pose.pae)
            rows.append(row)
        rep = outputs.representative(ctx) if ctx.manifest.ligands else poses[0]
        rr = next((r for r in rows if r["pose"] == rep.id), rows[0])
        checks = []
        for name in ("pocket_plddt", "iptm", "CNNscore", "plddt"):
            th = outputs.model_threshold(pset.executor, name)
            value = rr.get(name if name != "plddt" else "global_plddt")
            if th is not None and value is not None:
                ok = _compare(value, th.comparator, float(th.value))
                checks.append((th, value, ok))
        metrics = self._separate_metrics(pset)
        th_all = tuple(c[0] for c in checks)
        m: dict[str, Any] = {"poses": len(rows)}
        for key in (
            "pocket_plddt",
            "global_plddt",
            "iptm",
            "ptm",
            "confidence_score",
            "CNNscore",
            "vina_affinity",
            "diffdock_confidence",
        ):
            if key in rr:
                m[key] = rr[key]
        ev: dict[str, Any] = {"representative": rep.id, "poses": rows, "metrics": metrics}
        if pset.ranked() and pset.ranked()[0].pae is not None:
            ev["pae"] = {"pose": pset.ranked()[0].id, "path": str(pset.ranked()[0].pae)}
        failed = [
            f"{c[0].name} {c[1]} (needs {c[0].comparator} {c[0].value})" for c in checks if not c[2]
        ]
        if failed:
            return self.finding(
                Gate.WARN,
                f"{rep.id}: " + "; ".join(failed),
                measurements=m,
                thresholds=th_all,
                evidence=ev,
            )
        if not checks:
            shown = ", ".join(f"{k} {v}" for k, v in m.items() if k != "poses")
            return self.finding(
                Gate.PASS,
                f"{rep.id}: {shown}; no per-model confidence "
                f"threshold registered for {pset.executor} (reported)",
                measurements=m,
                evidence=ev,
            )
        shown = ", ".join(f"{c[0].name.split('.')[-1]} {c[1]}" for c in checks)
        return self.finding(
            Gate.PASS, f"{rep.id}: {shown}", measurements=m, thresholds=th_all, evidence=ev
        )

    def _separate_metrics(self, pset: Any) -> list[dict[str, Any]]:
        out = []
        aff = pset.settings.get("affinity")
        for row in aff if isinstance(aff, list) else [aff] if aff else []:
            for key in ("affinity_pred_value", "affinity_probability_binary"):
                if key in row:
                    out.append(
                        {
                            "name": key,
                            "value": row[key],
                            "tool": pset.executor,
                            "read": "ranking within a series, never pose quality",
                            "separate": True,
                        }
                    )
        return out


def _compare(value: float, comparator: str, limit: float) -> bool:
    return {
        ">=": value >= limit,
        ">": value > limit,
        "<=": value <= limit,
        "<": value < limit,
        "==": value == limit,
    }.get(comparator, False)


@register
class Seeds(Check):
    id = "l5.sampling.seeds"
    layer = Layer.SUPPORT
    title = "Independent seeds counted separately from samples; duplicates flagged"
    requires_modules = ("numpy",)

    def applies(self, ctx: CheckContext) -> str | None:
        return outputs.needs_predictions(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        import hashlib

        from pah.executors import Family

        pset = outputs.primary_set(ctx)
        name = "seeds_docking" if pset.family is Family.DOCKING else "seeds_cofolding"
        th = (outputs.configured(self.id, name),)
        seeds = pset.seeds
        samples = len(pset.poses)
        digests: dict[str, list[str]] = {}
        for pose in outputs.ensemble_poses(ctx) if ctx.manifest.ligands else pset.ranked():
            src = pose.ligand or pose.structure
            text = (
                "".join(
                    line[30:54]
                    for line in src.read_text().splitlines()
                    if line[:6] in ("ATOM  ", "HETATM")
                )
                or src.read_text()
            )
            digests.setdefault(hashlib.sha256(text.encode()).hexdigest(), []).append(pose.id)
        duplicates = [ids for ids in digests.values() if len(ids) > 1]
        rows = [{"seed": s, "poses": sum(1 for p in pset.poses if p.seed == s)} for s in seeds]
        m = {
            "independent_seeds": len(seeds),
            "samples": samples,
            "duplicated_outputs": len(duplicates),
        }
        ev = {"executor": pset.executor, "seeds": rows, "duplicates": duplicates}
        if duplicates:
            return self.finding(
                Gate.STOP,
                f"{len(duplicates)} outputs repeated across seeds; a "
                "duplicated run is not an independent replicate",
                measurements=m,
                thresholds=th,
                evidence=ev,
            )
        if len(seeds) < float(th[0].value):
            return self.finding(
                Gate.WARN,
                f"{len(seeds)} independent seeds ({samples} poses); task default {th[0].value}",
                measurements=m,
                thresholds=th,
                evidence=ev,
            )
        return self.finding(
            Gate.PASS,
            f"{len(seeds)} independent seeds, {samples} poses, no duplicates",
            measurements=m,
            thresholds=th,
            evidence=ev,
        )


@register
class Clusters(Check):
    id = "l5.sampling.clusters"
    layer = Layer.SUPPORT
    title = "Medoid of the largest cluster, populations, pairwise spread, site and pose accuracy"
    requires_modules = ("spyrmsd", "scipy", "numpy", "rdkit")

    def applies(self, ctx: CheckContext) -> str | None:
        return _ligand_outputs(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        import numpy as np

        ens = outputs.ensemble(ctx)
        th = (
            outputs.configured(self.id, "cluster_rmsd"),
            outputs.configured(self.id, "site_distance"),
            outputs.configured(self.id, "largest_fraction"),
        )
        n = len(ens.poses)
        label = {i: k + 1 for k, c in enumerate(ens.clusters) for i in c}
        site = outputs.site_coords(ctx)
        rows = []
        in_site = 0
        for i, pose in enumerate(ens.poses):
            row: dict[str, Any] = {
                "pose": pose.id,
                "executor": pose.executor,
                "seed": pose.seed,
                "sample": pose.sample,
                "cluster": label[i],
                "rmsd_to_medoid_A": round(float(ens.rmsd[i, ens.medoid]), 3),
                "confidence": _confidence(pose),
            }
            if site is not None:
                d = float(np.linalg.norm(ens.centroids[i] - np.asarray(site[0]).mean(axis=0)))
                row["site_distance_A"] = round(d, 2)
                in_site += d <= float(th[1].value)
            rows.append(row)
        iu = np.triu_indices(n, 1)
        pair = np.sort(ens.rmsd[iu]) if n > 1 else np.array([0.0])
        q1, med, q3 = (float(np.percentile(pair, q)) for q in (25, 50, 75))
        within = sum(1 for r in rows if r["rmsd_to_medoid_A"] <= float(th[0].value))
        largest = len(ens.clusters[0]) / n
        medoid = ens.poses[ens.medoid]
        site_txt = (
            f"{in_site} of {n} poses within {th[1].value} Å of the site ({site[1]})"
            if site is not None
            else "site not declared"
        )
        acc_txt = f"{within} of {n} poses within {th[0].value} Å of the medoid"
        best_any = None
        if outputs.reference_ligand(ctx) is not None:
            all_rmsd = [
                (_rmsd_to_reference(ctx, p), p.id)
                for p in outputs.primary_set(ctx).ranked()
                if p.ligand
            ][:50]
            all_rmsd = [r for r in all_rmsd if r[0] is not None]
            if all_rmsd:
                best_any = min(all_rmsd)
        m = {
            "poses": n,
            "clusters": len(ens.clusters),
            "largest_cluster": len(ens.clusters[0]),
            "pairwise_rmsd_median_A": round(med, 3),
            "within_medoid": within,
            "in_site": in_site if site is not None else None,
            "best_sampled_rmsd_to_reference_A": best_any[0] if best_any else None,
        }
        ev = {
            "poses": rows,
            "medoid": medoid.id,
            "frame": ens.frame,
            "clusters": [
                {
                    "id": k + 1,
                    "size": len(c),
                    "medoid": ens.poses[min(c, key=lambda i: float(ens.rmsd[i, c].sum()))].id,
                }
                for k, c in enumerate(ens.clusters)
            ],
            "pairwise_rmsd_A": {
                "median": round(med, 3),
                "q1": round(q1, 3),
                "q3": round(q3, 3),
                "n": len(pair),
            },
            "site_placement": site_txt,
            "pose_accuracy": acc_txt,
            "sampling": {
                "best_sampled_rmsd_to_reference_A": best_any[0] if best_any else None,
                "pose": best_any[1] if best_any else None,
            },
            "frame_ca_rmsd_A": ens.frame_rmsd,
        }
        tool = ToolRef(name="spyrmsd", version=_version("spyrmsd"))
        msg = (
            f"medoid {medoid.id}; {len(ens.clusters)} clusters, largest {len(ens.clusters[0])} "
            f"of {n}; pairwise RMSD median {med:.2f} Å (IQR {q1:.2f} to {q3:.2f}); "
            f"{site_txt}; {acc_txt}"
        )
        if largest < float(th[2].value):
            return self.finding(
                Gate.WARN, msg, measurements=m, thresholds=th, evidence=ev, tool=tool
            )
        return self.finding(Gate.PASS, msg, measurements=m, thresholds=th, evidence=ev, tool=tool)


def _version(module: str) -> str | None:
    import importlib.metadata

    try:
        return importlib.metadata.version(module)
    except importlib.metadata.PackageNotFoundError:
        return None


@register
class RankStability(Check):
    id = "l5.sampling.rank_stability"
    layer = Layer.SUPPORT
    title = "Ranking stability across seeds (Kendall tau)"
    requires_modules = ("scipy",)

    def applies(self, ctx: CheckContext) -> str | None:
        return outputs.needs_predictions(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        from itertools import combinations

        from scipy.stats import kendalltau

        by_seed: dict[Any, dict[str, float]] = {}
        for pset in outputs.assessed_sets(ctx):
            for pose in pset.ranked():
                score = _confidence(pose)
                if score is None or pose.ligand_id is None:
                    continue
                slot = by_seed.setdefault(pose.seed, {})
                slot[pose.ligand_id] = max(slot.get(pose.ligand_id, score), score)
        taus = []
        for a, b in combinations(sorted(by_seed, key=str), 2):
            common = sorted(set(by_seed[a]) & set(by_seed[b]))
            if len(common) >= 3:
                tau = kendalltau([by_seed[a][x] for x in common], [by_seed[b][x] for x in common])
                taus.append(round(float(tau.statistic), 3))
        m = {"seeds": len(by_seed), "pairs": len(taus), "min_tau": min(taus) if taus else None}
        if not taus:
            return self.finding(
                Gate.WARN,
                "fewer than three ranked items shared by two seeds; "
                "ranking stability not measurable",
                measurements=m,
            )
        return self.finding(
            Gate.PASS,
            f"Kendall tau across {len(taus)} seed pairs: min {min(taus)}",
            measurements=m,
            evidence={"taus": taus},
        )


@register
class CrossFamilyAgreement(Check):
    id = "l5.agreement.cross_family"
    layer = Layer.SUPPORT
    title = "Agreement between methods, weighted by independence"
    requires_modules = ("spyrmsd", "numpy", "rdkit")

    def applies(self, ctx: CheckContext) -> str | None:
        return _ligand_outputs(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        th = (outputs.configured(self.id, "rmsd"),)
        limit = float(th[0].value)
        medoids = []
        for pset in outputs.assessed_sets(ctx):
            poses = outputs.ensemble_poses(ctx, pset)
            if poses:
                medoids.append((pset, self._medoid(ctx, poses)))
        comparisons = []
        for i, (sa, pa) in enumerate(medoids):
            xa = _pose_frame(ctx, pa)
            for sb, pb in medoids[i + 1 :]:
                xb = _pose_frame(ctx, pb)
                d = outputs.symmetric_rmsd(outputs.pose_mol(pa), xa, outputs.pose_mol(pb), xb)
                fam = tuple(sorted((sa.family.value, sb.family.value)))
                comparisons.append(
                    {
                        "method": sa.executor,
                        "vs": sb.executor,
                        "value": round(d, 3),
                        "unit": "Å",
                        "weight": WEIGHTS.get(fam, "moderate"),
                    }
                )
            ref_rmsd = _rmsd_to_reference(ctx, pa)
            if ref_rmsd is not None:
                ref = outputs.reference_ligand(ctx)
                label = f"crystal {ref.source}" if ref else "crystal"
                comparisons.append(
                    {
                        "method": sa.executor,
                        "vs": label,
                        "value": ref_rmsd,
                        "unit": "Å",
                        "weight": "decisive",
                    }
                )
        if not comparisons:
            return self.finding(
                Gate.WARN,
                "one method and no experimental reference; agreement not measurable",
                measurements={"methods": len(medoids)},
                thresholds=th,
            )
        decisive = [c for c in comparisons if c["weight"] == "decisive"]
        disagree = [c for c in comparisons if c["value"] > limit]
        m = {
            "methods": len(medoids),
            "comparisons": len(comparisons),
            "disagreeing": len(disagree),
            "rmsd_to_crystal_A": decisive[0]["value"] if decisive else None,
        }
        ev = {"comparisons": comparisons, "medoids": {s.executor: p.id for s, p in medoids}}
        text = "; ".join(
            f"{c['method']} vs {c['vs']} {c['value']} Å ({c['weight']})" for c in comparisons
        )
        gate = Gate.WARN if disagree else Gate.PASS
        return self.finding(
            gate, text, measurements=m, thresholds=th, evidence=ev, tool=ToolRef(name="spyrmsd")
        )

    def _medoid(self, ctx: CheckContext, poses: list[Any]) -> Any:
        import numpy as np

        if len(poses) == 1:
            return poses[0]
        xyz = [_pose_frame(ctx, p) for p in poses]
        n = len(poses)
        mat = np.zeros((n, n))
        for i in range(n):
            for j in range(i + 1, n):
                mat[i, j] = mat[j, i] = outputs.symmetric_rmsd(
                    outputs.pose_mol(poses[i]), xyz[i], outputs.pose_mol(poses[j]), xyz[j]
                )
        clusters = outputs.cluster(
            mat, float(outputs.value("l5.sampling.clusters", "cluster_rmsd"))
        )
        big = clusters[0]
        return poses[min(big, key=lambda i: float(mat[i, big].sum()))]


@register
class PhysicsAgreement(Check):
    id = "l5.agreement.physics"
    layer = Layer.SUPPORT
    title = "Co-folding pose against physics-based docking"
    requires_modules = ("spyrmsd", "numpy", "rdkit")

    def applies(self, ctx: CheckContext) -> str | None:
        reason = _ligand_outputs(ctx)
        if reason:
            return reason
        fams = {s.family.value for s in outputs.assessed_sets(ctx)}
        return (
            None
            if {"cofolding", "docking"} <= fams
            else "needs one co-folding and one docking prediction set"
        )

    def run(self, ctx: CheckContext) -> Finding:
        inner = CrossFamilyAgreement().run(ctx)
        rows = [c for c in inner.evidence.get("comparisons", []) if c["weight"] == "high"]
        return self.finding(
            inner.gate,
            "; ".join(f"{c['method']} vs {c['vs']} {c['value']} Å" for c in rows) or inner.message,
            measurements=inner.evidence and {"comparisons": len(rows)},
            thresholds=inner.thresholds,
            evidence={"comparisons": rows},
        )


@register
class SiteConsistency(Check):
    id = "l5.agreement.site_consistency"
    layer = Layer.SUPPORT
    title = "Predicted site consistent across samples and with the known site"
    requires_modules = ("spyrmsd", "numpy", "rdkit")

    def applies(self, ctx: CheckContext) -> str | None:
        return _ligand_outputs(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        inner = Clusters().run(ctx)
        ev = inner.evidence
        n = inner.measurements[0].value
        in_site = next((x.value for x in inner.measurements if x.name == "in_site"), None)
        m = {"poses": n, "in_site": in_site}
        if in_site is None:
            return self.finding(
                Gate.WARN,
                f"known site not declared; consistency across samples only: {ev['pose_accuracy']}",
                measurements=m,
            )
        gate = Gate.PASS if int(in_site) * 2 >= int(n) else Gate.WARN  # type: ignore[arg-type]
        return self.finding(
            gate,
            ev["site_placement"],
            measurements=m,
            thresholds=inner.thresholds,
            evidence={"poses": ev["poses"]},
        )


@register
class Redocking(Check):
    id = "l5.controls.redocking"
    layer = Layer.SUPPORT
    title = "Redocking control reproduces the crystal pose"
    requires_modules = ("spyrmsd", "numpy", "rdkit", "gemmi")

    def applies(self, ctx: CheckContext) -> str | None:
        return outputs.needs_predictions(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        th = (outputs.configured(self.id, "rmsd"),)
        sets = outputs.control_sets(ctx, "redocking")
        ref = outputs.reference_ligand(ctx)
        if not sets:
            return self.finding(
                Gate.STOP,
                "redocking control required by the task and not supplied (controls.redocking)",
                thresholds=th,
            )
        if ref is None:
            return self.finding(
                Gate.STOP,
                "redocking control supplied without a reference ligand to compare against",
                thresholds=th,
            )
        rows = []
        for pose in sets[0].ranked():
            if pose.ligand:
                rows.append(
                    {
                        "pose": pose.id,
                        "rmsd_A": _rmsd_to_reference(ctx, pose),
                        "rank": pose.rank,
                        "seed": pose.seed,
                    }
                )
        top = min((r for r in rows if r["rank"] == 0), key=lambda r: r["rmsd_A"] or 99)
        best = min(rows, key=lambda r: r["rmsd_A"] or 99)
        m = {"rmsd_A": top["rmsd_A"], "best_sampled_rmsd_A": best["rmsd_A"], "poses": len(rows)}
        ev = {
            "rmsd_A": top["rmsd_A"],
            "pose": top["pose"],
            "reference": f"{ref.code} in {ref.source}",
            "poses": rows,
            "executor": sets[0].executor,
        }
        if (top["rmsd_A"] or 99) > float(th[0].value):
            return self.finding(
                Gate.STOP,
                f"top redocked pose {top['pose']} at {top['rmsd_A']} Å "
                f"from {ref.code} in {ref.source}; best sampled {best['rmsd_A']} Å",
                measurements=m,
                thresholds=th,
                evidence=ev,
            )
        return self.finding(
            Gate.PASS,
            f"top redocked pose {top['pose']} at {top['rmsd_A']} Å from {ref.code} in {ref.source}",
            measurements=m,
            thresholds=th,
            evidence=ev,
        )


@register
class RmsdToCrystal(Check):
    id = "l5.rmsd_to_crystal"
    layer = Layer.SUPPORT
    title = "Pose accuracy against the crystal ligand"
    requires_modules = ("spyrmsd", "numpy", "rdkit", "gemmi")

    def applies(self, ctx: CheckContext) -> str | None:
        reason = _ligand_outputs(ctx)
        if reason:
            return reason
        return None if outputs.reference_ids(ctx)[1] else "no reference ligand declared"

    def run(self, ctx: CheckContext) -> Finding:
        th = (outputs.configured(self.id, "rmsd"),)
        rows = [
            {"pose": p.id, "rmsd_A": _rmsd_to_reference(ctx, p)}
            for p in outputs.ensemble_poses(ctx)
        ]
        rep = outputs.representative(ctx).id
        rr = next(r for r in rows if r["pose"] == rep)
        within = sum(1 for r in rows if (r["rmsd_A"] or 99) <= float(th[0].value))
        m = {"rmsd_A": rr["rmsd_A"], "within": within, "poses": len(rows)}
        gate = Gate.PASS if (rr["rmsd_A"] or 99) <= float(th[0].value) else Gate.STOP
        return self.finding(
            gate,
            f"medoid {rep} at {rr['rmsd_A']} Å; {within} of {len(rows)} "
            f"poses within {th[0].value} Å",
            measurements=m,
            thresholds=th,
            evidence={"poses": rows},
        )


@register
class LengthConfound(Check):
    id = "l5.confidence.length_confound"
    layer = Layer.SUPPORT
    title = "Partner-length confound of ipTM"

    def applies(self, ctx: CheckContext) -> str | None:
        if len([p for p in ctx.manifest.proteins if p.sequence]) < 2:
            return "fewer than two protein sequences"
        return outputs.needs_predictions(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        th = (outputs.configured(self.id, "length_ratio"),)
        lengths = sorted(len(p.sequence or "") for p in ctx.manifest.proteins if p.sequence)
        ratio = round(lengths[-1] / lengths[0], 2) if lengths[0] else None
        top = outputs.primary_set(ctx).ranked()[0]
        m = {
            "length_ratio": ratio,
            "shortest": lengths[0],
            "longest": lengths[-1],
            "iptm": top.scores.get("iptm"),
        }
        gate = Gate.WARN if ratio is None or ratio > float(th[0].value) else Gate.PASS
        return self.finding(
            gate,
            f"partner length ratio {ratio} ({lengths[0]} and {lengths[-1]} residues)",
            measurements=m,
            thresholds=th,
        )


@register
class InterfaceConfidence(Check):
    id = "l5.confidence.interface"
    layer = Layer.SUPPORT
    title = "Interface confidence (ipTM and interface PAE)"

    def applies(self, ctx: CheckContext) -> str | None:
        return outputs.needs_predictions(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        pset = outputs.primary_set(ctx)
        top = pset.ranked()[0]
        th = outputs.model_threshold(pset.executor, "iptm")
        iptm = top.scores.get("iptm")
        m = {"iptm": iptm, "ptm": top.scores.get("ptm")}
        if iptm is None:
            return self.finding(Gate.WARN, f"{pset.executor} reports no ipTM", measurements=m)
        if th is None:
            return self.finding(
                Gate.PASS,
                f"ipTM {iptm}; no registered threshold for {pset.executor} (reported)",
                measurements=m,
            )
        ok = _compare(float(iptm), th.comparator, float(th.value))
        return self.finding(
            Gate.PASS if ok else Gate.WARN,
            f"ipTM {iptm} for {top.id}",
            measurements=m,
            thresholds=(th,),
        )


class _ControlCheck(Check):
    """A control the task requires. Missing means the comparative claim is refused."""

    control: ClassVar[str]
    field: ClassVar[str]

    def applies(self, ctx: CheckContext) -> str | None:
        return outputs.needs_predictions(ctx)

    def supplied(self, ctx: CheckContext) -> list[Any]:
        value = getattr(ctx.manifest.controls, self.field)
        return list(value) if isinstance(value, tuple) else [value] if value else []

    def run(self, ctx: CheckContext) -> Finding:
        items = self.supplied(ctx)
        if not items:
            return self.finding(
                Gate.STOP,
                f"{self.control} required by the task and not supplied (controls.{self.field})",
            )
        return self.evaluate(ctx, items)

    def evaluate(self, ctx: CheckContext, items: list[Any]) -> Finding:
        return self.finding(
            Gate.WARN,
            f"{len(items)} {self.control} supplied; evaluation of this control is not implemented",
            measurements={"supplied": len(items)},
        )


def _best_score(sets: list[Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for s in sets:
        for p in s.ranked():
            c = _confidence(p)
            if c is None:
                continue
            key = p.ligand_id or s.source.name
            lower_better = any(k in p.scores for k in ("vina_affinity", "minimizedAffinity"))
            val = -c if lower_better else c
            out[key] = max(out.get(key, val), val)
    return out


def _auc(pos: list[float], neg: list[float]) -> float | None:
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return round(wins / (len(pos) * len(neg)), 3)


@register
class Decoys(_ControlCheck):
    id = "l5.controls.decoys"
    layer = Layer.SUPPORT
    title = "Non-cognate decoy panel"
    control = "decoy panel"
    field = "decoys"

    def evaluate(self, ctx: CheckContext, items: list[Any]) -> Finding:
        th = (outputs.configured(self.id, "decoys"),)
        n = len(items)
        gate = Gate.WARN if n < float(th[0].value) else Gate.PASS
        return self.finding(gate, f"{n} decoys supplied", measurements={"decoys": n}, thresholds=th)


@register
class DecoysPropertyMatched(Decoys):
    id = "l5.controls.decoys_property_matched"
    title = "Property-matched ligand decoys"
    control = "property-matched decoy set"
    requires_modules = ("rdkit",)


@register
class KnownPositive(_ControlCheck):
    id = "l5.controls.known_positive"
    layer = Layer.SUPPORT
    title = "Known positive scores as a positive under the same pipeline"
    control = "known positive"
    field = "known_positive"


@register
class Sticky(_ControlCheck):
    id = "l5.controls.sticky"
    layer = Layer.SUPPORT
    title = "Sticky control reproduces its failure mode"
    control = "sticky control"
    field = "sticky"


@register
class ActivesInactives(_ControlCheck):
    id = "l5.controls.actives_inactives"
    layer = Layer.SUPPORT
    title = "Actives and confirmed inactives"
    control = "actives"
    field = "actives"


@register
class Enrichment(Check):
    id = "l5.enrichment"
    layer = Layer.SUPPORT
    title = "Enrichment of actives over decoys (ROC AUC)"

    def applies(self, ctx: CheckContext) -> str | None:
        return outputs.needs_predictions(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        th = (outputs.configured(self.id, "auc"),)
        actives = _best_score(outputs.control_sets(ctx, "active") or outputs.assessed_sets(ctx))
        decoys = _best_score(outputs.control_sets(ctx, "decoy"))
        if not decoys:
            return self.finding(
                Gate.STOP,
                "no decoys supplied; enrichment is not reported without decoys",
                thresholds=th,
            )
        auc = _auc(list(actives.values()), list(decoys.values()))
        m = {"actives": len(actives), "decoys": len(decoys), "auc": auc}
        gate = Gate.PASS if auc is not None and auc >= float(th[0].value) else Gate.WARN
        return self.finding(
            gate,
            f"ROC AUC {auc} ({len(actives)} actives, {len(decoys)} decoys)",
            measurements=m,
            thresholds=th,
        )


def _missing_control(check_id: str, title: str, control: str) -> type[Check]:
    cls = type(
        check_id.replace(".", "_"),
        (_ControlCheck,),
        {
            "id": check_id,
            "layer": Layer.SUPPORT,
            "title": title,
            "control": control,
            "field": "known_positive",
            "supplied": lambda self, ctx: [],
        },
    )
    return register(cls)


# Controls whose manifest input is not defined yet: they report the control as not supplied.
for _cid, _title, _control in (
    ("l5.controls.known_sites", "Known binding sites recovered", "known-site control"),
    ("l5.controls.non_cognate", "Non-cognate partner control", "non-cognate partner"),
    ("l5.controls.scrambled", "Scrambled designs fail", "scrambled designs"),
    (
        "l5.controls.wild_type_noise_floor",
        "Wild type against itself across seeds",
        "wild-type noise floor",
    ),
    ("l5.dockq_reference", "DockQ against the experimental complex", "experimental complex"),
    ("l5.refolding_consistency", "Design refolds to the design model", "refolding run"),
    ("l5.scaffold_pose_consistency", "Shared scaffold placed consistently", "series poses"),
):
    _missing_control(_cid, _title, _control)
