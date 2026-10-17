"""Fetch-once accessors used by checks. Every record fetched is added to the run's provenance."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

from pah.core.check import CheckContext
from pah.core.manifest import LigandInput, ProteinInput
from pah.core.models import ArtifactKind, Gate, Provenance, Threshold, provenance_id
from pah.sources.clients import (
    ChemComp,
    PdbEntry,
    PdbMolecules,
    PubChemCompound,
    SiftsMapping,
    SiftsSegment,
    UniProtAnnotations,
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
    name: str,
    value: Any,
    comparator: str,
    origin: str,
    level: str = "uncalibrated",
    *,
    measurement: str | None = None,
) -> Threshold:
    """A threshold with its origin; `measurement` names the measurement it is compared with."""
    return Threshold.model_validate(
        {
            "name": name,
            "value": value,
            "comparator": comparator,
            "origin": origin,
            "evidence_level": level,
            "measurement": measurement,
        }
    )


def _memo(ctx: CheckContext, key: str, fetch: Any) -> Any:
    """Fetches once per run; every access marks the record as used by the current check."""
    record = ctx.memo(key, fetch)
    prov = getattr(record, "provenance", None)
    if prov is not None:
        ctx.record(prov)
    return record


def uniprot(ctx: CheckContext, accession: str) -> UniProtEntry:
    return _memo(ctx, f"uniprot:{accession}", lambda: ctx.sources.uniprot.entry(accession))


def uniprot_annotations(ctx: CheckContext, accession: str) -> UniProtAnnotations:
    return _memo(
        ctx, f"uniprot_ann:{accession}", lambda: ctx.sources.uniprot.annotations(accession)
    )


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
    def fetch() -> tuple[Path, Provenance]:
        payload = ctx.sources.rcsb.mmcif(pdb_id)
        path = ctx.artifact_path(f"sources/{pdb_id.upper()}.cif")
        path.write_bytes(payload.data)
        ctx.add_artifact(
            path,
            ArtifactKind.SOURCE_STRUCTURE,
            label=f"{pdb_id.upper()} mmCIF",
            derived_from=(provenance_id(payload.provenance),),
        )
        return path, payload.provenance

    path, prov = ctx.memo(f"mmcif:{pdb_id.upper()}", fetch)
    ctx.record(prov)
    return path


def sifts_segments(ctx: CheckContext, p: ProteinInput) -> list[SiftsSegment]:
    if not (p.pdb_id and p.uniprot):
        return []
    return [
        s
        for s in sifts(ctx, p.pdb_id).segments
        if s.uniprot == p.uniprot and (p.chain is None or p.chain in (s.chain_id, s.struct_asym_id))
    ]


def parse_mutation(m: str) -> tuple[str, int, str]:
    return m[0], int(m[1:-1]), m[-1]


def mutation_errors(ctx: CheckContext, p: ProteinInput) -> list[str]:
    """Declared mutations whose wild-type residue disagrees with UniProt."""
    if not (p.uniprot and p.mutations):
        return []
    full = uniprot(ctx, p.uniprot).sequence
    errors = []
    for m in p.mutations:
        wt, pos, _ = parse_mutation(m)
        if pos < 1 or pos > len(full):
            errors.append(f"{m}: position outside {p.uniprot} (length {len(full)})")
        elif full[pos - 1] != wt:
            errors.append(f"{m}: {p.uniprot} has {full[pos - 1]} at {pos}")
    return errors


def mutated_uniprot(ctx: CheckContext, p: ProteinInput) -> str:
    """Canonical UniProt sequence with the declared mutations applied."""
    assert p.uniprot
    seq = list(uniprot(ctx, p.uniprot).sequence)
    for m in p.mutations:
        _, pos, mut = parse_mutation(m)
        if 1 <= pos <= len(seq):
            seq[pos - 1] = mut
    return "".join(seq)


def reference_sequence(ctx: CheckContext, p: ProteinInput) -> tuple[str, str]:
    """Expected sequence for a protein input and a label for where it came from.

    With a PDB chain mapped by SIFTS, the expected construct is the mapped UniProt range;
    otherwise it is the full canonical UniProt sequence. Declared mutations are applied.
    """
    full = mutated_uniprot(ctx, p)
    note = f" with {len(p.mutations)} declared mutations" if p.mutations else ""
    segs = sifts_segments(ctx, p)
    if segs:
        lo = min(s.unp_start for s in segs)
        hi = max(s.unp_end for s in segs)
        return full[lo - 1 : hi], f"{p.uniprot}[{lo}-{hi}] via SIFTS {p.pdb_id}{note}"
    return full, f"{p.uniprot} canonical{note}"


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


METALS = frozenset({
    "Li", "Na", "K", "Rb", "Cs", "Be", "Mg", "Ca", "Sr", "Ba", "Al", "Ga", "In", "Tl", "Sn",
    "Pb", "Bi", "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn", "Y", "Zr", "Nb",
    "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au",
    "Hg", "La", "Ce", "Pr", "Nd", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb", "Lu",
    "U",
})  # fmt: skip


@dataclass(frozen=True)
class PreparedMol:
    """A ligand after sanitisation. `mol` is None when the structure could not be sanitised."""

    mol: Any | None
    origin: str
    problems: tuple[str, ...] = ()
    metal: bool = False
    metal_disconnected: bool = False


def _problem_atoms(problem: Any) -> set[int]:
    if hasattr(problem, "GetAtomIdx"):
        return {int(problem.GetAtomIdx())}
    if hasattr(problem, "GetAtomIndices"):
        return {int(i) for i in problem.GetAtomIndices()}
    return set()


def prepare(mol: Any, origin: str) -> PreparedMol:
    """Sanitises an RDKit molecule. When every chemistry problem sits on an atom bonded to a
    metal, the metal bonds are disconnected (as standard InChI does) and sanitisation retried."""
    from rdkit import Chem, rdBase
    from rdkit.Chem.MolStandardize import rdMolStandardize

    with rdBase.BlockLogs():
        metal_idx = {a.GetIdx() for a in mol.GetAtoms() if a.GetSymbol() in METALS}
        problems = list(Chem.DetectChemistryProblems(mol))
        texts = tuple(f"{p.GetType()}: {p.Message()}" for p in problems)
        if not problems:
            Chem.SanitizeMol(mol)
            return PreparedMol(mol, origin, metal=bool(metal_idx))
        near_metal = set(metal_idx)
        for i in metal_idx:
            near_metal |= {n.GetIdx() for n in mol.GetAtomWithIdx(i).GetNeighbors()}
        on_metal = all(_problem_atoms(p) and _problem_atoms(p) <= near_metal for p in problems)
        if metal_idx and on_metal:
            mol.UpdatePropertyCache(strict=False)
            fixed = rdMolStandardize.MetalDisconnector().Disconnect(mol)
            if not Chem.DetectChemistryProblems(fixed):
                Chem.SanitizeMol(fixed)
                return PreparedMol(fixed, origin, texts, metal=True, metal_disconnected=True)
        return PreparedMol(None, origin, texts, metal=bool(metal_idx))


def mol_from_smiles(smiles: str, origin: str) -> PreparedMol:
    from rdkit import Chem, rdBase

    with rdBase.BlockLogs():
        mol = Chem.MolFromSmiles(smiles, sanitize=False)
    if mol is None:
        return PreparedMol(None, origin, (f"cannot parse SMILES {smiles!r}",))
    return prepare(mol, origin)


def prepared_ligand(ctx: CheckContext, lig: LigandInput) -> PreparedMol:
    """The ligand as given to the run: the file when declared, otherwise its SMILES."""

    def build() -> PreparedMol:
        from rdkit import Chem, rdBase

        if lig.file:
            path = ctx.manifest.path(lig.file)
            origin = f"file {lig.file}"
            if not path.is_file():
                return PreparedMol(None, origin, (f"file not found: {path}",))
            try:
                with rdBase.BlockLogs():
                    mol = Chem.MolFromMolFile(str(path), sanitize=False, removeHs=False)
            except OSError as exc:
                return PreparedMol(None, origin, (f"cannot read {path}: {exc}",))
            if mol is None:
                return PreparedMol(None, origin, (f"cannot parse {path}",))
            return prepare(mol, origin)
        smiles, origin = ligand_smiles(ctx, lig)
        if not smiles:
            return PreparedMol(None, "none", ("no ligand structure available",))
        return mol_from_smiles(smiles, f"SMILES ({origin})")

    return ctx.memo(f"ligand:{lig.id}", build)


def inchikey(prep: PreparedMol) -> str | None:
    """InChIKey with stereo from 3D coordinates when present; None when unavailable."""
    from rdkit import Chem, rdBase

    if prep.mol is None:
        return None
    with rdBase.BlockLogs():
        mol = Chem.Mol(prep.mol)
        if mol.GetNumConformers() and mol.GetConformer().Is3D():
            Chem.AssignStereochemistryFrom3D(mol)
        key = Chem.MolToInchiKey(Chem.RemoveHs(mol, sanitize=False))
    return key or None


def compare_inchikey(key: str | None, ref: str, metal: bool) -> tuple[Gate, str]:
    """Full match passes. For metal-containing ligands a skeleton-only match warns, because
    the stereo and charge blocks depend on how each toolkit represents metal bonds."""
    if key == ref:
        return Gate.PASS, "identical"
    if key and metal and key[:14] == ref[:14]:
        return (
            Gate.WARN,
            "skeleton identical; stereo/charge blocks differ (metal-containing ligand)",
        )
    if key and key[:14] == ref[:14]:
        return Gate.STOP, "skeleton identical; stereo or protonation blocks differ"
    return Gate.STOP, "different molecule" if key else "no InChIKey for input"


METAL_RULE = "Harness rule for metal-containing ligands (InChIKey skeleton); uncalibrated"


def reference_inchikeys(ctx: CheckContext, lig: LigandInput) -> dict[str, str]:
    refs: dict[str, str] = {}
    if lig.ccd:
        key = chemcomp(ctx, lig.ccd).inchikey
        if key:
            refs[f"CCD {lig.ccd.upper()}"] = key
    if lig.pubchem_cid:
        refs[f"PubChem {lig.pubchem_cid}"] = pubchem(ctx, lig.pubchem_cid).inchikey
    return refs


def read_a3m(path: Path) -> list[tuple[str, str]]:
    """Records of an A3M file, or of a Boltz MSA CSV (`key,sequence`; key -1 means unpaired,
    other keys pair rows across chains and become the header `key=<k>`)."""
    if path.suffix.lower() == ".csv":
        import csv

        with path.open(newline="") as fh:
            return [
                (f"key={row['key']}", row["sequence"].strip())
                for row in csv.DictReader(fh)
                if row.get("sequence")
            ]
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
