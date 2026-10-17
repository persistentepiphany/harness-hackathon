from pathlib import Path

import httpx
import pytest

from pah.sources import CachedHttp, ContentCache, Sources, SourceUnavailableError, Unavailable
from tests.fakeweb import FakeWeb


@pytest.fixture
def web() -> FakeWeb:
    return FakeWeb()


def _sources(web: FakeWeb, root: Path, **kw: bool) -> Sources:
    return Sources(CachedHttp(web.client(), ContentCache(root), **kw))


def test_uniprot_entry_with_release_and_checksum(web: FakeWeb, tmp_path: Path) -> None:
    entry = _sources(web, tmp_path).uniprot.entry("P00760")
    assert entry.accession == "P00760" and len(entry.sequence) == 246
    assert entry.sequence_version == 3
    prov = entry.provenance
    assert prov.release == "2026_03" and len(prov.sha256) == 64 and prov.size_bytes > 0
    assert prov.extra["cache"] == "miss"


def test_cache_hit_and_offline(web: FakeWeb, tmp_path: Path) -> None:
    _sources(web, tmp_path).uniprot.entry("P00760")
    calls = len(web.calls)
    again = _sources(web, tmp_path, offline=True).uniprot.entry("P00760")
    assert len(web.calls) == calls and again.provenance.extra["cache"] == "hit"
    with pytest.raises(SourceUnavailableError) as err:
        _sources(web, tmp_path, offline=True).uniprot.entry("P69905")
    assert err.value.reason is Unavailable.OFFLINE_MISS


def test_refresh_refetches(web: FakeWeb, tmp_path: Path) -> None:
    _sources(web, tmp_path).rcsb.entry("3ptb")
    _sources(web, tmp_path, refresh=True).rcsb.entry("3ptb")
    assert web.calls.count("https://data.rcsb.org/rest/v1/core/entry/3PTB") == 2


def test_corrupted_object_is_a_miss(web: FakeWeb, tmp_path: Path) -> None:
    entry = _sources(web, tmp_path).uniprot.entry("P00760")
    obj = tmp_path / "objects" / entry.provenance.sha256[:2] / entry.provenance.sha256
    obj.write_bytes(b"tampered")
    with pytest.raises(SourceUnavailableError):
        _sources(web, tmp_path, offline=True).uniprot.entry("P00760")


def test_rcsb_pdbe_sifts_ccd_pubchem_afdb(web: FakeWeb, tmp_path: Path) -> None:
    s = _sources(web, tmp_path)
    e = s.rcsb.entry("3ptb")
    assert (e.revision, e.resolution, e.method) == ("1.4", 1.7, "X-RAY DIFFRACTION")
    assert e.provenance.release == "1.4"
    mol = s.pdbe.molecules("3ptb")
    assert [x.ligand_code for x in mol.entities if x.molecule_type == "bound"] == ["CA", "BEN"]
    seg = s.pdbe.sifts("3ptb").segments[0]
    assert (seg.uniprot, seg.chain_id, seg.unp_start, seg.unp_end, seg.seq_start) == (
        "P00760",
        "A",
        24,
        246,
        1,
    )
    assert s.rcsb.chemcomp("ben").inchikey == "PXXJHWLDUBFPOL-UHFFFAOYSA-N"
    assert s.pubchem.compound(2332).inchikey == "PXXJHWLDUBFPOL-UHFFFAOYSA-N"
    af = s.alphafold_db.entry("P00760")
    assert af.version == 6 and af.provenance.release == "v6"
    assert s.rcsb.mmcif("3ptb").data.startswith(b"data_3PTB")


def test_failure_reasons(tmp_path: Path) -> None:
    def deny(request: httpx.Request) -> httpx.Response:
        raise httpx.ProxyError("403", request=request)

    blocked = Sources(
        CachedHttp(httpx.Client(transport=httpx.MockTransport(deny)), ContentCache(tmp_path))
    )
    with pytest.raises(SourceUnavailableError) as err:
        blocked.uniprot.entry("P00760")
    assert err.value.reason is Unavailable.BLOCKED

    web = FakeWeb(
        {"https://rest.uniprot.org/uniprotkb/P00760.json": httpx.Response(200, text="{bad")}
    )
    with pytest.raises(SourceUnavailableError) as err:
        _sources(web, tmp_path / "b").uniprot.entry("P00760")
    assert err.value.reason is Unavailable.PARSE

    with pytest.raises(SourceUnavailableError) as err:
        _sources(FakeWeb(), tmp_path / "c").uniprot.entry("Q00000")
    assert err.value.reason is Unavailable.NOT_FOUND
