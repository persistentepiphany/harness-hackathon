"""Gate policy: the category and standing of each check, and what a stop from it may do.

`configs/standing.yaml` is the table. The engine calls `apply_policy` on every finding: it stamps
the finding with its category and standing, and rewrites a gate the check's role does not allow
(a stop from a check that only narrows becomes a warning; a stop or warning from a context-only
check becomes a reported pass). Every rewrite is recorded under `evidence.policy`.
"""

from __future__ import annotations

from enum import StrEnum
from functools import cache
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from pah.config import load_yaml
from pah.core.models import Finding, Gate


class Standing(StrEnum):
    DEFINITIONAL = "definitional"
    PUBLISHED = "published"
    INHERITED = "inherited"
    UNCALIBRATED = "uncalibrated"
    UNDECLARED = "undeclared"


class Role(StrEnum):
    DECIDE = "decide"
    NARROW = "narrow"
    CONTEXT = "context"


class CheckStanding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    check_id: str
    category: str | None = None
    standing: Standing = Standing.UNDECLARED
    decisive: bool = False
    role: Role = Role.NARROW
    status: str = "built"
    thresholds: dict[str, Standing] = Field(default_factory=dict)
    notes: str = ""


class StandingTable(BaseModel):
    model_config = ConfigDict(frozen=True)

    policy: str = ""
    decided: str | None = None
    checks: dict[str, CheckStanding] = Field(default_factory=dict)
    categories: tuple[dict[str, Any], ...] = ()
    dimensions: tuple[dict[str, Any], ...] = ()
    errors: tuple[str, ...] = ()

    def get(self, check_id: str) -> CheckStanding:
        """The row for a check; an undeclared check narrows only."""
        return self.checks.get(check_id) or CheckStanding(
            check_id=check_id, notes="not declared in configs/standing.yaml"
        )

    def dimension_of(self, category: str | None) -> str | None:
        for c in self.categories:
            if c.get("id") == category:
                dim = c.get("dimension")
                return str(dim) if dim else None
        return None


def parse_standing(data: dict[str, Any]) -> StandingTable:
    """Builds the table; a bad row is reported in `errors` and left out (fail soft)."""
    rows: dict[str, CheckStanding] = {}
    errors: list[str] = []
    for cid, row in (data.get("checks") or {}).items():
        try:
            parsed = CheckStanding.model_validate({"check_id": cid, **(row or {})})
        except (ValidationError, TypeError) as exc:
            errors.append(f"{cid}: {exc}")
            continue
        if parsed.decisive != (parsed.role is Role.DECIDE):
            errors.append(f"{cid}: decisive={parsed.decisive} disagrees with role={parsed.role}")
            parsed = parsed.model_copy(update={"decisive": parsed.role is Role.DECIDE})
        rows[cid] = parsed
    return StandingTable(
        policy=str(data.get("policy") or ""),
        decided=str(data["decided"]) if data.get("decided") else None,
        checks=rows,
        categories=tuple(data.get("categories") or ()),
        dimensions=tuple(data.get("dimensions") or ()),
        errors=tuple(errors),
    )


@cache
def load_standing() -> StandingTable:
    """The table from configs/standing.yaml; empty (every check undeclared) when unreadable."""
    try:
        return parse_standing(load_yaml("standing.yaml"))
    except (OSError, ValueError) as exc:
        return StandingTable(errors=(f"standing.yaml: {exc}",))


def standing_for(check_id: str) -> CheckStanding:
    return load_standing().get(check_id)


def apply_policy(finding: Finding, table: StandingTable | None = None) -> Finding:
    """Stamps category and standing on a finding and enforces the check's role."""
    table = table or load_standing()
    row = table.get(finding.check_id)
    update: dict[str, Any] = {"category": row.category, "standing": row.standing.value}
    new_gate: Gate | None = None
    if row.role is Role.NARROW and finding.gate is Gate.STOP:
        new_gate = Gate.WARN
        reason = f"stop downgraded by policy: {row.standing.value}"
    elif row.role is Role.CONTEXT and finding.gate in (Gate.STOP, Gate.WARN):
        new_gate = Gate.PASS
        reason = f"{finding.gate.value} reported by policy: context only ({row.standing.value})"
    if new_gate is not None:
        update["gate"] = new_gate
        update["evidence"] = {
            **finding.evidence,
            "policy": {
                "original_gate": finding.gate.value,
                "gate": new_gate.value,
                "role": row.role.value,
                "standing": row.standing.value,
                "reason": reason,
            },
        }
    return finding.model_copy(update=update)


def policy_changed(finding: Finding) -> bool:
    """True when the gate policy rewrote this finding's gate."""
    return isinstance(finding.evidence.get("policy"), dict)
