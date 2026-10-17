"""Plan and run one executor invocation, streaming its output as events.

Under policy `auto` a kit run that cannot engage falls back to stock twice over: before any
compute through the kit's own dry run (`run.sh check`), and after the fact if the run itself
prints NOT ACTIVE and exits with the kit's not-active code. Both fallbacks are recorded in
`runtime_record.json` and in a `runtime.accel` finding.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pah.core.events import EventBus
from pah.core.models import EventKind, Finding, Gate, Layer, Measurement, ToolRef
from pah.runtimes.accel import (
    AccelUnavailableError,
    Decision,
    KitStatus,
    decide,
    parse_kit_line,
    stock_decision,
)
from pah.runtimes.hardware import Gpu
from pah.runtimes.launch import Invocation, Launcher
from pah.runtimes.models import (
    AccelConfig,
    Command,
    ExecutorRuntime,
    Policy,
    Route,
    RuntimeProfile,
    RuntimeRegistry,
)
from pah.runtimes.registry import fill, fill_env

Spawn = Callable[[Command, Mapping[str, str], Callable[[str], None]], int]
SPEC_ROW = "Layer 3: Accelerated mode verified against stock on this hardware"


def spawn(argv: Command, env: Mapping[str, str], on_line: Callable[[str], None]) -> int:
    """Start a process with stdout and stderr merged and pass each line on as it arrives."""
    proc = subprocess.Popen(
        list(argv),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env={**os.environ, **env},
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        on_line(line.rstrip("\n"))
    return proc.wait()


@dataclass
class RunRequest:
    executor: str
    out_dir: Path
    params: dict[str, str] = field(default_factory=dict)
    extra: tuple[str, ...] = ()
    policy: Policy | None = None
    mode: str | None = None
    preflight: bool = True


@dataclass(frozen=True)
class Plan:
    decision: Decision
    command: Command
    invocation: Invocation
    check: Invocation | None
    outputs: dict[str, str]
    weights: Path


@dataclass
class RunResult:
    exit_code: int
    plan: Plan
    kit_status: KitStatus | None
    record_path: Path
    finding: Finding


class ExecutorRunner:
    def __init__(
        self,
        reg: RuntimeRegistry,
        cfg: AccelConfig,
        profile: RuntimeProfile,
        launcher: Launcher,
        gpus: list[Gpu],
        bus: EventBus | None = None,
        runner: Spawn = spawn,
    ) -> None:
        self.reg = reg
        self.cfg = cfg
        self.profile = profile
        self.launcher = launcher
        self.gpus = gpus
        self.bus = bus
        self._spawn = runner

    # ------------------------------------------------------------------ planning

    def weights_dir(self, rt: ExecutorRuntime) -> Path:
        override = rt.native.weights_env_override if rt.native else None
        if override and os.environ.get(override):
            return Path(os.environ[override]).expanduser().resolve()
        return (self.profile.path("weights_root") / rt.weights_dir).resolve()

    def decide(self, rt: ExecutorRuntime, req: RunRequest) -> Decision:
        policy = req.policy or Policy(os.environ.get("PAH_ACCEL", self.cfg.policy.value))
        mode = req.mode or os.environ.get("PAH_ACCEL_MODE", self.cfg.mode)
        return decide(
            rt,
            self.cfg,
            policy=policy,
            mode=mode,
            gpus=self.gpus,
            kit=self.launcher.kit_available(rt),
            native=self.launcher.native_available(rt),
        )

    def plan(self, req: RunRequest, decision: Decision | None = None) -> Plan:
        rt = self.reg.get(req.executor)
        decision = decision or self.decide(rt, req)
        weights = self.weights_dir(rt)
        params = {k: _absolute_if_path(v) for k, v in req.params.items()}
        values: dict[str, object] = {**rt.defaults, **params}
        values.update(out_dir=str(req.out_dir.resolve()), weights=str(weights))
        binds = {req.out_dir.resolve(), weights, *_path_binds(params.values())}
        check: Invocation | None = None
        if decision.route is Route.NATIVE:
            assert rt.native is not None
            template, env_t, outputs = rt.native.command, rt.native.env, rt.native.outputs
        else:
            spec = rt.accel
            assert spec is not None and decision.kit is not None
            values.update(
                kit=spec.kit,
                kit_dir=self.launcher.kit_dir(spec.kit),
                card=decision.card,
                mode=decision.mode,
            )
            template, env_t = spec.command, spec.env
            outputs = spec.outputs_kit if decision.route is Route.KIT else spec.outputs_off
            if decision.route is Route.KIT:
                check_t = spec.check or self.reg.kit_defaults.check
                check = self.launcher.wrap(
                    rt, decision.route, fill(check_t, values), fill_env(env_t, values), binds
                )
        command = (*fill(template, values), *req.extra)
        env = fill_env(env_t, values)
        invocation = self.launcher.wrap(rt, decision.route, command, env, binds)
        return Plan(decision, command, invocation, check, dict(outputs), weights)

    # ------------------------------------------------------------------ running

    def run(self, req: RunRequest) -> RunResult:
        rt = self.reg.get(req.executor)
        req.out_dir.mkdir(parents=True, exist_ok=True)
        stage = f"executor.{rt.id}"
        plan = self.plan(req)
        record: dict[str, Any] = {
            "executor": rt.id,
            "tool": rt.tool,
            "launcher": self.launcher.name,
            "accel_repo": self.cfg.repo,
            "accel_commit": self.cfg.commit,
            "attempts": [],
        }
        record_path = req.out_dir / "runtime_record.json"
        plan.weights.mkdir(parents=True, exist_ok=True)
        self._emit(EventKind.STAGE_START, stage, f"{rt.id}: route={plan.decision.route.value}")
        for reason in plan.decision.reasons:
            self._emit(EventKind.LOG, stage, f"stock because: {reason}")

        if plan.check is not None and req.preflight:
            rc, status, _ = self._execute(plan.check, stage, req.out_dir / "kit_check.log")
            record["preflight"] = {
                "argv": list(plan.check.argv),
                "exit_code": rc,
                "kit_line": _line(status),
            }
            if rc != 0:
                plan = self._fallback(
                    rt, req, plan, f"kit check exited {rc}: {_line(status) or 'no kit line'}"
                )
        _write(record_path, {**record, "plan": _plan_dict(plan)})

        rc, status, started = self._run_once(plan, stage, req, record)
        if (
            plan.decision.route is Route.KIT
            and rc == self.cfg.not_active_exit_code
            and status is not None
            and not status.active
        ):
            plan = self._fallback(rt, req, plan, f"kit run printed: {status.line}")
            rc, status, started = self._run_once(plan, stage, req, record)

        finding = _accel_finding(rt, plan.decision, status, rc, time.monotonic() - started)
        record.update(plan=_plan_dict(plan), exit_code=rc, kit_line=_line(status))
        record["finding"] = finding.model_dump(mode="json")
        _write(record_path, record)
        self._emit(EventKind.FINDING, stage, finding.message, finding=record["finding"])
        self._emit(EventKind.ARTIFACT, stage, str(record_path), path=str(record_path))
        self._emit(EventKind.STAGE_END, stage, f"{rt.id}: exit {rc}", exit_code=rc)
        return RunResult(rc, plan, status, record_path, finding)

    def _run_once(
        self, plan: Plan, stage: str, req: RunRequest, record: dict[str, Any]
    ) -> tuple[int, KitStatus | None, float]:
        started = time.monotonic()
        log = req.out_dir / f"executor.{plan.decision.route.value}.log"
        self._emit(
            EventKind.PROGRESS,
            stage,
            " ".join(plan.invocation.argv),
            argv=list(plan.invocation.argv),
        )
        rc, status, _ = self._execute(plan.invocation, stage, log)
        record["attempts"].append(
            {
                "route": plan.decision.route.value,
                "mode": plan.decision.mode,
                "argv": list(plan.invocation.argv),
                "env": plan.invocation.env,
                "exit_code": rc,
                "kit_line": _line(status),
                "duration_s": round(time.monotonic() - started, 3),
                "log": str(log),
            }
        )
        return rc, status, started

    def _fallback(self, rt: ExecutorRuntime, req: RunRequest, plan: Plan, reason: str) -> Plan:
        decision = plan.decision
        if decision.policy is Policy.KIT:
            raise AccelUnavailableError(f"{rt.id}: kit required but did not engage: {reason}")
        self._emit(EventKind.LOG, f"executor.{rt.id}", f"falling back to stock: {reason}")
        fallback = stock_decision(
            rt,
            policy=decision.policy,
            gpu=decision.gpu,
            kit=self.launcher.kit_available(rt),
            native=self.launcher.native_available(rt),
            reasons=[reason],
            fallback_from=decision,
        )
        return self.plan(req, fallback)

    def _execute(
        self, inv: Invocation, stage: str, log: Path
    ) -> tuple[int, KitStatus | None, float]:
        started = time.monotonic()
        status: KitStatus | None = None
        with log.open("w", encoding="utf-8") as fh:

            def on_line(line: str) -> None:
                nonlocal status
                fh.write(line + "\n")
                fh.flush()
                parsed = parse_kit_line(line)
                if parsed is not None:
                    status = parsed
                self._emit(EventKind.LOG, stage, line)

            rc = self._spawn(inv.argv, inv.env, on_line)
        return rc, status, started

    def _emit(self, kind: EventKind, stage: str, message: str, **data: Any) -> None:
        if self.bus is not None:
            self.bus.emit(kind, stage, message, **data)


def _absolute_if_path(value: str) -> str:
    p = Path(value).expanduser()
    return str(p.resolve()) if p.exists() else value


def _path_binds(values: Any) -> set[Path]:
    binds: set[Path] = set()
    for v in values:
        p = Path(str(v))
        if p.is_absolute() and p.exists():
            binds.add(p if p.is_dir() else p.parent)
    return binds


def _line(status: KitStatus | None) -> str | None:
    return status.line if status else None


def _plan_dict(plan: Plan) -> dict[str, Any]:
    return {
        "decision": plan.decision.as_dict(),
        "command": list(plan.command),
        "argv": list(plan.invocation.argv),
        "env": plan.invocation.env,
        "image": plan.invocation.image,
        "check_argv": list(plan.check.argv) if plan.check else None,
        "outputs": plan.outputs,
        "weights": str(plan.weights),
    }


def _write(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def _accel_finding(
    rt: ExecutorRuntime, d: Decision, status: KitStatus | None, rc: int, duration: float
) -> Finding:
    measurements = (
        Measurement(name="route", value=d.route.value),
        Measurement(name="mode", value=d.mode),
        Measurement(name="card", value=d.card),
        Measurement(name="exit_code", value=rc),
    )
    evidence: dict[str, Any] = {
        "decision": d.as_dict(),
        "kit_line": _line(status),
        "specification": SPEC_ROW,
    }
    gate = Gate.PASS
    if d.route is Route.KIT:
        if status is None or not status.active:
            gate, message = Gate.WARN, f"{rt.id}: kit route ran but no ACTIVE line was seen"
        elif d.mode == "exact":
            message = f"{rt.id}: kit {d.kit} mode exact (outputs identical to stock per the kit)"
        else:
            gate = Gate.WARN
            message = (
                f"{rt.id}: kit {d.kit} mode {d.mode}; not verified against stock on this hardware"
            )
    else:
        why = "; ".join(d.reasons) or "stock requested"
        message = f"{rt.id}: stock ({d.route.value}); {why}"
    tool = ToolRef(name=d.kit or rt.id, version=None)
    return Finding(
        check_id="runtime.accel",
        layer=Layer.APPLICABILITY,
        gate=gate,
        message=message,
        measurements=measurements,
        evidence=evidence,
        tool=tool,
        duration_s=round(duration, 3),
    )
