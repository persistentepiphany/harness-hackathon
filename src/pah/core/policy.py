"""Turns findings into a verdict scoped to the declared claim."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from pah.core.check import INCOMPLETE_REASONS, SkipReason
from pah.core.models import Finding, Gate


class Outcome(StrEnum):
    PASS = "pass"
    PASS_WITH_WARNINGS = "pass_with_warnings"
    STOP = "stop"
    INCOMPLETE = "incomplete"


class Verdict(BaseModel):
    model_config = ConfigDict(frozen=True)

    claim: str
    scope: str
    outcome: Outcome
    stops: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    incomplete: tuple[str, ...] = ()
    not_applicable: tuple[str, ...] = ()
    downgraded: tuple[str, ...] = ()


def _skip_reason(f: Finding) -> SkipReason | None:
    raw = f.evidence.get("skip_reason")
    try:
        return SkipReason(raw) if raw else None
    except ValueError:
        return None


def decide(claim: str, scope: str, findings: list[Finding]) -> Verdict:
    """Any stop refuses the claim. A skip caused by a missing tool, an error or an unknown
    check makes the verdict incomplete, because the harness could not verify that point.

    Findings arrive after the gate policy (pah.core.standing): a stop here comes from a check
    allowed to decide. `downgraded` lists the checks whose gate the policy rewrote."""
    stops = tuple(f.check_id for f in findings if f.gate is Gate.STOP)
    warnings = tuple(f.check_id for f in findings if f.gate is Gate.WARN)
    incomplete = tuple(
        f.check_id
        for f in findings
        if f.gate is Gate.SKIP and _skip_reason(f) in INCOMPLETE_REASONS
    )
    na = tuple(
        f.check_id
        for f in findings
        if f.gate is Gate.SKIP and _skip_reason(f) is SkipReason.NOT_APPLICABLE
    )
    downgraded = tuple(f.check_id for f in findings if isinstance(f.evidence.get("policy"), dict))
    if stops:
        outcome = Outcome.STOP
    elif incomplete:
        outcome = Outcome.INCOMPLETE
    elif warnings:
        outcome = Outcome.PASS_WITH_WARNINGS
    else:
        outcome = Outcome.PASS
    return Verdict(
        claim=claim,
        scope=scope,
        outcome=outcome,
        stops=stops,
        warnings=warnings,
        incomplete=incomplete,
        not_applicable=na,
        downgraded=downgraded,
    )
