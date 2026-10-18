"""Uploads are stored by content and parsed lightly."""

import json
from pathlib import Path

import pytest

from pah.webui.uploads import MAX_BYTES, UploadError, kind_of, safe_name, store_upload
from tests.conftest import ROOT

FIXTURES = ROOT / "tests/fixtures/sources"
PDB = (
    "ATOM      1  N   ALA A   1      11.104   6.134  -6.504  1.00  0.00           N\n"
    "ATOM      2  CA  ALA A   1      11.639   6.071  -5.147  1.00  0.00           C\n"
    "ATOM      3  N   GLY B   1      12.000   7.000  -4.000  1.00  0.00           N\n"
    "END\n"
)


def test_kinds_and_names() -> None:
    assert [kind_of(n) for n in ("a.pdb", "b.CIF", "c.fasta", "d.sdf", "e.csv", "f.json")] == [
        "receptor", "receptor", "sequence", "ligand", "series", "manifest",
    ]  # fmt: skip
    assert kind_of("x.bin") == "file"
    assert safe_name("../../etc/passwd") == "passwd"
    assert safe_name("my file (1).pdb") == "my_file_1_.pdb"


def test_stored_once_by_sha(tmp_path: Path) -> None:
    a = store_upload(tmp_path, "x.fasta", b">a\nACDE\n")
    b = store_upload(tmp_path, "x.fasta", b">a\nACDE\n")
    assert a["sha256"] == b["sha256"] and a["path"] == b["path"]
    assert len(list(tmp_path.iterdir())) == 1
    assert (tmp_path / Path(a["path"]).name).read_bytes() == b">a\nACDE\n"


@pytest.mark.parametrize(
    ("name", "data", "detail"),
    [
        ("seqs.fasta", b">a\nMKV\nLL\n>b\nMK\n", "2 sequences · length 2\u20135"),
        ("model.pdb", PDB.encode(), "chains A,B · 2 residues · 3 atoms"),
        ("list.smi", b"CCO ethanol\nc1ccccc1\n# comment\n", "2 SMILES · 2 parsed by RDKit"),
        ("series.csv", b"name,smiles\na,CCO\nb,CCN\n", "2 rows · columns name, smiles"),
        (
            "m.json",
            json.dumps({"task": "ligand_pose", "proteins": []}).encode(),
            "task ligand_pose",
        ),
        ("cfg.yaml", b"a: 1\nb: 2\n", "object with 2 keys (a, b)"),
        ("aln.a3m", b">q\nACDE\n>h1\nAC-E\n", "2 sequences · query length 4"),
    ],
)
def test_parsed(tmp_path: Path, name: str, data: bytes, detail: str) -> None:
    pytest.importorskip("rdkit")
    pytest.importorskip("gemmi")
    row = store_upload(tmp_path, name, data)
    assert row["status"] == "parsed", row
    assert detail in row["detail"]
    assert row["size"] == len(data) and len(row["sha256"]) == 64


def test_fixture_structure_and_ligand(tmp_path: Path) -> None:
    pytest.importorskip("rdkit")
    pytest.importorskip("gemmi")
    cif = store_upload(tmp_path, "3PTB.cif", (FIXTURES / "3PTB.cif").read_bytes())
    assert cif["status"] == "parsed" and "chains" in cif["detail"] and cif["kind"] == "receptor"
    sdf = store_upload(tmp_path, "ben.sdf", (FIXTURES / "3PTB_BEN.sdf").read_bytes())
    assert sdf["status"] == "parsed" and sdf["detail"].startswith("1 molecule")


@pytest.mark.parametrize(
    ("name", "data", "message"),
    [
        ("bad.fasta", b"ACDE\n", "before the first"),
        ("bad.sdf", b"garbage\n$$$$\n", "0 of"),
        ("bad.json", b"{", "JSONDecodeError"),
        ("bad.json", b'{"task": 3}', "manifest does not validate"),
        ("x.bin", b"\x00\x01", "no parser for .bin"),
    ],
)
def test_errors_are_reported(tmp_path: Path, name: str, data: bytes, message: str) -> None:
    pytest.importorskip("rdkit")
    row = store_upload(tmp_path, name, data)
    assert row["status"] == "error" and message in row["detail"], row


def test_size_limit(tmp_path: Path) -> None:
    with pytest.raises(UploadError):
        store_upload(tmp_path, "big.csv", b"x" * (MAX_BYTES + 1))
