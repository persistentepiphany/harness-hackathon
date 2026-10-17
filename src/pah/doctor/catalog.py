"""Builds probes from the YAML registries. New probe kinds register a factory; no core edits."""

from __future__ import annotations

import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from pah.config import Profile, config_dir, load_yaml, repo_root
from pah.doctor.probes import (
    BinaryProbe,
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
        if prefix is None:
            return None
        path = prefix if prefix.is_absolute() else self.root / prefix
        return path / "bin"


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
    dirs = (ctx.conda_bin,) if ctx.conda_bin else ()
    exe = str(spec["executable"])
    return BinaryProbe(
        id=pid,
        category=cat,
        target=exe,
        executable=exe,
        args=tuple(str(a) for a in spec.get("args", [])),
        search_dirs=dirs,
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


def _source_probes(ctx: ProbeContext, base: Path) -> list[Probe]:
    data = load_yaml("sources.yaml", base)
    return [build_probe(s["id"], "sources", s["probe"], ctx) for s in data["sources"]]


def _tool_probes(ctx: ProbeContext, base: Path) -> list[Probe]:
    data = load_yaml("tools.yaml", base)
    return [build_probe(t["id"], "tools", t["probe"], ctx) for t in data["tools"]]


def _infra_probes(ctx: ProbeContext, base: Path) -> list[Probe]:
    data = load_yaml("tools.yaml", base)
    rows = [i for i in data.get("infrastructure", []) if ctx.profile.name in i.get("profiles", [])]
    return [build_probe(i["id"], "infrastructure", i["probe"], ctx) for i in rows]


def _skill_probes(ctx: ProbeContext, base: Path) -> list[Probe]:
    data = load_yaml("tools.yaml", base)
    probes: list[Probe] = []
    for skill in data.get("skills", []):
        probes.append(build_probe(f"{skill['id']}.remote", "skills", skill["probe"], ctx))
        probes.append(
            build_probe(
                f"{skill['id']}.local", "skills", {"kind": "file", "path": skill["path"]}, ctx
            )
        )
    return probes


def _executor_probes(ctx: ProbeContext, base: Path) -> list[Probe]:
    data = load_yaml("executors.yaml", base)
    probes = [
        build_probe(p["id"], "executors", p, ctx)
        for ex in data["executors"]
        for p in ex.get("probes", [])
    ]
    probes += [build_probe(r["id"], "executors", r, ctx) for r in data.get("runtime", [])]
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
    """Probes grouped by category, in the order the categories are requested."""
    base = base or config_dir()
    wanted = categories or list(ctx.profile.doctor.categories)
    unknown = [c for c in wanted if c not in _BUILDERS]
    if unknown:
        raise ValueError(f"unknown categories: {unknown}; expected {list(CATEGORIES)}")
    return {cat: _BUILDERS[cat](ctx, base) for cat in wanted}
