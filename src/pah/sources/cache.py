"""Content-addressed cache and the cached HTTP getter every source client uses.

Layout under the cache root:
    objects/<sha[:2]>/<sha256>          payload bytes
    refs/<source_id>/<key_sha256>.json  request key -> sha256 + provenance

A run in offline mode never touches the network: a cache miss raises SourceUnavailableError,
which checks turn into a stop finding. There is no silent fallback to a fresh fetch.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import httpx

from pah.core.models import Provenance


class Unavailable(StrEnum):
    OFFLINE_MISS = "offline_miss"
    BLOCKED = "blocked"
    NETWORK = "network"
    HTTP = "http"
    NOT_FOUND = "not_found"
    PARSE = "parse"


class SourceUnavailableError(Exception):
    def __init__(self, source_id: str, accession: str, reason: Unavailable, detail: str) -> None:
        super().__init__(f"{source_id}:{accession}: {reason.value}: {detail}")
        self.source_id = source_id
        self.accession = accession
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class Payload:
    data: bytes
    provenance: Provenance

    def text(self) -> str:
        return self.data.decode("utf-8")

    def json(self) -> Any:
        return json.loads(self.data)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


class ContentCache:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _object(self, sha: str) -> Path:
        return self.root / "objects" / sha[:2] / sha

    def _ref(self, source_id: str, key: str) -> Path:
        return self.root / "refs" / source_id / f"{_sha256(key.encode())}.json"

    def put(self, source_id: str, key: str, data: bytes, provenance: Provenance) -> Provenance:
        sha = _sha256(data)
        obj = self._object(sha)
        if not obj.is_file():
            _atomic_write(obj, data)
        prov = provenance.model_copy(update={"sha256": sha, "size_bytes": len(data)})
        ref = {"key": key, "sha256": sha, "provenance": prov.model_dump(mode="json")}
        _atomic_write(self._ref(source_id, key), json.dumps(ref, indent=1).encode())
        return prov

    def get(self, source_id: str, key: str) -> Payload | None:
        """Returns the cached payload, or None on a miss or a failed integrity check."""
        ref_path = self._ref(source_id, key)
        if not ref_path.is_file():
            return None
        try:
            ref = json.loads(ref_path.read_text())
            data = self._object(ref["sha256"]).read_bytes()
        except (OSError, ValueError, KeyError):
            return None
        if _sha256(data) != ref["sha256"]:
            ref_path.unlink(missing_ok=True)
            return None
        prov = Provenance.model_validate(ref["provenance"])
        return Payload(data, prov.model_copy(update={"extra": {**prov.extra, "cache": "hit"}}))


ReleaseFn = Callable[[httpx.Response], str | None]


class CachedHttp:
    """GET through the content cache. Every payload comes back with its provenance."""

    def __init__(
        self,
        client: httpx.Client,
        cache: ContentCache,
        *,
        offline: bool = False,
        refresh: bool = False,
    ) -> None:
        self.client = client
        self.cache = cache
        self.offline = offline
        self.refresh = refresh

    def get(
        self,
        source_id: str,
        accession: str,
        url: str,
        *,
        release: ReleaseFn | None = None,
        params: dict[str, str] | None = None,
    ) -> Payload:
        key = url if not params else f"{url}?{sorted(params.items())}"
        if not self.refresh:
            cached = self.cache.get(source_id, key)
            if cached is not None:
                return cached
        if self.offline:
            raise SourceUnavailableError(
                source_id, accession, Unavailable.OFFLINE_MISS, "not in cache"
            )
        try:
            resp = self.client.get(url, params=params)
        except httpx.ProxyError as exc:
            raise SourceUnavailableError(
                source_id, accession, Unavailable.BLOCKED, str(exc)
            ) from exc
        except httpx.HTTPError as exc:
            raise SourceUnavailableError(
                source_id, accession, Unavailable.NETWORK, f"{type(exc).__name__}: {exc}"
            ) from exc
        if resp.status_code == 404:
            raise SourceUnavailableError(
                source_id, accession, Unavailable.NOT_FOUND, f"HTTP 404 {url}"
            )
        if resp.status_code >= 400:
            raise SourceUnavailableError(
                source_id, accession, Unavailable.HTTP, f"HTTP {resp.status_code} {url}"
            )
        prov = Provenance(
            source_id=source_id,
            accession=accession,
            url=str(resp.url),
            sha256="",
            size_bytes=0,
            release=release(resp) if release else None,
            extra={"cache": "miss"},
        )
        return Payload(resp.content, self.cache.put(source_id, key, resp.content, prov))
