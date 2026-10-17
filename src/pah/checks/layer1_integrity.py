"""Layer 1: the run receives exactly what was declared."""

from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from pah.checks import resolve
from pah.core.check import Check, CheckContext, GateKind, SkipReason, register
from pah.core.models import Finding, Gate, Layer, Threshold, ToolRef
from pah.sources import SourceUnavailableError

SPEC_L1 = "Specification, Layer 1 (input integrity)"
HARNESS_DEFAULT = "Harness default; not yet calibrated on the harness benchmark"


def _proteins_with_sequence(ctx: CheckContext) -> list[Any]:
    return [p for p in ctx.manifest.proteins if p.sequence and p.uniprot]


@register
class SequenceMatchesRecord(Check):
    id = "l1.sequence.matches_record"
    layer = Layer.INTEGRITY
    title = "Sequence given to the run matches the declared source record"

    def applies(self, ctx: CheckContext) -> str | None:
        return (
            None
            if _proteins_with_sequence(ctx)
            else "no protein declares both sequence and UniProt"
        )

    def run(self, ctx: CheckContext) -> Finding:
        rows = []
        for p in _proteins_with_sequence(ctx):
            ref, label = resolve.reference_sequence(ctx, p)
            seq = p.sequence.strip().upper()
            full = resolve.mutated_uniprot(ctx, p)
            errors = resolve.mutation_errors(ctx, p)
            rows.append(
                {
                    "protein": p.id,
                    "reference": label,
                    "length": len(seq),
                    "reference_length": len(ref),
                    "identical": seq == ref and not errors,
                    "contained_in_reference": seq in full,
                    "declared_mutations": list(p.mutations),
                    "declaration_errors": errors,
                }
            )
        bad = [r for r in rows if not r["identical"]]
        th = (resolve.threshold("identical", True, "==", SPEC_L1, "reproduced"),)
        measurements = {"proteins": len(rows), "differing": len(bad)}
        if bad:
            ids = ", ".join(r["protein"] for r in bad)
            errs = [e for r in bad for e in r["declaration_errors"]]
            return self.finding(
                Gate.STOP,
                f"sequence differs from record for {ids}"
                + (f"; {'; '.join(errs[:3])}" if errs else ""),
                measurements=measurements,
                thresholds=th,
                evidence={"proteins": rows},
            )
        return self.finding(
            Gate.PASS,
            f"{len(rows)} sequences identical to their records",
            measurements=measurements,
            thresholds=th,
            evidence={"proteins": rows},
        )


def _diff(ref: str, seq: str) -> dict[str, Any]:
    ops = SequenceMatcher(None, ref, seq, autojunk=False).get_opcodes()
    out: dict[str, Any] = {
        "substitutions": [],
        "n_truncation": 0,
        "c_truncation": 0,
        "internal_deletions": 0,
        "insertions": 0,
    }
    for tag, i1, i2, j1, j2 in ops:
        if tag == "replace":
            out["substitutions"] += [
                f"{ref[i]}{i + 1}{seq[j]}"
                for i, j in zip(range(i1, i2), range(j1, j2), strict=False)
            ]
            if (i2 - i1) != (j2 - j1):
                out["internal_deletions"] += max(0, (i2 - i1) - (j2 - j1))
                out["insertions"] += max(0, (j2 - j1) - (i2 - i1))
        elif tag == "delete":
            if i1 == 0:
                out["n_truncation"] += i2 - i1
            elif i2 == len(ref):
                out["c_truncation"] += i2 - i1
            else:
                out["internal_deletions"] += i2 - i1
        elif tag == "insert":
            out["insertions"] += j2 - j1
    return out


