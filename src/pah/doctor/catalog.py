"""Builds probes from the YAML registries. New probe kinds register a factory; no core edits."""

from __future__ import annotations

import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from pah.config import Profile, config_dir, load_yaml, repo_root, resolve_path
from pah.doctor.probes import (
    BinaryProbe,
    ConfigErrorProbe,
    EnvProbe,
    FileProbe,
    GitProbe,
    HttpProbe,
    ManualProbe,
    Probe,
    PythonProbe,
)

CATEGORIES = ("sources", "tools", "executors", "skills", "infrastructure")


@dataclass
class ProbeContext:
    """Shared resources handed to every probe factory."""

    client: httpx.Client
    profile: Profile
    python: str = sys.executable
    root: Path = field(default_factory=lambda: repo_root() or Path.cwd())

    @property
    def conda_bin(self) -> Path | None:
        prefix = self.profile.conda_prefix
        return resolve_path(prefix, self.root) / "bin" if prefix is not None else None

    @property
    def search_dirs(self) -> tuple[Path, ...]:
        """Fetched binaries (tools_dir/bin) first, then the conda prefix."""
        dirs = [resolve_path(self.profile.tools_dir, self.root) / "bin"]
        if self.conda_bin is not None:
            dirs.append(self.conda_bin)
        return tuple(dirs)


ProbeFactory = Callable[[str, str, Mapping[str, Any], ProbeContext], Probe]
_FACTORIES: dict[str, ProbeFactory] = {}


def register(kind: str) -> Callable[[ProbeFactory], ProbeFactory]:
    def deco(fn: ProbeFactory) -> ProbeFactory:
        _FACTORIES[kind] = fn
        return fn

    return deco


def build_probe(pid: str, category: str, spec: Mapping[str, Any], ctx: ProbeContext) -> Probe:
    kind = str(spec.get("kind"))
    try:
        factory = _FACTORIES[kind]
    except KeyError as exc:
        raise ValueError(f"{pid}: unknown probe kind {kind!r}") from exc
    return factory(pid, category, spec, ctx)


def safe_probe(pid: str, category: str, spec: Mapping[str, Any], ctx: ProbeContext) -> Probe:
    """Like build_probe, but a malformed entry becomes an error result instead of an exception."""
    try:
        return build_probe(pid, category, spec, ctx)
    except Exception as exc:
        return ConfigErrorProbe(id=pid, category=category, target=str(spec), error=str(exc))


@register("http")
def _http(pid: str, cat: str, spec: Mapping[str, Any], ctx: ProbeContext) -> Probe:
    accept = frozenset(int(c) for c in spec.get("accept", []))
    return HttpProbe(
        id=pid, category=cat, target=str(spec["url"]), client=ctx.client, accept=accept
    )


@register("git")
def _git(pid: str, cat: str, spec: Mapping[str, Any], ctx: ProbeContext) -> Probe:
    return GitProbe(id=pid, category=cat, target=str(spec["url"]))


@register("python")
def _python(pid: str, cat: str, spec: Mapping[str, Any], ctx: ProbeContext) -> Probe:
    module = str(spec["module"])
    return PythonProbe(
        id=pid,
        category=cat,
        target=module,
        module=module,
        dist=spec.get("dist"),
        python=ctx.python,
    )


@register("conda_python")
def _conda_python(pid: str, cat: str, spec: Mapping[str, Any], ctx: ProbeContext) -> Probe:
    module = str(spec["module"])
    conda_bin = ctx.conda_bin
    python = str(conda_bin / "python") if conda_bin else "python"
    return PythonProbe(id=pid, category=cat, target=module, module=module, python=python)


@register("binary")
def _binary(pid: str, cat: str, spec: Mapping[str, Any], ctx: ProbeContext) -> Probe:
    dirs = ctx.search_dirs
    exe = str(spec["executable"])
    return BinaryProbe(
        id=pid,
        category=cat,
        target=exe,
        executable=exe,
        args=tuple(str(a) for a in spec.get("args", [])),
        search_dirs=dirs,
        hint=str(spec.get("hint", "")),
        expect=spec.get("expect"),
    )


@register("env")
def _env(pid: str, cat: str, spec: Mapping[str, Any], ctx: ProbeContext) -> Probe:
    variables = tuple(str(v) for v in spec.get("variables", []))
    return EnvProbe(
        id=pid,
        category=cat,
        target=",".join(variables),
        variables=variables,
        alt_file=spec.get("alt_file"),
    )


@register("file")
def _file(pid: str, cat: str, spec: Mapping[str, Any], ctx: ProbeContext) -> Probe:
    path = Path(str(spec["path"]))
    return FileProbe(
        id=pid, category=cat, target=str(path if path.is_absolute() else ctx.root / path)
    )


