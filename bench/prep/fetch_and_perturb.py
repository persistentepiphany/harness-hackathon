"""Fetch each benchmark entry, build wild-type and perturbed inputs, record every checksum.

    python bench/prep/fetch_and_perturb.py --out bench/runs/<id>/prep

Per system and state, writes `<out>/<system>_<state>/`:
  boltz.yaml   Boltz-2 input (protein sequence, ligand SMILES, context components, affinity)
  rec.pdb      receptor for DiffDock-L: the chain's modelled residues, contacts cut to glycine
               in the pocket_to_gly state
  ligand.smi   ligand SMILES given to both executors
  meta.json    sequence, mutations (author and SEQRES numbering), ligand, context, sha256s
Downloads go to `<out>/sources/` with their sha256 in `<out>/sources.json`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml

RCSB_FILES = "https://files.rcsb.org/download/{pdb}.cif"
CCD = "https://data.rcsb.org/rest/v1/core/chemcomp/{code}"
BACKBONE = {"N", "CA", "C", "O", "OXT"}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(client: httpx.Client, url: str, dest: Path, record: dict[str, Any]) -> bytes:
    if dest.is_file():
        data = dest.read_bytes()
    else:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.content
        dest.write_bytes(data)
    record[dest.name] = {
        "url": url,
        "sha256": sha256(data),
        "bytes": len(data),
        "retrieved": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    return data


def ccd_smiles(client: httpx.Client, code: str, sources: Path, record: dict[str, Any]) -> str:
    data = fetch(client, CCD.format(code=code), sources / f"ccd_{code}.json", record)
    desc = json.loads(data)["rcsb_chem_comp_descriptor"]
    return str(desc.get("SMILES_stereo") or desc["SMILES"])


def contact_residues(st: Any, chain: str, ligand: str, radius: float) -> list[Any]:
    """Polymer residues of `chain` with any atom within `radius` Å of the first `ligand` residue
    bound to that chain (nearest by centroid)."""
    import gemmi
    import numpy as np

    model = st[0]
    ch = model[chain]
    ca = np.array([r["CA"][0].pos.tolist() for r in ch if r.find_atom("CA", "*")])
    centre = ca.mean(axis=0)
    ligs = [r for c in model for r in c if r.name == ligand]
    if not ligs:
        raise SystemExit(f"ligand {ligand} not found")
    lig = min(
        ligs,
        key=lambda r: np.linalg.norm(np.array([a.pos.tolist() for a in r]).mean(axis=0) - centre),
    )
    ns = gemmi.NeighborSearch(model, st.cell, 6.0).populate()
    hits: dict[tuple[int, str], Any] = {}
    for atom in lig:
        for mark in ns.find_atoms(atom.pos, "\0", radius=radius):
            cra = mark.to_cra(model)
            if cra.chain.name != chain or cra.residue.het_flag == "H":
                continue
            hits[(cra.residue.seqid.num, cra.residue.seqid.icode)] = cra.residue
    return [hits[k] for k in sorted(hits)], lig


def receptor_pdb(st: Any, chain: str, to_gly: set[tuple[int, str]], out: Path) -> None:
    """Protein chain only; residues in `to_gly` keep backbone atoms and are renamed GLY."""
    import gemmi

    rec = gemmi.Structure()
    rec.cell = st.cell
    model = gemmi.Model("1")
    src = st[0][chain]
    new = gemmi.Chain(chain)
    for res in src:
        if res.het_flag == "H":
            continue
        r = gemmi.Residue()
        r.name, r.seqid, r.entity_type = res.name, res.seqid, res.entity_type
        mutate = (res.seqid.num, res.seqid.icode) in to_gly
        if mutate:
            r.name = "GLY"
        for atom in res:
            if atom.element.name == "H" or (mutate and atom.name not in BACKBONE):
                continue
            r.add_atom(atom)
        new.add_residue(r)
    model.add_chain(new)
    rec.add_model(model)
    rec.setup_entities()
    rec.write_pdb(str(out))


def methylate(smiles: str, n: int) -> tuple[str, list[int]]:
    """Methylates the hydroxyls on ring carbons not bonded to the ring oxygen (for glucose:
    O2, O3, O4), up to `n` of them, in atom order."""
    from rdkit import Chem

    mol = Chem.RWMol(Chem.MolFromSmiles(smiles))
    ri = mol.GetRingInfo()
    targets = []
    for atom in mol.GetAtoms():
        if atom.GetSymbol() != "O" or atom.GetTotalNumHs() != 1:
            continue
        carbon = atom.GetNeighbors()[0]
        if not ri.NumAtomRings(carbon.GetIdx()):
            continue
        if any(
            n_.GetSymbol() == "O" and ri.NumAtomRings(n_.GetIdx()) for n_ in carbon.GetNeighbors()
        ):
            continue
        targets.append(atom.GetIdx())
    targets = targets[:n]
    for idx in targets:
        c = mol.AddAtom(Chem.Atom(6))
        mol.AddBond(idx, c, Chem.BondType.SINGLE)
    out = mol.GetMol()
    Chem.SanitizeMol(out)
    return Chem.MolToSmiles(out), targets


def boltz_yaml(sequence: str, smiles: str, context: list[str]) -> str:
    seqs: list[dict[str, Any]] = [{"protein": {"id": "A", "sequence": sequence}}]
    seqs.append({"ligand": {"id": "L", "smiles": smiles}})
    for i, code in enumerate(context):
        seqs.append({"ligand": {"id": f"C{i + 1}", "ccd": code}})
    doc = {"version": 1, "sequences": seqs, "properties": [{"affinity": {"binder": "L"}}]}
    return yaml.safe_dump(doc, sort_keys=False)


def prepare(
    system: dict[str, Any], out: Path, client: httpx.Client, record: dict[str, Any]
) -> None:
    import gemmi

    sources = out / "sources"
    pdb, chain, code = system["pdb"], system["chain"], system["ligand"]
    cif = sources / f"{pdb}.cif"
    fetch(client, RCSB_FILES.format(pdb=pdb), cif, record)
    st = gemmi.read_structure(str(cif))
    st.setup_entities()
    st.remove_hydrogens()
    smiles = ccd_smiles(client, code, sources, record)
    contacts, lig = contact_residues(
        st, chain, code, float(system["perturbation"].get("radius", 3.5))
    )
    polymer = st[0][chain].get_polymer()
    entity = st.get_entity_of(polymer)
    full = gemmi.one_letter_code(entity.full_sequence)
    pert = system["perturbation"]
    for state in ("wt", "pert"):
        d = out / f"{system['id']}_{state}"
        d.mkdir(parents=True, exist_ok=True)
        seq = list(full)
        to_gly: set[tuple[int, str]] = set()
        mutations: list[dict[str, Any]] = []
        lig_smiles = smiles
        methylated: list[int] = []
        if state == "pert" and pert["kind"] == "pocket_to_gly":
            for res in contacts:
                idx = res.label_seq - 1 if res.label_seq else None
                if idx is None or res.name == "GLY":
                    continue
                to_gly.add((res.seqid.num, res.seqid.icode))
                mutations.append(
                    {
                        "residue": f"{res.name}{res.seqid.num}{res.seqid.icode.strip()}",
                        "seqres_index": idx + 1,
                        "from": seq[idx],
                        "to": "G",
                    }
                )
                seq[idx] = "G"
        if state == "pert" and pert["kind"] == "ligand_methylate":
            lig_smiles, methylated = methylate(smiles, int(pert["n_hydroxyls"]))
        sequence = "".join(seq)
        (d / "boltz.yaml").write_text(boltz_yaml(sequence, lig_smiles, list(system["context"])))
        receptor_pdb(st, chain, to_gly, d / "rec.pdb")
        (d / "ligand.smi").write_text(lig_smiles + "\n")
        meta = {
            "system": system["id"],
            "state": state,
            "protein": system["protein"],
            "pdb": pdb,
            "chain": chain,
            "ligand_code": code,
            "ligand_smiles": lig_smiles,
            "reference_ligand": {"code": code, "chain": lig.subchain, "seqid": str(lig.seqid)},
            "context": list(system["context"]),
            "perturbation": pert if state == "pert" else None,
            "contacts_within_A": float(pert.get("radius", 3.5)),
            "contacts": [f"{r.name}{r.seqid.num}{r.seqid.icode.strip()}" for r in contacts],
            "mutations": mutations,
            "methylated_oxygens": methylated,
            "sequence": sequence,
            "sequence_length": len(sequence),
            "files": {p.name: sha256(p.read_bytes()) for p in sorted(d.iterdir()) if p.is_file()},
        }
        (d / "meta.json").write_text(json.dumps(meta, indent=2))
        print(
            f"{d.name}: {len(sequence)} residues, {len(mutations)} mutations, "
            f"{len(methylated)} methylations, ligand {lig_smiles}"
        )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=Path("bench/config/targets.yaml"))
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    cfg = yaml.safe_load(args.config.read_text())
    (args.out / "sources").mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {}
    with httpx.Client(follow_redirects=True, timeout=60) as client:
        for system in cfg["systems"]:
            prepare(system, args.out, client, record)
    (args.out / "sources.json").write_text(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
