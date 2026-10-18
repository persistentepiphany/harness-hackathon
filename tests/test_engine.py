import json
from pathlib import Path

import httpx
import pytest

from pah.core.check import CHECKS, Check, CheckContext, SkipReason, register
from pah.core.engine import Engine
from pah.core.events import EventBus, MemorySink
from pah.core.manifest import Manifest
from pah.core.models import EventKind, Finding, Gate, Layer
from pah.core.policy import Outcome, decide
from pah.core.standing import CheckStanding, Role, Standing, StandingTable, load_standing
from pah.core.task import TaskSpec
from pah.sources import CachedHttp, ContentCache, Sources


def _make(
    cid: str,
    layer: Layer,
    gate: Gate | None = None,
    *,
    boom: bool = False,
    modules: tuple[str, ...] = (),
    na: str | None = None,
) -> str:
    class Stub(Check):
        id = cid
        title = cid
        requires_modules = modules

        def applies(self, ctx: CheckContext) -> str | None:
            return na

        def run(self, ctx: CheckContext) -> Finding:
            if boom:
                raise RuntimeError("bug in check")
            assert gate is not None
            return self.finding(gate, f"{cid} done", measurements={"x": 1})

    Stub.layer = layer
    CHECKS.pop(cid, None)
    register(Stub)
    return cid


@pytest.fixture
def ctx(tmp_path: Path) -> CheckContext:
    task = TaskSpec(id="t", title="t", families=("docking",), claim="claim text", layers={})
    sources = Sources(CachedHttp(httpx.Client(), ContentCache(tmp_path / "cache"), offline=True))
    return CheckContext(Manifest(task="t"), task, sources, tmp_path / "run")


def _decisive(*ids: str) -> StandingTable:
    """A gate-policy table in which the given synthetic checks may decide."""
    rows = {
        cid: CheckStanding(
            check_id=cid, standing=Standing.DEFINITIONAL, decisive=True, role=Role.DECIDE
        )
        for cid in ids
    }
    return StandingTable(checks=rows)


def _run(
    ctx: CheckContext,
    layers: dict[int, tuple[str, ...]],
    escalate: tuple[str, ...] = (),
    standing: StandingTable | None = None,
):
    ctx.task = ctx.task.model_copy(update={"layers": layers, "escalate": escalate})
    mem = MemorySink()
    engine = Engine(EventBus("run-t", [mem]), ctx, standing=standing or StandingTable())
    record = engine.run(tuple(layers))
    return record, mem


def test_streams_writes_and_passes(ctx: CheckContext) -> None:
    a = _make("t.a", Layer.PROVENANCE, Gate.PASS)
    b = _make("t.b", Layer.INTEGRITY, Gate.WARN)
    record, mem = _run(ctx, {0: (a,), 1: (b,)})
    kinds = [e.kind for e in mem.events]
    assert kinds == [
        EventKind.RUN_START,
        EventKind.STAGE_START,
        EventKind.FINDING,
        EventKind.STAGE_END,
        EventKind.STAGE_START,
        EventKind.FINDING,
        EventKind.STAGE_END,
        EventKind.RUN_END,
    ]
    assert record.verdict and record.verdict.outcome is Outcome.PASS_WITH_WARNINGS
    assert (ctx.run_dir / "findings" / "L0_t.a.json").is_file()
    saved = json.loads((ctx.run_dir / "record.json").read_text())
    assert saved["verdict"]["outcome"] == "pass_with_warnings"
    assert record.findings[0].duration_s is not None


def test_stop_halts_later_layers(ctx: CheckContext) -> None:
    a = _make("t.stop", Layer.PROVENANCE, Gate.STOP)
    b = _make("t.after", Layer.INTEGRITY, Gate.PASS)
    record, _ = _run(ctx, {0: (a,), 1: (b,)}, standing=_decisive(a))
    assert record.findings[1].gate is Gate.SKIP
    assert record.findings[1].evidence["skip_reason"] == SkipReason.UPSTREAM_STOP
    assert record.verdict and record.verdict.outcome is Outcome.STOP


