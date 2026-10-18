"""Layer 2: a correct input carries enough information for the task."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pah.checks import outputs, resolve
from pah.core.check import Check, CheckContext, GateKind, SkipReason, register
from pah.core.models import Finding, Gate, Layer, ToolRef

SPEC_L2 = "Specification, Layer 2 (input adequacy)"
TAXON = re.compile(r"(?:TaxID|OX|taxid|tax)[=:_ ]?(\d+)")
MAX_NEFF_ROWS = 1000


def _cofolding(ctx: CheckContext) -> bool:
    entries = [outputs.model_entry(e) for e in outputs.executors(ctx)]
    return any(e and e.get("family") == "cofolding" for e in entries)


def _docking(ctx: CheckContext) -> bool:
    entries = [outputs.model_entry(e) for e in outputs.executors(ctx)]
    return any(e and e.get("family") == "docking" for e in entries)


def _aligned_columns(row: str) -> str:
    """A3M row restricted to match columns (uppercase and gaps); insertions are dropped."""
    return "".join(c for c in row if c.isupper() or c == "-")


def msa_stats(records: list[tuple[str, str]], identity: float = 0.8) -> dict[str, Any]:
    """Depth, distinct rows, Neff at the given identity (AlphaFold definition) and gaps."""
    import numpy as np

    rows = [_aligned_columns(seq) for _, seq in records]
    length = len(rows[0]) if rows else 0
    rows = [r for r in rows if len(r) == length]
    distinct = len(set(rows))
    sample = rows[:MAX_NEFF_ROWS]
    if not sample or length == 0:
        return {"sequences": len(rows), "distinct": distinct, "neff": 0.0, "length": length}
    x = np.frombuffer("".join(sample).encode(), dtype=np.uint8).reshape(len(sample), length)
    gap = ord("-")
    gaps = float((x == gap).mean())
    counts = np.zeros(len(sample))
    for i in range(len(sample)):
        same = (x == x[i]).sum(axis=1) / length
        counts[i] = float((same >= identity).sum())
    neff = float((1.0 / counts).sum())
    return {
        "sequences": len(rows),
        "distinct": distinct,
        "neff": round(neff, 1),
        "neff_per_length": round(neff / length, 3),
        "length": length,
        "gap_fraction": round(gaps, 3),
        "neff_rows": len(sample),
    }


def _msa_proteins(ctx: CheckContext) -> list[Any]:
    """Chains whose MSA feeds a co-folding model (an MSA declared for a docking run is unused)."""
    if outputs.executors(ctx) and not _cofolding(ctx):
        return []
    return [p for p in ctx.manifest.proteins if p.msa]


@register
class MsaDepth(Check):
    id = "l2.msa.depth"
    layer = Layer.ADEQUACY
    gate_kind = GateKind.WARN
    title = "Alignment depth, distinct sequences, Neff and gap fraction"
    requires_modules = ("numpy",)

    def applies(self, ctx: CheckContext) -> str | None:
        return None if _msa_proteins(ctx) else "no MSA declared for a co-folding model"

    def run(self, ctx: CheckContext) -> Finding:
        rows: list[dict[str, Any]] = []
        for p in _msa_proteins(ctx):
            path = ctx.manifest.path(p.msa)
            if not path.is_file():
                rows.append({"protein": p.id, "error": "file not found"})
                continue
            rows.append({"protein": p.id, **msa_stats(resolve.read_a3m(path))})
        compared = {
            "sequences": "min_sequences",
            "neff": "min_neff",
            "gap_fraction": "max_gap_fraction",
        }
        th = tuple(outputs.configured(self.id, n, measurement=m) for n, m in compared.items())
        n_min, neff_min, gap_max = (t.value for t in th)
        missing = [r["protein"] for r in rows if "error" in r]
        query_only = [r["protein"] for r in rows if r.get("sequences", 0) < n_min]
        shallow = [r["protein"] for r in rows if "neff" in r and r["neff"] < neff_min]
        gappy = [r["protein"] for r in rows if r.get("gap_fraction", 0) > gap_max]
        worst = min((r for r in rows if "neff" in r), key=lambda r: r["neff"], default={})
        m: dict[str, Any] = {
            "msas": len(rows),
            "min_neff": worst.get("neff"),
            "min_sequences": min((r["sequences"] for r in rows if "sequences" in r), default=None),
            "max_gap_fraction": max(
                (r["gap_fraction"] for r in rows if "gap_fraction" in r), default=None
            ),
        }
        ev: dict[str, Any] = {"msas": rows}
        if missing or query_only:
            names = ", ".join(missing + query_only)
            return self.finding(
                Gate.STOP,
                f"query-only or missing alignment: {names}",
                measurements=m,
                thresholds=th,
                evidence=ev,
            )
        if shallow or gappy:
            parts = [f"Neff below {neff_min} for {', '.join(shallow)}"] if shallow else []
            parts += [f"gap fraction above {gap_max} for {', '.join(gappy)}"] if gappy else []
            return self.finding(
                Gate.WARN, "; ".join(parts), measurements=m, thresholds=th, evidence=ev
            )
        return self.finding(
            Gate.PASS,
            f"{len(rows)} alignments, minimum Neff {m['min_neff']}",
            measurements=m,
            thresholds=th,
            evidence=ev,
        )


def _taxa(records: list[tuple[str, str]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for header, _ in records[1:]:
        hit = TAXON.search(header)
        if hit:
            out[hit.group(1)] = out.get(hit.group(1), 0) + 1
    return out


def _pairing(ctx: CheckContext) -> dict[str, Any]:
    chains = {}
    for p in _msa_proteins(ctx):
        path = ctx.manifest.path(p.msa)
        if path.is_file():
            chains[p.id] = _taxa(resolve.read_a3m(path))
    if len(chains) < 2:
        return {"chains": len(chains)}
    shared = set.intersection(*(set(v) for v in chains.values()))
    ambiguous = sorted(t for t in shared if any(v[t] > 1 for v in chains.values()))
    return {
        "chains": len(chains),
        "species_per_chain": {k: len(v) for k, v in chains.items()},
        "paired_species": len(shared),
        "ambiguous_species": len(ambiguous),
        "tagged": all(v for v in chains.values()),
    }


def _complex_with_msas(ctx: CheckContext) -> str | None:
    if len(ctx.manifest.proteins) < 2:
        return "single-chain input"
    return None if len(_msa_proteins(ctx)) >= 2 else "fewer than two chain MSAs declared"


@register
class MsaPairing(Check):
    id = "l2.msa.pairing"
    layer = Layer.ADEQUACY
    gate_kind = GateKind.WARN
    title = "Paired alignment depth for complexes, species pairing"

    def applies(self, ctx: CheckContext) -> str | None:
        return _complex_with_msas(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        info = _pairing(ctx)
        th = (outputs.configured(self.id, "paired_sequences"),)
        m: dict[str, Any] = {
            "paired_species": info.get("paired_species", 0),
            "chains": info["chains"],
        }
        if not info.get("tagged"):
            return self.finding(
                Gate.WARN,
                "alignment headers carry no taxonomy identifiers; pairing cannot be verified",
                measurements=m,
                thresholds=th,
                evidence=info,
            )
        if m["paired_species"] < float(th[0].value):
            return self.finding(
                Gate.WARN,
                f"{m['paired_species']} paired species",
                measurements=m,
                thresholds=th,
                evidence=info,
            )
        return self.finding(
            Gate.PASS,
            f"{m['paired_species']} paired species",
            measurements=m,
            thresholds=th,
            evidence=info,
        )


@register
class MsaParalogAmbiguity(Check):
    id = "l2.msa.paralog_ambiguity"
    layer = Layer.ADEQUACY
    gate_kind = GateKind.WARN
    title = "Paralog ambiguity in pairing"

    def applies(self, ctx: CheckContext) -> str | None:
        return _complex_with_msas(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        info = _pairing(ctx)
        th = (outputs.configured(self.id, "ambiguous_fraction"),)
        paired = info.get("paired_species", 0)
        frac = round(info.get("ambiguous_species", 0) / paired, 3) if paired else None
        m: dict[str, Any] = {
            "paired_species": paired,
            "ambiguous_species": info.get("ambiguous_species", 0),
            "ambiguous_fraction": frac,
        }
        if frac is None:
            return self.finding(
                Gate.WARN,
                "no paired species to assess",
                measurements=m,
                thresholds=th,
                evidence=info,
            )
        gate = Gate.WARN if frac > float(th[0].value) else Gate.PASS
        return self.finding(
            gate,
            f"{m['ambiguous_species']} of {paired} paired species have more than one candidate",
            measurements=m,
            thresholds=th,
            evidence=info,
        )


@register
class Disorder(Check):
    id = "l2.disorder"
    layer = Layer.ADEQUACY
    gate_kind = GateKind.WARN
    title = "Disorder in the region of interest"

    def applies(self, ctx: CheckContext) -> str | None:
        return None if any(p.uniprot for p in ctx.manifest.proteins) else "no UniProt accession"

    def run(self, ctx: CheckContext) -> Finding:
        rows: list[dict[str, Any]] = []
        for p in ctx.manifest.proteins:
            if not p.uniprot:
                continue
            ann = resolve.uniprot_annotations(ctx, p.uniprot)
            length = len(resolve.uniprot(ctx, p.uniprot).sequence)
            covered: set[int] = set()
            for f in ann.features:
                if f.type == "Region" and "disorder" in f.description.lower() and f.start:
                    covered |= set(range(f.start, (f.end or f.start) + 1))
            rows.append(
                {
                    "protein": p.id,
                    "uniprot": p.uniprot,
                    "length": length,
                    "disordered": len(covered),
                    "fraction": round(len(covered) / length, 3) if length else 0.0,
                }
            )
        th = (outputs.configured(self.id, "disordered_fraction"),)
        worst = max(rows, key=lambda r: r["fraction"])
        m: dict[str, Any] = {
            "max_disordered_fraction": worst["fraction"],
            "disordered": worst["disordered"],
        }
        gate = Gate.WARN if worst["fraction"] > float(th[0].value) else Gate.PASS
        return self.finding(
            gate,
            f"{worst['disordered']} of {worst['length']} residues of "
            f"{worst['protein']} annotated disordered",
            measurements=m,
            thresholds=th,
            evidence={"proteins": rows},
            tool=ToolRef(name="UniProt (MobiDB-lite regions)"),
        )


def _site(ctx: CheckContext) -> tuple[Any, str]:
    site = outputs.site_coords(ctx)
    if site is None:
        raise outputs.OutputUnavailableError("no reference ligand or docking box declares the site")
    return site


def _needs_site(ctx: CheckContext) -> str | None:
    pdb_id, code = outputs.reference_ids(ctx)
    if code and (pdb_id or (ctx.manifest.reference and ctx.manifest.reference.file)):
        return None
    if ctx.manifest.docking_box:
        return None
    return "no reference ligand or docking box declares the site"


@register
class Cofactors(Check):
    id = "l2.context.cofactors"
    layer = Layer.ADEQUACY
    gate_kind = GateKind.WARN
    title = "Required cofactors, ions and partners present"
    requires_modules = ("gemmi", "numpy")

    def applies(self, ctx: CheckContext) -> str | None:
        pdb_id, code = outputs.reference_ids(ctx)
        return None if pdb_id and code else "no reference entry with a ligand"

    def run(self, ctx: CheckContext) -> Finding:
        import gemmi

        pdb_id, code = outputs.reference_ids(ctx)
        assert pdb_id and code
        ref = outputs.reference_ligand(ctx)
        assert ref is not None
        st = outputs.read_structure(resolve.mmcif_path(ctx, pdb_id))
        th = (outputs.configured(self.id, "pocket_distance"),)
        cutoff = float(th[0].value)
        ns = gemmi.NeighborSearch(st[0], st.cell, cutoff + 1).populate()
        near: dict[str, float] = {}
        for xyz in ref.coords:
            pos = gemmi.Position(*map(float, xyz))
            for mark in ns.find_atoms(pos, "\0", radius=cutoff):
                cra = mark.to_cra(st[0])
                res = cra.residue
                if res.het_flag != "H" or res.name in outputs.WATER or res.name == code:
                    continue
                if (cra.chain.name, str(res.seqid)) == (ref.chain, ref.seqid):
                    continue
                d = round(cra.atom.pos.dist(pos), 2)
                near[res.name] = min(d, near.get(res.name, d))
        declared = {x.ccd.upper() for x in ctx.manifest.ligands if x.ccd}
        retained = self._in_receptor(ctx)
        missing = sorted(c for c in near if c not in declared and c not in retained)
        annotated: list[str] = []
        for p in ctx.manifest.proteins:
            if p.uniprot:
                ann = resolve.uniprot_annotations(ctx, p.uniprot)
                annotated += list(ann.cofactors)
        m: dict[str, Any] = {
            "near_site": len(near),
            "missing": len(missing),
            "uniprot_cofactors": len(annotated),
        }
        ev: dict[str, Any] = {
            "near_site_A": near,
            "declared": sorted(declared),
            "retained_in_receptor": sorted(retained),
            "missing": missing,
            "uniprot_cofactors": annotated,
        }
        if missing:
            return self.finding(
                Gate.WARN,
                f"components within {cutoff} Å of {code} in "
                f"{pdb_id} not supplied: {', '.join(missing)}",
                measurements=m,
                thresholds=th,
                evidence=ev,
            )
        detail = ", ".join(f"{k} {v} Å" for k, v in near.items()) or "none"
        return self.finding(
            Gate.PASS,
            f"components within {cutoff} Å of {code}: {detail}",
            measurements=m,
            thresholds=th,
            evidence=ev,
        )

    def _in_receptor(self, ctx: CheckContext) -> set[str]:
        m = ctx.manifest
        if not (m.receptor and m.receptor.file):
            return set()
        path = m.path(m.receptor.file)
        if not path.is_file():
            return set()
        st = outputs.read_structure(path)
        return {res.name for ch in st[0] for res in ch if res.het_flag == "H"}


def _receptor_for_docking(ctx: CheckContext) -> Path:
    path = outputs.receptor_path(ctx)
    if path is None:
        raise outputs.OutputUnavailableError("no receptor file or reference entry")
    return path


EXPECTED_HEAVY = {
    "ALA": 5,
    "ARG": 11,
    "ASN": 8,
    "ASP": 8,
    "CYS": 6,
    "GLN": 9,
    "GLU": 9,
    "GLY": 4,
    "HIS": 10,
    "ILE": 8,
    "LEU": 8,
    "LYS": 9,
    "MET": 8,
    "PHE": 11,
    "PRO": 7,
    "SER": 6,
    "THR": 7,
    "TRP": 14,
    "TYR": 12,
    "VAL": 7,
}


@register
class PocketResolved(Check):
    id = "l2.pocket.resolved"
    layer = Layer.ADEQUACY
    title = "Pocket residues resolved, no missing loops lining the pocket"
    requires_modules = ("gemmi", "numpy")

    def applies(self, ctx: CheckContext) -> str | None:
        return _needs_site(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        path = _receptor_for_docking(ctx)
        coords, label = _site(ctx)
        st = outputs.read_structure(path)
        th = (
            outputs.configured(self.id, "pocket_distance"),
            outputs.configured(self.id, "missing_pocket_residues"),
        )
        pocket = outputs.pocket_residues(st, coords, float(th[0].value))
        incomplete: list[str] = []
        breaks: list[str] = []
        index = {
            (ch.name, r.seqid.num, r.seqid.icode): (ch, i) for ch in st[0] for i, r in enumerate(ch)
        }
        for pr in pocket:
            ch, i = index[(pr.chain, pr.seqnum, pr.icode)]
            res = ch[i]
            heavy = sum(1 for a in res if a.element.name != "H" and a.name != "OXT")
            if res.name in EXPECTED_HEAVY and heavy < EXPECTED_HEAVY[res.name]:
                incomplete.append(f"{pr.label} ({heavy}/{EXPECTED_HEAVY[res.name]} atoms)")
            for a, b in ((i - 1, i), (i, i + 1)):
                if a >= 0 and b < len(ch) and _chain_break(ch[a], ch[b]):
                    breaks.append(f"{ch[a].name}{ch[a].seqid}-{ch[b].name}{ch[b].seqid}")
        m: dict[str, Any] = {
            "pocket_residues": len(pocket),
            "incomplete": len(incomplete),
            "sequence_gaps": len(breaks),
        }
        ev: dict[str, Any] = {
            "site": label,
            "receptor": path.name,
            "pocket": [p.label for p in pocket],
            "incomplete": incomplete,
            "gaps": breaks,
        }
        if incomplete or breaks:
            return self.finding(
                Gate.WARN,
                f"pocket incomplete: {len(incomplete)} residues with "
                f"missing atoms, {len(breaks)} sequence gaps next to pocket "
                "residues",
                measurements=m,
                thresholds=th,
                evidence=ev,
                tool=ToolRef(name="gemmi"),
            )
        return self.finding(
            Gate.PASS,
            f"{len(pocket)} pocket residues complete in {path.name}",
            measurements=m,
            thresholds=th,
            evidence=ev,
            tool=ToolRef(name="gemmi"),
        )


def _chain_break(a: Any, b: Any) -> bool:
    """True when consecutive polymer residues are not joined by a peptide bond (C-N > 2 Å)."""
    if a.het_flag == "H" or b.het_flag == "H":
        return False
    c, n = a.find_atom("C", "*"), b.find_atom("N", "*")
    return c is None or n is None or c.pos.dist(n.pos) > 2.0


@register
class ReceptorState(Check):
    id = "l2.receptor.state"
    layer = Layer.ADEQUACY
    gate_kind = GateKind.WARN
    title = "Receptor state apo or holo"
    requires_modules = ("gemmi", "numpy")

    def applies(self, ctx: CheckContext) -> str | None:
        return _needs_site(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        import gemmi

        coords, label = _site(ctx)
        pdb_id, _ = outputs.reference_ids(ctx)
        source = resolve.mmcif_path(ctx, pdb_id) if pdb_id else _receptor_for_docking(ctx)
        st = outputs.read_structure(source)
        ns = gemmi.NeighborSearch(st[0], st.cell, 6).populate()
        ligands: set[str] = set()
        for xyz in coords:
            for mark in ns.find_atoms(gemmi.Position(*map(float, xyz)), "\0", radius=4.0):
                res = mark.to_cra(st[0]).residue
                heavy = sum(1 for a in res if a.element.name != "H")
                if res.het_flag == "H" and res.name not in outputs.WATER and heavy >= 6:
                    ligands.add(res.name)
        state = "holo" if ligands else "apo"
        m: dict[str, Any] = {"state": state, "site_ligands": len(ligands)}
        ev: dict[str, Any] = {"source": source.name, "site": label, "ligands": sorted(ligands)}
        if state == "apo":
            return self.finding(
                Gate.WARN,
                f"{source.name} has no ligand in the site (apo)",
                measurements=m,
                evidence=ev,
            )
        return self.finding(
            Gate.PASS,
            f"{source.name} holo: {', '.join(sorted(ligands))} in the site",
            measurements=m,
            evidence=ev,
        )


TITRATABLE = {"ASP", "GLU", "HIS", "CYS", "TYR", "LYS", "ARG"}


@register
class ReceptorProtonation(Check):
    id = "l2.receptor.protonation"
    layer = Layer.ADEQUACY
    gate_kind = GateKind.WARN
    title = "Receptor protonation at the stated pH"
    requires_modules = ("propka", "gemmi")

    def applies(self, ctx: CheckContext) -> str | None:
        if not (_docking(ctx) or (ctx.manifest.receptor and ctx.manifest.receptor.file)):
            return "no docking receptor"
        return _needs_site(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        import gemmi

        th = (outputs.configured(self.id, "pka_margin"),)
        path = _docked_receptor(ctx) or _receptor_for_docking(ctx)
        raw = gemmi.read_structure(str(path))
        has_h = any(a.element.name == "H" for ch in raw[0] for r in ch for a in r)
        pdb = ctx.artifact_path(f"work/{path.stem}_propka.pdb")
        st = outputs.read_structure(path)
        st.remove_ligands_and_waters()
        st.write_pdb(str(pdb))
        ph = ctx.manifest.ph
        coords, label = _site(ctx)
        pocket = {(p.chain, p.seqnum) for p in outputs.pocket_residues(st, coords, 8.0)}
        pkas = _propka(pdb)
        rows = [r for r in pkas if (r["chain"], r["seqnum"]) in pocket]
        margin = float(th[0].value)
        ambiguous = [r for r in rows if ph is not None and abs(r["pka"] - ph) <= margin]
        m: dict[str, Any] = {
            "hydrogens_present": has_h,
            "ph": ph,
            "pocket_titratable": len(rows),
            "ambiguous": len(ambiguous),
        }
        ev: dict[str, Any] = {"site": label, "pocket_pka": rows, "ambiguous": ambiguous}
        tool = ToolRef(name="propka", version=_version("propka"))
        problems = []
        if ph is None:
            problems.append("pH not stated")
        if not has_h:
            problems.append("receptor has no hydrogens (protonation not assigned)")
        if ambiguous:
            names = ", ".join(f"{r['residue']} pKa {r['pka']}" for r in ambiguous)
            problems.append(f"pKa within {margin} of pH {ph}: {names}")
        if problems:
            return self.finding(
                Gate.WARN,
                "; ".join(problems),
                measurements=m,
                thresholds=th,
                evidence=ev,
                tool=tool,
            )
        return self.finding(
            Gate.PASS,
            f"{len(rows)} titratable pocket residues, none within {margin} pH unit of {ph}",
            measurements=m,
            thresholds=th,
            evidence=ev,
            tool=tool,
        )


def _docked_receptor(ctx: CheckContext) -> Path | None:
    """The receptor file a docking prediction declares it was run against."""
    for p in ctx.manifest.predictions:
        entry = outputs.model_entry(p.executor) or {}
        if entry.get("family") == "docking" and p.receptor:
            path = ctx.manifest.path(p.receptor)
            if path.is_file():
                return path
    return None


def _version(module: str) -> str | None:
    import importlib.metadata

    try:
        return importlib.metadata.version(module)
    except importlib.metadata.PackageNotFoundError:
        return None


def _propka(pdb: Path) -> list[dict[str, Any]]:
    import logging

    import propka.run

    logging.getLogger("propka").setLevel(logging.ERROR)
    mol = propka.run.single(str(pdb), optargs=["--quiet"], write_pka=False)
    rows: list[dict[str, Any]] = []
    for g in mol.conformations["AVR"].groups:
        if g.residue_type not in TITRATABLE or g.atom is None:
            continue
        rows.append(
            {
                "residue": f"{g.residue_type}{g.atom.res_num}{g.atom.chain_id}",
                "chain": g.atom.chain_id,
                "seqnum": int(g.atom.res_num),
                "pka": round(float(g.pka_value), 2),
                "model_pka": round(float(g.model_pka), 2),
            }
        )
    return rows


@register
class LigandProtonation(Check):
    id = "l2.ligand.protonation"
    layer = Layer.ADEQUACY
    gate_kind = GateKind.WARN
    title = "Ligand protonation and tautomers enumerated at the stated pH"
    requires_modules = ("rdkit", "dimorphite_dl")

    def applies(self, ctx: CheckContext) -> str | None:
        return None if ctx.manifest.ligands else "no ligand declared"

    def run(self, ctx: CheckContext) -> Finding:
        from dimorphite_dl import protonate_smiles
        from rdkit import Chem, rdBase
        from rdkit.Chem.MolStandardize import rdMolStandardize

        th = (outputs.configured(self.id, "ph_window"), outputs.configured(self.id, "states"))
        ph = ctx.manifest.ph
        window = float(th[0].value)
        rows: list[dict[str, Any]] = []
        for lig in ctx.manifest.ligands:
            prep = resolve.prepared_ligand(ctx, lig)
            if prep.mol is None:
                rows.append({"ligand": lig.id, "error": "; ".join(prep.problems)})
                continue
            declared = Chem.MolToSmiles(Chem.RemoveHs(prep.mol))
            centre = ph if ph is not None else 7.4
            with rdBase.BlockLogs():
                states = sorted(
                    set(protonate_smiles(declared, ph_min=centre - window, ph_max=centre + window))
                )
                canon = {Chem.MolToSmiles(Chem.MolFromSmiles(s)) for s in states}
                enum = rdMolStandardize.TautomerEnumerator()
                enum.SetMaxTautomers(50)
                tautomers = len(enum.Enumerate(Chem.MolFromSmiles(declared)))
            rows.append(
                {
                    "ligand": lig.id,
                    "declared": declared,
                    "states": sorted(canon),
                    "n_states": len(canon),
                    "declared_in_states": declared in canon,
                    "tautomers": tautomers,
                }
            )
        m: dict[str, Any] = {
            "ph": ph,
            "max_states": max((r.get("n_states", 0) for r in rows), default=0),
            "declared_not_enumerated": sum(1 for r in rows if r.get("declared_in_states") is False),
            "max_tautomers": max((r.get("tautomers", 0) for r in rows), default=0),
        }
        tool = ToolRef(name="dimorphite_dl", version=_version("dimorphite_dl"))
        problems = [f"{r['ligand']}: {r['error']}" for r in rows if "error" in r]
        problems += [
            f"{r['ligand']}: {r['n_states']} states" for r in rows if r.get("n_states", 0) > 1
        ]
        problems += [
            f"{r['ligand']}: declared form {r['declared']} differs from enumerated "
            f"{', '.join(r['states'])}"
            for r in rows
            if r.get("declared_in_states") is False
        ]
        if ph is None:
            problems.append("pH not stated; enumerated at 7.4")
        gate = Gate.WARN if problems else Gate.PASS
        msg = "; ".join(problems) if problems else f"one state at pH {ph} for every ligand"
        return self.finding(
            gate, msg, measurements=m, thresholds=th, evidence={"ligands": rows}, tool=tool
        )


@register
class LigandConformers(Check):
    id = "l2.ligand.conformers"
    layer = Layer.ADEQUACY
    gate_kind = GateKind.WARN
    title = "Ligand conformers generated and minimised"
    requires_modules = ("rdkit",)

    def applies(self, ctx: CheckContext) -> str | None:
        return None if ctx.manifest.ligands else "no ligand declared"

    def run(self, ctx: CheckContext) -> Finding:
        from rdkit import Chem, rdBase

        allchem = outputs.rdkit_module("AllChem")

        th = (outputs.configured(self.id, "conformers"),)
        n = int(th[0].value)
        rows: list[dict[str, Any]] = []
        for lig in ctx.manifest.ligands:
            prep = resolve.prepared_ligand(ctx, lig)
            if prep.mol is None:
                rows.append({"ligand": lig.id, "embedded": 0, "error": "; ".join(prep.problems)})
                continue
            mol = Chem.AddHs(Chem.RemoveHs(prep.mol))
            params = allchem.ETKDGv3()
            params.randomSeed = 0xF00D
            with rdBase.BlockLogs():
                ids = list(allchem.EmbedMultipleConfs(mol, numConfs=n, params=params))
                results = allchem.MMFFOptimizeMoleculeConfs(mol) if ids else []
            energies = [e for conv, e in results if conv == 0] if results else []
            row: dict[str, Any] = {
                "ligand": lig.id,
                "embedded": len(ids),
                "converged": len(energies),
            }
            if energies:
                row["energy_range_kcal"] = round(max(energies) - min(energies), 2)
            row["meeko"] = _meeko_ok(mol)
            rows.append(row)
        failed = [r["ligand"] for r in rows if r["embedded"] == 0]
        m: dict[str, Any] = {
            "ligands": len(rows),
            "failed": len(failed),
            "min_embedded": min(r["embedded"] for r in rows),
        }
        if failed:
            return self.finding(
                Gate.STOP,
                f"conformer generation failed for {', '.join(failed)}",
                measurements=m,
                thresholds=th,
                evidence={"ligands": rows},
            )
        return self.finding(
            Gate.PASS,
            f"{m['min_embedded']} ETKDG conformers per ligand, MMFF minimised",
            measurements=m,
            thresholds=th,
            evidence={"ligands": rows},
            tool=ToolRef(name="rdkit"),
        )


def _meeko_ok(mol: Any) -> str:
    try:
        from meeko import MoleculePreparation
    except ImportError:
        return "not installed"
    from rdkit import Chem

    single = Chem.Mol(mol, confId=0) if mol.GetNumConformers() else mol
    try:
        MoleculePreparation().prepare(single)
    except Exception as exc:  # recorded per ligand; conformer generation is the gate
        return f"failed: {type(exc).__name__}"
    return "ok"


def docking_box(ctx: CheckContext) -> tuple[Any, Any, str] | None:
    """(centre, size, origin) from the manifest box or the first prediction's settings."""
    import numpy as np

    box = ctx.manifest.docking_box
    if box:
        return np.array(box.center), np.array(box.size), box.origin
    for p in ctx.manifest.predictions:
        s = p.settings
        keys = ("center_x", "center_y", "center_z", "size_x", "size_y", "size_z")
        if all(k in s for k in keys):
            vals = [float(s[k]) for k in keys]
            return np.array(vals[:3]), np.array(vals[3:]), f"{p.executor} settings"
    return None


