import hashlib
import io
import tarfile
import zipfile
from pathlib import Path

import httpx
import pytest

from pah.externals.download import (
    DownloadError,
    DownloadFailure,
    UnsafeArchiveError,
    download,
    safe_extract,
)


def _client(handler) -> httpx.Client:  # type: ignore[no-untyped-def]
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_download_atomic_with_checksum(tmp_path: Path) -> None:
    body = b"x" * 5000
    seen: list[tuple[int, int | None]] = []
    target = tmp_path / "d" / "f.bin"
    digest, size = download(
        _client(lambda r: httpx.Response(200, content=body)),
        "https://h/f.bin",
        target,
        sha256=hashlib.sha256(body).hexdigest(),
        progress=lambda d, t: seen.append((d, t)),
    )
    assert target.read_bytes() == body and size == 5000
    assert digest == hashlib.sha256(body).hexdigest()
    assert not list(tmp_path.rglob("*.part"))
    assert seen[-1][0] == 5000


def test_checksum_mismatch_leaves_nothing(tmp_path: Path) -> None:
    target = tmp_path / "f"
    with pytest.raises(DownloadError) as err:
        download(
            _client(lambda r: httpx.Response(200, content=b"a")), "u://x", target, sha256="0" * 64
        )
    assert err.value.failure is DownloadFailure.CHECKSUM
    assert not target.exists() and not list(tmp_path.iterdir())


def test_retries_network_errors_then_succeeds(tmp_path: Path) -> None:
    calls = {"n": 0}

    def flaky(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ReadError("reset", request=request)
        return httpx.Response(200, content=b"ok")

    sleeps: list[float] = []
    download(_client(flaky), "https://h/x", tmp_path / "x", sleep=sleeps.append)
    assert calls["n"] == 3 and sleeps == [2.0, 4.0]


def test_blocked_and_404_are_not_retried(tmp_path: Path) -> None:
    calls = {"n": 0}

    def deny(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ProxyError("403", request=request)

    with pytest.raises(DownloadError) as err:
        download(_client(deny), "https://h/x", tmp_path / "x", sleep=lambda s: None)
    assert err.value.failure is DownloadFailure.BLOCKED and calls["n"] == 1

    with pytest.raises(DownloadError) as err:
        download(
            _client(lambda r: httpx.Response(404)),
            "https://h/x",
            tmp_path / "y",
            sleep=lambda s: None,
        )
    assert err.value.failure is DownloadFailure.HTTP


def _tar(path: Path, members: dict[str, bytes], link: tuple[str, str] | None = None) -> None:
    with tarfile.open(path, "w:gz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        if link:
            info = tarfile.TarInfo(link[0])
            info.type = tarfile.SYMTYPE
            info.linkname = link[1]
            tar.addfile(info)


def test_safe_extract_tar_and_zip(tmp_path: Path) -> None:
    arc = tmp_path / "a.tar.gz"
    _tar(arc, {"pkg/bin/tool": b"#!/bin/sh\n"})
    safe_extract(arc, tmp_path / "out", "tar")
    assert (tmp_path / "out/pkg/bin/tool").is_file()

    z = tmp_path / "a.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("p/f.txt", "x")
    safe_extract(z, tmp_path / "zout", "zip")
    assert (tmp_path / "zout/p/f.txt").read_text() == "x"


@pytest.mark.parametrize("name", ["../evil", "/abs/evil"])
def test_safe_extract_rejects_traversal(tmp_path: Path, name: str) -> None:
    arc = tmp_path / "bad.tar.gz"
    _tar(arc, {name: b"x"})
    with pytest.raises(UnsafeArchiveError):
        safe_extract(arc, tmp_path / "out", "tar")


def test_safe_extract_rejects_escaping_symlink(tmp_path: Path) -> None:
    arc = tmp_path / "bad.tar.gz"
    _tar(arc, {}, link=("pkg/link", "../../etc/passwd"))
    with pytest.raises(UnsafeArchiveError):
        safe_extract(arc, tmp_path / "out", "tar")
