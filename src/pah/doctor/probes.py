"""Reachability and availability probes. Each probe answers one question about one target."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import ClassVar, Protocol
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict


class ProbeStatus(StrEnum):
    OK = "ok"
    BLOCKED = "blocked"
    UNREACHABLE = "unreachable"
    HTTP_ERROR = "http_error"
    MISSING = "missing"
    ERROR = "error"
    MANUAL = "manual"


class ProbeResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    category: str
    kind: str
    target: str
    status: ProbeStatus
    detail: str = ""
    latency_ms: float | None = None
    version: str | None = None


class Probe(Protocol):
    kind: ClassVar[str]
    id: str
    category: str
    target: str

    def run(self) -> ProbeResult: ...


Runner = Callable[[Sequence[str], float], subprocess.CompletedProcess[str]]


def run_command(argv: Sequence[str], timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(argv), capture_output=True, text=True, timeout=timeout, check=False)


_VERSION = re.compile(r"\d+\.\d+")


def _version_line(*texts: str, limit: int = 160) -> str | None:
    """First line that contains a dotted version number, else the first non-empty line."""
    lines = [ln.strip() for t in texts for ln in t.splitlines() if ln.strip()]
    for line in lines:
        if _VERSION.search(line):
            return line[:limit]
    return lines[0][:limit] if lines else None


def _first_line(text: str, limit: int = 160) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()[:limit]
    return ""


@dataclass
class _Base:
    kind: ClassVar[str] = "base"
    id: str
    category: str
    target: str

    def _result(
        self,
        status: ProbeStatus,
        detail: str = "",
        started: float | None = None,
        version: str | None = None,
    ) -> ProbeResult:
        latency = round((time.perf_counter() - started) * 1000, 1) if started else None
        return ProbeResult(
            id=self.id,
            category=self.category,
            kind=self.kind,
            target=self.target,
            status=status,
            detail=detail,
            latency_ms=latency,
            version=version,
        )


@dataclass
class HttpProbe(_Base):
    """GET of the first kilobyte. Separates proxy denial, network failure and HTTP errors."""

    client: httpx.Client
    accept: frozenset[int] = frozenset()
    kind: ClassVar[str] = "http"

    def run(self) -> ProbeResult:
        started = time.perf_counter()
        try:
            with self.client.stream("GET", self.target, headers={"Range": "bytes=0-1023"}) as resp:
                code = resp.status_code
                final = str(resp.url)
                body = "" if code < 400 else _body_snippet(resp)
        except httpx.ProxyError as exc:
            host = urlsplit(str(exc.request.url)).hostname if exc.request else None
            return self._result(ProbeStatus.BLOCKED, f"proxy denied {host}: {exc}", started)
        except httpx.TimeoutException:
            return self._result(ProbeStatus.UNREACHABLE, "timeout", started)
        except httpx.ConnectError as exc:
            return self._result(ProbeStatus.UNREACHABLE, f"connect failed: {exc}", started)
        except httpx.HTTPError as exc:
            return self._result(ProbeStatus.ERROR, f"{type(exc).__name__}: {exc}", started)
        redirected = f" via {urlsplit(final).hostname}" if final != self.target else ""
        if 200 <= code < 300 or code in self.accept:
            return self._result(ProbeStatus.OK, f"HTTP {code}{redirected}", started)
        snippet = f": {body}" if body else ""
        return self._result(ProbeStatus.HTTP_ERROR, f"HTTP {code}{redirected}{snippet}", started)


def _body_snippet(resp: httpx.Response, limit: int = 160) -> str:
    try:
        raw = next(resp.iter_bytes(), b"")
    except httpx.HTTPError:
        return ""
    return " ".join(raw[:limit].decode("utf-8", "replace").split())


@dataclass
class GitProbe(_Base):
    """`git ls-remote` of HEAD; the commit is reported as the version."""

    runner: Runner = run_command
    timeout: float = 60.0
    kind: ClassVar[str] = "git"

    def run(self) -> ProbeResult:
        started = time.perf_counter()
        try:
            proc = self.runner(["git", "ls-remote", self.target, "HEAD"], self.timeout)
        except FileNotFoundError:
            return self._result(ProbeStatus.MISSING, "git not installed", started)
        except subprocess.TimeoutExpired:
            return self._result(ProbeStatus.UNREACHABLE, "timeout", started)
        if proc.returncode == 0 and proc.stdout.strip():
            sha = proc.stdout.split()[0]
            return self._result(ProbeStatus.OK, "ls-remote HEAD", started, version=sha[:12])
        err = _first_line(proc.stderr)
        status = ProbeStatus.BLOCKED if "403" in err else ProbeStatus.UNREACHABLE
        return self._result(status, err or f"exit {proc.returncode}", started)


@dataclass
class PythonProbe(_Base):
    """Module importable in a given interpreter, with its distribution version."""

    module: str = ""
    dist: str | None = None
    python: str = "python"
    runner: Runner = run_command
    timeout: float = 120.0
    kind: ClassVar[str] = "python"

    def run(self) -> ProbeResult:
        started = time.perf_counter()
        code = (
            "import importlib, importlib.metadata as md, sys\n"
            f"m = importlib.import_module({self.module!r})\n"
            f"d = {self.dist!r}\n"
            "v = md.version(d) if d else getattr(m, '__version__', '')\n"
            "print(v)\n"
        )
        try:
            proc = self.runner([self.python, "-c", code], self.timeout)
        except FileNotFoundError:
            return self._result(
                ProbeStatus.MISSING, f"interpreter not found: {self.python}", started
            )
        except subprocess.TimeoutExpired:
            return self._result(ProbeStatus.ERROR, "import timed out", started)
        if proc.returncode == 0:
            version = _first_line(proc.stdout) or None
            return self._result(ProbeStatus.OK, "import ok", started, version=version)
        err = proc.stderr.strip().splitlines()
        last = err[-1][:200] if err else f"exit {proc.returncode}"
        status = ProbeStatus.MISSING if "ModuleNotFoundError" in last else ProbeStatus.ERROR
        return self._result(status, last, started)


@dataclass
class BinaryProbe(_Base):
    """Executable on PATH or in extra directories; runs it once to read a version line."""

    executable: str = ""
    args: tuple[str, ...] = ()
    search_dirs: tuple[Path, ...] = ()
    runner: Runner = run_command
    timeout: float = 30.0
    which: Callable[[str, str | None], str | None] = field(
        default=lambda name, path: shutil.which(name, path=path)
    )
    kind: ClassVar[str] = "binary"

    def run(self) -> ProbeResult:
        started = time.perf_counter()
        path = os.pathsep.join([*(str(d) for d in self.search_dirs), os.environ.get("PATH", "")])
        found = self.which(self.executable, path)
        if not found:
            return self._result(ProbeStatus.MISSING, f"{self.executable} not on PATH", started)
        try:
            proc = self.runner([found, *self.args], self.timeout)
        except subprocess.TimeoutExpired:
            return self._result(ProbeStatus.ERROR, f"{found} timed out", started)
        except OSError as exc:
            return self._result(ProbeStatus.ERROR, f"{found}: {exc}", started)
        version = _version_line(proc.stdout, proc.stderr)
        detail = f"{found} (exit {proc.returncode})"
        return self._result(ProbeStatus.OK, detail, started, version=version)


@dataclass
class EnvProbe(_Base):
    """Credentials present as environment variables or a config file."""

    variables: tuple[str, ...] = ()
    alt_file: str | None = None
    environ: dict[str, str] | None = None
    kind: ClassVar[str] = "env"

    def run(self) -> ProbeResult:
        env = os.environ if self.environ is None else self.environ
        missing = [v for v in self.variables if not env.get(v)]
        if not missing:
            return self._result(ProbeStatus.OK, "variables set")
        if self.alt_file and Path(self.alt_file).expanduser().is_file():
            return self._result(ProbeStatus.OK, f"{self.alt_file} present")
        alt = f" and no {self.alt_file}" if self.alt_file else ""
        return self._result(ProbeStatus.MISSING, f"unset: {', '.join(missing)}{alt}")


@dataclass
class FileProbe(_Base):
    """Local file present (for example an initialised skill submodule)."""

    kind: ClassVar[str] = "file"

    def run(self) -> ProbeResult:
        if Path(self.target).is_file():
            return self._result(ProbeStatus.OK, "present")
        return self._result(ProbeStatus.MISSING, "absent; run git submodule update --init")


@dataclass
class ManualProbe(_Base):
    """Access that cannot be tested automatically (licences, weights issued by request)."""

    note: str = ""
    env_var: str | None = None
    kind: ClassVar[str] = "manual"

    def run(self) -> ProbeResult:
        if self.env_var:
            value = os.environ.get(self.env_var)
            if value and Path(value).expanduser().exists():
                return self._result(ProbeStatus.OK, f"{self.env_var}={value}")
        return self._result(ProbeStatus.MANUAL, self.note)
