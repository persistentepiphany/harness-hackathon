"""Offline stand-in for the public APIs, serving recorded responses from tests/fixtures/sources."""

from __future__ import annotations

from pathlib import Path

import httpx

FIXTURES = Path(__file__).parent / "fixtures" / "sources"

ROUTES: dict[str, tuple[str, dict[str, str]]] = {
    "https://rest.uniprot.org/uniprotkb/P00760.json": (
        "uniprot_P00760.json",
        {"x-uniprot-release": "2026_03"},
    ),
    "https://data.rcsb.org/rest/v1/core/entry/3PTB": ("rcsb_entry_3PTB.json", {}),
    "https://www.ebi.ac.uk/pdbe/api/pdb/entry/molecules/3ptb": ("pdbe_molecules_3ptb.json", {}),
    "https://www.ebi.ac.uk/pdbe/api/mappings/uniprot/3ptb": ("sifts_3ptb.json", {}),
    "https://data.rcsb.org/rest/v1/core/chemcomp/BEN": ("chemcomp_BEN.json", {}),
    "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/2332/property/InChIKey,SMILES/JSON": (
        "pubchem_2332.json",
        {},
    ),
    "https://alphafold.ebi.ac.uk/api/prediction/P00760": ("afdb_P00760.json", {}),
    "https://files.rcsb.org/download/3PTB.cif": ("3PTB.cif", {}),
}


class FakeWeb:
    def __init__(self, overrides: dict[str, httpx.Response] | None = None) -> None:
        self.calls: list[str] = []
        self.overrides = overrides or {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.calls.append(url)
        if url in self.overrides:
            return self.overrides[url]
        if url not in ROUTES:
            return httpx.Response(404, text=f"no fixture for {url}")
        name, headers = ROUTES[url]
        return httpx.Response(200, content=(FIXTURES / name).read_bytes(), headers=headers)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))
