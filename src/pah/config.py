"""Locating and loading configuration (sources, tools, executors, profiles)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

_PACKAGE_DIR = Path(__file__).resolve().parent


def repo_root() -> Path | None:
    """Repository root when running from a checkout, else None."""
    candidate = _PACKAGE_DIR.parents[1]
    return candidate if (candidate / "configs").is_dir() else None


def config_dir() -> Path:
    env = os.environ.get("PAH_CONFIG_DIR")
    if env:
        return Path(env).expanduser().resolve()
    root = repo_root()
    if root is not None:
        return root / "configs"
    return _PACKAGE_DIR / "_configs"


def load_yaml(relative: str | Path, base: Path | None = None) -> dict[str, Any]:
    path = (base or config_dir()) / relative
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a mapping at top level")
    return data


def _expand(value: str) -> str:
    return str(Path(os.path.expandvars(value)).expanduser())


class DoctorSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    categories: list[str] = Field(
        default_factory=lambda: ["sources", "tools", "executors", "skills", "infrastructure"]
    )


class Profile(BaseModel):
    """Deployment profile. Backend-specific blocks are kept as raw mappings."""

    model_config = ConfigDict(extra="allow")

    name: str
    backend: str
    cache_dir: Path
    runs_dir: Path
    offline: bool = False
    conda_prefix: Path | None = None
    tools_dir: Path = Path(".tools")
    doctor: DoctorSettings = Field(default_factory=DoctorSettings)


def load_profile(name_or_path: str) -> Profile:
    path = Path(name_or_path)
    if path.suffix not in {".yaml", ".yml"}:
        path = config_dir() / "profiles" / f"{name_or_path}.yaml"
    raw = load_yaml(path.name, path.parent)
    for key in ("cache_dir", "runs_dir", "conda_prefix", "tools_dir"):
        if isinstance(raw.get(key), str):
            raw[key] = _expand(raw[key])
    return Profile.model_validate(raw)


def resolve_path(path: Path, root: Path | None = None) -> Path:
    """Relative profile paths are taken from the repository root, else the working directory."""
    if path.is_absolute():
        return path
    return (root or repo_root() or Path.cwd()) / path


def available_profiles() -> list[str]:
    return sorted(p.stem for p in (config_dir() / "profiles").glob("*.yaml"))