@register
class NoTruncationOrSubstitution(Check):
    id = "l1.sequence.no_truncation_substitution"
    layer = Layer.INTEGRITY
    title = "No silent truncation, substitution or non-standard residue"

    def applies(self, ctx: CheckContext) -> str | None:
        return (
            None
            if _proteins_with_sequence(ctx)
            else "no protein declares both sequence and UniProt"
        )

    def run(self, ctx: CheckContext) -> Finding:
        rows = []
        for p in _proteins_with_sequence(ctx):
            ref, label = resolve.reference_sequence(ctx, p)
            seq = p.sequence.strip()
            nonstd = sorted({c for c in seq.upper() if c not in resolve.CANONICAL})
            d = _diff(ref, seq.upper())
            rows.append({"protein": p.id, "reference": label, "non_standard": nonstd, **d})
        totals = {
            "substitutions": sum(len(r["substitutions"]) for r in rows),
            "n_truncation": sum(r["n_truncation"] for r in rows),
            "c_truncation": sum(r["c_truncation"] for r in rows),
            "internal_deletions": sum(r["internal_deletions"] for r in rows),
            "insertions": sum(r["insertions"] for r in rows),
            "non_standard": sum(len(r["non_standard"]) for r in rows),
        }
        th = (resolve.threshold("changes", 0, "==", SPEC_L1, "reproduced"),)
        for r in rows:
            r["substitutions"] = r["substitutions"][:30]
        if any(totals.values()):
            changed = {k: v for k, v in totals.items() if v}
            return self.finding(
                Gate.STOP,
                "sequence changed relative to reference: "
                + ", ".join(f"{k}={v}" for k, v in changed.items()),
                measurements=totals,
                thresholds=th,
                evidence={"proteins": rows},
            )
        return self.finding(
            Gate.PASS,
            f"{len(rows)} sequences have no truncation, substitution or non-standard residue",
            measurements=totals,
            thresholds=th,
            evidence={"proteins": rows},
        )


def _read_a3m(path: Path) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    header: str | None = None
    parts: list[str] = []
    for line in path.read_text().splitlines():
        if line.startswith("#"):
            continue
        if line.startswith(">"):
            if header is not None:
                records.append((header, "".join(parts)))
            header, parts = line[1:].strip(), []
        elif header is not None:
            parts.append(line.strip())
    if header is not None:
        records.append((header, "".join(parts)))
    return records


def _query_residues(aligned: str) -> str:
    """A3M query row without gaps or lowercase insertions."""
    return "".join(c for c in aligned if c.isupper())


@register
class MsaIntegrity(Check):
    id = "l1.msa.integrity"
    layer = Layer.INTEGRITY
    title = "MSA belongs to its chain, is not query-only and is not shared across chains"

    def applies(self, ctx: CheckContext) -> str | None:
        return None if any(p.msa for p in ctx.manifest.proteins) else "no MSA declared"

    def run(self, ctx: CheckContext) -> Finding:
        rows = []
        by_path: dict[Path, set[str]] = {}
        stop = False
        for p in ctx.manifest.proteins:
            if not p.msa:
                continue
            path = ctx.manifest.path(p.msa)
            row: dict[str, Any] = {"protein": p.id, "path": str(p.msa)}
            if not path.is_file():
                row["error"] = "file not found"
                rows.append(row)
                stop = True
                continue
            records = _read_a3m(path)
            query = _query_residues(records[0][1]).upper() if records else ""
            expected = p.sequence or (resolve.uniprot(ctx, p.uniprot).sequence if p.uniprot else "")
            expected = expected.strip().upper()
            row.update(
                {
                    "sequences": len(records),
                    "query_length": len(query),
                    "query_matches_chain": bool(expected) and query == expected,
                }
            )
            by_path.setdefault(path.resolve(), set()).add(expected)
            stop = stop or len(records) <= 1 or not row["query_matches_chain"]
            rows.append(row)
        collisions = [str(k) for k, v in by_path.items() if len(v) > 1]
        stop = stop or bool(collisions)
        th = (
            resolve.threshold(
                "sequences", 1, ">", SPEC_L1 + "; query-only alignment", "reproduced"
            ),
            resolve.threshold("query_matches_chain", True, "==", SPEC_L1, "reproduced"),
        )
        measurements = {
            "msas": len(rows),
            "query_only": sum(1 for r in rows if r.get("sequences", 0) <= 1),
            "query_mismatch": sum(1 for r in rows if r.get("query_matches_chain") is False),
            "shared_across_chains": len(collisions),
        }
        evidence = {"msas": rows, "collisions": collisions}
        if stop:
            return self.finding(
                Gate.STOP,
                "MSA integrity failed: "
                + ", ".join(f"{k}={v}" for k, v in measurements.items() if k != "msas" and v),
                measurements=measurements,
                thresholds=th,
                evidence=evidence,
            )
        return self.finding(
            Gate.PASS,
            f"{len(rows)} MSAs match their chains",
            measurements=measurements,
            thresholds=th,
            evidence=evidence,
        )


