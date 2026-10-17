"""Fetch-once accessors used by checks. Every record fetched is added to the run's provenance."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypeVar

from pah.core.check import CheckContext
from pah.core.manifest import LigandInput, ProteinInput
from pah.core.models import Threshold
from pah.sources.clients import (
    ChemComp,
    PdbEntry,
    PdbMolecules,
    PubChemCompound,
    SiftsMapping,
    SiftsSegment,
    UniProtEntry,
)

R = TypeVar("R")

ONE_LETTER = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q", "GLU": "E",
    "GLY": "G", "HIS": "H", "ILE": "I", "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F",
    "PRO": "P", "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V", "SEC": "U",
    "PYL": "O",
}  # fmt: skip
CANONICAL = frozenset("ACDEFGHIKLMNPQRSTVWY")


def threshold(
    name: str, value: Any, comparator: str, origin: str, level: str = "uncalibrated"
) -> Threshold:
    return Threshold.model_validate(
        {
            "name": name,
            "value": value,
            "comparator": comparator,
            "origin": origin,
            "evidence_level": level,
        }
    )


def _memo(ctx: CheckContext, key: str, fetch: Any) -> Any:
    def run() -> Any:
        record = fetch()
        prov = getattr(record, "provenance", None)
        if prov is not None:
            ctx.record(prov)
        return record

    return ctx.memo(key, run)


def uniprot(ctx: CheckContext, accession: str) -> UniProtEntry:
    return _memo(ctx, f"uniprot:{accession}", lambda: ctx.sources.uniprot.entry(accession))


def pdb_entry(ctx: CheckContext, pdb_id: str) -> PdbEntry:
    return _memo(ctx, f"pdb_entry:{pdb_id.upper()}", lambda: ctx.sources.rcsb.entry(pdb_id))


def pdb_molecules(ctx: CheckContext, pdb_id: str) -> PdbMolecules:
    return _memo(ctx, f"pdb_mol:{pdb_id.lower()}", lambda: ctx.sources.pdbe.molecules(pdb_id))


def sifts(ctx: CheckContext, pdb_id: str) -> SiftsMapping:
    return _memo(ctx, f"sifts:{pdb_id.lower()}", lambda: ctx.sources.pdbe.sifts(pdb_id))


def chemcomp(ctx: CheckContext, code: str) -> ChemComp:
    return _memo(ctx, f"ccd:{code.upper()}", lambda: ctx.sources.rcsb.chemcomp(code))


def pubchem(ctx: CheckContext, cid: int) -> PubChemCompound:
    return _memo(ctx, f"pubchem:{cid}", lambda: ctx.sources.pubchem.compound(cid))


def mmcif_path(ctx: CheckContext, pdb_id: str) -> Path:
    def fetch() -> Path:
        payload = ctx.sources.rcsb.mmcif(pdb_id)
        ctx.record(payload.provenance)
        path = ctx.artifact_path(f"sources/{pdb_id.upper()}.cif")
        path.write_bytes(payload.data)
        return path

    return ctx.memo(f"mmcif:{pdb_id.upper()}", fetch)


def sifts_segments(ctx: CheckContext, p: ProteinInput) -> list[SiftsSegment]:
    if not (p.pdb_id and p.uniprot):
        return []
    return [
        s
        for s in sifts(ctx, p.pdb_id).segments
        if s.uniprot == p.uniprot and (p.chain is None or p.chain in (s.chain_id, s.struct_asym_id))
    ]


def reference_sequence(ctx: CheckContext, p: ProteinInput) -> tuple[str, str]:
    """Expected sequence for a protein input and a label for where it came from.

    With a PDB chain mapped by SIFTS, the expected construct is the mapped UniProt range;
    otherwise it is the full canonical UniProt sequence.
    """
    assert p.uniprot
    full = uniprot(ctx, p.uniprot).sequence
    segs = sifts_segments(ctx, p)
    if segs:
        lo = min(s.unp_start for s in segs)
        hi = max(s.unp_end for s in segs)
        return full[lo - 1 : hi], f"{p.uniprot}[{lo}-{hi}] via SIFTS {p.pdb_id}"
    return full, f"{p.uniprot} canonical"


def ligand_smiles(ctx: CheckContext, lig: LigandInput) -> tuple[str | None, str]:
    """SMILES for a ligand and its origin: declared SMILES, else CCD, else PubChem."""
    if lig.smiles:
        return lig.smiles, "manifest"
    if lig.ccd:
        cc = chemcomp(ctx, lig.ccd)
        return cc.smiles_stereo or cc.smiles, f"CCD {cc.code}"
    if lig.pubchem_cid:
        return pubchem(ctx, lig.pubchem_cid).smiles, f"PubChem {lig.pubchem_cid}"
    return None, "none"


def ligand_mol(ctx: CheckContext, lig: LigandInput) -> tuple[Any, str]:
    """RDKit molecule as given to the run (file first, then SMILES), unsanitised errors raised."""
    from rdkit import Chem, rdBase

    with rdBase.BlockLogs():
        return _parse_ligand(ctx, lig, Chem)


def _parse_ligand(ctx: CheckContext, lig: LigandInput, chem: Any) -> tuple[Any, str]:
    Chem = chem  # noqa: N806 - RDKit module alias
    if lig.file:
        path = ctx.manifest.path(lig.file)
        mol = Chem.MolFromMolFile(str(path), sanitize=False, removeHs=False)
        if mol is None:
            raise ValueError(f"cannot parse {path}")
        return mol, f"file {lig.file}"
    smiles, origin = ligand_smiles(ctx, lig)
    if not smiles:
        raise ValueError("no ligand structure available")
    mol = Chem.MolFromSmiles(smiles, sanitize=False)
    if mol is None:
        raise ValueError(f"cannot parse SMILES {smiles!r}")
    return mol, f"SMILES ({origin})"


def reference_inchikeys(ctx: CheckContext, lig: LigandInput) -> dict[str, str]:
    refs: dict[str, str] = {}
    if lig.ccd:
        key = chemcomp(ctx, lig.ccd).inchikey
        if key:
            refs[f"CCD {lig.ccd.upper()}"] = key
    if lig.pubchem_cid:
        refs[f"PubChem {lig.pubchem_cid}"] = pubchem(ctx, lig.pubchem_cid).inchikey
    return refs
