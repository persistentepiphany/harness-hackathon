"""Structure helpers shared by the output parsers.

Ligand extraction from co-folding complexes, complex assembly for docking poses and per-residue
pLDDT from B-factors. RDKit and gemmi are imported inside the functions that use them.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LIGAND_RESNAME = "LIG"
LIGAND_CHAIN = "L"

# AutoDock atom types to elements (PDBQT columns 78-79).
_AD_ELEMENTS = {
    "A": "C",
    "C": "C",
    "N": "N",
    "NA": "N",
    "NS": "N",
    "OA": "O",
    "OS": "O",
    "SA": "S",
    "S": "S",
    "HD": "H",
    "HS": "H",
    "H": "H",
    "P": "P",
    "F": "F",
    "CL": "Cl",
    "BR": "Br",
    "I": "I",
    "MG": "Mg",
    "MN": "Mn",
    "ZN": "Zn",
    "CA": "Ca",
    "FE": "Fe",
    "G0": "C",
    "G1": "C",
    "G2": "C",
    "G3": "C",
    "CG0": "C",
    "CG1": "C",
    "CG2": "C",
    "CG3": "C",
    "W": "O",
}


@dataclass(frozen=True)
class _Atom:
    name: str
    element: str
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class _LigandGroup:
    chain: str
    resname: str
    atoms: tuple[_Atom, ...]

    @property
    def heavy(self) -> int:
        return sum(1 for a in self.atoms if a.element.upper() not in ("H", "D"))


def pdb_atom_line(
    record: str,
    serial: int,
    name: str,
    resname: str,
    chain: str,
    resseq: int,
    xyz: tuple[float, float, float],
    element: str,
    occupancy: float = 1.0,
    bfactor: float = 0.0,
) -> str:
    """One fixed-column PDB ATOM/HETATM record."""
    name = name[:4]
    padded = name if len(name) >= 4 or len(element) == 2 else f" {name}"
    x, y, z = xyz
    return (
        f"{record:<6}{serial % 100000:>5} {padded:<4} {resname[:3]:>3} {chain[:1]:1}"
        f"{resseq % 10000:>4}    {x:8.3f}{y:8.3f}{z:8.3f}{occupancy:6.2f}{bfactor:6.2f}"
        f"          {element[:2].upper():>2}"
    )


def ad_type_element(ad_type: str) -> str:
    """Element symbol for an AutoDock atom type, e.g. OA -> O, A -> C."""
    key = ad_type.strip().upper()
    if key in _AD_ELEMENTS:
        return _AD_ELEMENTS[key]
    return key[:1] + key[1:].lower()


def pdbqt_to_pdb_lines(lines: Iterable[str]) -> list[str]:
    """ATOM/HETATM records of a PDBQT block with the charge and type columns replaced by element."""
    out: list[str] = []
    for line in lines:
        if line.startswith(("ATOM", "HETATM")):
            element = ad_type_element(line[77:79] if len(line) > 77 else line[12:14])
            out.append(f"{line[:66].ljust(66)}          {element.upper():>2}")
    return out


def _polymer_like(res: Any) -> bool:
    import gemmi

    if res.entity_type == gemmi.EntityType.Polymer:
        return True
    if res.entity_type in (gemmi.EntityType.NonPolymer, gemmi.EntityType.Branched):
        return False
    if res.entity_type == gemmi.EntityType.Water or res.is_water():
        return False
    info = gemmi.find_tabulated_residue(res.name)
    return bool(info is not None and (info.is_amino_acid() or info.is_nucleic_acid()))


def _read(path: Path) -> Any:
    import gemmi

    st = gemmi.read_structure(str(path))
    st.setup_entities()
    return st


def ligand_groups(structure_path: Path) -> list[_LigandGroup]:
    """Non-polymer, non-water residues of the first model, one group per residue."""
    st = _read(structure_path)
    groups: list[_LigandGroup] = []
    if len(st) == 0:
        return groups
    for chain in st[0]:
        for res in chain:
            if res.is_water() or _polymer_like(res):
                continue
            atoms = tuple(_Atom(a.name, a.element.name, a.pos.x, a.pos.y, a.pos.z) for a in res)
            if atoms:
                groups.append(_LigandGroup(chain.name, res.name, atoms))
    return groups


def _select_group(
    groups: Sequence[_LigandGroup],
    template_heavy: int | None,
    resname: str | None,
    chain: str | None,
    issues: list[str],
) -> _LigandGroup | None:
    pool = list(groups)
    if chain is not None:
        on_chain = [g for g in pool if g.chain == chain]
        if on_chain:
            merged = tuple(a for g in on_chain for a in g.atoms)
            pool = [_LigandGroup(chain, on_chain[0].resname, merged)]
        else:
            issues.append(f"no ligand residue on chain {chain}; chose among all ligand residues")
    if resname is not None and chain is None:
        named = [g for g in pool if g.resname.upper() == resname.upper()]
        if named:
            pool = named
        else:
            issues.append(f"no ligand residue named {resname}; chose among all ligand residues")
    if not pool:
        return None
    if template_heavy is not None:
        matching = [g for g in pool if g.heavy == template_heavy]
        if matching:
            pool = matching
    return max(pool, key=lambda g: g.heavy)


def _pdb_block(atoms: Sequence[_Atom]) -> str:
    lines = [
        pdb_atom_line(
            "HETATM", i, a.name, LIGAND_RESNAME, LIGAND_CHAIN, 1, (a.x, a.y, a.z), a.element
        )
        for i, a in enumerate(atoms, start=1)
    ]
    return "\n".join([*lines, "END", ""])


def mol_from_pdb_block(block: str) -> Any:
    """RDKit molecule from a PDB block with bonds by proximity, hydrogens removed, or None."""
    from rdkit import Chem

    mol = Chem.MolFromPDBBlock(block, removeHs=False, proximityBonding=True)
    if mol is None:
        mol = Chem.MolFromPDBBlock(block, sanitize=False, removeHs=False, proximityBonding=True)
        if mol is None:
            return None
    try:
        return Chem.RemoveHs(mol)
    except Exception:
        return Chem.RemoveHs(mol, sanitize=False)


def template_heavy_atoms(smiles: str | None) -> int | None:
    if not smiles:
        return None
    from rdkit import Chem

    tmpl = Chem.MolFromSmiles(smiles)
    return None if tmpl is None else int(tmpl.GetNumHeavyAtoms())


def assign_bond_orders(mol: Any, smiles: str | None, issues: list[str], what: str) -> Any:
    """`mol` with bond orders from the SMILES template, or `mol` unchanged plus an issue."""
    from rdkit import Chem
    from rdkit.Chem import AllChem

    if not smiles:
        issues.append(f"{what}: no declared SMILES; bond orders from coordinates only")
        return mol
    template = Chem.MolFromSmiles(smiles)
    if template is None:
        issues.append(f"{what}: declared SMILES does not parse; bond orders from coordinates")
        return mol
    template = Chem.RemoveHs(template)
    try:
        heavy = Chem.RemoveHs(mol, sanitize=False)
        return AllChem.AssignBondOrdersFromTemplate(template, heavy)
    except Exception as exc:
        issues.append(
            f"{what}: bond orders from SMILES failed ({type(exc).__name__}: {exc}); "
            "kept bonds from coordinates"
        )
        return mol


def write_sdf(mol: Any, out_sdf: Path, name: str | None = None) -> Path:
    from rdkit import Chem

    out_sdf.parent.mkdir(parents=True, exist_ok=True)
    if name:
        mol.SetProp("_Name", name)
    writer = Chem.SDWriter(str(out_sdf))
    try:
        writer.SetKekulize(False)
        writer.write(mol)
    finally:
        writer.close()
    return out_sdf


def extract_ligand(
    structure_path: Path,
    smiles: str | None,
    out_sdf: Path,
    *,
    resname: str | None = None,
    chain: str | None = None,
    issues: list[str] | None = None,
    name: str | None = None,
) -> Path | None:
    """Writes the predicted ligand of a co-folding complex to `out_sdf`.

    The ligand is the non-polymer, non-water residue on `chain` or named `resname` when given,
    else the residue whose heavy-atom count matches the SMILES, else the largest. Bond orders come
    from the SMILES; when that fails the coordinate-derived molecule is written and an issue
    appended to `issues`. Returns None when the structure holds no ligand residue.
    """
    sink: list[str] = issues if issues is not None else []
    groups = ligand_groups(structure_path)
    group = _select_group(groups, template_heavy_atoms(smiles), resname, chain, sink)
    if group is None:
        sink.append(f"{structure_path.name}: no non-polymer, non-water residue")
        return None
    mol = mol_from_pdb_block(_pdb_block(group.atoms))
    if mol is None:
        sink.append(f"{structure_path.name}: RDKit could not read ligand {group.resname}")
        return None
    mol = assign_bond_orders(mol, smiles, sink, f"{structure_path.name} ligand {group.resname}")
    return write_sdf(mol, out_sdf, name)


def _receptor_lines(receptor: Path) -> list[str]:
    suffix = receptor.suffix.lower()
    if suffix in (".cif", ".mmcif") or receptor.name.lower().endswith((".cif.gz", ".pdb.gz")):
        import gemmi

        st = gemmi.read_structure(str(receptor))
        st.setup_entities()
        text = st.make_pdb_string()
        return [ln for ln in text.splitlines() if ln.startswith(("ATOM", "HETATM"))]
    raw = receptor.read_text(encoding="utf-8", errors="replace").splitlines()
    model: list[str] = []
    for line in raw:
        if line.startswith("ENDMDL"):
            break
        model.append(line)
    if suffix == ".pdbqt":
        return pdbqt_to_pdb_lines(model)
    return [ln[:80] for ln in model if ln.startswith(("ATOM", "HETATM"))]


def ligand_pdb_lines(mol: Any, start_serial: int) -> tuple[list[str], list[str]]:
    """HETATM records (residue LIG, chain L) and CONECT records for an RDKit molecule."""
    conf = mol.GetConformer()
    atoms: list[str] = []
    counts: dict[str, int] = {}
    for atom in mol.GetAtoms():
        el = atom.GetSymbol()
        counts[el] = counts.get(el, 0) + 1
        p = conf.GetAtomPosition(atom.GetIdx())
        atoms.append(
            pdb_atom_line(
                "HETATM",
                start_serial + atom.GetIdx(),
                f"{el.upper()}{counts[el]}",
                LIGAND_RESNAME,
                LIGAND_CHAIN,
                1,
                (p.x, p.y, p.z),
                el,
            )
        )
    conect: list[str] = []
    for atom in mol.GetAtoms():
        partners = sorted(start_serial + n.GetIdx() for n in atom.GetNeighbors())
        if partners:
            serial = start_serial + atom.GetIdx()
            conect.append("CONECT" + "".join(f"{s:>5}" for s in (serial, *partners[:4])))
    return atoms, conect


def assemble_complex(receptor: Path, ligand_sdf: Path, out_pdb: Path) -> Path:
    """Writes receptor atoms plus the ligand as HETATM residue LIG on chain L to `out_pdb`."""
    from rdkit import Chem

    mol = next(iter(Chem.SDMolSupplier(str(ligand_sdf), sanitize=False, removeHs=False)), None)
    if mol is None:
        raise ValueError(f"{ligand_sdf}: no molecule")
    rec = _receptor_lines(receptor)
    if not rec:
        raise ValueError(f"{receptor}: no ATOM or HETATM records")
    lig, conect = ligand_pdb_lines(mol, len(rec) + 1)
    out_pdb.parent.mkdir(parents=True, exist_ok=True)
    out_pdb.write_text("\n".join([*rec, "TER", *lig, *conect, "END", ""]), encoding="utf-8")
    return out_pdb


def polymer_residues(structure_path: Path) -> list[tuple[tuple[str, int], list[float], int]]:
    """Polymer residues of the first model: `((chain, seqnum), atom B-factors, heavy atoms)`."""
    st = _read(structure_path)
    out: list[tuple[tuple[str, int], list[float], int]] = []
    if len(st) == 0:
        return out
    for chain in st[0]:
        for res in chain:
            if _polymer_like(res):
                b = [a.b_iso for a in res]
                heavy = sum(1 for a in res if not a.is_hydrogen())
                out.append(((chain.name, int(res.seqid.num)), b, heavy))
    return out


def residue_plddt(
    structure_path: Path,
) -> tuple[tuple[float, ...], tuple[tuple[str, int], ...]]:
    """Per-residue mean B-factor for polymer residues, read as pLDDT on the file's own scale."""
    rows = polymer_residues(structure_path)
    values = tuple(round(sum(b) / len(b), 3) for _, b, _ in rows if b)
    residues = tuple(key for key, b, _ in rows if b)
    return values, residues


