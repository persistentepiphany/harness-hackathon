import io
import json
import tarfile
from pathlib import Path

import httpx

from pah.core.events import EventBus, MemorySink
from pah.core.models import EventKind
from pah.externals import ExternalAsset, Fetcher, FetchStatus, InstallContext, load_registry, select
from pah.externals.installers import (
    COMPLETE_MARKER,
    CommandInstaller,
    GithubReleaseInstaller,
    HttpInstaller,
    ManualInstaller,
)
from pah.externals.models import AssetKind
from pah.externals.runner import write_lock
from tests.conftest import completed


def _targz(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _ctx(tmp_path: Path, handler, **kw) -> InstallContext:  # type: ignore[no-untyped-def]
    return InstallContext(
        client=httpx.Client(transport=httpx.MockTransport(handler)), tools_dir=tmp_path, **kw
    )


TOOL = ExternalAsset(
    id="tool",
    kind=AssetKind.HTTP,
    description="d",
    url="https://h/tool-linux.tar.gz",
    dest="opt/tool",
    extract="tar",
    links={"tool": "*/bin/tool"},
)


def test_http_archive_install_links_and_is_idempotent(tmp_path: Path) -> None:
    payload = _targz({"tool/bin/tool": b"#!/bin/sh\necho 1\n"})
    ctx = _ctx(tmp_path, lambda r: httpx.Response(200, content=payload))
    first = HttpInstaller().install(TOOL, ctx)
    assert first.status is FetchStatus.INSTALLED, first.detail
    link = tmp_path / "bin" / "tool"
    assert link.stat().st_mode & 0o111
    assert str((tmp_path / "opt/tool/tool/bin/tool").resolve()) in link.read_text()
    assert not (tmp_path / "downloads" / "tool-linux.tar.gz").exists()
    assert HttpInstaller().install(TOOL, ctx).status is FetchStatus.PRESENT


def test_http_missing_link_target_fails(tmp_path: Path) -> None:
    payload = _targz({"other/file": b"x"})
    result = HttpInstaller().install(
        TOOL, _ctx(tmp_path, lambda r: httpx.Response(200, content=payload))
    )
    assert result.status is FetchStatus.FAILED and "no file matches" in result.detail


def test_http_blocked(tmp_path: Path) -> None:
    def deny(request: httpx.Request) -> httpx.Response:
        raise httpx.ProxyError("403", request=request)

    assert HttpInstaller().install(TOOL, _ctx(tmp_path, deny)).status is FetchStatus.BLOCKED


def test_github_release_resolves_pattern(tmp_path: Path) -> None:
    payload = _targz({"p2rank_2.5/prank": b"#!/bin/sh\n"})

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.github.com":
            assets = [
                {
                    "name": "p2rank_2.5.tar.gz",
                    "browser_download_url": "https://dl/p2rank_2.5.tar.gz",
                },
                {"name": "source.zip", "browser_download_url": "https://dl/source.zip"},
            ]
            return httpx.Response(200, json={"tag_name": "2.5", "assets": assets})
        assert request.url.path == "/p2rank_2.5.tar.gz"
        return httpx.Response(200, content=payload)

    asset = ExternalAsset(
        id="p2rank",
        kind=AssetKind.GITHUB_RELEASE,
        description="d",
        repo="rdk/p2rank",
        asset_patterns=(r"^p2rank_.*\.tar\.gz$",),
        dest="opt/p2rank",
        extract="tar",
        links={"prank": "*/prank"},
    )
    result = GithubReleaseInstaller().install(asset, _ctx(tmp_path, handler))
    assert result.status is FetchStatus.INSTALLED, result.detail
    assert result.detail.startswith("2.5/p2rank_2.5.tar.gz")
    assert (tmp_path / "bin" / "prank").exists()


def test_github_release_no_match_and_403(tmp_path: Path) -> None:
    asset = ExternalAsset(
        id="g",
        kind=AssetKind.GITHUB_RELEASE,
        description="d",
        repo="a/b",
        asset_patterns=("^x$",),
        dest="g",
    )
    none = GithubReleaseInstaller().install(
        asset, _ctx(tmp_path, lambda r: httpx.Response(200, json={"tag_name": "v1", "assets": []}))
    )
    assert none.status is FetchStatus.FAILED and "no asset" in none.detail
    denied = GithubReleaseInstaller().install(
        asset, _ctx(tmp_path, lambda r: httpx.Response(403, text="nope"))
    )
    assert denied.status is FetchStatus.BLOCKED


CMD = ExternalAsset(
    id="c",
    kind=AssetKind.COMMAND,
    description="d",
    command=("gcloud", "cp"),
    requires=("gcloud",),
    dest="data/c",
)


def test_command_missing_prerequisite_skips(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, lambda r: httpx.Response(200), which=lambda n, p: None)
    result = CommandInstaller().install(CMD, ctx)
    assert result.status is FetchStatus.SKIPPED and "gcloud" in result.detail


def test_command_success_marks_complete_and_failure_does_not(tmp_path: Path) -> None:
    fail_ctx = _ctx(
        tmp_path,
        lambda r: httpx.Response(200),
        which=lambda n, p: "/x",
        runner=lambda a, c, t, e: completed(1, err="401 denied"),
    )
    failed = CommandInstaller().install(CMD, fail_ctx)
    assert failed.status is FetchStatus.FAILED and "401" in failed.detail
    assert not (tmp_path / "data/c" / COMPLETE_MARKER).exists()

    ok_ctx = _ctx(
        tmp_path,
        lambda r: httpx.Response(200),
        which=lambda n, p: "/x",
        runner=lambda a, c, t, e: completed(0),
    )
    assert CommandInstaller().install(CMD, ok_ctx).status is FetchStatus.INSTALLED
    assert CommandInstaller().install(CMD, ok_ctx).status is FetchStatus.PRESENT


def test_manual(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    asset = ExternalAsset(
        id="m", kind=AssetKind.MANUAL, description="d", env_var="PAH_X", instructions="ask"
    )
    ctx = _ctx(tmp_path, lambda r: httpx.Response(200))
    assert ManualInstaller().install(asset, ctx).status is FetchStatus.MANUAL
    monkeypatch.setenv("PAH_X", str(tmp_path))
    assert ManualInstaller().install(asset, ctx).status is FetchStatus.PRESENT


def test_fetcher_isolates_installer_crash(tmp_path: Path) -> None:
    class Boom:
        def install(self, asset, ctx):  # type: ignore[no-untyped-def]
            raise RuntimeError("bug")

    mem = MemorySink()
    assets = [
        ExternalAsset(id="a", kind=AssetKind.HTTP, description="d", url="u"),
        ExternalAsset(id="b", kind=AssetKind.MANUAL, description="d"),
    ]
    fetcher = Fetcher(
        EventBus("f", [mem]),
        _ctx(tmp_path, lambda r: httpx.Response(200)),
        installers={AssetKind.HTTP: Boom(), AssetKind.MANUAL: ManualInstaller()},
    )
    results = fetcher.run(assets)
    assert [r.status for r in results] == [FetchStatus.FAILED, FetchStatus.MANUAL]
    assert "RuntimeError" in results[0].detail
    assert [e.kind for e in mem.events].count(EventKind.RESULT) == 2
    assert (tmp_path / "externals.lock.json").is_file()


def test_registry_reports_bad_entries(tmp_path: Path) -> None:
    (tmp_path / "externals.yaml").write_text(
        "assets:\n"
        "  - {id: ok, kind: manual, description: d}\n"
        "  - {id: bad, kind: teleport, description: d}\n"
        "  - {id: ok, kind: manual, description: dup}\n"
        "  - not-a-mapping\n"
    )
    reg = load_registry(tmp_path)
    assert [a.id for a in reg.assets] == ["ok"]
    assert len(reg.errors) == 3


def test_registry_missing_file(tmp_path: Path) -> None:
    reg = load_registry(tmp_path)
    assert reg.assets == [] and "externals.yaml" in reg.errors[0]


def test_real_registry_loads_cleanly() -> None:
    reg = load_registry()
    assert reg.errors == []
    defaults, _ = select(reg.assets, None, False)
    assert {"p2rank", "mmseqs", "foldseek"} <= {a.id for a in defaults}
    assert "gnina" not in {a.id for a in defaults}
    chosen, unknown = select(reg.assets, ["gnina", "nope"], False)
    assert [a.id for a in chosen] == ["gnina"] and unknown == ["nope"]


def test_lock_merges_and_survives_corruption(tmp_path: Path) -> None:
    (tmp_path / "externals.lock.json").write_text("{not json")
    from pah.externals.models import FetchResult

    write_lock(tmp_path, [FetchResult(id="a", status=FetchStatus.INSTALLED, sha256="s")])
    write_lock(tmp_path, [FetchResult(id="b", status=FetchStatus.FAILED)])
    lock = json.loads((tmp_path / "externals.lock.json").read_text())
    assert list(lock) == ["a"] and lock["a"]["sha256"] == "s"


def test_command_links_after_success(tmp_path: Path) -> None:
    def build(argv, cwd, timeout, env):  # type: ignore[no-untyped-def]
        assert str(tmp_path / "bin") in env["PATH"]
        (cwd / "out").mkdir()
        (cwd / "out" / "prank").write_text("#!/bin/sh\n")
        return completed(0)

    asset = ExternalAsset(
        id="s",
        kind=AssetKind.COMMAND,
        description="d",
        command=("make",),
        dest="opt/s",
        links={"prank": "out/prank"},
    )
    ctx = _ctx(tmp_path, lambda r: httpx.Response(200), which=lambda n, p: "/x", runner=build)
    assert CommandInstaller().install(asset, ctx).status is FetchStatus.INSTALLED
    assert "out/prank" in (tmp_path / "bin" / "prank").read_text()


def test_fallback_runs_only_when_primary_fails(tmp_path: Path) -> None:
    class Fixed:
        def __init__(self, status: FetchStatus) -> None:
            self.status = status
            self.calls = 0

        def install(self, asset, ctx):  # type: ignore[no-untyped-def]
            self.calls += 1
            from pah.externals.models import FetchResult

            return FetchResult(id=asset.id, status=self.status)

    assets = [
        ExternalAsset(id="p", kind=AssetKind.HTTP, description="d", url="u"),
        ExternalAsset(id="f", kind=AssetKind.COMMAND, description="d", fallback_for="p"),
    ]
    for primary, expected_calls in ((FetchStatus.INSTALLED, 0), (FetchStatus.BLOCKED, 1)):
        fb = Fixed(FetchStatus.INSTALLED)
        fetcher = Fetcher(
            EventBus("f", []),
            _ctx(tmp_path, lambda r: httpx.Response(200)),
            installers={AssetKind.HTTP: Fixed(primary), AssetKind.COMMAND: fb},
        )
        results = fetcher.run(assets)
        assert fb.calls == expected_calls
        assert results[1].status is (
            FetchStatus.SKIPPED if expected_calls == 0 else FetchStatus.INSTALLED
        )
