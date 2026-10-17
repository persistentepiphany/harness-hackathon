"""Atomic, checksummed downloads and path-safe archive extraction."""

from __future__ import annotations

import hashlib
import tarfile
import time
import zipfile
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path, PurePosixPath

import httpx

ProgressCallback = Callable[[int, int | None], None]


class DownloadFailure(StrEnum):
    BLOCKED = "blocked"
    HTTP = "http"
    NETWORK = "network"
    CHECKSUM = "checksum"


class DownloadError(Exception):
    def __init__(self, failure: DownloadFailure, message: str) -> None:
        super().__init__(message)
        self.failure = failure


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def download(
    client: httpx.Client,
    url: str,
    target: Path,
    *,
    sha256: str | None = None,
    retries: int = 3,
    backoff_s: float = 2.0,
    progress: ProgressCallback | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[str, int]:
    """Download to `target` via a `.part` file. Returns (sha256, size). Never leaves partial files.

    Proxy denials and checksum mismatches are not retried; network and 5xx errors are.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part")
    last: DownloadError | None = None
    for attempt in range(1, retries + 1):
        try:
            digest, size = _stream(client, url, part, progress)
        except DownloadError as exc:
            part.unlink(missing_ok=True)
            last = exc
            if exc.failure in {DownloadFailure.BLOCKED, DownloadFailure.HTTP}:
                break
            if attempt < retries:
                sleep(backoff_s * 2 ** (attempt - 1))
            continue
        if sha256 and digest != sha256.lower():
            part.unlink(missing_ok=True)
            raise DownloadError(DownloadFailure.CHECKSUM, f"sha256 {digest} != expected {sha256}")
        part.replace(target)
        return digest, size
    assert last is not None
    raise last


def _stream(
    client: httpx.Client, url: str, part: Path, progress: ProgressCallback | None
) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    try:
        with client.stream("GET", url) as resp:
            if resp.status_code >= 500:
                raise DownloadError(DownloadFailure.NETWORK, f"HTTP {resp.status_code}")
            if resp.status_code >= 400:
                raise DownloadError(DownloadFailure.HTTP, f"HTTP {resp.status_code} for {url}")
            total = (
                int(resp.headers["content-length"]) if "content-length" in resp.headers else None
            )
            with part.open("wb") as fh:
                for chunk in resp.iter_bytes(1 << 20):
                    fh.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                    if progress:
                        progress(size, total)
    except httpx.ProxyError as exc:
        raise DownloadError(DownloadFailure.BLOCKED, f"proxy denied: {exc}") from exc
    except httpx.HTTPError as exc:
        raise DownloadError(DownloadFailure.NETWORK, f"{type(exc).__name__}: {exc}") from exc
    return digest.hexdigest(), size


class UnsafeArchiveError(Exception):
    pass


def _check_member(name: str) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise UnsafeArchiveError(f"unsafe path in archive: {name}")


def safe_extract(archive: Path, target: Path, kind: str) -> None:
    """Extract a tar or zip archive, rejecting absolute paths, `..` and links leaving `target`."""
    target.mkdir(parents=True, exist_ok=True)
    if kind == "tar":
        with tarfile.open(archive) as tar:
            members = tar.getmembers()
            for m in members:
                _check_member(m.name)
                if (m.issym() or m.islnk()) and m.linkname:
                    resolved = (target / m.name).parent / m.linkname
                    if not resolved.resolve().is_relative_to(target.resolve()):
                        raise UnsafeArchiveError(f"link escapes target: {m.name} -> {m.linkname}")
                if m.isdev():
                    raise UnsafeArchiveError(f"device file in archive: {m.name}")
            if hasattr(tarfile, "data_filter"):
                tar.extractall(target, members=members, filter="data")
            else:  # Python < 3.11.4; members were validated above
                tar.extractall(target, members=members)
    elif kind == "zip":
        with zipfile.ZipFile(archive) as zf:
            for name in zf.namelist():
                _check_member(name)
            zf.extractall(target)
    else:
        raise ValueError(f"unknown archive kind {kind!r}")
