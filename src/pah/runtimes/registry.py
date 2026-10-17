"""Loading the runtime and kit registries, and filling command templates."""

from __future__ import annotations

import string
from collections.abc import Iterable, Mapping
from pathlib import Path

from pah.config import config_dir, load_yaml
from pah.runtimes.models import AccelConfig, Command, RuntimeRegistry


def load_runtimes(base: Path | None = None) -> RuntimeRegistry:
    return RuntimeRegistry.model_validate(load_yaml("runtimes.yaml", base or config_dir()))


def load_accel(base: Path | None = None) -> AccelConfig:
    return AccelConfig.model_validate(load_yaml("accel.yaml", base or config_dir()))


class MissingParameterError(KeyError):
    """A template placeholder has no value."""


_FORMATTER = string.Formatter()


def placeholders(template: Iterable[str]) -> set[str]:
    """Placeholder names used in a template."""
    return {field for arg in template for _, field, _, _ in _FORMATTER.parse(arg) if field}


def fill(template: Iterable[str], values: Mapping[str, object]) -> Command:
    """Substitute `{name}` placeholders. A missing value raises MissingParameterError."""
    missing = sorted(placeholders(template) - set(values))
    if missing:
        raise MissingParameterError(f"missing parameters: {', '.join(missing)}")
    return tuple(arg.format_map(values) for arg in template)


def fill_env(env: Mapping[str, str], values: Mapping[str, object]) -> dict[str, str]:
    return {k: fill([v], values)[0] for k, v in env.items()}
