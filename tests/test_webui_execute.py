"""Executor dispatch for UI runs (pah.webui.execute) with fake dispatchers: no network, no Modal."""

import shutil
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml

from pah.webui import execute
from pah.webui.execute import (
    BUILDERS,
    BuildContext,
    BuildError,
    DispatchConfig,
    DispatchJob,
    DispatchUnavailableError,
    ExecDeniedError,
    ExecuteStage,
    ExecutorDispatch,
    Guard,
    ModalSettings,
    check_exec_token,
    load_dispatch,
)
from tests.conftest import ROOT

BOLTZ_OUT = ROOT / "examples/3ptb_boltz2/seed_0/boltz_results_trypsin_ben/predictions/trypsin_ben"
SEQ = "IVGGYTCGANTVPYQVSLNSGYHFCGG"
MANIFEST: dict[str, Any] = {
    "task": "ligand_pose",
    "proteins": [{"id": "trypsin", "uniprot": "P00760", "pdb_id": "3PTB", "chain": "A",
                  "sequence": SEQ}],
    "ligands": [{"id": "benzamidine", "smiles": "NC(=N)c1ccccc1", "ccd": "BEN"}],
    "receptor": {"pdb_id": "3PTB", "chains": ["A"]},
    "model": {"executor": "boltz2", "seeds": [0, 1, 2, 3, 4, 5, 6]},
}  # fmt: skip


def _config(**executors: ExecutorDispatch) -> DispatchConfig:
    return DispatchConfig(Guard(max_seeds=5, poll_s=0.01), ModalSettings(), executors)


class FakeBoltz:
    """Writes the Boltz-2 layout per seed and reports progress like the GPU app does."""

    def __init__(self) -> None:
        self.jobs: list[DispatchJob] = []

    def run(self, job: DispatchJob, progress: execute.Progress) -> dict[str, Any]:
        self.jobs.append(job)
        seeds = job.request.seeds
        progress({"phase": "building", "message": "container started", "route": "kit",
                  "gpu": "NVIDIA A100-SXM4-40GB", "seeds": [{"seed": s, "phase": "queued"}
                                                           for s in seeds]})  # fmt: skip
        for s in seeds:
            shutil.copytree(BOLTZ_OUT, job.dest / f"seed_{s}" / "predictions" / "trypsin_ben")
        done = [{"seed": s, "phase": "done", "ms": 1000} for s in seeds]
        progress({"phase": "running", "message": "kit: seeds", "seeds": done})
        return {"status": "done", "route": "kit", "routeNote": "kit boltz2 mode fast",
                "gpu": "NVIDIA A100-SXM4-40GB", "version": "2.2.1", "seeds": done}  # fmt: skip


class Unreachable:
    def run(self, job: DispatchJob, progress: execute.Progress) -> dict[str, Any]:
        raise DispatchUnavailableError("Modal function pah-gpu-x.predict not deployed")


class Recorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []
        self.rows: list[list[dict[str, Any]]] = []

    def emit(self, message: str, data: Mapping[str, Any]) -> None:
        self.events.append((message, dict(data)))

    def phases(self, executor: str) -> list[str]:
        return [d["phase"] for _, d in self.events if d["executor"] == executor]


def test_dispatch_config_matches_builders() -> None:
    cfg = load_dispatch()
    assert cfg.guard.max_concurrent_gpu_runs == 1 and cfg.guard.max_seeds == 5
    assert cfg.modal.app("protenix_v2") == "pah-gpu-protenix-v2"
    for spec in cfg.executors.values():
        if spec.route == "modal":
            assert spec.input in BUILDERS, spec.id
            assert spec.gpu and spec.prediction.get("path"), spec.id
        if spec.route == "none":
            assert spec.reason, spec.id
    assert cfg.executors["vina"].route == "local"
    assert cfg.executors["boltz2"].params["samples"] == 1


