"""Layer 0: every input traced to a named source, and sources agree with each other."""

from __future__ import annotations

from typing import Any

from pah.checks import resolve
from pah.core.check import Check, CheckContext, register
from pah.core.models import Finding, Gate, Layer, Threshold, ToolRef
from pah.sources import SourceUnavailableError

SPEC_L0 = "Specification, Layer 0 (cross-source checks)"


@register
class SourcesResolved(Check):
    id = "l0.sources.resolved"
    layer = Layer.PROVENANCE
    title = "Every declared identifier resolves to a source record with checksum"

    def run(self, ctx: CheckContext) -> Finding:
        m = ctx.manifest
        jobs: list[tuple[str, Any]] = []
        for p in m.proteins:
            if p.uniprot:
                jobs.append((f"uniprot:{p.uniprot}", lambda a=p.uniprot: resolve.uniprot(ctx, a)))
            if p.pdb_id:
                pid = p.pdb_id
                jobs.append((f"pdb:{pid}", lambda pid=pid: resolve.pdb_entry(ctx, pid)))
                jobs.append((f"pdbe:{pid}", lambda pid=pid: resolve.pdb_molecules(ctx, pid)))
                if p.uniprot:
                    jobs.append((f"sifts:{pid}", lambda pid=pid: resolve.sifts(ctx, pid)))
        for lig in m.ligands:
            if lig.ccd:
                jobs.append((f"ccd:{lig.ccd}", lambda c=lig.ccd: resolve.chemcomp(ctx, c)))
            if lig.pubchem_cid:
                jobs.append(
                    (
                        f"pubchem:{lig.pubchem_cid}",
                        lambda c=lig.pubchem_cid: resolve.pubchem(ctx, c),
                    )
                )
        if m.receptor and m.receptor.pdb_id and not m.receptor.file:
            pid = m.receptor.pdb_id
            jobs.append((f"pdb:{pid}", lambda pid=pid: resolve.pdb_entry(ctx, pid)))
            jobs.append((f"mmcif:{pid}", lambda pid=pid: resolve.mmcif_path(ctx, pid)))
        if not jobs:
            return self.finding(
                Gate.PASS, "no external identifiers declared", measurements={"n": 0}
            )
        failed: dict[str, str] = {}
        for label, job in jobs:
            try:
                job()
            except SourceUnavailableError as exc:
                failed[label] = f"{exc.reason.value}: {exc.detail}"
        hits = sum(1 for p in ctx.provenance if p.extra.get("cache") == "hit")
        records = [
            {
                "source": p.source_id,
                "accession": p.accession,
                "release": p.release,
                "sha256": p.sha256,
                "url": p.url,
            }
            for p in ctx.provenance
        ]
        measurements = {
            "identifiers": len(jobs),
            "failed": len(failed),
            "records": len(ctx.provenance),
            "cache_hits": hits,
        }
        if failed:
            return self.finding(
                Gate.STOP,
                f"{len(failed)} of {len(jobs)} identifiers did not resolve",
                measurements=measurements,
                evidence={"failed": failed, "records": records},
            )
        return self.finding(
            Gate.PASS,
            f"{len(jobs)} identifiers resolved to {len(ctx.provenance)} records",
            measurements=measurements,
            evidence={"records": records},
        )


