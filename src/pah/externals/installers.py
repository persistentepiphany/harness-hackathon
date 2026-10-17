"""One installer per asset kind. Installers return a result; they do not raise."""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

import httpx

from pah.externals.download import (
    DownloadError,
    DownloadFailure,
    ProgressCallback,
    UnsafeArchiveError,
    download,
    safe_extract,
    sha256_file,
)
from pah.externals.models import AssetKind, ExternalAsset, Extract, FetchResult, FetchStatus

Runner = Callable[[Sequence[str], Path, float, dict[str, str]], subprocess.CompletedProcess[str]]

COMPLETE_MARKER = ".pah-complete"


def run_in(
    argv: Sequence[str], cwd: Path, timeout: float, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv), cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout, check=False
    )


@dataclass
class InstallContext:
    client: httpx.Client
    tools_dir: Path
    force: bool = False
    progress: ProgressCallback | None = None
    runner: Runner = run_in
    which: Callable[[str, str | None], str | None] = field(
        default=lambda name, path: shutil.which(name, path=path)
    )
    command_timeout_s: float = 6 * 3600
    extra_path: tuple[Path, ...] = ()

    @property
    def path(self) -> str:
        """PATH with tools_dir/bin and extra directories (conda prefix) in front."""
        dirs = [str(self.bin_dir), *(str(d) for d in self.extra_path)]
        return os.pathsep.join([*dirs, os.environ.get("PATH", "")])

    def find(self, name: str) -> str | None:
        return self.which(name, self.path)

    def env(self) -> dict[str, str]:
        return {**os.environ, "PATH": self.path}

    @property
    def bin_dir(self) -> Path:
        return self.tools_dir / "bin"

    @property
    def downloads_dir(self) -> Path:
        return self.tools_dir / "downloads"


class Installer(Protocol):
    def install(self, asset: ExternalAsset, ctx: InstallContext) -> FetchResult: ...


def _result(asset: ExternalAsset, status: FetchStatus, detail: str, **kw: object) -> FetchResult:
    return FetchResult(id=asset.id, status=status, detail=detail, **kw)


def _make_executable(path: Path) -> None:
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _link_targets(asset: ExternalAsset, ctx: InstallContext) -> dict[str, Path]:
    return {name: ctx.bin_dir / name for name in asset.links}


def _create_links(asset: ExternalAsset, ctx: InstallContext, dest: Path) -> list[str]:
    """Writes bin/<name> wrappers that exec the file matching each pattern under dest.

    Wrappers rather than symlinks, because launchers such as P2Rank's `prank` locate their
    jars relative to their own path. Returns the problems found.
    """
    problems: list[str] = []
    ctx.bin_dir.mkdir(parents=True, exist_ok=True)
    for name, pattern in asset.links.items():
        match = dest if pattern == "." else next(iter(sorted(dest.glob(pattern))), None)
        if match is None or not match.is_file():
            problems.append(f"no file matches {pattern!r} under {dest}")
            continue
        _make_executable(match)
        wrapper = ctx.bin_dir / name
        if wrapper.is_symlink() or wrapper.exists():
            wrapper.unlink()
        wrapper.write_text(f'#!/usr/bin/env bash\nexec "{match.resolve()}" "$@"\n')
        _make_executable(wrapper)
    return problems


def _present(asset: ExternalAsset, ctx: InstallContext, dest: Path) -> bool:
    if ctx.force:
        return False
    links = _link_targets(asset, ctx)
    if links:
        return all(p.exists() for p in links.values())
    if asset.extract is Extract.NONE:
        return dest.is_file() and (asset.sha256 is None or sha256_file(dest) == asset.sha256)
    return dest.is_dir() and any(dest.iterdir())


class HttpInstaller:
    def install(self, asset: ExternalAsset, ctx: InstallContext) -> FetchResult:
        if not asset.url:
            return _result(asset, FetchStatus.FAILED, "no url declared")
        return self.install_from(asset, asset.url, ctx)

    def install_from(self, asset: ExternalAsset, url: str, ctx: InstallContext) -> FetchResult:
        dest = ctx.tools_dir / asset.dest
        if _present(asset, ctx, dest):
            return _result(asset, FetchStatus.PRESENT, "already installed", path=str(dest), url=url)
        archive = asset.extract is not Extract.NONE
        target = ctx.downloads_dir / Path(urlsplit(url).path).name if archive else dest
        try:
            digest, size = download(
                ctx.client, url, target, sha256=asset.sha256, progress=ctx.progress
            )
        except DownloadError as exc:
            status = (
                FetchStatus.BLOCKED
                if exc.failure is DownloadFailure.BLOCKED
                else FetchStatus.FAILED
            )
            return _result(asset, status, f"{exc.failure.value}: {exc}", url=url)
        if archive:
            try:
                safe_extract(target, dest, asset.extract.value)
            except (UnsafeArchiveError, OSError, ValueError) as exc:
                return _result(asset, FetchStatus.FAILED, f"extract: {exc}", url=url)
            finally:
                target.unlink(missing_ok=True)
        elif asset.executable:
            _make_executable(dest)
        problems = _create_links(asset, ctx, dest)
        if problems:
            return _result(asset, FetchStatus.FAILED, "; ".join(problems), path=str(dest), url=url)
        return _result(
            asset,
            FetchStatus.INSTALLED,
            f"{size} bytes",
            path=str(dest),
            url=url,
            sha256=digest,
            size_bytes=size,
        )


