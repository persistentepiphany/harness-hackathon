"""End-to-end runner tests against a fake kit and a fake stock tool (shell scripts)."""

import json
import stat
from pathlib import Path

import pytest

from pah.core.events import EventBus
from pah.core.models import Event, Gate
from pah.runtimes.accel import AccelUnavailableError
from pah.runtimes.hardware import Gpu
from pah.runtimes.launch import ApptainerLauncher, DockerLauncher, HostLauncher
from pah.runtimes.models import AccelConfig, Policy, Route, RuntimeProfile, RuntimeRegistry
from pah.runtimes.registry import load_accel, load_runtimes
from pah.runtimes.runner import ExecutorRunner, RunRequest

H100 = Gpu(0, "NVIDIA H100 80GB HBM3", 9.0, 81559, "580.65.06")

# The fake kit: `check` and `pred` behave according to FAKE_CHECK_RC and FAKE_PRED.
RUN_SH = """#!/usr/bin/env bash
cmd="$1"; shift
mode=""
while [ $# -gt 0 ]; do case "$1" in --mode) mode="$2"; shift 2;; *) shift;; esac; done
if [ "$cmd" = check ]; then
  if [ "${FAKE_CHECK_RC:-0}" != 0 ]; then echo "[fake-opt] NOT ACTIVE: reason=check"; fi
  exit "${FAKE_CHECK_RC:-0}"
fi
if [ "$mode" = off ]; then echo "[fake-opt] NOT ACTIVE: mode off: stock"; echo stock-ran; exit 0; fi
if [ "${FAKE_PRED:-active}" = refuse ]; then
  echo "[fake-opt] NOT ACTIVE: reason=card_off" >&2; exit 3
fi
echo "[fake-opt] ACTIVE mode=$mode levers=x"; exit 0
"""


class Collect:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def handle(self, event: Event) -> None:
        self.events.append(event)

    def close(self) -> None:
        pass


def _registry(tmp: Path) -> tuple[RuntimeRegistry, RuntimeProfile]:
    kit = tmp / "kits" / "fake"
    (kit / "opt" / "fake_opt").mkdir(parents=True)
    (kit / "opt" / "fake_opt" / "__init__.py").write_text("")
    run_sh = kit / "run.sh"
    run_sh.write_text(RUN_SH)
    run_sh.chmod(run_sh.stat().st_mode | stat.S_IEXEC)
    base = load_runtimes().model_dump()
    base["executors"] = [
        {
            "id": "fake",
            "tool": "Fake",
            "gpu": True,
            "weights_dir": "fake",
            "defaults": {"seed": 1},
            "native": {
                "version": "1.0",
                "command": ["echo", "native", "{input}", "{out_dir}"],
                "outputs": {"structures": "*.cif"},
            },
            "accel": {
                "kit": "fake",
                "stock": "fake 1.0",
                "configs": ["a100", "h100"],
                "modes": ["off", "exact", "fast", "big"],
                "min_driver": 580,
                "env": {"FAKE_WEIGHTS": "{weights}"},
                "command": [
                    "bash",
                    "{kit_dir}/run.sh",
                    "pred",
                    "--config",
                    "{card}",
                    "--mode",
                    "{mode}",
                    "--input",
                    "{input}",
                    "--out_dir",
                    "{out_dir}",
                ],
                "outputs_kit": {"structures": "by_seed/*.cif"},
                "outputs_off": {"structures": "*.cif"},
            },
        }
    ]
    reg = RuntimeRegistry.model_validate(base)
    prof = RuntimeProfile(
        launcher="host",
        envs_root=str(tmp / "envs"),
        kits_root=str(tmp / "kits"),
        images_root=str(tmp / "images"),
        weights_root=str(tmp / "weights"),
    )
    return reg, prof


def _runner(tmp: Path, gpus: list[Gpu] | None = None) -> tuple[ExecutorRunner, Collect]:
    reg, prof = _registry(tmp)
    launcher = HostLauncher(reg, prof, importable=lambda python, module: module == "fake_opt")
    sink = Collect()
    cfg: AccelConfig = load_accel()
    return ExecutorRunner(
        reg, cfg, prof, launcher, [H100] if gpus is None else gpus, EventBus("t", [sink])
    ), sink


def _req(tmp: Path, **kw: object) -> RunRequest:
    inp = tmp / "in.yaml"
    inp.write_text("x")
    return RunRequest("fake", tmp / "out", {"input": str(inp)}, **kw)  # type: ignore[arg-type]


