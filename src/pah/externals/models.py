"""Declarations and results for assets fetched on the end user's host."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from pah.core.models import utcnow


class AssetKind(StrEnum):
    HTTP = "http"
    GITHUB_RELEASE = "github_release"
    COMMAND = "command"
    MANUAL = "manual"


class Extract(StrEnum):
    NONE = "none"
    TAR = "tar"
    ZIP = "zip"


class ExternalAsset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    kind: AssetKind
    description: str
    required_for: tuple[str, ...] = ()
    default: bool = True
    size_hint: str | None = None
    source: str | None = None
    dest: str = ""
    url: str | None = None
    repo: str | None = None
    tag: str = "latest"
    asset_patterns: tuple[str, ...] = ()
    extract: Extract = Extract.NONE
    executable: bool = False
    links: dict[str, str] = Field(default_factory=dict)
    sha256: str | None = None
    command: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()
    env_var: str | None = None
    instructions: str | None = None


class FetchStatus(StrEnum):
    INSTALLED = "installed"
    PRESENT = "present"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    FAILED = "failed"
    MANUAL = "manual"


class FetchResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    status: FetchStatus
    detail: str = ""
    path: str | None = None
    url: str | None = None
    sha256: str | None = None
    size_bytes: int | None = None
    finished_at: datetime = Field(default_factory=utcnow)

    @property
    def usable(self) -> bool:
        return self.status in {FetchStatus.INSTALLED, FetchStatus.PRESENT}
