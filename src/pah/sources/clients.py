"""Layer 0 source clients. Each turns one public API into typed records with provenance."""

from __future__ import annotations

from typing import Any, ClassVar

import httpx
from pydantic import BaseModel, ConfigDict

from pah.core.models import Provenance
from pah.sources.cache import CachedHttp, Payload, ReleaseFn, SourceUnavailableError, Unavailable


class _Record(BaseModel):
    model_config = ConfigDict(frozen=True)
    provenance: Provenance


class UniProtEntry(_Record):
    accession: str
    sequence: str
    sequence_version: int
    entry_version: int
    md5: str | None = None


class PdbEntry(_Record):
    pdb_id: str
    revision: str
    initial_release_date: str
    revision_date: str | None
    resolution: float | None
    method: str | None


class PdbEntity(BaseModel):
    model_config = ConfigDict(frozen=True)
    entity_id: int
    molecule_type: str
    chains: tuple[str, ...]
    sequence: str | None
    length: int | None
    ligand_code: str | None = None


class PdbMolecules(_Record):
    pdb_id: str
    entities: tuple[PdbEntity, ...]


class SiftsSegment(BaseModel):
    model_config = ConfigDict(frozen=True)
    uniprot: str
    entity_id: int
    chain_id: str
    struct_asym_id: str
    unp_start: int
    unp_end: int
    seq_start: int
    seq_end: int
    author_start: int | None
    author_end: int | None
    identity: float | None


class SiftsMapping(_Record):
    pdb_id: str
    segments: tuple[SiftsSegment, ...]


class ChemComp(_Record):
    code: str
    inchikey: str | None
    inchi: str | None
    smiles: str | None
    smiles_stereo: str | None
    modified_date: str | None


class PubChemCompound(_Record):
    cid: int
    inchikey: str
    smiles: str | None


class AfdbEntry(_Record):
    entry_id: str
    accession: str
    version: int | None
    sequence_checksum: str | None
    cif_url: str | None
    uniprot_start: int | None
    uniprot_end: int | None


def _parse(source_id: str, accession: str, payload: Payload) -> Any:
    try:
        return payload.json()
    except ValueError as exc:
        raise SourceUnavailableError(source_id, accession, Unavailable.PARSE, str(exc)) from exc


def _header(name: str) -> ReleaseFn:
    def read(resp: httpx.Response) -> str | None:
        value = resp.headers.get(name)
        return str(value) if value is not None else None

    return read


class SourceClient:
    id: ClassVar[str]

    def __init__(self, http: CachedHttp) -> None:
        self.http = http


class UniProtClient(SourceClient):
    id = "uniprot"
    base = "https://rest.uniprot.org/uniprotkb"

    def entry(self, accession: str) -> UniProtEntry:
        payload = self.http.get(
            self.id,
            accession,
            f"{self.base}/{accession}.json",
            release=_header("x-uniprot-release"),
        )
        d = _parse(self.id, accession, payload)
        try:
            return UniProtEntry(
                accession=d["primaryAccession"],
                sequence=d["sequence"]["value"],
                sequence_version=int(d["entryAudit"]["sequenceVersion"]),
                entry_version=int(d["entryAudit"]["entryVersion"]),
                md5=d["sequence"].get("md5"),
                provenance=payload.provenance,
            )
        except (KeyError, TypeError) as exc:
            raise SourceUnavailableError(self.id, accession, Unavailable.PARSE, repr(exc)) from exc


class RcsbClient(SourceClient):
    id = "rcsb"
    data = "https://data.rcsb.org/rest/v1/core"
    files = "https://files.rcsb.org/download"

    def entry(self, pdb_id: str) -> PdbEntry:
        pid = pdb_id.upper()
        payload = self.http.get(self.id, pid, f"{self.data}/entry/{pid}")
        d = _parse(self.id, pid, payload)
        try:
            info = d["rcsb_accession_info"]
            revision = f"{info['major_revision']}.{info['minor_revision']}"
            resolution = (d.get("rcsb_entry_info") or {}).get("resolution_combined") or [None]
            method = (d.get("exptl") or [{}])[0].get("method")
            prov = payload.provenance.model_copy(update={"release": revision})
            return PdbEntry(
                pdb_id=pid,
                revision=revision,
                initial_release_date=info["initial_release_date"][:10],
                revision_date=(info.get("revision_date") or "")[:10] or None,
                resolution=resolution[0],
                method=method,
                provenance=prov,
            )
        except (KeyError, TypeError, IndexError) as exc:
            raise SourceUnavailableError(self.id, pid, Unavailable.PARSE, repr(exc)) from exc

    def mmcif(self, pdb_id: str) -> Payload:
        pid = pdb_id.upper()
        return self.http.get("rcsb_files", pid, f"{self.files}/{pid}.cif")

    def chemcomp(self, code: str) -> ChemComp:
        cc = code.upper()
        payload = self.http.get("ccd", cc, f"{self.data}/chemcomp/{cc}")
        d = _parse("ccd", cc, payload)
        desc = d.get("rcsb_chem_comp_descriptor") or {}
        modified = ((d.get("chem_comp") or {}).get("pdbx_modified_date") or "")[:10] or None
        return ChemComp(
            code=cc,
            inchikey=desc.get("InChIKey"),
            inchi=desc.get("InChI"),
            smiles=desc.get("SMILES"),
            smiles_stereo=desc.get("SMILES_stereo"),
            modified_date=modified,
            provenance=payload.provenance.model_copy(update={"release": modified}),
        )