def test_exec_token_guard() -> None:
    guard = Guard(require_token_profiles=("modal",))
    check_exec_token(guard, "local", None, env={})
    with pytest.raises(ExecDeniedError, match="not enabled"):
        check_exec_token(guard, "modal", "x", env={})
    with pytest.raises(ExecDeniedError, match="X-Pah-Exec-Token"):
        check_exec_token(guard, "local", "wrong", env={"PAH_EXEC_TOKEN": "s3cret"})
    with pytest.raises(ExecDeniedError):
        check_exec_token(guard, "modal", None, env={"PAH_EXEC_TOKEN": "s3cret"})
    check_exec_token(guard, "modal", "s3cret", env={"PAH_EXEC_TOKEN": "s3cret"})


def test_boltz_yaml_builder() -> None:
    ctx = BuildContext(MANIFEST, [0, 1], {"affinity": True}, {})
    req = BUILDERS["boltz_yaml"](ctx)
    assert req.name == "trypsin_benzamidine" and req.params["input"] == "trypsin_benzamidine.yaml"
    doc = yaml.safe_load(req.files["trypsin_benzamidine.yaml"])
    assert doc["sequences"][0] == {"protein": {"id": "A", "sequence": SEQ}}
    assert doc["sequences"][1] == {"ligand": {"id": "L", "smiles": "NC(=N)c1ccccc1"}}
    assert doc["properties"] == [{"affinity": {"binder": "L"}}]
    fasta = BUILDERS["chai_fasta"](ctx).files["trypsin_benzamidine.fasta"]
    assert fasta.startswith(">protein|name=A\n") and ">ligand|name=L\nNC(=N)c1ccccc1" in fasta
    no_seq = {**MANIFEST, "proteins": [{"id": "trypsin", "uniprot": "P00760"}]}
    with pytest.raises(BuildError, match="no sequence"):
        BUILDERS["boltz_yaml"](BuildContext(no_seq, [0], {}, {}))


def test_receptor_builders_from_reference_entry() -> None:
    pytest.importorskip("gemmi")
    pytest.importorskip("rdkit")
    cif = (ROOT / "tests/fixtures/sources/3PTB.cif").read_bytes()
    ctx = BuildContext(MANIFEST, [0], {}, {}, structures=lambda pid: cif)
    req = BUILDERS["receptor_ligand_box"](ctx)
    rec = req.files["receptor.pdb"]
    assert "ATOM" in rec and "HETATM" not in rec and " BEN " not in rec
    assert "$$$$" in req.files["box_ligand.sdf"] and "$$$$" in req.files["ligand.sdf"]
    dd = BUILDERS["receptor_smiles"](ctx)
    assert dd.params == {"receptor": "receptor.pdb", "ligand": "NC(=N)c1ccccc1",
                         "name": "trypsin_benzamidine"}  # fmt: skip
    no_ref = {**MANIFEST, "receptor": None}
    with pytest.raises(BuildError, match="no reference"):
        BUILDERS["receptor_smiles"](BuildContext(no_ref, [0], {}, {}, structures=lambda p: cif))