def _ligands(ctx: CheckContext) -> list[Any]:
    return list(ctx.manifest.ligands)


@register
class LigandSanitization(Check):
    id = "l1.ligand.sanitization"
    layer = Layer.INTEGRITY
    title = "Ligand parses, valences are correct and charges are within range"
    requires_modules = ("rdkit",)

    def applies(self, ctx: CheckContext) -> str | None:
        return None if _ligands(ctx) else "no ligand declared"

    def run(self, ctx: CheckContext) -> Finding:
        from rdkit import Chem, rdBase

        max_charge = 2
        rows = []
        stop = warn = False
        for lig in _ligands(ctx):
            row: dict[str, Any] = {"ligand": lig.id}
            try:
                prep = resolve.prepared_ligand(ctx, lig)
            except SourceUnavailableError as exc:
                rows.append({**row, "error": str(exc)})
                stop = True
                continue
            row.update(
                {
                    "origin": prep.origin,
                    "problems": list(prep.problems),
                    "metal": prep.metal,
                    "metal_disconnected": prep.metal_disconnected,
                }
            )
            if prep.mol is None:
                stop = True
            else:
                mol = prep.mol
                charge = Chem.GetFormalCharge(mol)
                radicals = sum(a.GetNumRadicalElectrons() for a in mol.GetAtoms())
                row.update(
                    {
                        "heavy_atoms": mol.GetNumHeavyAtoms(),
                        "net_charge": charge,
                        "radicals": radicals,
                    }
                )
                stop = stop or radicals > 0
                warn = warn or abs(charge) > max_charge
            rows.append(row)
        th: tuple[Threshold, ...] = (
            resolve.threshold("chemistry_problems", 0, "==", SPEC_L1, "published"),
            resolve.threshold("radicals", 0, "==", SPEC_L1, "published"),
            resolve.threshold("abs_net_charge", max_charge, "<=", HARNESS_DEFAULT),
        )
        if any(r.get("metal_disconnected") for r in rows):
            th += (
                resolve.threshold(
                    "valence_problems_only_on_metal_bonds", True, "==", resolve.METAL_RULE
                ),
            )
        tool = ToolRef(name="rdkit", version=rdBase.rdkitVersion)
        failed = sum(
            1 for r in rows if r.get("error") or "net_charge" not in r or r.get("radicals")
        )
        measurements = {
            "ligands": len(rows),
            "failed": failed,
            "metal_disconnected": sum(1 for r in rows if r.get("metal_disconnected")),
            "max_abs_charge": max((abs(r.get("net_charge", 0)) for r in rows), default=0),
        }
        if stop:
            gate, msg = Gate.STOP, f"{failed} ligands failed parsing or valence checks"
        elif warn:
            gate, msg = Gate.WARN, f"net charge beyond ±{max_charge}"
        else:
            disc = measurements["metal_disconnected"]
            note = f"; metal bonds disconnected for {disc}" if disc else ""
            gate, msg = Gate.PASS, f"{len(rows)} ligands sanitised{note}"
        return self.finding(
            gate,
            msg,
            measurements=measurements,
            thresholds=th,
            evidence={"ligands": rows},
            tool=tool,
        )