class GithubReleaseInstaller:
    """Resolves the release asset through the GitHub API, then downloads it over HTTP."""

    api = "https://api.github.com"

    def __init__(self, http: HttpInstaller | None = None) -> None:
        self._http = http or HttpInstaller()

    def install(self, asset: ExternalAsset, ctx: InstallContext) -> FetchResult:
        if not asset.repo:
            return _result(asset, FetchStatus.FAILED, "no repo declared")
        dest = ctx.tools_dir / asset.dest
        if _present(asset, ctx, dest):
            return _result(asset, FetchStatus.PRESENT, "already installed", path=str(dest))
        path = "latest" if asset.tag == "latest" else f"tags/{asset.tag}"
        url = f"{self.api}/repos/{asset.repo}/releases/{path}"
        headers = {"Accept": "application/vnd.github+json"}
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            resp = ctx.client.get(url, headers=headers)
        except httpx.ProxyError as exc:
            return _result(asset, FetchStatus.BLOCKED, f"proxy denied: {exc}", url=url)
        except httpx.HTTPError as exc:
            return _result(asset, FetchStatus.FAILED, f"{type(exc).__name__}: {exc}", url=url)
        if resp.status_code != 200:
            body = " ".join(resp.text[:160].split())
            status = FetchStatus.BLOCKED if resp.status_code == 403 else FetchStatus.FAILED
            return _result(
                asset, status, f"release lookup HTTP {resp.status_code}: {body}", url=url
            )
        release = resp.json()
        names = {a["name"]: a["browser_download_url"] for a in release.get("assets", [])}
        for pattern in asset.asset_patterns:
            rx = re.compile(pattern)
            for name in sorted(names):
                if rx.search(name):
                    result = self._http.install_from(asset, names[name], ctx)
                    tag = release.get("tag_name", "?")
                    return result.model_copy(update={"detail": f"{tag}/{name}: {result.detail}"})
        return _result(
            asset,
            FetchStatus.FAILED,
            f"no asset in {release.get('tag_name', '?')} matches {list(asset.asset_patterns)}; "
            f"assets: {sorted(names)[:10]}",
            url=url,
        )


class CommandInstaller:
    def install(self, asset: ExternalAsset, ctx: InstallContext) -> FetchResult:
        missing = [r for r in asset.requires if ctx.find(r) is None]
        hint = f" {asset.instructions}" if asset.instructions else ""
        if missing:
            return _result(asset, FetchStatus.SKIPPED, f"missing {', '.join(missing)}.{hint}")
        dest = ctx.tools_dir / asset.dest
        marker = dest / COMPLETE_MARKER
        if not ctx.force and marker.is_file():
            return _result(asset, FetchStatus.PRESENT, "already completed", path=str(dest))
        dest.mkdir(parents=True, exist_ok=True)
        marker.unlink(missing_ok=True)
        try:
            proc = ctx.runner(asset.command, dest, ctx.command_timeout_s, ctx.env())
        except subprocess.TimeoutExpired:
            return _result(asset, FetchStatus.FAILED, "command timed out", path=str(dest))
        except OSError as exc:
            return _result(asset, FetchStatus.FAILED, f"{exc}", path=str(dest))
        if proc.returncode != 0:
            tail = " ".join((proc.stderr or proc.stdout).strip().splitlines()[-2:])[:240]
            return _result(
                asset, FetchStatus.FAILED, f"exit {proc.returncode}: {tail}.{hint}", path=str(dest)
            )
        problems = _create_links(asset, ctx, dest)
        if problems:
            return _result(asset, FetchStatus.FAILED, "; ".join(problems), path=str(dest))
        marker.write_text(" ".join(asset.command) + "\n")
        return _result(asset, FetchStatus.INSTALLED, "command completed", path=str(dest))


class ManualInstaller:
    def install(self, asset: ExternalAsset, ctx: InstallContext) -> FetchResult:
        if asset.env_var:
            value = os.environ.get(asset.env_var)
            if value and Path(value).expanduser().exists():
                return _result(asset, FetchStatus.PRESENT, f"{asset.env_var}={value}", path=value)
        return _result(asset, FetchStatus.MANUAL, asset.instructions or "manual install required")


INSTALLERS: dict[AssetKind, Installer] = {
    AssetKind.HTTP: HttpInstaller(),
    AssetKind.GITHUB_RELEASE: GithubReleaseInstaller(),
    AssetKind.COMMAND: CommandInstaller(),
    AssetKind.MANUAL: ManualInstaller(),
}