def test_stage_runs_dispatches_and_writes_predictions(tmp_path: Path) -> None:
    cfg = _config(
        boltz2=ExecutorDispatch("boltz2", "modal", gpu="A100", input="boltz_yaml",
                                options={"affinity": True}, params={"samples": 1},
                                prediction={"path": "."}),
        diffdock=ExecutorDispatch("diffdock", "modal", gpu="A100", input="receptor_smiles",
                                  prediction={"path": "."}),
        chai1=ExecutorDispatch("chai1", "unreachable", gpu="A100", input="chai_fasta",
                               prediction={"path": "."}),
        pydock=ExecutorDispatch("pydock", "none", reason="academic licence"),
    )  # fmt: skip
    fake, rec = FakeBoltz(), Recorder()
    stage = ExecuteStage(
        cfg, {"modal": fake, "unreachable": Unreachable()}, rec.emit,
        slots=threading.BoundedSemaphore(1), on_change=rec.rows.append,
    )  # fmt: skip
    out = stage.run(MANIFEST, ["boltz2", "diffdock", "chai1", "pydock", "nosuch"], "run-1",
                    tmp_path)  # fmt: skip
    assert rec.phases("pydock") == ["skipped"] and rec.phases("nosuch") == ["skipped"]
    assert rec.phases("chai1") == ["queued", "skipped"]
    # diffdock needs the reference structure; no structure source here, so it is skipped
    assert rec.phases("diffdock") == ["skipped"]
    phases = rec.phases("boltz2")
    assert phases[0] == "queued" and phases[-1] == "done" and "building" in phases
    seeds = {d["seed"] for _, d in rec.events if d["executor"] == "boltz2"} - {None}
    assert seeds == {0, 1, 2, 3, 4}  # capped at guard.max_seeds
    assert all(d["stage"] == "execute" for _, d in rec.events)
    assert fake.jobs[0].request.seeds == [0, 1, 2, 3, 4]
    assert (tmp_path / "predictions/boltz2/inputs/trypsin_benzamidine.yaml").is_file()
    (pred,) = out.manifest["predictions"]
    assert pred["executor"] == "boltz2" and pred["path"] == "predictions/boltz2"
    assert pred["role"] == "primary" and pred["ligand"] == "benzamidine"
    assert pred["seeds"] == [0, 1, 2, 3, 4] and pred["settings"]["route"] == "kit"
    rows = {r["executor"]: r for r in out.executions}
    assert rows["boltz2"]["phase"] == "done" and rows["boltz2"]["route"] == "kit"
    assert rows["pydock"]["message"] == "academic licence"
    assert rec.rows and "predictions" not in MANIFEST


def test_failed_dispatch_adds_no_prediction(tmp_path: Path) -> None:
    class Broken:
        def run(self, job: DispatchJob, progress: execute.Progress) -> dict[str, Any]:
            return {"status": "failed", "error": "boom rc 1", "route": "stock"}

    cfg = _config(boltz2=ExecutorDispatch("boltz2", "modal", input="boltz_yaml",
                                          prediction={"path": "."}))  # fmt: skip
    rec = Recorder()
    out = ExecuteStage(cfg, {"modal": Broken()}, rec.emit).run(MANIFEST, ["boltz2"], "r", tmp_path)
    assert rec.phases("boltz2") == ["queued", "failed"] and "predictions" not in out.manifest
    assert rec.events[-1][1]["message"] == "boom rc 1"


def test_gpu_slot_queues_second_run(tmp_path: Path) -> None:
    cfg = _config(boltz2=ExecutorDispatch("boltz2", "modal", input="boltz_yaml",
                                          prediction={"path": "."}))  # fmt: skip
    slots = threading.BoundedSemaphore(1)
    slots.acquire()
    rec = Recorder()
    stage = ExecuteStage(cfg, {"modal": FakeBoltz()}, rec.emit, slots=slots)
    t = threading.Thread(target=stage.run, args=(MANIFEST, ["boltz2"], "r", tmp_path))
    t.start()
    for _ in range(200):
        if any("waiting for the GPU slot" in d["message"] for _, d in rec.events):
            break
        threading.Event().wait(0.01)
    assert rec.phases("boltz2") == ["queued", "queued"]
    slots.release()
    t.join(10)
    assert rec.phases("boltz2")[-1] == "done"


class FakeSpawner(FakeBoltz):
    """Spawns detached calls: `spawn` returns a handle at once, `wait` writes the outputs."""

    def __init__(self) -> None:
        super().__init__()
        self.spawned: list[str] = []
        self.waited: list[str] = []

    def spawn(self, job: DispatchJob) -> dict[str, Any]:
        call_id = f"fc-{len(self.spawned) + 1}"
        self.spawned.append(call_id)
        return {"callId": call_id, "app": "pah-gpu-boltz2", "function": "predict"}

    def wait(
        self, job: DispatchJob, handle: Mapping[str, Any], progress: execute.Progress
    ) -> dict[str, Any]:
        self.waited.append(str(handle["callId"]))
        return self.run(job, progress)


