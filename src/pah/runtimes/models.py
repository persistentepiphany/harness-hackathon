"""Typed view of configs/runtimes.yaml and configs/accel.yaml."""

from __future__ import annotations

import os
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


Command = tuple[str, ...]


class Policy(StrEnum):
    """Whether to use the optimisation kit for an executor that has one."""

    AUTO = "auto"
    KIT = "kit"
    STOCK = "stock"


class Route(StrEnum):
    """How a run is executed."""

    KIT = "kit"
    KIT_OFF = "kit_off"
    NATIVE = "native"


class ImageBuild(_Model):
    git: str
    ref: str
    dockerfile: str


class ImageRecipe(_Model):
    base: str
    steps: tuple[str, ...]


class NativeImage(_Model):
    pull: str | None = None
    workdir: str | None = None
    build: ImageBuild | None = None
    recipe: ImageRecipe | None = None
    tag: str | None = None


class Binary(_Model):
    url: str
    name: str
    sha256: str | None = None


class NativeRoute(_Model):
    """The stock tool from its own pinned install."""

    version: str
    python: str | None = None
    pip: tuple[str, ...] = ()
    pip_note: str | None = None
    image: NativeImage | None = None
    binary: Binary | None = None
    env: dict[str, str] = Field(default_factory=dict)
    fetch_weights: Command | None = None
    fetch_note: str | None = None
    weights_env_override: str | None = None
    host_probe: str | None = None
    command: Command
    outputs: dict[str, str] = Field(default_factory=dict)
    note: str | None = None

    @property
    def kind(self) -> Literal["pip", "binary", "image"]:
        if self.pip:
            return "pip"
        if self.binary is not None:
            return "binary"
        return "image"


class AccelSpec(_Model):
    """One optimisation kit and how to call it."""

    kit: str
    stock: str
    configs: tuple[str, ...]
    modes: tuple[str, ...]
    min_driver: int
    env: dict[str, str] = Field(default_factory=dict)
    command: Command
    check: Command | None = None
    install_weights: Command | None = None
    outputs_kit: dict[str, str] = Field(default_factory=dict)
    outputs_off: dict[str, str] = Field(default_factory=dict)
    note: str | None = None


class ExecutorRuntime(_Model):
    id: str
    tool: str
    gpu: bool
    weights_dir: str
    defaults: dict[str, str | int | float] = Field(default_factory=dict)
    native: NativeRoute | None = None
    native_note: str | None = None
    accel: AccelSpec | None = None
    accel_note: str | None = None
    verified: tuple[str, ...] = ()


class RuntimeProfile(_Model):
    launcher: Literal["host", "docker", "apptainer"]
    # How the host launcher decides a kit is usable: `import` checks that the kit package imports
    # in the kit environment; `checkout` trusts run.sh (inside a kit image) and leaves the rest
    # to the kit's own `run.sh check`.
    kit_probe: Literal["import", "checkout"] = "import"
    envs_root: str
    kits_root: str
    images_root: str
    weights_root: str

    def path(self, field: Literal["envs_root", "kits_root", "images_root", "weights_root"]) -> Path:
        """Absolute root directory, with environment variables and `~` expanded."""
        return Path(os.path.expandvars(getattr(self, field))).expanduser().resolve()


class KitDefaults(_Model):
    check: Command
    install_weights: Command
    dockerfile: str
    apptainer_def: str
    image_tag: str
    dir_in_image: str


class NativeImageDefaults(_Model):
    base: str
    uv_tarball: str


class RuntimeRegistry(_Model):
    version: int
    profiles: dict[str, RuntimeProfile]
    kit_defaults: KitDefaults
    native_image: NativeImageDefaults
    executors: tuple[ExecutorRuntime, ...]

    def get(self, executor_id: str) -> ExecutorRuntime:
        for rt in self.executors:
            if rt.id == executor_id:
                return rt
        known = ", ".join(rt.id for rt in self.executors)
        raise KeyError(f"unknown executor {executor_id!r}; known: {known}")

    def profile(self, name: str) -> RuntimeProfile:
        try:
            return self.profiles[name]
        except KeyError as exc:
            raise KeyError(f"no runtime profile {name!r} in runtimes.yaml") from exc


class NameRule(_Model):
    contains: str
    config: str


class CapabilityRule(_Model):
    min: float
    configs: tuple[str, ...]


class CardRules(_Model):
    by_name: tuple[NameRule, ...] = ()
    by_compute_capability: tuple[CapabilityRule, ...] = ()


class AccelConfig(_Model):
    version: int
    repo: str
    commit: str
    policy: Policy = Policy.AUTO
    mode: str = "fast"
    not_active_exit_code: int = 3
    min_compute_capability: float = 8.0
    cards: CardRules = Field(default_factory=CardRules)