@register
class DockingBoxCheck(Check):
    id = "l2.docking.box"
    layer = Layer.ADEQUACY
    gate_kind = GateKind.WARN
    title = "Docking box encloses the pocket with margin"
    requires_modules = ("gemmi", "numpy")

    def applies(self, ctx: CheckContext) -> str | None:
        if not (_docking(ctx) or ctx.manifest.docking_box):
            return "no docking executor or box declared"
        return None

    def run(self, ctx: CheckContext) -> Finding:
        import numpy as np

        th = (
            outputs.configured(self.id, "margin"),
            outputs.configured(self.id, "contact_distance"),
        )
        margin = float(th[0].value)
        box = docking_box(ctx)
        ref = outputs.reference_ligand(ctx) if _needs_site(ctx) is None else None
        if box is None:
            if ref is None:
                return self.finding(
                    Gate.STOP,
                    "no docking box declared and no reference ligand to derive one",
                    thresholds=th,
                )
            lo, hi = ref.coords.min(axis=0), ref.coords.max(axis=0)
            box = ((lo + hi) / 2, (hi - lo) + 8.0, f"derived from {ref.code} (+4 Å)")
            derived = True
        else:
            derived = False
        centre, size, origin = box
        lo, hi = centre - size / 2, centre + size / 2
        ev: dict[str, Any] = {
            "center": [round(float(x), 3) for x in centre],
            "size": [round(float(x), 3) for x in size],
            "origin": origin,
            "derived": derived,
        }
        m: dict[str, Any] = {"volume_A3": round(float(np.prod(size)), 1)}
        if ref is None:
            return self.finding(
                Gate.WARN,
                "box declared; no reference ligand to test it against",
                measurements=m,
                thresholds=th,
                evidence=ev,
            )
        inside_margin = np.all((ref.coords >= lo + margin) & (ref.coords <= hi - margin), axis=1)
        st = outputs.read_structure(_receptor_for_docking(ctx))
        pocket = outputs.pocket_residues(st, ref.coords, float(th[1].value))
        outside: list[str] = []
        for pr in pocket:
            res = st[0][pr.chain][str(pr.seqnum) + pr.icode.strip()][0]
            pts = np.array([a.pos.tolist() for a in res])
            if not np.any(np.all((pts >= lo) & (pts <= hi), axis=1)):
                outside.append(pr.label)
        m.update(
            {
                "ligand_atoms_inside_margin": int(inside_margin.sum()),
                "ligand_atoms": len(inside_margin),
                "contact_residues": len(pocket),
                "contact_residues_outside": len(outside),
            }
        )
        ev["contacts_outside"] = outside
        if outside or not inside_margin.all():
            return self.finding(
                Gate.STOP,
                f"box excludes {len(outside)} contact residues and "
                f"{int((~inside_margin).sum())} reference ligand atoms lie "
                f"within {margin} Å of its faces",
                measurements=m,
                thresholds=th,
                evidence=ev,
            )
        gate = Gate.WARN if derived else Gate.PASS
        prefix = "no box declared; derived box" if derived else "box"
        return self.finding(
            gate,
            f"{prefix} encloses {len(pocket)} contact residues and the "
            f"{ref.code} ligand with {margin} Å margin",
            measurements=m,
            thresholds=th,
            evidence=ev,
        )


