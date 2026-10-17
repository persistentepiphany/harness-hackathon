"""Choosing between the optimisation kit and the stock tool for one run.

The kit is used by default (policy `auto`) whenever it can engage on this host. When it cannot,
the run uses stock and the decision lists every reason, so the substitution is recorded rather
than silent. Policy `kit` turns any such reason into an error; policy `stock` skips the kit.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from pah.runtimes.hardware import Gpu
from pah.runtimes.models import AccelConfig, AccelSpec, ExecutorRuntime, Policy, Route

KIT_MODES = ("off", "exact", "fast", "big")


class AccelUnavailableError(RuntimeError):
    """Policy `kit` was requested and the kit cannot engage."""


class RuntimeUnavailableError(RuntimeError):
    """Neither the kit image nor a native install is available for this executor."""


@dataclass(frozen=True)
class Availability:
    ok: bool
    where: str


@dataclass(frozen=True)
class Decision:
    executor: str
    route: Route
    policy: Policy
    mode: str | None
    card: str | None
    kit: str | None
    gpu: Gpu | None
    reasons: tuple[str, ...] = ()
    fallback_from: Decision | None = field(default=None, compare=False)

    @property
    def accelerated(self) -> bool:
        return self.route is Route.KIT

    def as_dict(self) -> dict[str, Any]:
        return {
            "executor": self.executor,
            "route": self.route.value,
            "policy": self.policy.value,
            "mode": self.mode,
            "card": self.card,
            "kit": self.kit,
            "gpu": self.gpu.as_dict() if self.gpu else None,
            "reasons": list(self.reasons),
            "fallback_from": self.fallback_from.as_dict() if self.fallback_from else None,
        }


def select_card(gpu: Gpu, spec: AccelSpec, cfg: AccelConfig) -> str | None:
    """Kit card config for this GPU, or None when the kit ships none for it."""
    name = gpu.name.upper()
    for rule in cfg.cards.by_name:
        if rule.contains.upper() in name and rule.config in spec.configs:
            return rule.config
    for cap in sorted(cfg.cards.by_compute_capability, key=lambda r: r.min, reverse=True):
        if gpu.compute_capability >= cap.min:
            return next((c for c in cap.configs if c in spec.configs), None)
    return None


def _kit_blockers(
    spec: AccelSpec, cfg: AccelConfig, gpu: Gpu | None, kit: Availability
) -> tuple[list[str], str | None]:
    reasons: list[str] = []
    card: str | None = None
    if gpu is None:
        reasons.append("no NVIDIA GPU visible (nvidia-smi absent or reports none)")
    else:
        if gpu.compute_capability < cfg.min_compute_capability:
            reasons.append(
                f"GPU {gpu.name} has compute capability {gpu.compute_capability}; "
                f"kits need >= {cfg.min_compute_capability}"
            )
        if gpu.driver_major < spec.min_driver:
            reasons.append(
                f"driver {gpu.driver} is older than {spec.min_driver} required by the kit"
            )
        card = select_card(gpu, spec, cfg)
        if card is None:
            reasons.append(f"kit {spec.kit} ships no card config for {gpu.name}")
    if not kit.ok:
        reasons.append(f"kit {spec.kit} not available: {kit.where}")
    return reasons, card


def decide(
    rt: ExecutorRuntime,
    cfg: AccelConfig,
    *,
    policy: Policy,
    mode: str,
    gpus: Sequence[Gpu],
    kit: Availability,
    native: Availability,
) -> Decision:
    """Route for one run. Raises AccelUnavailableError or RuntimeUnavailableError."""
    if mode not in KIT_MODES:
        raise ValueError(f"unknown kit mode {mode!r}; expected one of {KIT_MODES}")
    gpu = gpus[0] if gpus else None
    spec = rt.accel
    reasons: list[str] = []
    card: str | None = None

    if policy is Policy.STOCK:
        reasons.append("policy stock")
    elif spec is None:
        reasons.append(
            f"no optimisation kit for {rt.id}" + (f": {rt.accel_note}" if rt.accel_note else "")
        )
    elif mode not in spec.modes:
        raise ValueError(f"kit {spec.kit} has no mode {mode!r}; modes: {', '.join(spec.modes)}")
    elif mode == "off":
        reasons.append("mode off requested")
    else:
        reasons, card = _kit_blockers(spec, cfg, gpu, kit)

    if spec is not None and not reasons:
        return Decision(rt.id, Route.KIT, policy, mode, card, spec.kit, gpu)
    if policy is Policy.KIT:
        raise AccelUnavailableError(
            f"{rt.id}: kit required but cannot engage: " + "; ".join(reasons)
        )
    return stock_decision(rt, policy=policy, gpu=gpu, kit=kit, native=native, reasons=reasons)


def stock_decision(
    rt: ExecutorRuntime,
    *,
    policy: Policy,
    gpu: Gpu | None,
    kit: Availability,
    native: Availability,
    reasons: Sequence[str],
    fallback_from: Decision | None = None,
) -> Decision:
    """Stock route: the kit image in mode `off` when it can run here (same pinned stack),
    otherwise the native install."""
    spec = rt.accel
    why = list(reasons)
    driver_ok = gpu is None or spec is None or gpu.driver_major >= spec.min_driver
    if spec is not None and kit.ok and driver_ok:
        card = spec.configs[0] if gpu is None else (_card_or_first(gpu, spec))
        return Decision(
            rt.id, Route.KIT_OFF, policy, "off", card, spec.kit, gpu, tuple(why), fallback_from
        )
    if native.ok:
        return Decision(
            rt.id, Route.NATIVE, policy, None, None, None, gpu, tuple(why), fallback_from
        )
    if spec is not None and not driver_ok:
        why.append(f"kit image needs driver >= {spec.min_driver}")
    why.append(f"native install not available: {native.where}")
    raise RuntimeUnavailableError(f"{rt.id}: nothing to run: " + "; ".join(why))


def _card_or_first(gpu: Gpu, spec: AccelSpec) -> str:
    name = gpu.name.upper()
    return next((c for c in spec.configs if c.upper() in name), spec.configs[0])


_ACTIVE = re.compile(r"\[(?P<tag>[\w.-]+-opt)[^\]]*\]\s+(?P<state>NOT ACTIVE|ACTIVE)\b(?P<rest>.*)")


@dataclass(frozen=True)
class KitStatus:
    """A kit's own report of whether it engaged, parsed from its ACTIVE / NOT ACTIVE line."""

    tag: str
    active: bool
    line: str


def parse_kit_line(line: str) -> KitStatus | None:
    m = _ACTIVE.search(line)
    if m is None:
        return None
    return KitStatus(tag=m["tag"], active=m["state"] == "ACTIVE", line=line.strip())
