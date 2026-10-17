"""Synthetic executor output trees that follow the layouts in docs/EXECUTORS.md.

A three-residue peptide (chain A) with benzamidine (residue LIG, chain B) placed beside it. The
ligand coordinates come from a seeded RDKit ETKDG embedding; the peptide is written by hand.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

SMILES = "NC(=N)c1ccccc1"
LIGAND_ID = "BEN"
PLDDT = {1: 80.0, 2: 70.0, 3: 90.0}
LIGAND_PLDDT = 60.0

# (resname, atom name, element, x, y, z) for residues 1-3 of chain A.
_PEPTIDE: list[tuple[int, str, list[tuple[str, str, float, float, float]]]] = [
    (
        1,
        "ALA",
        [
            ("N", "N", 0.0, 6.0, 0.0),
            ("CA", "C", 1.46, 6.0, 0.0),
            ("C", "C", 2.0, 7.4, 0.0),
            ("O", "O", 1.3, 8.4, 0.0),
            ("CB", "C", 2.0, 5.2, 1.2),
        ],
    ),
    (
        2,
        "GLY",
        [
            ("N", "N", 3.3, 7.5, 0.0),
            ("CA", "C", 4.0, 8.8, 0.0),
            ("C", "C", 5.5, 8.6, 0.0),
            ("O", "O", 6.1, 7.5, 0.0),
        ],
    ),
    (
        3,
        "SER",
        [
            ("N", "N", 6.2, 9.7, 0.0),
            ("CA", "C", 7.6, 9.7, 0.0),
            ("C", "C", 8.2, 11.1, 0.0),
            ("O", "O", 7.5, 12.1, 0.0),
            ("CB", "C", 8.1, 8.9, 1.2),
            ("OG", "O", 9.5, 8.9, 1.2),
            ("OXT", "O", 9.4, 11.2, 0.0),
        ],
    ),
]


def ligand_mol(with_h: bool = False) -> Any:
    from rdkit import Chem
    from rdkit.Chem import AllChem

    mol = Chem.AddHs(Chem.MolFromSmiles(SMILES))
    params = AllChem.ETKDGv3()
    params.randomSeed = 42
    assert AllChem.EmbedMolecule(mol, params) == 0
    conf = mol.GetConformer()
    n = mol.GetNumAtoms()
    cx = sum(conf.GetAtomPosition(i).x for i in range(n)) / n
    cy = sum(conf.GetAtomPosition(i).y for i in range(n)) / n
    cz = sum(conf.GetAtomPosition(i).z for i in range(n)) / n
    for i in range(n):
        p = conf.GetAtomPosition(i)
        conf.SetAtomPosition(i, (p.x - cx + 4.0, p.y - cy, p.z - cz))
    return mol if with_h else Chem.RemoveHs(mol)


def inchikey(smiles: str = SMILES) -> str:
    from rdkit import Chem

    return str(Chem.MolToInchiKey(Chem.MolFromSmiles(smiles)))


def structure(with_ligand: bool = True) -> Any:
    import gemmi

    st = gemmi.Structure()
    st.name = "synthetic"
    model = gemmi.Model("1")
    chain = gemmi.Chain("A")
    for num, resname, atoms in _PEPTIDE:
        res = gemmi.Residue()
        res.name = resname
        res.seqid = gemmi.SeqId(num, " ")
        res.entity_type = gemmi.EntityType.Polymer
        for name, el, x, y, z in atoms:
            a = gemmi.Atom()
            a.name = name
            a.element = gemmi.Element(el)
            a.pos = gemmi.Position(x, y, z)
            a.occ = 1.0
            a.b_iso = PLDDT[num]
            res.add_atom(a)
        chain.add_residue(res)
    model.add_chain(chain)
    if with_ligand:
        lig = ligand_mol()
        conf = lig.GetConformer()
        lchain = gemmi.Chain("B")
        res = gemmi.Residue()
        res.name = "LIG"
        res.seqid = gemmi.SeqId(1, " ")
        res.het_flag = "H"
        res.entity_type = gemmi.EntityType.NonPolymer
        counts: dict[str, int] = {}
        for atom in lig.GetAtoms():
            el = atom.GetSymbol()
            counts[el] = counts.get(el, 0) + 1
            p = conf.GetAtomPosition(atom.GetIdx())
            a = gemmi.Atom()
            a.name = f"{el}{counts[el]}"
            a.element = gemmi.Element(el)
            a.pos = gemmi.Position(p.x, p.y, p.z)
            a.occ = 1.0
            a.b_iso = LIGAND_PLDDT
            res.add_atom(a)
        lchain.add_residue(res)
        model.add_chain(lchain)
    st.add_model(model)
    st.setup_entities()
    return st


def write_cif(path: Path, b_scale: float = 1.0) -> Path:
    st = structure()
    if b_scale != 1.0:
        for m in st:
            for ch in m:
                for res in ch:
                    for a in res:
                        a.b_iso *= b_scale
    path.parent.mkdir(parents=True, exist_ok=True)
    st.make_mmcif_document().write_file(str(path))
    return path


def write_pdb(path: Path, with_ligand: bool = True) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    structure(with_ligand).write_pdb(str(path))
    return path


def atom_count() -> int:
    return sum(len(a) for _, _, a in _PEPTIDE) + 9


def token_count() -> int:
    return len(_PEPTIDE) + 9


def write_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# Co-folding trees -------------------------------------------------------------------------------


def boltz_tree(out: Path, *, n_models: int = 2, pae: bool = True, affinity: bool = True) -> Path:
    import numpy as np

    d = out / "boltz_results_job" / "predictions" / "job"
    for k in range(n_models):
        write_cif(d / f"job_model_{k}.cif")
        write_json(
            d / f"confidence_job_model_{k}.json",
            {
                "confidence_score": 0.9 - 0.1 * k,
                "ptm": 0.8,
                "iptm": 0.7 - 0.1 * k,
                "ligand_iptm": 0.6,
                "protein_iptm": 0.0,
                "complex_plddt": 0.75,
                "complex_iplddt": 0.7,
                "complex_pde": 0.5,
                "complex_ipde": 0.9,
                "chains_ptm": {"0": 0.8, "1": 0.7},
                "pair_chains_iptm": {"0": {"0": 0.8, "1": 0.7}, "1": {"0": 0.7, "1": 0.7}},
            },
        )
        tokens = [PLDDT[1] / 100, PLDDT[2] / 100, PLDDT[3] / 100] + [LIGAND_PLDDT / 100] * 9
        np.savez(d / f"plddt_job_model_{k}.npz", plddt=np.array(tokens, dtype=np.float32))
        if pae:
            n = token_count()
            np.savez(d / f"pae_job_model_{k}.npz", pae=np.full((n, n), 2.5, dtype=np.float32))
    if affinity:
        write_json(
            d / "affinity_job.json",
            {"affinity_pred_value": -1.2, "affinity_probability_binary": 0.81},
        )
    return out


def protenix_tree(out: Path, seeds: tuple[int, ...] = (101, 102), n: int = 2) -> Path:
    for seed in seeds:
        d = out / "job" / f"seed_{seed}" / "predictions"
        for r in range(n):
            write_cif(d / f"job_sample_{r}.cif")
            write_json(
                d / f"job_summary_confidence_sample_{r}.json",
                {
                    "plddt": 77.5,
                    "ptm": 0.8,
                    "iptm": 0.7,
                    "ranking_score": 0.72 - 0.01 * r,
                    "has_clash": 0.0,
                    "chain_ptm": [0.8, 0.7],
                },
            )
    (out / "ERR").mkdir(parents=True, exist_ok=True)
    return out


def alphafold3_tree(out: Path, seeds: tuple[int, ...] = (1,), n: int = 2) -> Path:
    import gemmi

    job = out / "job_20261017_120000"
    rows = ["seed,sample,ranking_score"]
    scores = {(1, 0): 0.61, (1, 1): 0.83}
    for seed in seeds:
        for i in range(n):
            stem = f"job_seed-{seed}_sample-{i}"
            d = job / f"seed-{seed}_sample-{i}"
            cif = write_cif(d / f"{stem}_model.cif")
            st = gemmi.read_structure(str(cif))
            chain_ids: list[str] = []
            plddts: list[float] = []
            for ch in st[0]:
                for res in ch:
                    for a in res:
                        chain_ids.append(ch.name)
                        plddts.append(a.b_iso)
            score = scores.get((seed, i), 0.5)
            rows.append(f"{seed},{i},{score}")
            write_json(
                d / f"{stem}_summary_confidences.json",
                {
                    "ptm": 0.8,
                    "iptm": 0.75,
                    "ranking_score": score,
                    "fraction_disordered": 0.0,
                    "has_clash": 0.0,
                    "chain_ptm": [0.8, 0.7],
                    "chain_ids": ["A", "B"],
                },
            )
            t = token_count()
            write_json(
                d / f"{stem}_confidences.json",
                {
                    "atom_plddts": plddts,
                    "atom_chain_ids": chain_ids,
                    "pae": [[1.5] * t for _ in range(t)],
                    "token_chain_ids": ["A"] * 3 + ["B"] * 9,
                    "token_res_ids": [1, 2, 3] + [1] * 9,
                },
            )
    (job / "job_ranking_scores.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    return out


def chai_tree(out: Path, aggregate: tuple[float, ...] = (0.31, 0.92, 0.55)) -> Path:
    import numpy as np

    out.mkdir(parents=True, exist_ok=True)
    for i, agg in enumerate(aggregate):
        write_cif(out / f"pred.model_idx_{i}.cif")
        np.savez(
            out / f"scores.model_idx_{i}.npz",
            aggregate_score=np.array([agg]),
            ptm=np.array([0.8]),
            iptm=np.array([0.7]),
            per_chain_ptm=np.array([[0.8, 0.7]]),
            has_inter_chain_clashes=np.array([False]),
        )
    return out


def colabfold_tree(out: Path, pae: bool = True) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    tag = "alphafold2_multimer_v3_model_{m}_seed_000"
    for rank, m in ((1, 3), (2, 1)):
        t = tag.format(m=m)
        write_pdb(out / f"job_unrelaxed_rank_{rank:03d}_{t}.pdb", with_ligand=False)
        data: dict[str, Any] = {
            "plddt": [PLDDT[1], PLDDT[2], PLDDT[3]],
            "ptm": 0.7,
            "iptm": 0.65 - 0.1 * rank,
            "pdockq": {"A-B": 0.3},
        }
        if pae:
            data["max_pae"] = 31.75
            data["pae"] = [[1.0] * 3 for _ in range(3)]
        write_json(out / f"job_scores_rank_{rank:03d}_{t}.json", data)
    return out


# Docking trees ----------------------------------------------------------------------------------


def _shift_pdbqt(text: str, dx: float) -> str:
    lines = []
    for line in text.splitlines():
        if line.startswith(("ATOM", "HETATM")):
            x = float(line[30:38]) + dx
            line = f"{line[:30]}{x:8.3f}{line[38:]}"
        lines.append(line)
    return "\n".join(lines)


def ligand_pdbqt() -> str:
    from meeko import MoleculePreparation, PDBQTWriterLegacy

    setups = MoleculePreparation().prepare(ligand_mol(with_h=True))
    text, ok, err = PDBQTWriterLegacy.write_string(setups[0])
    assert ok, err
    return str(text)


def vina_out(path: Path, energies: tuple[float, ...] = (-6.5, -5.9)) -> Path:
    body = ligand_pdbqt().rstrip("\n")
    blocks = []
    for i, e in enumerate(energies):
        lb, ub = (0.0, 0.0) if i == 0 else (1.0, 1.732)
        blocks.append(
            "\n".join(
                [
                    f"MODEL {i + 1}",
                    f"REMARK VINA RESULT: {e:9.3f}{lb:11.3f}{ub:11.3f}",
                    "REMARK INTER + INTRA:          -7.000",
                    _shift_pdbqt(body, float(i)),
                    "ENDMDL",
                ]
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(blocks) + "\n", encoding="utf-8")
    return path


def receptor_pdbqt(path: Path) -> Path:
    """The peptide as a PDBQT receptor: PDB columns 1-66, charge and AutoDock type after."""
    types = {"N": "NA", "C": "C", "O": "OA"}
    lines = []
    serial = 1
    for num, resname, atoms in _PEPTIDE:
        for name, el, x, y, z in atoms:
            lines.append(
                f"ATOM  {serial:>5} {name:<4} {resname} A{num:>4}    {x:8.3f}{y:8.3f}{z:8.3f}"
                f"  1.00  0.00    +0.000 {types[el]:<2}"
            )
            serial += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([*lines, "TER", ""]), encoding="utf-8")
    return path


def gnina_sdf(path: Path, gz: bool = False) -> Path:
    from rdkit import Chem

    path.parent.mkdir(parents=True, exist_ok=True)
    blocks = []
    for i, (aff, cnn) in enumerate(((-7.1, 0.91), (-6.4, 0.55))):
        mol = ligand_mol()
        mol.SetProp("_Name", "ben")
        mol.SetProp("minimizedAffinity", f"{aff:.5f}")
        mol.SetProp("CNNscore", f"{cnn:.4f}")
        mol.SetProp("CNNaffinity", "5.2")
        mol.SetProp("CNN_VS", f"{cnn * 5.2:.4f}")
        mol.SetProp("minimizedRMSD", f"{0.5 * i:.3f}")
        blocks.append(
            Chem.MolToMolBlock(mol)
            + "".join(
                f">  <{p}>\n{mol.GetProp(p)}\n\n"
                for p in ("minimizedAffinity", "CNNscore", "CNNaffinity", "CNN_VS", "minimizedRMSD")
            )
            + "$$$$\n"
        )
    data = "".join(blocks).encode()
    if gz:
        path.write_bytes(gzip.compress(data))
    else:
        path.write_bytes(data)
    return path


def diffdock_tree(out: Path) -> Path:
    from rdkit import Chem

    d = out / "complex_0"
    d.mkdir(parents=True, exist_ok=True)
    for name in ("rank1.sdf", "rank1_confidence0.53.sdf", "rank2_confidence-1.27.sdf"):
        w = Chem.SDWriter(str(d / name))
        w.write(ligand_mol())
        w.close()
    return out


def haddock_tree(run: Path) -> Path:
    step = run / "1_rigidbody"
    step.mkdir(parents=True, exist_ok=True)
    pdb_one = write_pdb(step / "rigidbody_1.pdb", with_ligand=False)
    (step / "rigidbody_1.pdb.gz").write_bytes(gzip.compress(pdb_one.read_bytes()))
    pdb_one.unlink()
    write_pdb(step / "rigidbody_2.pdb", with_ligand=False)
    cap = run / "2_caprieval"
    cap.mkdir(parents=True, exist_ok=True)
    header = [
        "model",
        "md5",
        "caprieval_rank",
        "score",
        "irmsd",
        "fnat",
        "lrmsd",
        "ilrmsd",
        "dockq",
        "rmsd",
        "cluster_id",
        "cluster_ranking",
        "model-cluster_ranking",
        "total",
    ]
    rows = [
        [
            "../1_rigidbody/rigidbody_1.pdb",
            "-",
            "1",
            "-45.2",
            "1.10",
            "0.62",
            "3.2",
            "2.1",
            "0.71",
            "1.0",
            "-",
            "-",
            "-",
            "-120.5",
        ],
        [
            "../1_rigidbody/rigidbody_2.pdb",
            "-",
            "2",
            "-30.0",
            "-",
            "0.10",
            "9.9",
            "8.8",
            "0.12",
            "5.0",
            "-",
            "-",
            "-",
            "-80.1",
        ],
    ]
    text = "\n".join("\t".join(r) for r in [header, *rows]) + "\n"
    (cap / "capri_ss.tsv").write_text(text, encoding="utf-8")
    return run