def test_kit_engages_by_default(tmp_path: Path) -> None:
    runner, sink = _runner(tmp_path)
    result = runner.run(_req(tmp_path))
    assert result.exit_code == 0
    assert result.plan.decision.route is Route.KIT and result.plan.decision.mode == "fast"
    assert result.kit_status is not None and result.kit_status.active
    assert result.finding.gate is Gate.WARN  # fast is not yet verified against stock here
    record = json.loads(result.record_path.read_text())
    assert record["preflight"]["exit_code"] == 0 and len(record["attempts"]) == 1
    assert record["accel_commit"] == load_accel().commit
    assert any(e.kind == "finding" for e in sink.events)


def test_exact_mode_passes(tmp_path: Path) -> None:
    runner, _ = _runner(tmp_path)
    result = runner.run(_req(tmp_path, mode="exact"))
    assert result.finding.gate is Gate.PASS


def test_failed_check_falls_back_before_compute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CHECK_RC", "3")
    runner, _ = _runner(tmp_path)
    result = runner.run(_req(tmp_path))
    assert result.exit_code == 0
    d = result.plan.decision
    assert d.route is Route.KIT_OFF and d.fallback_from is not None
    assert "kit check exited 3" in d.reasons[0]
    record = json.loads(result.record_path.read_text())
    assert len(record["attempts"]) == 1 and record["attempts"][0]["mode"] == "off"


def test_not_active_run_falls_back_to_stock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_PRED", "refuse")
    runner, _ = _runner(tmp_path)
    result = runner.run(_req(tmp_path))
    assert result.exit_code == 0
    assert result.plan.decision.route is Route.KIT_OFF
    assert "card_off" in result.plan.decision.reasons[0]
    record = json.loads(result.record_path.read_text())
    assert [a["route"] for a in record["attempts"]] == ["kit", "kit_off"]
    assert record["attempts"][0]["exit_code"] == 3
    assert "stock-ran" in Path(record["attempts"][1]["log"]).read_text()


def test_policy_kit_does_not_fall_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_PRED", "refuse")
    runner, _ = _runner(tmp_path)
    with pytest.raises(AccelUnavailableError, match="card_off"):
        runner.run(_req(tmp_path, policy=Policy.KIT))


def test_no_gpu_runs_stock_and_records_reason(tmp_path: Path) -> None:
    runner, _ = _runner(tmp_path, gpus=[])
    result = runner.run(_req(tmp_path))
    assert result.plan.decision.route is Route.KIT_OFF
    assert result.finding.gate is Gate.PASS
    assert "no NVIDIA GPU" in result.finding.message


def test_env_overrides_policy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAH_ACCEL", "stock")
    runner, _ = _runner(tmp_path)
    assert runner.plan(_req(tmp_path)).decision.route is Route.KIT_OFF


def test_plan_fills_kit_command(tmp_path: Path) -> None:
    runner, _ = _runner(tmp_path)
    plan = runner.plan(_req(tmp_path, extra=("--extra", "1")))
    argv = plan.invocation.argv
    assert argv[0] == "bash" and argv[1].endswith("kits/fake/run.sh")
    assert argv[3:5] == ("--config", "h100") and argv[-2:] == ("--extra", "1")
    assert plan.invocation.env["FAKE_WEIGHTS"].endswith("weights/fake")
    assert plan.check is not None and plan.check.argv[2] == "check"


def test_docker_and_apptainer_wrapping(tmp_path: Path) -> None:
    reg, prof = _registry(tmp_path)
    rt = reg.get("fake")
    docker = DockerLauncher(reg, prof, present=lambda ref: True)
    inv = docker.wrap(rt, Route.KIT, ("bash", "/kit/fake/run.sh"), {"A": "1"}, [tmp_path])
    assert inv.argv[:6] == ("docker", "run", "--rm", "--ipc=host", "--gpus", "all")
    assert f"{tmp_path}:{tmp_path}" in inv.argv and "fake-kit:dev" in inv.argv
    assert docker.kit_dir("fake") == "/kit/fake"
    app = ApptainerLauncher(reg, prof)
    inv = app.wrap(rt, Route.KIT, ("bash", "/kit/fake/run.sh"), {"A": "1"}, [tmp_path])
    assert inv.argv[:4] == ("apptainer", "exec", "--cleanenv", "--nv")
    assert inv.argv[inv.argv.index("--env") + 1] == "A=1"
    assert inv.image is not None and inv.image.endswith("images/fake-kit.sif")
    assert not app.kit_available(rt).ok


def test_host_kit_needs_importable_package(tmp_path: Path) -> None:
    reg, prof = _registry(tmp_path)
    launcher = HostLauncher(reg, prof, importable=lambda python, module: False)
    avail = launcher.kit_available(reg.get("fake"))
    assert not avail.ok and "fake_opt not importable" in avail.where
