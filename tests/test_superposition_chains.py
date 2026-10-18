"""Superposition pairs one target chain at a time.

A homodimeric reference used to align the mobile chain across both copies, which fits neither and
silently corrupted every value measured in the reference frame (pose RMSD, interaction mapping).
"""

from __future__ import annotations

from typing import Any

import pytest

from pah.checks import outputs

gemmi = pytest.importorskip("gemmi")

SEQ = "ACDEFGHIKLMNPQRSTVWYACDEFGHIKLMNPQRSTVWY"


def _chain(name: str, offset: tuple[float, float, float]) -> Any:
    """A CA-only chain of SEQ, rigidly shifted by `offset`."""
    ch = gemmi.Chain(name)
    for i, code in enumerate(SEQ):
        res = gemmi.Residue()
        res.name = _three(code)
        res.seqid = gemmi.SeqId(i + 1, " ")
        atom = gemmi.Atom()
        atom.name = "CA"
        atom.element = gemmi.Element("C")
        # A bent trace, so the fit is determined rather than degenerate.
        atom.pos = gemmi.Position(
            i * 3.8 + offset[0], (i % 7) * 1.1 + offset[1], (i % 3) * 0.9 + offset[2]
        )
        res.add_atom(atom)
        ch.add_residue(res)
    return ch


def _three(code: str) -> str:
    table = {
        "A": "ALA", "C": "CYS", "D": "ASP", "E": "GLU", "F": "PHE", "G": "GLY", "H": "HIS",
        "I": "ILE", "K": "LYS", "L": "LEU", "M": "MET", "N": "ASN", "P": "PRO", "Q": "GLN",
        "R": "ARG", "S": "SER", "T": "THR", "V": "VAL", "W": "TRP", "Y": "TYR",
    }  # fmt: skip
    return table[code]


def _structure(chains: list[Any]) -> Any:
    st = gemmi.Structure()
    st.add_model(gemmi.Model("1"))
    for ch in chains:
        st[0].add_chain(ch)
    st.setup_entities()
    return st


def test_homodimer_target_fits_one_chain() -> None:
    mobile = _structure([_chain("A", (0.0, 0.0, 0.0))])
    # Two copies of the same sequence, far apart: aligning across both fits neither.
    target = _structure([_chain("A", (0.0, 0.0, 0.0)), _chain("B", (0.0, 60.0, 0.0))])
    sup = outputs.superposition(mobile, target)
    assert sup.pairs == len(SEQ)
    assert sup.rmsd < 0.1
    # Every paired residue comes from a single target chain.
    assert len({chain for chain, _, _ in sup.residue_map.values()}) == 1


def test_single_chain_target_is_unchanged() -> None:
    mobile = _structure([_chain("A", (0.0, 0.0, 0.0))])
    target = _structure([_chain("X", (5.0, -2.0, 1.0))])
    sup = outputs.superposition(mobile, target)
    assert sup.pairs == len(SEQ)
    assert sup.rmsd < 0.1