@register
class LigandStereo(Check):
    id = "l1.ligand.stereo_defined"
    layer = Layer.INTEGRITY
    title = "Stereocentres and double-bond geometry explicitly defined"
    requires_modules = ("rdkit",)
    gate_kind = GateKind.WARN

    def applies(self, ctx: CheckContext) -> str | None:
        return None if _ligands(ctx) else "no ligand declared"

    def run(self, ctx: CheckContext) -> Finding:
        from rdkit import Chem, rdBase

        rows = []
        unparsed = []
        for lig in _ligands(ctx):
            prep = resolve.prepared_ligand(ctx, lig)
            if prep.mol is None:
                unparsed.append(lig.id)
                continue
            mol = Chem.Mol(prep.mol)
            with rdBase.BlockLogs():
                if mol.GetNumConformers() and mol.GetConformer().Is3D():
                    Chem.AssignStereochemistryFrom3D(mol)
                info = Chem.FindPotentialStereo(mol)
            undefined = [
                f"{str(i.type).split('.')[-1]}@{i.centeredOn}"
                for i in info
                if i.specified == Chem.StereoSpecified.Unspecified
            ]
            rows.append(
                {
                    "ligand": lig.id,
                    "origin": prep.origin,
                    "stereo_elements": len(info),
                    "undefined": undefined,
                }
            )
        if unparsed and not rows:
            return self.skip(
                SkipReason.NOT_APPLICABLE,
                f"no sanitised structure for {', '.join(unparsed)}; see l1.ligand.sanitization",
            )
        n_undef = sum(len(r["undefined"]) for r in rows)
        th = (resolve.threshold("undefined_stereo", 0, "==", SPEC_L1, "published"),)
        tool = ToolRef(name="rdkit", version=rdBase.rdkitVersion)
        measurements = {
            "stereo_elements": sum(r["stereo_elements"] for r in rows),
            "undefined": n_undef,
            "unparsed": len(unparsed),
        }
        gate = Gate.WARN if n_undef else Gate.PASS
        msg = f"{n_undef} stereo elements undefined" if n_undef else "all stereo elements defined"
        return self.finding(
            gate,
            msg,
            measurements=measurements,
            thresholds=th,
            evidence={"ligands": rows, "unparsed": unparsed},
            tool=tool,
        )


@register
class LigandIdentity(Check):
    id = "l1.ligand.identity"
    layer = Layer.INTEGRITY
    title = "Ligand given to the run matches its database record by InChIKey"
    requires_modules = ("rdkit",)

    def applies(self, ctx: CheckContext) -> str | None:
        if not any(lig.ccd or lig.pubchem_cid for lig in _ligands(ctx)):
            return "no ligand declares a CCD or PubChem identifier"
        return None

    def run(self, ctx: CheckContext) -> Finding:
        from rdkit import rdBase

        from pah.checks.layer0_provenance import inchikey_finding

        rows = []
        for lig in _ligands(ctx):
            refs = resolve.reference_inchikeys(ctx, lig)
            if not refs:
                continue
            prep = resolve.prepared_ligand(ctx, lig)
            key = resolve.inchikey(prep)
            for ref, ref_key in refs.items():
                gate, note = resolve.compare_inchikey(key, ref_key, prep.metal)
                rows.append(
                    {
                        "ligand": lig.id,
                        "input": prep.origin,
                        "reference": ref,
                        "input_inchikey": key,
                        "reference_inchikey": ref_key,
                        "gate": gate.value,
                        "comparison": note,
                        "metal": prep.metal,
                        "metal_disconnected": prep.metal_disconnected,
                    }
                )
        return inchikey_finding(self, rows, "ligand identities", rdBase.rdkitVersion, SPEC_L1)


def _gemmi_version() -> str:
    from importlib.metadata import version

    return version("gemmi")


def _receptor_path(ctx: CheckContext) -> Path | None:
    r = ctx.manifest.receptor
    if r is None:
        return None
    if r.file:
        return ctx.manifest.path(r.file)
    if r.pdb_id:
        return resolve.mmcif_path(ctx, r.pdb_id)
    return None