def test_errors_missing_tools_unknown_checks_are_incomplete(ctx: CheckContext) -> None:
    boom = _make("t.boom", Layer.INTEGRITY, boom=True)
    tool = _make("t.tool", Layer.INTEGRITY, Gate.PASS, modules=("no_such_module_xyz",))
    na = _make("t.na", Layer.INTEGRITY, Gate.PASS, na="no MSA declared")
    record, _ = _run(ctx, {1: (boom, tool, na, "t.unregistered")})
    reasons = [f.evidence.get("skip_reason") for f in record.findings]
    assert reasons == ["error", "tool_missing", "not_applicable", "unknown_check"]
    assert "RuntimeError" in record.findings[0].message
    v = record.verdict
    assert v and v.outcome is Outcome.INCOMPLETE
    assert v.incomplete == ("t.boom", "t.tool", "t.unregistered") and v.not_applicable == ("t.na",)


def test_task_escalates_warn_to_stop(ctx: CheckContext) -> None:
    w = _make("t.warn", Layer.INTEGRITY, Gate.WARN)
    record, _ = _run(ctx, {1: (w,)}, escalate=(w,), standing=_decisive(w))
    assert record.findings[0].gate is Gate.STOP
    assert record.findings[0].evidence["escalated_by_task"] == "t"


def test_stop_from_a_narrowing_check_becomes_a_recorded_warning(ctx: CheckContext) -> None:
    a = _make("t.narrow", Layer.PROVENANCE, Gate.STOP)
    b = _make("t.next", Layer.INTEGRITY, Gate.PASS)
    narrow = StandingTable(
        checks={a: CheckStanding(check_id=a, standing=Standing.UNCALIBRATED, role=Role.NARROW)}
    )
    record, _ = _run(ctx, {0: (a,), 1: (b,)}, standing=narrow)
    f = record.findings[0]
    assert f.gate is Gate.WARN and f.standing == "uncalibrated"
    assert f.evidence["policy"]["original_gate"] == "stop"
    assert f.evidence["policy"]["role"] == "narrow"
    assert record.findings[1].gate is Gate.PASS  # a narrowing warning does not halt
    v = record.verdict
    assert v and v.outcome is Outcome.PASS_WITH_WARNINGS and v.downgraded == (a,)


def test_undeclared_check_narrows_and_escalation_cannot_make_it_decide(
    ctx: CheckContext,
) -> None:
    w = _make("t.undeclared", Layer.INTEGRITY, Gate.WARN)
    record, _ = _run(ctx, {1: (w,)}, escalate=(w,))
    f = record.findings[0]
    assert f.gate is Gate.WARN and f.standing == "undeclared"
    assert f.evidence["escalated_by_task"] == "t"
    assert f.evidence["policy"]["original_gate"] == "stop"


def test_every_registered_check_is_classified() -> None:
    import pah.checks  # noqa: F401  registers the library

    table = load_standing()
    assert not table.errors, table.errors
    library = [cid for cid in CHECKS if not cid.startswith("t.")]
    assert [cid for cid in library if cid not in table.checks] == []
    decide_ids = {cid for cid, row in table.checks.items() if row.role is Role.DECIDE}
    assert all(
        table.checks[c].standing in (Standing.DEFINITIONAL, Standing.PUBLISHED)
        or c.startswith("l4.posebusters")
        for c in decide_ids
    ), sorted(decide_ids)


def test_decide_precedence() -> None:
    def f(cid: str, gate: Gate, reason: str | None = None) -> Finding:
        ev = {"skip_reason": reason} if reason else {}
        return Finding(check_id=cid, layer=Layer.INTEGRITY, gate=gate, message="m", evidence=ev)

    assert decide("c", "s", [f("a", Gate.PASS)]).outcome is Outcome.PASS
    assert (
        decide("c", "s", [f("a", Gate.SKIP, "error"), f("b", Gate.WARN)]).outcome
        is Outcome.INCOMPLETE
    )
    assert decide("c", "s", [f("a", Gate.SKIP, "error"), f("b", Gate.STOP)]).outcome is Outcome.STOP