class PdbeClient(SourceClient):
    id = "pdbe"
    api = "https://www.ebi.ac.uk/pdbe/api"

    def molecules(self, pdb_id: str) -> PdbMolecules:
        pid = pdb_id.lower()
        payload = self.http.get(self.id, pid, f"{self.api}/pdb/entry/molecules/{pid}")
        d = _parse(self.id, pid, payload)
        try:
            entities = tuple(
                PdbEntity(
                    entity_id=int(m["entity_id"]),
                    molecule_type=str(m.get("molecule_type")),
                    chains=tuple(m.get("in_chains") or ()),
                    sequence=m.get("sequence"),
                    length=m.get("length"),
                    ligand_code=(m.get("chem_comp_ids") or [None])[0]
                    if m.get("molecule_type") == "bound"
                    else None,
                )
                for m in d[pid]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SourceUnavailableError(self.id, pid, Unavailable.PARSE, repr(exc)) from exc
        return PdbMolecules(pdb_id=pid, entities=entities, provenance=payload.provenance)

    def sifts(self, pdb_id: str) -> SiftsMapping:
        pid = pdb_id.lower()
        payload = self.http.get("sifts", pid, f"{self.api}/mappings/uniprot/{pid}")
        d = _parse("sifts", pid, payload)
        segments: list[SiftsSegment] = []
        try:
            for acc, block in (d.get(pid, {}).get("UniProt") or {}).items():
                for m in block.get("mappings", []):
                    segments.append(
                        SiftsSegment(
                            uniprot=acc,
                            entity_id=int(m["entity_id"]),
                            chain_id=m["chain_id"],
                            struct_asym_id=m["struct_asym_id"],
                            unp_start=int(m["unp_start"]),
                            unp_end=int(m["unp_end"]),
                            seq_start=int(m["start"]["residue_number"]),
                            seq_end=int(m["end"]["residue_number"]),
                            author_start=m["start"].get("author_residue_number"),
                            author_end=m["end"].get("author_residue_number"),
                            identity=m.get("identity"),
                        )
                    )
        except (KeyError, TypeError, ValueError) as exc:
            raise SourceUnavailableError("sifts", pid, Unavailable.PARSE, repr(exc)) from exc
        return SiftsMapping(pdb_id=pid, segments=tuple(segments), provenance=payload.provenance)


class PubChemClient(SourceClient):
    id = "pubchem"
    base = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"

    def compound(self, cid: int) -> PubChemCompound:
        url = f"{self.base}/cid/{cid}/property/InChIKey,SMILES/JSON"
        payload = self.http.get(self.id, str(cid), url)
        d = _parse(self.id, str(cid), payload)
        try:
            row = d["PropertyTable"]["Properties"][0]
            return PubChemCompound(
                cid=int(row["CID"]),
                inchikey=row["InChIKey"],
                smiles=row.get("SMILES"),
                provenance=payload.provenance,
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise SourceUnavailableError(self.id, str(cid), Unavailable.PARSE, repr(exc)) from exc


class AlphaFoldDbClient(SourceClient):
    id = "alphafold_db"
    api = "https://alphafold.ebi.ac.uk/api/prediction"

    def entry(self, accession: str) -> AfdbEntry:
        payload = self.http.get(self.id, accession, f"{self.api}/{accession}")
        d = _parse(self.id, accession, payload)
        try:
            row = d[0]
            version = row.get("latestVersion")
            return AfdbEntry(
                entry_id=row["entryId"],
                accession=accession,
                version=version,
                sequence_checksum=row.get("sequenceChecksum"),
                cif_url=row.get("cifUrl"),
                uniprot_start=row.get("uniprotStart"),
                uniprot_end=row.get("uniprotEnd"),
                provenance=payload.provenance.model_copy(update={"release": f"v{version}"}),
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise SourceUnavailableError(self.id, accession, Unavailable.PARSE, repr(exc)) from exc


class Sources:
    """Facade handed to checks. Clients share one cached HTTP getter."""

    def __init__(self, http: CachedHttp) -> None:
        self.http = http
        self.uniprot = UniProtClient(http)
        self.rcsb = RcsbClient(http)
        self.pdbe = PdbeClient(http)
        self.pubchem = PubChemClient(http)
        self.alphafold_db = AlphaFoldDbClient(http)