def _structure(ctx: CheckContext) -> Any:
    import gemmi

    path = _receptor_path(ctx)
    assert path is not None

    def load() -> Any:
        st = gemmi.read_structure(str(path))
        st.setup_entities()
        return st

    return ctx.memo(f"structure:{path}", load)


@register
class ReceptorChains(Check):
    id = "l1.receptor.chains"
    layer = Layer.INTEGRITY
    title = "Receptor complete, chains and residue numbering as declared"
    requires_modules = ("gemmi",)

    def applies(self, ctx: CheckContext) -> str | None:
        r = ctx.manifest.receptor
        if r is None or not (r.file or r.pdb_id):
            return "no receptor declared"
        return None

    def run(self, ctx: CheckContext) -> Finding:
        import gemmi

        r = ctx.manifest.receptor
        assert r is not None
        path = _receptor_path(ctx)
        if path is None or not path.is_file():
            return self.finding(Gate.STOP, f"receptor file not found: {path}")
        st = _structure(ctx)
        model = st[0]
        present = [ch.name for ch in model]
        declared = list(r.chains) or present
        missing = [c for c in declared if c not in present]
        seqres = {}
        for ent in st.entities:
            if ent.full_sequence:
                for sub in ent.subchains:
                    seqres[sub] = gemmi.one_letter_code(ent.full_sequence)
        checked = mismatched = 0
        examples: list[str] = []
        per_chain: dict[str, dict[str, int]] = {}
        for ch in model:
            if ch.name not in declared:
                continue
            poly = ch.get_polymer()
            n_res = len(poly)
            per_chain[ch.name] = {"polymer_residues": n_res}
            for res in poly:
                if res.label_seq is None:
                    continue
                seq = seqres.get(res.subchain)
                if not seq or res.label_seq > len(seq):
                    continue
                expected = seq[res.label_seq - 1].upper()
                got = resolve.ONE_LETTER.get(res.name, "X")
                checked += 1
                if expected != got:
                    mismatched += 1
                    if len(examples) < 20:
                        examples.append(f"{ch.name}:{res.seqid.num}{res.name}!={expected}")
        th = (resolve.threshold("numbering_mismatches", 0, "==", SPEC_L1, "published"),)
        measurements = {
            "chains_declared": len(declared),
            "chains_missing": len(missing),
            "residues_checked": checked,
            "numbering_mismatches": mismatched,
        }
        tool = ToolRef(name="gemmi", version=_gemmi_version())
        evidence = {
            "path": str(path),
            "present": present,
            "missing": missing,
            "chains": per_chain,
            "mismatches": examples,
        }
        if missing or mismatched:
            return self.finding(
                Gate.STOP,
                f"missing chains {missing}"
                if missing
                else f"{mismatched} residues disagree with SEQRES numbering",
                measurements=measurements,
                thresholds=th,
                evidence=evidence,
                tool=tool,
            )
        if checked == 0:
            return self.finding(
                Gate.WARN,
                "chains present; numbering not checkable (no label_seq or SEQRES in file)",
                measurements=measurements,
                evidence=evidence,
                tool=tool,
            )
        return self.finding(
            Gate.PASS,
            f"{len(declared)} chains present; {checked} residues agree with SEQRES numbering",
            measurements=measurements,
            thresholds=th,
            evidence=evidence,
            tool=tool,
        )


