"""Executor runtimes: install, boot and run co-folding and docking engines on GPU hosts.

The Anthropic optimisation kits are used by default where one exists for the executor and it can
engage on the host (see configs/accel.yaml); otherwise the stock tool runs and the reason is
recorded.
"""

from pah.runtimes.accel import AccelUnavailableError, Decision, RuntimeUnavailableError, decide
from pah.runtimes.hardware import Gpu, detect_gpus
from pah.runtimes.models import Policy, Route
from pah.runtimes.registry import load_accel, load_runtimes
from pah.runtimes.runner import ExecutorRunner, RunRequest

__all__ = [
    "AccelUnavailableError",
    "Decision",
    "ExecutorRunner",
    "Gpu",
    "Policy",
    "Route",
    "RunRequest",
    "RuntimeUnavailableError",
    "decide",
    "detect_gpus",
    "load_accel",
    "load_runtimes",
]