def test_spawned_calls_are_stored_and_followed(tmp_path: Path) -> None:
    from pah.webui.execute import Eta, estimate_run

    eta = Eta(per_seed_s=100, cold_start_s=40, first_seed_extra_s=10, basis="measured")
    spec = ExecutorDispatch("boltz2", "modal", gpu="A100", input="boltz_yaml",
                            prediction={"path": "."}, eta=eta)  # fmt: skip
    cfg = _config(boltz2=spec)
    fake, rec, stored = FakeSpawner(), Recorder(), []
    stage = ExecuteStage(cfg, {"modal": fake}, rec.emit, on_call=stored.append, run_eta_ms=123)
    out = stage.run({**MANIFEST, "model": {"executor": "boltz2", "seeds": [0, 1]}}, ["boltz2"],
                    "r", tmp_path)  # fmt: skip
    assert fake.spawned == ["fc-1"] and fake.waited == ["fc-1"]
    first, last = stored[0]["boltz2"], stored[-1]["boltz2"]
    assert first["status"] == "spawned" and first["callId"] == "fc-1"
    assert first["seeds"] == [0, 1] and first["etaMs"] == 250_000
    assert last["status"] == "done" and last["entries"][0]["path"] == "predictions/boltz2"
    queued = [d for _, d in rec.events if d["phase"] == "queued"]
    assert queued[0]["etaMs"] == 250_000 and all(d["runEtaMs"] == 123 for _, d in rec.events)
    assert any(d["callId"] == "fc-1" for d in queued)
    assert out.manifest["predictions"][0]["settings"]["route"] == "kit"
    est = estimate_run(cfg, ["boltz2", "nosuch"], [0, 1, 2, 3, 4, 5, 6])
    assert est["etaMs"] == (40 + 10 + 100 * 5) * 1000 and est["gpuSeconds"] == 550.0
    assert est["executors"][0]["seeds"] == 5 and est["complete"] is True


def test_resume_follows_stored_calls_without_spawning(tmp_path: Path) -> None:
    spec = ExecutorDispatch("boltz2", "modal", input="boltz_yaml", prediction={"path": "."})
    cfg = _config(boltz2=spec)
    fake, rec = FakeSpawner(), Recorder()
    calls = {
        "boltz2": {"callId": "fc-9", "app": "pah-gpu-boltz2", "function": "predict",
                   "status": "spawned", "seeds": [3], "name": "trypsin_benzamidine",
                   "ligand": "benzamidine", "params": {"samples": 1}},
        "chai1": {"callId": "fc-8", "status": "done",
                  "entries": [{"executor": "chai1", "path": "predictions/chai1", "seeds": [3]}]},
    }  # fmt: skip
    out = ExecuteStage(cfg, {"modal": fake}, rec.emit).resume(MANIFEST, calls, "r", tmp_path)
    assert fake.spawned == [] and fake.waited == ["fc-9"]
    assert fake.jobs[0].request.seeds == [3] and fake.jobs[0].request.ligand == "benzamidine"
    assert rec.phases("boltz2")[0] == "running" and rec.phases("boltz2")[-1] == "done"
    executors = [p["executor"] for p in out.manifest["predictions"]]
    assert executors == ["boltz2", "chai1"]  # model.executor boltz2 is the primary


def test_local_vina_runs_in_a_child_process(tmp_path: Path) -> None:
    from pah.config import Profile
    from pah.webui.execute import ExecRequest, LocalVinaDispatcher

    profile = Profile(name="local", backend="local", cache_dir=tmp_path, runs_dir=tmp_path)
    spec = ExecutorDispatch("vina", "local", options={"exhaustiveness": 4})
    job = DispatchJob(spec, "r", ExecRequest("x", {}, {}, [0, 2]), tmp_path, tmp_path / "m.yaml")
    argv = LocalVinaDispatcher(profile, python="py").command(job)
    assert argv[:4] == ["py", "-m", "pah.interfaces.cli", "dock"]
    assert argv[argv.index("--seeds") + 1] == "0,2" and "--no-redock" in argv
    assert argv[argv.index("--exhaustiveness") + 1] == "4"
    assert argv[argv.index("--profile") + 1] == "local"