@register
class ReceptorAltlocs(Check):
    id = "l1.receptor.altlocs"
    layer = Layer.INTEGRITY
    title = "Alternate locations resolved deliberately"
    requires_modules = ("gemmi",)
    gate_kind = GateKind.WARN

    def applies(self, ctx: CheckContext) -> str | None:
        r = ctx.manifest.receptor
        if r is None or not (r.file or r.pdb_id):
            return "no receptor declared"
        return None

    def run(self, ctx: CheckContext) -> Finding:

        r = ctx.manifest.receptor
        assert r is not None
        st = _structure(ctx)
        residues: list[str] = []
        atoms = 0
        for ch in st[0]:
            for res in ch:
                alt = [a for a in res if a.altloc != "\0"]
                if alt:
                    atoms += len(alt)
                    residues.append(f"{ch.name}:{res.seqid.num}{res.name}")
        measurements = {"altloc_residues": len(residues), "altloc_atoms": atoms}
        tool = ToolRef(name="gemmi", version=_gemmi_version())
        evidence = {"residues": residues[:50], "declared_policy": r.altloc_policy}
        if residues and not r.altloc_policy:
            return self.finding(
                Gate.WARN,
                f"{len(residues)} residues have alternate locations; no altloc_policy declared",
                measurements=measurements,
                evidence=evidence,
                tool=tool,
            )
        msg = (
            f"{len(residues)} altloc residues handled by declared policy {r.altloc_policy!r}"
            if residues
            else "no alternate locations"
        )
        return self.finding(Gate.PASS, msg, measurements=measurements, evidence=evidence, tool=tool)


@register
class ChainComposition(Check):
    id = "l1.context.composition"
    layer = Layer.INTEGRITY
    title = "Chain composition and stoichiometry match the declared assembly"

    def applies(self, ctx: CheckContext) -> str | None:
        if "cofolding" not in ctx.task.families:
            return "task is not a co-folding task"
        if not any(p.pdb_id for p in ctx.manifest.proteins):
            return "no reference PDB entry declared for the assembly"
        return None

    def run(self, ctx: CheckContext) -> Finding:
        rows = []
        for p in ctx.manifest.proteins:
            if not p.pdb_id:
                continue
            segs = resolve.sifts_segments(ctx, p)
            entity_ids = {s.entity_id for s in segs}
            ents = [
                e
                for e in resolve.pdb_molecules(ctx, p.pdb_id).entities
                if e.entity_id in entity_ids
            ]
            ref_copies = sum(len(e.chains) for e in ents)
            rows.append(
                {
                    "protein": p.id,
                    "declared_copies": p.copies,
                    "reference_copies": ref_copies,
                    "pdb": p.pdb_id,
                }
            )
        bad = [
            r
            for r in rows
            if r["reference_copies"] and r["declared_copies"] != r["reference_copies"]
        ]
        th = (resolve.threshold("copies_equal", True, "==", SPEC_L1, "published"),)
        measurements = {"proteins": len(rows), "mismatched": len(bad)}
        if bad:
            return self.finding(
                Gate.STOP,
                f"stoichiometry differs from the reference entry for {len(bad)} proteins",
                measurements=measurements,
                thresholds=th,
                evidence={"proteins": rows},
            )
        return self.finding(
            Gate.PASS,
            f"{len(rows)} proteins match reference stoichiometry",
            measurements=measurements,
            thresholds=th,
            evidence={"proteins": rows},
        )


@register
class ModelProvenance(Check):
    id = "l1.provenance.model_config"
    layer = Layer.INTEGRITY
    title = "Model version, checkpoint and database snapshot recorded and consistent"

    def run(self, ctx: CheckContext) -> Finding:
        m = ctx.manifest.model
        required = ["executor", "version"]
        if "cofolding" in ctx.task.families:
            required.append("checkpoint")
        if any(p.msa for p in ctx.manifest.proteins):
            required.append("database_snapshot")
        values = m.model_dump() if m else {}
        missing = [k for k in required if not values.get(k)]
        th = (resolve.threshold("missing_fields", 0, "==", SPEC_L1, "published"),)
        measurements = {
            "required": len(required),
            "missing": len(missing),
            "seeds": len(values.get("seeds") or ()),
        }
        evidence = {"required": required, "recorded": {k: v for k, v in values.items() if v}}
        if missing:
            return self.finding(
                Gate.STOP,
                f"model provenance missing: {', '.join(missing)}",
                measurements=measurements,
                thresholds=th,
                evidence=evidence,
            )
        return self.finding(
            Gate.PASS,
            "model provenance recorded: " + ", ".join(f"{k}={values[k]}" for k in required),
            measurements=measurements,
            thresholds=th,
            evidence=evidence,
        )