@register
class PocketDetectionAgreement(Check):
    id = "l2.pocket.detection_agreement"
    layer = Layer.ADEQUACY
    gate_kind = GateKind.WARN
    title = "Pocket detection agrees with the known site"
    requires_modules = ("gemmi", "numpy")

    def applies(self, ctx: CheckContext) -> str | None:
        return _needs_site(ctx)

    def run(self, ctx: CheckContext) -> Finding:
        import numpy as np

        binary = _fpocket()
        if binary is None:
            return self.skip(
                SkipReason.TOOL_MISSING, "fpocket not found on PATH or in PAH_CONDA_PREFIX"
            )
        th = (outputs.configured(self.id, "site_distance"),)
        coords, label = _site(ctx)
        site = np.asarray(coords).mean(axis=0)
        pockets = _run_fpocket(binary, _receptor_for_docking(ctx), ctx)
        rows: list[dict[str, Any]] = [
            {
                "rank": i + 1,
                "center": [round(float(x), 2) for x in c],
                "distance_A": round(float(np.linalg.norm(c - site)), 2),
            }
            for i, c in enumerate(pockets)
        ]
        limit = float(th[0].value)
        hit = next((r for r in rows if r["distance_A"] <= limit), None)
        m: dict[str, Any] = {"pockets": len(rows), "site_rank": hit["rank"] if hit else None}
        ev: dict[str, Any] = {"site": label, "pockets": rows[:10]}
        tool = ToolRef(name="fpocket")
        if hit is None:
            return self.finding(
                Gate.WARN,
                f"no fpocket pocket within {th[0].value} Å of the site",
                measurements=m,
                thresholds=th,
                evidence=ev,
                tool=tool,
            )
        return self.finding(
            Gate.PASS,
            f"fpocket pocket {hit['rank']} of {len(rows)} at {hit['distance_A']} Å from the site",
            measurements=m,
            thresholds=th,
            evidence=ev,
            tool=tool,
        )


