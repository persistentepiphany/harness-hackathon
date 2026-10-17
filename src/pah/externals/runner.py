"""Loads the externals registry, fetches each asset in isolation and records provenance."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from pah.config import load_yaml
from pah.core.events import EventBus
from pah.core.models import EventKind
from pah.externals.installers import INSTALLERS, InstallContext, Installer
from pah.externals.models import ExternalAsset, FetchResult, FetchStatus

LOCK_NAME = "externals.lock.json"


@dataclass(frozen=True)
class Registry:
    assets: list[ExternalAsset]
    errors: list[str]


def load_registry(base: Path | None = None) -> Registry:
    """Invalid entries are reported, not raised, so one bad entry does not block the rest."""
    try:
        data = load_yaml("externals.yaml", base)
    except (OSError, ValueError) as exc:
        return Registry([], [f"externals.yaml: {exc}"])
    assets: list[ExternalAsset] = []
    errors: list[str] = []
    seen: set[str] = set()
    for i, raw in enumerate(data.get("assets", [])):
        try:
            asset = ExternalAsset.model_validate(raw)
        except ValidationError as exc:
            ident = raw.get("id", f"#{i}") if isinstance(raw, dict) else f"#{i}"
            errors.append(
                f"{ident}: {exc.error_count()} validation errors: {exc.errors()[0]['msg']}"
            )
            continue
        if asset.id in seen:
            errors.append(f"{asset.id}: duplicate id")
            continue
        seen.add(asset.id)
        assets.append(asset)
    return Registry(assets, errors)


def select(
    assets: list[ExternalAsset], only: list[str] | None, include_all: bool
) -> tuple[list[ExternalAsset], list[str]]:
    if only:
        by_id = {a.id: a for a in assets}
        return [by_id[i] for i in only if i in by_id], [i for i in only if i not in by_id]
    return [a for a in assets if include_all or a.default], []


class Fetcher:
    def __init__(
        self,
        bus: EventBus,
        ctx: InstallContext,
        installers: dict[Any, Installer] | None = None,
    ) -> None:
        self._bus = bus
        self._ctx = ctx
        self._installers = installers or INSTALLERS

    def run(self, assets: list[ExternalAsset]) -> list[FetchResult]:
        self._bus.emit(
            EventKind.RUN_START,
            "fetch",
            f"{len(assets)} assets into {self._ctx.tools_dir}",
            assets=[a.id for a in assets],
        )
        results: list[FetchResult] = []
        for asset in assets:
            results.append(self._fallback_skip(asset, results) or self._one(asset))
        counts = dict(Counter(r.status.value for r in results))
        self._bus.emit(
            EventKind.RUN_END,
            "fetch",
            " ".join(f"{k}={v}" for k, v in sorted(counts.items())),
            counts=counts,
        )
        write_lock(self._ctx.tools_dir, results)
        return results

    def _fallback_skip(self, asset: ExternalAsset, done: list[FetchResult]) -> FetchResult | None:
        """A fallback asset is skipped when the asset it backs up is already usable."""
        if asset.fallback_for is None:
            return None
        primary = next((r for r in done if r.id == asset.fallback_for), None)
        if primary is None or not primary.usable:
            return None
        result = FetchResult(
            id=asset.id, status=FetchStatus.SKIPPED, detail=f"{asset.fallback_for} is usable"
        )
        self._bus.emit(EventKind.RESULT, asset.id, result.detail, status=result.status.value)
        return result

    def _one(self, asset: ExternalAsset) -> FetchResult:
        size = f" ({asset.size_hint})" if asset.size_hint else ""
        self._bus.emit(
            EventKind.STAGE_START, asset.id, f"{asset.kind.value}: {asset.description}{size}"
        )
        self._ctx.progress = _Progress(self._bus, asset.id)
        try:
            result = self._installers[asset.kind].install(asset, self._ctx)
        except Exception as exc:  # an installer bug must not stop the other assets
            result = FetchResult(
                id=asset.id, status=FetchStatus.FAILED, detail=f"{type(exc).__name__}: {exc}"
            )
        finally:
            self._ctx.progress = None
        self._bus.emit(
            EventKind.RESULT,
            asset.id,
            result.detail,
            status=result.status.value,
            result=result.model_dump(mode="json"),
        )
        return result


class _Progress:
    """Emits a progress event every 10 percent, or every 100 MB when the size is unknown."""

    def __init__(self, bus: EventBus, stage: str) -> None:
        self._bus = bus
        self._stage = stage
        self._next = 0.1
        self._next_bytes = 100 << 20

    def __call__(self, done: int, total: int | None) -> None:
        if total:
            if done / total >= self._next:
                pct = int(done / total * 100)
                self._bus.emit(
                    EventKind.PROGRESS, self._stage, f"{pct}% of {total} bytes", done=done
                )
                self._next += 0.1
        elif done >= self._next_bytes:
            self._bus.emit(EventKind.PROGRESS, self._stage, f"{done >> 20} MB", done=done)
            self._next_bytes += 100 << 20


def write_lock(tools_dir: Path, results: list[FetchResult]) -> Path:
    """Merges usable results into tools_dir/externals.lock.json (url, sha256, size, time)."""
    path = tools_dir / LOCK_NAME
    lock: dict[str, Any] = {}
    if path.is_file():
        try:
            lock = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            lock = {}
    for r in results:
        if r.status is FetchStatus.INSTALLED:
            lock[r.id] = r.model_dump(mode="json")
    tools_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(lock, indent=2, sort_keys=True))
    return path