def atom_table(structure_path: Path) -> list[tuple[str, tuple[str, int], bool, bool]]:
    """Atoms of the first model in file order: `(chain, (chain, seqnum), polymer, hydrogen)`."""
    st = _read(structure_path)
    out: list[tuple[str, tuple[str, int], bool, bool]] = []
    if len(st) == 0:
        return out
    for chain in st[0]:
        for res in chain:
            poly = _polymer_like(res)
            for a in res:
                out.append((chain.name, (chain.name, int(res.seqid.num)), poly, a.is_hydrogen()))
    return out


def standard_residue(name: str) -> bool:
    import gemmi

    info = gemmi.find_tabulated_residue(name)
    return bool(info is not None and info.is_standard())


def token_residues(structure_path: Path) -> list[tuple[str, int] | None]:
    """Token order of a co-folding model: one token per standard polymer residue, one per heavy
    atom otherwise (Boltz, AF3 and Protenix tokenisation). Polymer tokens map to their residue,
    the others to None."""
    st = _read(structure_path)
    tokens: list[tuple[str, int] | None] = []
    if len(st) == 0:
        return tokens
    for chain in st[0]:
        for res in chain:
            if res.is_water():
                continue
            if _polymer_like(res) and standard_residue(res.name):
                tokens.append((chain.name, int(res.seqid.num)))
            else:
                tokens.extend(None for a in res if not a.is_hydrogen())
    return tokens
