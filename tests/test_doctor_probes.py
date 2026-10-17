import subprocess
from pathlib import Path

import httpx
import pytest

from pah.doctor.probes import (
    BinaryProbe,
    EnvProbe,
    FileProbe,
    GitProbe,
    HttpProbe,
    ManualProbe,
    ProbeStatus,
    PythonProbe,
)
from tests.conftest import FakeRunner, completed


def _client(handler: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(transport=handler, follow_redirects=True)


@pytest.mark.parametrize(
    ("code", "accept", "status"),
    [
        (200, frozenset(), ProbeStatus.OK),
        (206, frozenset(), ProbeStatus.OK),
        (401, frozenset({401}), ProbeStatus.OK),
        (404, frozenset(), ProbeStatus.HTTP_ERROR),
    ],
)
def test_http_status_mapping(code: int, accept: frozenset[int], status: ProbeStatus) -> None:
    client = _client(httpx.MockTransport(lambda r: httpx.Response(code, text="nope")))
    result = HttpProbe(
        id="x", category="sources", target="https://h/x", client=client, accept=accept
    ).run()
    assert result.status is status
    assert f"HTTP {code}" in result.detail
    if status is ProbeStatus.HTTP_ERROR:
        assert "nope" in result.detail


def test_http_proxy_denial_is_blocked() -> None:
    def deny(request: httpx.Request) -> httpx.Response:
        raise httpx.ProxyError("403 Forbidden", request=request)

    result = HttpProbe(
        id="x",
        category="s",
        target="https://blocked.org/a",
        client=_client(httpx.MockTransport(deny)),
    ).run()
    assert result.status is ProbeStatus.BLOCKED
    assert "blocked.org" in result.detail


def test_http_connect_error_is_unreachable() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("dns", request=request)

    result = HttpProbe(
        id="x", category="s", target="https://h/", client=_client(httpx.MockTransport(fail))
    ).run()
    assert result.status is ProbeStatus.UNREACHABLE


def test_git_ok_reports_sha() -> None:
    runner = FakeRunner(completed(out="abcdef1234567890\tHEAD\n"))
    result = GitProbe(
        id="g", category="skills", target="https://github.com/a/b", runner=runner
    ).run()
    assert result.status is ProbeStatus.OK
    assert result.version == "abcdef123456"
    assert runner.calls[0][:3] == ["git", "ls-remote", "https://github.com/a/b"]


def test_git_403_is_blocked() -> None:
    runner = FakeRunner(
        completed(rc=128, err="fatal: unable to access: The requested URL returned error: 403")
    )
    assert (
        GitProbe(id="g", category="s", target="u", runner=runner).run().status
        is ProbeStatus.BLOCKED
    )


def test_git_timeout() -> None:
    runner = FakeRunner(subprocess.TimeoutExpired(cmd="git", timeout=1))
    assert (
        GitProbe(id="g", category="s", target="u", runner=runner).run().status
        is ProbeStatus.UNREACHABLE
    )


def test_python_probe_ok_and_missing() -> None:
    ok = PythonProbe(
        id="p", category="t", target="m", module="m", runner=FakeRunner(completed(out="1.2.3\n"))
    ).run()
    assert ok.status is ProbeStatus.OK and ok.version == "1.2.3"
    err = "Traceback...\nModuleNotFoundError: No module named 'm'"
    missing = PythonProbe(
        id="p", category="t", target="m", module="m", runner=FakeRunner(completed(rc=1, err=err))
    ).run()
    assert missing.status is ProbeStatus.MISSING


def test_python_probe_real_interpreter() -> None:
    import sys

    result = PythonProbe(
        id="p", category="t", target="json", module="json", python=sys.executable
    ).run()
    assert result.status is ProbeStatus.OK


def test_binary_probe_missing_and_found(tmp_path: Path) -> None:
    missing = BinaryProbe(
        id="b", category="t", target="nope", executable="nope", which=lambda n, p: None
    ).run()
    assert missing.status is ProbeStatus.MISSING
    found = BinaryProbe(
        id="b",
        category="t",
        target="tool",
        executable="tool",
        which=lambda n, p: "/opt/tool",
        runner=FakeRunner(completed(rc=1, err="tool 4.0\nusage")),
    ).run()
    assert found.status is ProbeStatus.OK and found.version == "tool 4.0"


def test_binary_probe_searches_extra_dirs() -> None:
    seen: list[str | None] = []

    def which(name: str, path: str | None) -> str | None:
        seen.append(path)
        return None

    BinaryProbe(
        id="b",
        category="t",
        target="x",
        executable="x",
        search_dirs=(Path("/extra/bin"),),
        which=which,
    ).run()
    assert seen[0] is not None and seen[0].startswith("/extra/bin")


def test_env_probe(tmp_path: Path) -> None:
    ok = EnvProbe(id="e", category="i", target="A", variables=("A",), environ={"A": "1"}).run()
    assert ok.status is ProbeStatus.OK
    missing = EnvProbe(id="e", category="i", target="A", variables=("A",), environ={}).run()
    assert missing.status is ProbeStatus.MISSING
    cfg = tmp_path / "cfg.toml"
    cfg.write_text("x")
    alt = EnvProbe(
        id="e", category="i", target="A", variables=("A",), environ={}, alt_file=str(cfg)
    ).run()
    assert alt.status is ProbeStatus.OK


def test_file_and_manual_probes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    f = tmp_path / "SKILL.md"
    assert FileProbe(id="f", category="s", target=str(f)).run().status is ProbeStatus.MISSING
    f.write_text("x")
    assert FileProbe(id="f", category="s", target=str(f)).run().status is ProbeStatus.OK
    manual = ManualProbe(id="m", category="e", target="m", note="by request", env_var="PAH_W")
    assert manual.run().status is ProbeStatus.MANUAL
    monkeypatch.setenv("PAH_W", str(tmp_path))
    assert manual.run().status is ProbeStatus.OK


def test_binary_version_prefers_dotted_number() -> None:
    result = BinaryProbe(
        id="b",
        category="t",
        target="apbs",
        executable="apbs",
        which=lambda n, p: "/x/apbs",
        runner=FakeRunner(completed(rc=13, out="-----\nAPBS 3.4.1\n")),
    ).run()
    assert result.version == "APBS 3.4.1"


def test_run_command_uses_temp_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from pah.doctor.probes import run_command

    monkeypatch.chdir(tmp_path)
    proc = run_command(["sh", "-c", "pwd; touch side.file"], 10)
    assert proc.stdout.strip() != str(tmp_path)
    assert not (tmp_path / "side.file").exists()