@register
class UniProtSeqresAgreement(Check):
    id = "l0.cross.uniprot_seqres"
    layer = Layer.PROVENANCE
    title = "UniProt sequence agrees with PDB SEQRES through the SIFTS mapping"

    def applies(self, ctx: CheckContext) -> str | None:
        if not any(p.uniprot and p.pdb_id for p in ctx.manifest.proteins):
            return "no protein declares both a UniProt accession and a PDB entry"
        return None

    def run(self, ctx: CheckContext) -> Finding:
        rows: list[dict[str, Any]] = []
        stop = False
        for p in ctx.manifest.proteins:
            if not (p.uniprot and p.pdb_id):
                continue
            segs = resolve.sifts_segments(ctx, p)
            if not segs:
                rows.append(
                    {"protein": p.id, "error": f"no SIFTS segment for {p.uniprot} chain {p.chain}"}
                )
                stop = True
                continue
            unp = resolve.uniprot(ctx, p.uniprot).sequence
            declared = {pos: mut for _, pos, mut in map(resolve.parse_mutation, p.mutations)}
            errors = resolve.mutation_errors(ctx, p)
            if errors:
                rows.append({"protein": p.id, "error": "declared mutations", "detail": errors})
                stop = True
            entities = {e.entity_id: e for e in resolve.pdb_molecules(ctx, p.pdb_id).entities}
            for s in segs:
                seqres = entities.get(s.entity_id)
                if seqres is None or not seqres.sequence:
                    rows.append(
                        {"protein": p.id, "chain": s.chain_id, "error": "no SEQRES for entity"}
                    )
                    stop = True
                    continue
                a = unp[s.unp_start - 1 : s.unp_end]
                b = seqres.sequence[s.seq_start - 1 : s.seq_end]
                n = min(len(a), len(b))
                diffs: list[str] = []
                seen_declared: list[str] = []
                for i in range(n):
                    if a[i] == b[i]:
                        continue
                    pos = s.unp_start + i
                    label = f"{a[i]}{pos}{b[i]}"
                    (seen_declared if declared.get(pos) == b[i] else diffs).append(label)
                length_diff = abs(len(a) - len(b))
                stop = stop or bool(diffs) or length_diff > 0
                rows.append(
                    {
                        "protein": p.id,
                        "chain": s.chain_id,
                        "uniprot_range": [s.unp_start, s.unp_end],
                        "seqres_range": [s.seq_start, s.seq_end],
                        "compared": n,
                        "mismatches": len(diffs),
                        "declared_mutations_observed": seen_declared,
                        "length_difference": length_diff,
                        "first_mismatches": diffs[:20],
                    }
                )
        compared = sum(r.get("compared", 0) for r in rows)
        mismatches = sum(r.get("mismatches", 0) for r in rows)
        declared_seen = sum(len(r.get("declared_mutations_observed", [])) for r in rows)
        declaration_errors = [
            e for r in rows if r.get("error") for e in r.get("detail", [r["error"]])
        ]
        th = (resolve.threshold("mismatches", 0, "==", SPEC_L0, "published"),)
        measurements = {
            "segments": sum(1 for r in rows if "compared" in r),
            "residues_compared": compared,
            "mismatches": mismatches,
            "declared_mutations": declared_seen,
            "declaration_errors": len(declaration_errors),
        }
        if stop:
            return self.finding(
                Gate.STOP,
                f"UniProt and SEQRES disagree: {mismatches} undeclared mismatches over "
                f"{compared} residues"
                + (f"; {'; '.join(declaration_errors[:3])}" if declaration_errors else ""),
                measurements=measurements,
                thresholds=th,
                evidence={"segments": rows},
            )
        return self.finding(
            Gate.PASS,
            f"{compared} residues agree across {len(rows)} mapped segments"
            + (f" ({declared_seen} declared mutations)" if declared_seen else ""),
            measurements=measurements,
            thresholds=th,
            evidence={"segments": rows},
        )


@register
class LigandInchikeyAgreement(Check):
    id = "l0.cross.ligand_inchikey"
    layer = Layer.PROVENANCE
    title = "Declared ligand SMILES matches its CCD or PubChem record by InChIKey"
    requires_modules = ("rdkit",)

    def applies(self, ctx: CheckContext) -> str | None:
        if not any(lig.smiles and (lig.ccd or lig.pubchem_cid) for lig in ctx.manifest.ligands):
            return "no ligand declares both a SMILES and a CCD or PubChem identifier"
        return None

    def run(self, ctx: CheckContext) -> Finding:
        from rdkit import rdBase

        rows: list[dict[str, Any]] = []
        for lig in ctx.manifest.ligands:
            if not (lig.smiles and (lig.ccd or lig.pubchem_cid)):
                continue
            prep = resolve.mol_from_smiles(lig.smiles, "manifest SMILES")
            key = resolve.inchikey(prep)
            for ref, ref_key in resolve.reference_inchikeys(ctx, lig).items():
                gate, note = resolve.compare_inchikey(key, ref_key, prep.metal)
                rows.append(
                    {
                        "ligand": lig.id,
                        "reference": ref,
                        "smiles_inchikey": key,
                        "reference_inchikey": ref_key,
                        "gate": gate.value,
                        "comparison": note,
                        "metal": prep.metal,
                        "metal_disconnected": prep.metal_disconnected,
                        "problems": list(prep.problems),
                    }
                )
        return inchikey_finding(self, rows, "InChIKey comparisons", rdBase.rdkitVersion, SPEC_L0)


def inchikey_finding(
    check: Check, rows: list[dict[str, Any]], noun: str, rdkit_version: str, spec: str
) -> Finding:
    """Shared gate logic for InChIKey comparisons in layers 0 and 1."""
    gates = [Gate(r["gate"]) for r in rows]
    stops = gates.count(Gate.STOP)
    warns = gates.count(Gate.WARN)
    thresholds: tuple[Threshold, ...] = (
        resolve.threshold("inchikey_equal", True, "==", spec, "published"),
    )
    if any(r["metal"] for r in rows):
        thresholds += (
            resolve.threshold("skeleton_equal_if_metal", True, "==", resolve.METAL_RULE),
        )
    measurements = {"comparisons": len(rows), "mismatches": stops, "metal_skeleton_only": warns}
    tool = ToolRef(name="rdkit", version=rdkit_version)
    if stops:
        gate, msg = Gate.STOP, f"{stops} of {len(rows)} {noun} differ"
    elif warns:
        gate, msg = Gate.WARN, f"{warns} of {len(rows)} {noun} match on skeleton only (metal)"
    else:
        gate, msg = Gate.PASS, f"{len(rows)} {noun} identical"
    return check.finding(
        gate,
        msg,
        measurements=measurements,
        thresholds=thresholds,
        evidence={"comparisons": rows},
        tool=tool,
    )
