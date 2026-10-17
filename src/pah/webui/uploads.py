"""Uploaded input files (`POST /ui/uploads`).

Each file is stored once under `runs/uploads/<sha256[:12]>-<name>`, its kind is taken from the
extension, and a light parse reports what it holds (records, chains, atoms, molecules). gemmi and
RDKit are used when installed; otherwise a text count is reported and says so.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

KINDS = {
    "pdb": "receptor", "cif": "receptor", "mmcif": "receptor",
    "fasta": "sequence", "fa": "sequence", "faa": "sequence",
    "a3m": "msa",
    "sdf": "ligand", "mol": "ligand", "mol2": "ligand", "smi": "ligand",
    "csv": "series",
    "json": "manifest", "yaml": "manifest", "yml": "manifest",
}  # fmt: skip
MAX_BYTES = 50 * 1024 * 1024
_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


class UploadError(ValueError):
    """A file that cannot be stored (for example larger than MAX_BYTES)."""


def safe_name(name: str) -> str:
    base = Path(name.replace("\\", "/")).name
    cleaned = _SAFE.sub("_", base).strip("._") or "upload"
    return cleaned[-120:]


def kind_of(name: str) -> str:
    return KINDS.get(Path(name).suffix.lower().lstrip("."), "file")


def _structure(path: Path, data: bytes) -> str:
    try:
        import gemmi
    except ImportError:
        atoms = sum(1 for line in data.splitlines() if line[:6] in (b"ATOM  ", b"HETATM"))
        if not atoms and b"_atom_site." not in data:
            raise ValueError("no ATOM, HETATM or _atom_site records") from None
        return f"{atoms:,} ATOM/HETATM lines (text count; gemmi not installed)"
    st = gemmi.read_structure(str(path))
    if len(st) == 0:
        raise ValueError("no models")
    model = st[0]
    chains = [ch.name for ch in model]
    residues = sum(len(ch) for ch in model)
    atoms = sum(len(r) for ch in model for r in ch)
    if atoms == 0:
        raise ValueError("no atoms")
    shown = ",".join(chains[:8]) + ("…" if len(chains) > 8 else "")
    models = f"{len(st)} model{'s' if len(st) != 1 else ''}"
    return f"{models} · chains {shown} · {residues:,} residues · {atoms:,} atoms"


def _fasta(path: Path, data: bytes) -> str:
    text = data.decode("utf-8", errors="replace")
    records: list[str] = []
    current: list[str] | None = None
    for line in text.splitlines():
        if line.startswith(">"):
            if current is not None:
                records.append("".join(current))
            current = []
        elif current is not None:
            current.append(line.strip())
        elif line.strip():
            raise ValueError("sequence before the first '>' header")
    if current is not None:
        records.append("".join(current))
    if not records:
        raise ValueError("no '>' records")
    empty = sum(1 for r in records if not r)
    if empty:
        raise ValueError(f"{empty} of {len(records)} records have no sequence")
    bad = sorted({c for r in records for c in r.upper() if not c.isalpha() and c not in "*-"})
    if bad:
        raise ValueError(f"characters outside sequence letters: {''.join(bad)}")
    lengths = [len(r) for r in records]
    return f"{len(records)} sequence{'s' if len(records) != 1 else ''} · length {min(lengths)}" + (
        f"\u2013{max(lengths)}" if max(lengths) != min(lengths) else ""
    )


def _a3m(path: Path, data: bytes) -> str:
    text = data.decode("utf-8", errors="replace")
    seqs = [line for line in text.splitlines() if line.startswith(">")]
    if not seqs:
        raise ValueError("no '>' records")
    lines = [ln for ln in text.splitlines() if ln and not ln.startswith(("#", ">"))]
    query = "".join(c for c in (lines[0] if lines else "") if not c.islower())
    return f"{len(seqs)} sequences · query length {len(query)}"


def _rdkit() -> Any:
    try:
        from rdkit import Chem, rdBase
    except ImportError:
        return None
    return Chem, rdBase


def _sdf(path: Path, data: bytes) -> str:
    blocks = [b for b in data.split(b"$$$$") if b.strip()]
    if not blocks:
        raise ValueError("no molecule blocks")
    rd = _rdkit()
    if rd is None:
        return f"{len(blocks)} molecule blocks (text count; RDKit not installed)"
    chem, rdbase = rd
    with rdbase.BlockLogs():
        mols = list(chem.SDMolSupplier(str(path), sanitize=True, removeHs=False))
    ok = sum(1 for m in mols if m is not None)
    if ok == 0:
        raise ValueError(f"0 of {len(mols)} molecules parse with RDKit")
    return f"{len(mols)} molecule{'s' if len(mols) != 1 else ''} · {ok} sanitised by RDKit"


def _mol(path: Path, data: bytes) -> str:
    rd = _rdkit()
    if rd is None:
        return "1 molecule block (RDKit not installed)"
    chem, rdbase = rd
    with rdbase.BlockLogs():
        mol = chem.MolFromMolBlock(data.decode("utf-8", errors="replace"), removeHs=False)
    if mol is None:
        raise ValueError("RDKit cannot parse the molecule")
    return f"1 molecule · {mol.GetNumAtoms()} atoms · sanitised by RDKit"


def _mol2(path: Path, data: bytes) -> str:
    text = data.decode("utf-8", errors="replace")
    parts = text.split("@<TRIPOS>MOLECULE")[1:]
    if not parts:
        raise ValueError("no @<TRIPOS>MOLECULE records")
    rd = _rdkit()
    if rd is None:
        return f"{len(parts)} molecule records (text count; RDKit not installed)"
    chem, rdbase = rd
    with rdbase.BlockLogs():
        ok = sum(
            1
            for p in parts
            if chem.MolFromMol2Block("@<TRIPOS>MOLECULE" + p, removeHs=False) is not None
        )
    if ok == 0:
        raise ValueError(f"0 of {len(parts)} molecules parse with RDKit")
    return f"{len(parts)} molecule{'s' if len(parts) != 1 else ''} · {ok} sanitised by RDKit"


def _smi(path: Path, data: bytes) -> str:
    rows = [
        line.split()[0]
        for line in data.decode("utf-8", errors="replace").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not rows:
        raise ValueError("no SMILES lines")
    rd = _rdkit()
    if rd is None:
        return f"{len(rows)} SMILES lines (RDKit not installed)"
    chem, rdbase = rd
    with rdbase.BlockLogs():
        ok = sum(1 for s in rows if chem.MolFromSmiles(s) is not None)
    if ok == 0:
        raise ValueError(f"0 of {len(rows)} SMILES parse with RDKit")
    return f"{len(rows)} SMILES · {ok} parsed by RDKit"


def _csv(path: Path, data: bytes) -> str:
    text = data.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        raise ValueError("empty table")
    header = [c.strip() for c in rows[0]]
    shown = ", ".join(header[:6]) + ("…" if len(header) > 6 else "")
    return f"{len(rows) - 1} rows · columns {shown}"


def _manifest_note(data: Any) -> str:
    if isinstance(data, dict) and "task" in data:
        from pydantic import ValidationError

        from pah.core.manifest import Manifest

        try:
            m = Manifest.model_validate({k: v for k, v in data.items() if k != "base_dir"})
        except ValidationError as exc:
            raise ValueError(f"manifest does not validate: {exc.error_count()} errors") from exc
        return f"manifest · task {m.task} · {len(m.proteins)} proteins · {len(m.ligands)} ligands"
    if isinstance(data, dict):
        keys = ", ".join(list(data)[:6])
        return f"object with {len(data)} keys ({keys})"
    if isinstance(data, list):
        return f"array of {len(data)} items"
    return f"scalar {type(data).__name__}"


def _json(path: Path, data: bytes) -> str:
    return _manifest_note(json.loads(data.decode("utf-8")))


def _yaml(path: Path, data: bytes) -> str:
    return _manifest_note(yaml.safe_load(data.decode("utf-8")))


PARSERS: dict[str, Callable[[Path, bytes], str]] = {
    "pdb": _structure, "cif": _structure, "mmcif": _structure,
    "fasta": _fasta, "fa": _fasta, "faa": _fasta,
    "a3m": _a3m,
    "sdf": _sdf, "mol": _mol, "mol2": _mol2, "smi": _smi,
    "csv": _csv,
    "json": _json, "yaml": _yaml, "yml": _yaml,
}  # fmt: skip


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        Path(tmp).replace(path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def store_upload(uploads_dir: Path, name: str, data: bytes) -> dict[str, Any]:
    """Stores one file (content-addressed) and parses it. Returns the UI upload row."""
    if len(data) > MAX_BYTES:
        raise UploadError(f"{name}: {len(data):,} bytes is over the {MAX_BYTES:,} byte limit")
    sha = hashlib.sha256(data).hexdigest()
    clean = safe_name(name)
    path = uploads_dir / f"{sha[:12]}-{clean}"
    if not path.is_file():
        _atomic_write(path, data)
    ext = Path(clean).suffix.lower().lstrip(".")
    row: dict[str, Any] = {
        "name": name,
        "size": len(data),
        "sha256": sha,
        "kind": kind_of(clean),
        "path": f"uploads/{path.name}",
    }
    parser = PARSERS.get(ext)
    if parser is None:
        row.update(status="error", detail=f"no parser for .{ext or '(none)'} files; stored only")
        return row
    try:
        detail = parser(path, data)
    except Exception as exc:  # any parse failure is reported on the row
        row.update(status="error", detail=f"{type(exc).__name__}: {exc}")
    else:
        row.update(status="parsed", detail=detail)
    return row