def _fpocket() -> str | None:
    import os
    import shutil

    found = shutil.which("fpocket")
    prefix = os.environ.get("PAH_CONDA_PREFIX") or ".tools/conda-env"
    cand = Path(prefix) / "bin" / "fpocket"
    return found or (str(cand) if cand.is_file() else None)


def _run_fpocket(binary: str, receptor: Path, ctx: CheckContext) -> list[Any]:
    import subprocess

    import numpy as np

    work = ctx.artifact_path("work/fpocket/receptor.pdb")
    st = outputs.read_structure(receptor)
    st.remove_ligands_and_waters()
    st.write_pdb(str(work))
    subprocess.run([binary, "-f", str(work)], check=True, capture_output=True, timeout=300)
    out = work.parent / "receptor_out" / "receptor_out.pdb"
    centres: dict[int, list[list[float]]] = {}
    for line in out.read_text().splitlines():
        if line.startswith("HETATM") and line[17:20] == "STP":
            centres.setdefault(int(line[22:26]), []).append(
                [float(line[30:38]), float(line[38:46]), float(line[46:54])]
            )
    return [np.array(v).mean(axis=0) for _, v in sorted(centres.items())]


@register
class LibraryProperties(Check):
    id = "l2.library.properties"
    layer = Layer.ADEQUACY
    gate_kind = GateKind.WARN
    title = "Library physicochemical properties"
    requires_modules = ("rdkit",)

    def applies(self, ctx: CheckContext) -> str | None:
        return None if ctx.manifest.ligands else "no ligand declared"

    def run(self, ctx: CheckContext) -> Finding:
        from rdkit import Chem
        from rdkit.Chem import rdMolDescriptors

        crippen, descriptors, lipinski = (
            outputs.rdkit_module(n) for n in ("Crippen", "Descriptors", "Lipinski")
        )

        rows: list[dict[str, Any]] = []
        for lig in ctx.manifest.ligands:
            prep = resolve.prepared_ligand(ctx, lig)
            if prep.mol is None:
                rows.append({"ligand": lig.id, "error": "; ".join(prep.problems)})
                continue
            mol = Chem.RemoveHs(prep.mol)
            row: dict[str, Any] = {
                "ligand": lig.id,
                "mw": round(descriptors.MolWt(mol), 1),
                "logp": round(crippen.MolLogP(mol), 2),
                "hbd": lipinski.NumHDonors(mol),
                "hba": lipinski.NumHAcceptors(mol),
                "charge": Chem.GetFormalCharge(mol),
                "rotatable": rdMolDescriptors.CalcNumRotatableBonds(mol),
                "heavy_atoms": mol.GetNumHeavyAtoms(),
            }
            row["ro5_violations"] = sum(
                [row["mw"] > 500, row["logp"] > 5, row["hbd"] > 5, row["hba"] > 10]
            )
            rows.append(row)
        ok = [r for r in rows if "error" not in r]
        errors = [r["ligand"] for r in rows if "error" in r]
        m: dict[str, Any] = {
            "ligands": len(rows),
            "unreadable": len(errors),
            "ro5_violating": sum(1 for r in ok if r["ro5_violations"] > 1),
        }
        if ok:
            m["median_mw"] = sorted(r["mw"] for r in ok)[len(ok) // 2]
        if errors:
            return self.finding(
                Gate.WARN,
                f"properties not computed for {', '.join(errors)}",
                measurements=m,
                evidence={"ligands": rows},
            )
        return self.finding(
            Gate.PASS,
            f"{len(ok)} ligands profiled",
            measurements=m,
            evidence={"ligands": rows},
            tool=ToolRef(name="rdkit"),
        )
