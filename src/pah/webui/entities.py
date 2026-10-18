"""Entity lookups for the New-run side panel (`GET /ui/entities?q=`).

Names in the query are matched against `configs/catalog.yaml` the same way `lookupEntities()` in
the prototype matches them; raw UniProt accessions, PDB ids, `CID <n>` and `CCD <code>` are
accepted too. Every row shown is fetched through the `pah.sources` clients and the content cache.
Each group carries its measured latency and an ok or error status; one failed source does not
affect the others.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from pah.webui.catalog import Catalog, load_catalog

_A = re.ASCII
_ACCESSION = re.compile(
    r"\b([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})\b", _A
)
_PDB = re.compile(r"\b([1-9][A-Z0-9]{3})\b", _A)
_CID = re.compile(r"\bcid[:\s]*(\d{1,12})\b", _A | re.IGNORECASE)
_CCD = re.compile(r"\bccd[:\s]+([A-Za-z0-9]{1,5})\b", _A | re.IGNORECASE)
MAX_GROUPS = 24

Rows = list[list[str]]


@dataclass(frozen=True)
class Lookup:
    key: str
    kind: str  # protein | ligand
    title: str
    source: str  # display name
    query: str
    fetch: Callable[[], Rows]


def _err(exc: Exception) -> str:
    reason = getattr(exc, "reason", None)
    detail = getattr(exc, "detail", None)
    if reason is not None and detail is not None:
        return f"{getattr(reason, 'value', reason)}: {detail}"
    return f"{type(exc).__name__}: {exc}"


def _cache_row(prov: Any) -> list[str]:
    hit = prov.extra.get("cache") == "hit"
    return ["Retrieved", f"{'cache' if hit else 'network'} · sha256 {prov.sha256[:12]}"]


class _Fetchers:
    """Row builders per source. Each reads typed records from the clients and, for display
    fields the typed record does not carry, the same cached payload."""

    def __init__(self, sources: Any) -> None:
        self.s = sources

    def _raw(self, source_id: str, accession: str, url: str) -> Any:
        return self.s.http.get(source_id, accession, url).json()

    def uniprot(self, acc: str) -> Rows:
        entry = self.s.uniprot.entry(acc)
        d = self._raw("uniprot", acc, f"{self.s.uniprot.base}/{acc}.json")
        desc = d.get("proteinDescription") or {}
        name = ((desc.get("recommendedName") or {}).get("fullName") or {}).get("value")
        if not name:
            subs = desc.get("submissionNames") or [{}]
            name = (subs[0].get("fullName") or {}).get("value")
        rows: Rows = [[str(d.get("uniProtkbId") or acc), f"{len(entry.sequence):,} aa"]]
        if name:
            rows.append(["Protein", str(name)])
        organism = (d.get("organism") or {}).get("scientificName")
        if organism:
            rows.append(["Organism", str(organism)])
        rows.append(["Release", entry.provenance.release or "n/a"])
        rows.append(["Sequence version", str(entry.sequence_version)])
        rows.append(_cache_row(entry.provenance))
        return rows

    def rcsb(self, pdb: str, acc: str | None) -> Rows:
        e = self.s.rcsb.entry(pdb)
        d = self._raw("rcsb", e.pdb_id, f"{self.s.rcsb.data}/entry/{e.pdb_id}")
        title = (d.get("struct") or {}).get("title")
        ref = f"{e.pdb_id} · {e.resolution:.2f} Å" if e.resolution is not None else e.pdb_id
        rows: Rows = [["Reference", ref]]
        if title:
            rows.append(["Title", str(title)])
        if e.method:
            rows.append(["Method", e.method])
        rows.append(["Released", e.initial_release_date])
        rows.append(["Revision", e.revision])
        try:
            segs = self.s.pdbe.sifts(pdb).segments
        except Exception as exc:  # SIFTS is one row; the entry itself resolved
            rows.append(["SIFTS", f"unavailable: {_err(exc)}"])
        else:
            by_acc: dict[str, set[str]] = {}
            for s in segs:
                by_acc.setdefault(s.uniprot, set()).add(s.chain_id)
            if acc and acc in by_acc:
                rows.append(["SIFTS", f"{acc} → chains {', '.join(sorted(by_acc[acc]))}"])
            elif acc:
                maps = ", ".join(sorted(by_acc)) or "nothing"
                rows.append(["SIFTS", f"{acc} not mapped; {e.pdb_id} maps {maps}"])
            else:
                rows.extend(
                    ["SIFTS", f"{a} → chains {', '.join(sorted(c))}"]
                    for a, c in sorted(by_acc.items())
                )
        rows.append(_cache_row(e.provenance))
        return rows

    def afdb(self, acc: str) -> Rows:
        entry = self.s.alphafold_db.entry(acc)
        d = self._raw("alphafold_db", acc, f"{self.s.alphafold_db.api}/{acc}")
        row = d[0] if isinstance(d, list) and d else {}
        rows: Rows = [["Model", entry.entry_id]]
        if entry.version is not None:
            rows.append(["Version", f"v{entry.version}"])
        plddt = row.get("globalMetricValue")
        if isinstance(plddt, (int, float)):
            rows.append(["Mean pLDDT", f"{plddt:.1f}"])
        if entry.uniprot_start is not None and entry.uniprot_end is not None:
            rows.append(["UniProt range", f"{entry.uniprot_start}\u2013{entry.uniprot_end}"])
        rows.append(_cache_row(entry.provenance))
        return rows

    def pubchem(self, cid: int) -> Rows:
        c = self.s.pubchem.compound(cid)
        rows: Rows = []
        try:
            props_path = "property/MolecularFormula,MolecularWeight,Title/JSON"
            url = f"{self.s.pubchem.base}/cid/{cid}/{props_path}"
            props = self._raw("pubchem", str(cid), url)["PropertyTable"]["Properties"][0]
        except Exception as exc:  # formula and name are extra; identity rows still shown
            rows.append(["Formula", f"unavailable: {_err(exc)}"])
        else:
            if props.get("Title"):
                rows.append(["Name", str(props["Title"])])
            if props.get("MolecularFormula"):
                mw = props.get("MolecularWeight")
                rows.append(
                    ["Formula", f"{props['MolecularFormula']}" + (f" · {mw}" if mw else "")]
                )
        rows.append(["InChIKey", c.inchikey])
        if c.smiles:
            rows.append(["SMILES", c.smiles])
        rows.append(_cache_row(c.provenance))
        return rows

    def ccd(self, code: str) -> Rows:
        cc = self.s.rcsb.chemcomp(code)
        d = self._raw("ccd", cc.code, f"{self.s.rcsb.data}/chemcomp/{cc.code}")
        comp = d.get("chem_comp") or {}
        rows: Rows = []
        if comp.get("name"):
            rows.append(["Name", str(comp["name"])])
        if comp.get("formula"):
            fw = comp.get("formula_weight")
            rows.append(["Formula", f"{comp['formula']}" + (f" · {fw}" if fw else "")])
        if cc.inchikey:
            rows.append(["InChIKey", cc.inchikey])
        if comp.get("type"):
            rows.append(["Type", str(comp["type"])])
        if cc.modified_date:
            rows.append(["Modified", cc.modified_date])
        rows.append(_cache_row(cc.provenance))
        return rows


def plan_lookups(text: str, sources: Any, catalog: Catalog | None = None) -> list[Lookup]:
    """The lookups `text` asks for, catalog matches first, in prototype order."""
    cat = catalog or load_catalog()
    f = _Fetchers(sources)
    t = (text or "").lower()
    upper = (text or "").upper()
    out: list[Lookup] = []
    seen: set[str] = set()

    def add(lk: Lookup) -> None:
        if lk.key not in seen and len(out) < MAX_GROUPS:
            seen.add(lk.key)
            out.append(lk)

    def protein(acc: str, title: str, pdb: str | None) -> None:
        add(Lookup(f"uniprot:{acc}", "protein", title, "UniProt", acc, lambda: f.uniprot(acc)))
        if pdb:
            add(Lookup(f"rcsb:{pdb}", "protein", title, "RCSB PDB", pdb, lambda: f.rcsb(pdb, acc)))
        add(Lookup(f"afdb:{acc}", "protein", title, "AlphaFold DB", f"AF-{acc}-F1",
                   lambda: f.afdb(acc)))  # fmt: skip

    def entry_only(pid: str) -> None:
        add(Lookup(f"rcsb:{pid}", "protein", pid, "RCSB PDB", pid, lambda: f.rcsb(pid, None)))

    def ligand(title: str, cid: int | None, ccd: str | None) -> None:
        if cid is not None:
            add(Lookup(f"pubchem:{cid}", "ligand", title, "PubChem", f"CID {cid}",
                       lambda: f.pubchem(cid)))  # fmt: skip
        if ccd:
            add(Lookup(f"ccd:{ccd}", "ligand", title, "PDB CCD", ccd, lambda: f.ccd(ccd)))

    for p in cat.proteins:
        if any(n in t for n in p.names):
            protein(p.accession, p.label, p.pdb)
    for m in _ACCESSION.finditer(upper):
        acc = m.group(1)
        entry = cat.protein(acc)
        protein(acc, entry.label if entry else acc, entry.pdb if entry else None)
    accessions = {m.group(1) for m in _ACCESSION.finditer(upper)}
    for m in _PDB.finditer(upper):
        pid = m.group(1)
        if any(c.isalpha() for c in pid) and pid not in accessions:
            entry_only(pid)
    for lig in cat.ligands:
        if any(n in t for n in lig.names):
            ligand(lig.names[0], lig.pubchem_cid, lig.ccd)
    for m in _CID.finditer(text or ""):
        cid = int(m.group(1))
        ligand(f"CID {cid}", cid, None)
    for m in _CCD.finditer(text or ""):
        code = m.group(1).upper()
        ligand(code, None, code)
    return out


def _run(lk: Lookup) -> dict[str, Any]:
    started = time.perf_counter()
    group: dict[str, Any] = {
        "key": lk.key,
        "kind": lk.kind,
        "title": lk.title,
        "source": lk.source,
        "query": lk.query,
    }
    try:
        rows = lk.fetch()
    except Exception as exc:  # fail soft per source
        group.update(status="error", message=_err(exc), rows=[])
    else:
        group.update(status="ok", rows=rows)
    group["ms"] = round((time.perf_counter() - started) * 1000)
    return group


def resolve_entities(
    text: str, sources: Any, catalog: Catalog | None = None, workers: int = 6
) -> list[dict[str, Any]]:
    """EntityGroup objects for `text`, resolved in parallel, in plan order."""
    lookups = plan_lookups(text, sources, catalog)
    if not lookups:
        return []
    with ThreadPoolExecutor(max_workers=min(workers, len(lookups))) as pool:
        return list(pool.map(_run, lookups))
