"""Settings for the UI routes, taken from a deployment profile, and an app factory for ASGI hosts.

On Modal (or any ASGI host that imports an app factory) use
`pah.webui.settings:create_app_from_env`: the profile comes from `PAH_PROFILE` (default `local`),
its runs and cache directories are created if missing, and CORS origins come from
`PAH_CORS_ORIGINS` (comma-separated) or the localhost:3000 defaults.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pah.config import Profile, load_profile, repo_root, resolve_path

if TYPE_CHECKING:
    from fastapi import FastAPI

log = logging.getLogger(__name__)

DEFAULT_CORS_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")
PROFILE_ENV = "PAH_PROFILE"
CORS_ENV = "PAH_CORS_ORIGINS"


@dataclass(frozen=True)
class ApiSettings:
    """Where the UI routes read runs from.

    `runs_dir` holds one directory per run (`events.jsonl`, `record.json`, ...). `examples_dir`
    is the directory of example manifests, or None when the package runs outside a checkout.
    """

    runs_dir: Path
    cache_dir: Path
    profile: str = "local"
    offline: bool = False
    examples_dir: Path | None = None
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS
    backend: str = "local"

    @classmethod
    def from_profile_model(cls, prof: Profile) -> ApiSettings:
        root = repo_root()
        examples = root / "examples" if root is not None else None
        return cls(
            runs_dir=resolve_path(prof.runs_dir),
            cache_dir=resolve_path(prof.cache_dir),
            profile=prof.name,
            offline=prof.offline,
            examples_dir=examples if examples is not None and examples.is_dir() else None,
            cors_origins=cors_origins(),
            backend=prof.backend,
        )

    @classmethod
    def from_profile(cls, name: str | None = None) -> ApiSettings:
        """Builds settings from a profile name or YAML path; `PAH_PROFILE` when name is None.

        Raises OSError, ValueError or pydantic.ValidationError for an unusable profile.
        """
        return cls.from_profile_model(profile_from_env(name))

    def ensure_dirs(self) -> list[str]:
        """Creates runs_dir and cache_dir if missing. Returns the problems, never raises."""
        problems = []
        for path in (self.runs_dir, self.cache_dir):
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                problems.append(f"{path}: {exc}")
                log.warning("cannot create %s: %s", path, exc)
        return problems


def profile_from_env(name: str | None = None) -> Profile:
    return load_profile(name or os.environ.get(PROFILE_ENV) or "local")


def cors_origins() -> tuple[str, ...]:
    raw = os.environ.get(CORS_ENV, "")
    chosen = tuple(o.strip() for o in raw.split(",") if o.strip())
    return chosen or DEFAULT_CORS_ORIGINS


def cors_config(entries: Iterable[str]) -> tuple[tuple[str, ...], str | None]:
    """Splits origins into exact entries and one regex for the entries with `*`.

    `*` matches one or more characters other than `/` (`https://*.vercel.app` matches
    `https://pah-git-main.vercel.app`); everything else in a pattern is matched literally.
    """
    items = tuple(entries)
    if "*" in items:  # a bare `*` allows every origin, as CORSMiddleware's allow_origins=["*"]
        return ("*",), None
    plain = tuple(e for e in items if "*" not in e)
    patterns = [e for e in items if "*" in e]
    if not patterns:
        return plain, None
    parts = ["[^/]+".join(re.escape(piece) for piece in p.split("*")) for p in patterns]
    return plain, "^(?:" + "|".join(parts) + ")$"


def add_cors(app: FastAPI, entries: Iterable[str]) -> bool:
    """Adds one CORSMiddleware for `entries` unless the app already has one. True if added."""
    from fastapi.middleware.cors import CORSMiddleware

    if any(getattr(m, "cls", None) is CORSMiddleware for m in app.user_middleware):
        return False
    plain, regex = cors_config(entries)
    if not plain and regex is None:
        return False
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(plain),
        allow_origin_regex=regex,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return True


def create_app_from_env() -> FastAPI:
    """The harness API (native routes plus /ui) for the profile named in `PAH_PROFILE`, with CORS
    from `PAH_CORS_ORIGINS` (exact origins and `*` patterns) or the localhost:3000 defaults."""
    from pah.interfaces.api import create_app

    prof = profile_from_env()
    ApiSettings.from_profile_model(prof).ensure_dirs()
    app = create_app(prof)
    add_cors(app, cors_origins())
    return app