@register("manual")
def _manual(pid: str, cat: str, spec: Mapping[str, Any], ctx: ProbeContext) -> Probe:
    detail = str(spec.get("detail", ""))
    env_var = next((w for w in detail.replace(";", " ").split() if w.startswith("PAH_")), None)
    return ManualProbe(id=pid, category=cat, target=pid, note=detail, env_var=env_var)


def _entries(data: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    rows = data.get(key) or []
    return [
        r if isinstance(r, Mapping) else {"id": f"{key}[{i}]", "_raw": r}
        for i, r in enumerate(rows)
    ]


def _entry_probe(
    entry: Mapping[str, Any],
    category: str,
    ctx: ProbeContext,
    suffix: str = "",
    spec_key: str = "probe",
) -> Probe:
    """Builds one probe from one registry row; a malformed row yields an error probe."""
    pid = f"{entry.get('id', '?')}{suffix}"
    spec = entry if spec_key == "" else entry.get(spec_key)
    if not isinstance(spec, Mapping):
        return ConfigErrorProbe(id=pid, category=category, target=str(entry), error="no probe spec")
    return safe_probe(pid, category, spec, ctx)


def _source_probes(ctx: ProbeContext, base: Path) -> list[Probe]:
    data = load_yaml("sources.yaml", base)
    return [_entry_probe(e, "sources", ctx) for e in _entries(data, "sources")]


def _tool_probes(ctx: ProbeContext, base: Path) -> list[Probe]:
    data = load_yaml("tools.yaml", base)
    return [_entry_probe(_with_install_hint(e), "tools", ctx) for e in _entries(data, "tools")]


def _with_install_hint(entry: Mapping[str, Any]) -> Mapping[str, Any]:
    """Adds `pah fetch --only <id>` to tools installed through configs/externals.yaml."""
    install = entry.get("install")
    probe = entry.get("probe")
    if not (isinstance(install, Mapping) and isinstance(probe, Mapping)):
        return entry
    if install.get("route") != "pah_fetch":
        return entry
    hint = f"install with `pah fetch --only {install.get('package', entry.get('id'))}`"
    return {**entry, "probe": {**probe, "hint": hint}}


def _infra_probes(ctx: ProbeContext, base: Path) -> list[Probe]:
    data = load_yaml("tools.yaml", base)
    rows = [
        e for e in _entries(data, "infrastructure") if ctx.profile.name in e.get("profiles", [])
    ]
    return [_entry_probe(e, "infrastructure", ctx) for e in rows]


def _skill_probes(ctx: ProbeContext, base: Path) -> list[Probe]:
    data = load_yaml("tools.yaml", base)
    probes: list[Probe] = []
    for skill in _entries(data, "skills"):
        probes.append(_entry_probe(skill, "skills", ctx, ".remote"))
        local = {"id": skill.get("id", "?"), "probe": {"kind": "file", "path": skill.get("path")}}
        probes.append(_entry_probe(local, "skills", ctx, ".local"))
    return probes


def _executor_probes(ctx: ProbeContext, base: Path) -> list[Probe]:
    data = load_yaml("executors.yaml", base)
    probes = [
        _entry_probe(p, "executors", ctx, spec_key="")
        for ex in _entries(data, "executors")
        for p in _entries(ex, "probes")
    ]
    probes += [_entry_probe(r, "executors", ctx, spec_key="") for r in _entries(data, "runtime")]
    return probes


_BUILDERS: dict[str, Callable[[ProbeContext, Path], list[Probe]]] = {
    "sources": _source_probes,
    "tools": _tool_probes,
    "executors": _executor_probes,
    "skills": _skill_probes,
    "infrastructure": _infra_probes,
}


def build_catalog(
    ctx: ProbeContext, categories: list[str] | None = None, base: Path | None = None
) -> dict[str, list[Probe]]:
    """Probes grouped by category. Unknown categories and unreadable registries become error
    probes, so a configuration mistake shows up in the report without stopping the run."""
    base = base or config_dir()
    wanted = categories or list(ctx.profile.doctor.categories)
    catalog: dict[str, list[Probe]] = {}
    for cat in wanted:
        builder = _BUILDERS.get(cat)
        if builder is None:
            error = f"unknown category; expected one of {list(CATEGORIES)}"
            catalog[cat] = [
                ConfigErrorProbe(id=f"{cat}.config", category=cat, target=cat, error=error)
            ]
            continue
        try:
            catalog[cat] = builder(ctx, base)
        except Exception as exc:
            catalog[cat] = [
                ConfigErrorProbe(
                    id=f"{cat}.config", category=cat, target=str(base), error=repr(exc)
                )
            ]
    return catalog
