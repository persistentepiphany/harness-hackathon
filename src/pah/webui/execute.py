"""Executor dispatch for runs started from the web UI with `execute: true`.

`configs/dispatch.yaml` says, per executor, where it runs (`route`: modal, local or none), which
input builder turns the run manifest into the request, and which manifest `predictions` entry
describes its outputs. GPU executors run as the `predict` function of the deployed Modal app
`pah-gpu-<executor>` (deploy/modal/gpu_app.py); CPU tools run in this process.

`ExecuteStage.run` takes the completed manifest and the selected tools and, for each executor:
emits `queued`, builds the request, dispatches it, turns the function's progress into events as
it changes (`building`, `running` per seed), fetches the outputs into
`runs/<id>/predictions/<executor>/` and appends the `predictions` entry. An executor that cannot
run here (route none, no input builder, inputs missing, app not deployed or not reachable) gets a
`skipped` event with the reason; a dispatched one that fails gets `failed`. Nothing is invented:
an executor without outputs adds no predictions entry, and layers 4-5 report the gap.

Events (contract with the UI): `kind=log`, `stage=execute`, data
    {stage, executor, phase, gpu, route, routeNote, seed, elapsedMs, message}

GPU spend is guarded: `check_exec_token` (header against env, profiles that require it) and a
process-wide semaphore of `guard.max_concurrent_gpu_runs` runs; seeds are capped by `max_seeds`.
"""

from __future__ import annotations

import hmac
import os
import re
import sys
import threading
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import yaml

from pah.config import config_dir

PHASES = ("queued", "building", "running", "done", "failed", "skipped")
_NAME = re.compile(r"[^A-Za-z0-9_]+")


# --------------------------------------------------------------------------- configuration


@dataclass(frozen=True)
class Eta:
    """Duration estimate of one executor call (configs/dispatch.yaml `eta`).

    One call runs its seeds in sequence in one container: cold start, then the first seed with
    its one-off extra (an MSA server query, a compile cache), then the other seeds.
    `basis` is `measured` (with the runs it was measured on in `origin`) or `estimate` (with the
    reasoning in `origin`)."""

    per_seed_s: float
    cold_start_s: float = 0.0
    first_seed_extra_s: float = 0.0
    basis: str = "estimate"
    origin: str = ""
    measured_at: str | None = None

    def seconds(self, n_seeds: int) -> float:
        n = max(1, n_seeds)
        return self.cold_start_s + self.first_seed_extra_s + self.per_seed_s * n

    def wire(self) -> dict[str, Any]:
        return {
            "perSeedS": self.per_seed_s,
            "coldStartS": self.cold_start_s,
            "firstSeedExtraS": self.first_seed_extra_s,
            "basis": self.basis,
            "origin": self.origin,
            "measuredAt": self.measured_at,
        }


def parse_eta(row: Any) -> Eta | None:
    """An `eta` block; None when absent or malformed (the estimate is then reported unknown)."""
    if not isinstance(row, Mapping) or row.get("per_seed_s") is None:
        return None
    try:
        return Eta(
            per_seed_s=float(row["per_seed_s"]),
            cold_start_s=float(row.get("cold_start_s") or 0.0),
            first_seed_extra_s=float(row.get("first_seed_extra_s") or 0.0),
            basis=str(row.get("basis") or "estimate"),
            origin=str(row.get("origin") or ""),
            measured_at=str(row["measured_at"]) if row.get("measured_at") else None,
        )
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class ExecutorDispatch:
    id: str
    route: str
    gpu: str | None = None
    timeout_s: int = 3600
    input: str | None = None
    options: Mapping[str, Any] = field(default_factory=dict)
    params: Mapping[str, Any] = field(default_factory=dict)
    prediction: Mapping[str, str] = field(default_factory=dict)
    max_seeds: int | None = None
    reason: str | None = None
    eta: Eta | None = None
    requires_modules: tuple[str, ...] = ()

    def eta_ms(self, n_seeds: int) -> int | None:
        return None if self.eta is None else int(self.eta.seconds(n_seeds) * 1000)


@dataclass(frozen=True)
class Guard:
    token_env: str = "PAH_EXEC_TOKEN"
    header: str = "X-Pah-Exec-Token"
    require_token_profiles: tuple[str, ...] = ("modal",)
    max_concurrent_gpu_runs: int = 1
    max_seeds: int = 5
    poll_s: float = 5.0


@dataclass(frozen=True)
class ModalSettings:
    app_prefix: str = "pah-gpu-"
    progress_dict: str = "pah-gpu-progress"
    predict_function: str = "predict"
    list_function: str = "list_outputs"
    read_function: str = "read_batch"
    read_batch_bytes: int = 1_500_000

    def app(self, executor: str) -> str:
        return self.app_prefix + executor.replace("_", "-")


@dataclass(frozen=True)
class DispatchConfig:
    guard: Guard
    modal: ModalSettings
    executors: Mapping[str, ExecutorDispatch]


def load_dispatch(path: Path | None = None) -> DispatchConfig:
    """configs/dispatch.yaml. A malformed executor entry is dropped, never fatal."""
    data = yaml.safe_load((path or config_dir() / "dispatch.yaml").read_text(encoding="utf-8"))
    data = data if isinstance(data, dict) else {}
    g = data.get("guard") or {}
    guard = Guard(
        token_env=str(g.get("token_env", Guard.token_env)),
        header=str(g.get("header", Guard.header)),
        require_token_profiles=tuple(g.get("require_token_profiles") or ()),
        max_concurrent_gpu_runs=max(1, int(g.get("max_concurrent_gpu_runs", 1))),
        max_seeds=max(1, int(g.get("max_seeds", Guard.max_seeds))),
        poll_s=float(g.get("poll_s", Guard.poll_s)),
    )
    m = data.get("modal") or {}
    modal = ModalSettings(**{k: m[k] for k in ModalSettings.__dataclass_fields__ if k in m})
    executors: dict[str, ExecutorDispatch] = {}
    for eid, row in (data.get("executors") or {}).items():
        if not isinstance(row, dict) or "route" not in row:
            continue
        executors[str(eid)] = ExecutorDispatch(
            id=str(eid),
            route=str(row["route"]),
            gpu=row.get("gpu"),
            timeout_s=int(row.get("timeout_s", 3600)),
            input=row.get("input"),
            options=dict(row.get("options") or {}),
            params=dict(row.get("params") or {}),
            prediction={str(k): str(v) for k, v in (row.get("prediction") or {}).items()},
            max_seeds=int(row["max_seeds"]) if row.get("max_seeds") else None,
            reason=row.get("reason"),
            eta=parse_eta(row.get("eta")),
            requires_modules=tuple(str(m) for m in row.get("requires_modules") or ()),
        )
    return DispatchConfig(guard, modal, executors)


def seeds_for(cfg: DispatchConfig, spec: ExecutorDispatch, requested: Sequence[int]) -> list[int]:
    """The seeds an executor runs: the requested ones, capped by guard and executor limits."""
    cap = min(cfg.guard.max_seeds, spec.max_seeds or cfg.guard.max_seeds)
    return [int(s) for s in requested][:cap] or [0]


def estimate_run(
    cfg: DispatchConfig, executors: Sequence[str], seeds: Sequence[int]
) -> dict[str, Any]:
    """Wall-time estimate of a run's execute stage from the `eta` blocks.

    GPU executors are spawned together and run in parallel (one container each, seeds in
    sequence); local executors run in this process at the same time, one after another. The run
    estimate is the longer of the two; `gpuSeconds` sums the GPU containers. An executor without
    an estimate is listed with `etaMs: null`, and the run estimate is then a lower bound
    (`complete: false`)."""
    rows: list[dict[str, Any]] = []
    gpu_ms: list[int] = []
    local_ms = 0
    gpu_s = 0.0
    complete = True
    for eid in dict.fromkeys(executors):
        spec = cfg.executors.get(eid)
        if spec is None or spec.route not in ("modal", "local"):
            continue
        run_seeds = seeds_for(cfg, spec, seeds)
        ms = spec.eta_ms(len(run_seeds))
        rows.append(
            {
                "executor": eid,
                "route": spec.route,
                "gpu": spec.gpu,
                "seeds": len(run_seeds),
                "etaMs": ms,
                "basis": spec.eta.basis if spec.eta else None,
                "origin": spec.eta.origin if spec.eta else None,
            }
        )
        if ms is None:
            complete = False
            continue
        if spec.route == "local":
            local_ms += ms
        else:
            gpu_ms.append(ms)
            gpu_s += ms / 1000
    total = max([local_ms, *gpu_ms]) if rows else 0
    return {
        "etaMs": total if rows else None,
        "gpuSeconds": round(gpu_s, 1),
        "complete": complete,
        "parallel": "GPU executors in parallel, seeds in sequence per executor",
        "executors": rows,
    }


# --------------------------------------------------------------------------- guard


class ExecDeniedError(PermissionError):
    """Execution refused on this server; the HTTP layer answers 403."""


def check_exec_token(
    guard: Guard, profile: str, presented: str | None, env: Mapping[str, str] | None = None
) -> None:
    """Raises ExecDeniedError unless the request may start executors."""
    expected = (env if env is not None else os.environ).get(guard.token_env)
    if not expected:
        if profile in guard.require_token_profiles:
            raise ExecDeniedError(
                f"execution is not enabled on this server: {guard.token_env} is not set "
                f"(required for profile {profile})"
            )
        return
    if not presented or not hmac.compare_digest(presented.encode(), expected.encode()):
        raise ExecDeniedError(f"execution needs a valid {guard.header} header")


_GPU_SLOTS: dict[int, threading.BoundedSemaphore] = {}
_SLOTS_LOCK = threading.Lock()


def gpu_slots(n: int) -> threading.BoundedSemaphore:
    """The process-wide semaphore of GPU runs (one per configured size)."""
    with _SLOTS_LOCK:
        return _GPU_SLOTS.setdefault(n, threading.BoundedSemaphore(n))


# --------------------------------------------------------------------------- inputs


class BuildError(ValueError):
    """The manifest lacks what the executor needs; the executor is skipped with this reason."""


@dataclass
class ExecRequest:
    name: str
    files: dict[str, str]
    params: dict[str, Any]
    seeds: list[int]
    ligand: str | None = None  # manifest ligand id the poses belong to (not sent)

    def wire(self) -> dict[str, Any]:
        return {"name": self.name, "files": self.files, "params": self.params, "seeds": self.seeds}


StructureSource = Callable[[str], bytes]
"""PDB id to mmCIF bytes (the harness sources, through the content cache)."""


@dataclass
class BuildContext:
    manifest: Mapping[str, Any]
    seeds: list[int]
    options: Mapping[str, Any]
    params: Mapping[str, Any]
    structures: StructureSource | None = None

    @property
    def proteins(self) -> list[Mapping[str, Any]]:
        return [p for p in self.manifest.get("proteins") or [] if isinstance(p, Mapping)]

    @property
    def ligand(self) -> Mapping[str, Any] | None:
        ligs = [x for x in self.manifest.get("ligands") or [] if isinstance(x, Mapping)]
        return ligs[0] if ligs else None

    def name(self) -> str:
        parts = [str(self.proteins[0].get("id"))] if self.proteins else []
        if self.ligand is not None:
            parts.append(str(self.ligand.get("id")))
        return _NAME.sub("_", "_".join(parts) or "complex").strip("_")[:60] or "complex"

    def sequences(self) -> list[tuple[str, str]]:
        """(chain id, sequence) per protein; BuildError when one has no sequence."""
        out: list[tuple[str, str]] = []
        for i, p in enumerate(self.proteins):
            seq = str(p.get("sequence") or "").replace(" ", "").replace("\n", "")
            if not seq:
                raise BuildError(f"protein {p.get('id')} has no sequence (UniProt lookup failed)")
            out.append((chr(ord("A") + i), seq))
        if not out:
            raise BuildError("no protein in the manifest")
        return out

    def smiles(self) -> str:
        lig = self.ligand
        if lig is None or not lig.get("smiles"):
            raise BuildError("ligand SMILES not resolved in the manifest")
        return str(lig["smiles"])

    def reference_id(self) -> str:
        rec = self.manifest.get("receptor") or {}
        ref = self.manifest.get("reference") or {}
        pid = (rec.get("pdb_id") if isinstance(rec, Mapping) else None) or (
            ref.get("pdb_id") if isinstance(ref, Mapping) else None
        )
        if not pid:
            raise BuildError("no reference PDB entry declared for the receptor")
        return str(pid).upper()

    def reference_structure(self) -> Any:
        import gemmi

        if self.structures is None:
            raise BuildError("no structure source configured for receptor preparation")
        pid = self.reference_id()
        try:
            data = self.structures(pid)
        except Exception as exc:  # recorded as the skip reason
            raise BuildError(f"{pid} mmCIF unavailable: {type(exc).__name__}: {exc}") from exc
        doc = gemmi.cif.read_string(data.decode("utf-8", "replace"))
        st = gemmi.make_structure_from_block(doc.sole_block())
        st.setup_entities()
        st.remove_hydrogens()
        return st

    def receptor_pdb(self) -> str:
        """Protein chains of the reference entry (receptor.chains when declared), no HETATM."""
        st = self.reference_structure()
        rec = self.manifest.get("receptor") or {}
        chains = set(rec.get("chains") or []) if isinstance(rec, Mapping) else set()
        st.remove_ligands_and_waters()
        for model in st:
            for name in [c.name for c in model if chains and c.name not in chains]:
                model.remove_chain(name)
            break
        while len(st) > 1:
            del st[1]
        st.setup_entities()
        return str(st.make_pdb_string())

    def reference_ligand_sdf(self) -> str:
        """The crystal ligand of the reference entry as SDF (bond orders from the SMILES)."""
        from rdkit import Chem

        from pah.checks.outputs import residue_mol

        ref = self.manifest.get("reference") or {}
        lig = self.ligand or {}
        code = (ref.get("ligand") if isinstance(ref, Mapping) else None) or lig.get("ccd")
        if not code:
            raise BuildError("no CCD code for the reference ligand, so no box can be derived")
        st = self.reference_structure()
        for chain in st[0]:
            for res in chain:
                if res.name == str(code).upper():
                    mol, _ = residue_mol(res, lig.get("smiles"))
                    return str(Chem.MolToMolBlock(mol)) + "$$$$\n"
        raise BuildError(f"ligand {code} not found in {self.reference_id()}")

    def ligand_sdf(self) -> str:
        """3D conformer of the declared SMILES (ETKDG, MMFF), seed 0."""
        from rdkit import Chem
        from rdkit.Chem import AllChem

        mol = Chem.MolFromSmiles(self.smiles())
        if mol is None:
            raise BuildError(f"ligand SMILES {self.smiles()!r} does not parse")
        mol = Chem.AddHs(mol)
        if AllChem.EmbedMolecule(mol, randomSeed=0) != 0:  # type: ignore[attr-defined]
            raise BuildError("RDKit could not embed a 3D conformer for the ligand")
        AllChem.MMFFOptimizeMolecule(mol)  # type: ignore[attr-defined]
        return str(Chem.MolToMolBlock(mol)) + "$$$$\n"


InputBuilder = Callable[[BuildContext], ExecRequest]
BUILDERS: dict[str, InputBuilder] = {}


def input_builder(name: str) -> Callable[[InputBuilder], InputBuilder]:
    def wrap(fn: InputBuilder) -> InputBuilder:
        BUILDERS[name] = fn
        return fn

    return wrap


@input_builder("boltz_yaml")
def _boltz_yaml(ctx: BuildContext) -> ExecRequest:
    seqs: list[dict[str, Any]] = [
        {"protein": {"id": cid, "sequence": seq}} for cid, seq in ctx.sequences()
    ]
    doc: dict[str, Any] = {"version": 1, "sequences": seqs}
    lig = ctx.ligand
    if lig is not None:
        if lig.get("smiles"):
            seqs.append({"ligand": {"id": "L", "smiles": str(lig["smiles"])}})
        elif lig.get("ccd"):
            seqs.append({"ligand": {"id": "L", "ccd": str(lig["ccd"])}})
        else:
            raise BuildError("ligand has neither SMILES nor CCD code")
        if ctx.options.get("affinity"):
            doc["properties"] = [{"affinity": {"binder": "L"}}]
    name = ctx.name()
    text = yaml.safe_dump(doc, sort_keys=False)
    return ExecRequest(
        name, {f"{name}.yaml": text}, {"input": f"{name}.yaml", "name": name}, ctx.seeds
    )


@input_builder("chai_fasta")
def _chai_fasta(ctx: BuildContext) -> ExecRequest:
    lines = [f">protein|name={cid}\n{seq}" for cid, seq in ctx.sequences()]
    if ctx.ligand is not None:
        lines.append(f">ligand|name=L\n{ctx.smiles()}")
    name = ctx.name()
    return ExecRequest(
        name, {f"{name}.fasta": "\n".join(lines) + "\n"}, {"input": f"{name}.fasta"}, ctx.seeds
    )


@input_builder("protenix_json")
def _protenix_json(ctx: BuildContext) -> ExecRequest:
    import json

    seqs: list[dict[str, Any]] = [
        {"proteinChain": {"sequence": seq, "count": 1}} for _, seq in ctx.sequences()
    ]
    lig = ctx.ligand
    if lig is not None:
        value = str(lig["smiles"]) if lig.get("smiles") else f"CCD_{lig.get('ccd')}"
        if not lig.get("smiles") and not lig.get("ccd"):
            raise BuildError("ligand has neither SMILES nor CCD code")
        seqs.append({"ligand": {"ligand": value, "count": 1}})
    name = ctx.name()
    text = json.dumps([{"name": name, "sequences": seqs}], indent=1)
    return ExecRequest(
        name, {f"{name}.json": text}, {"input": f"{name}.json", "name": name}, ctx.seeds
    )


@input_builder("colabfold_fasta")
def _colabfold_fasta(ctx: BuildContext) -> ExecRequest:
    name = ctx.name()
    chains = ":".join(seq for _, seq in ctx.sequences())
    return ExecRequest(
        name, {f"{name}.fasta": f">{name}\n{chains}\n"}, {"input": f"{name}.fasta"}, ctx.seeds
    )


@input_builder("openfold3_json")
def _openfold3_json(ctx: BuildContext) -> ExecRequest:
    import json

    chains: list[dict[str, Any]] = [
        {"molecule_type": "protein", "chain_ids": [cid], "sequence": seq}
        for cid, seq in ctx.sequences()
    ]
    if ctx.ligand is not None:
        chains.append({"molecule_type": "ligand", "chain_ids": ["L"], "smiles": ctx.smiles()})
    name = ctx.name()
    text = json.dumps({"queries": {name: {"chains": chains}}}, indent=1)
    return ExecRequest(name, {f"{name}.json": text}, {"input": f"{name}.json"}, ctx.seeds)


@input_builder("receptor_smiles")
def _receptor_smiles(ctx: BuildContext) -> ExecRequest:
    name = ctx.name()
    files = {"receptor.pdb": ctx.receptor_pdb()}
    params = {"receptor": "receptor.pdb", "ligand": ctx.smiles(), "name": name}
    return ExecRequest(name, files, params, ctx.seeds)


@input_builder("receptor_ligand_box")
def _receptor_ligand_box(ctx: BuildContext) -> ExecRequest:
    files = {
        "receptor.pdb": ctx.receptor_pdb(),
        "ligand.sdf": ctx.ligand_sdf(),
        "box_ligand.sdf": ctx.reference_ligand_sdf(),
    }
    params = {"receptor": "receptor.pdb", "ligand": "ligand.sdf", "box_ligand": "box_ligand.sdf"}
    return ExecRequest(ctx.name(), files, params, ctx.seeds)


# --------------------------------------------------------------------------- dispatchers


class DispatchUnavailableError(RuntimeError):
    """The executor's function is not deployed or not reachable: the executor is skipped."""


Progress = Callable[[Mapping[str, Any]], None]


@dataclass
class DispatchJob:
    executor: ExecutorDispatch
    run_id: str
    request: ExecRequest
    dest: Path
    manifest_path: Path | None = None


class Dispatcher(Protocol):
    """Runs one executor job, reports progress snapshots and returns the execution record.

    The record carries at least `status` (done | failed), and optionally `route`, `routeNote`,
    `gpu`, `error`, `seeds`; outputs are written under `job.dest`. Raises
    DispatchUnavailableError when the executor cannot be reached at all.
    """

    def run(self, job: DispatchJob, progress: Progress) -> dict[str, Any]: ...


class SpawningDispatcher(Dispatcher, Protocol):
    """A dispatcher whose calls run detached from this process (fire and forget).

    `spawn` starts the call and returns at once with a handle ({callId, app, function}) that is
    stored in runs/<id>/dispatch.json; `wait` follows a handle (also one read back after a
    restart) until the call ends, fetches the outputs and returns the execution record."""

    def spawn(self, job: DispatchJob) -> dict[str, Any]: ...

    def wait(
        self, job: DispatchJob, handle: Mapping[str, Any], progress: Progress
    ) -> dict[str, Any]: ...


def can_spawn(dispatcher: Dispatcher) -> bool:
    return callable(getattr(dispatcher, "spawn", None)) and callable(
        getattr(dispatcher, "wait", None)
    )


# Modal exceptions that end a spawned call without a result (the poll timeout is TimeoutError).
_CALL_ENDED = frozenset({"FunctionTimeoutError", "OutputExpiredError", "InputCancellation"})


class ModalDispatcher:
    """`pah-gpu-<executor>.predict` through the Modal client, outputs read back in batches."""

    def __init__(self, settings: ModalSettings, poll_s: float = 5.0) -> None:
        self.settings = settings
        self.poll_s = poll_s

    def _function(self, executor: str, name: str) -> Any:
        try:
            import modal
        except ImportError as exc:
            raise DispatchUnavailableError(f"modal client not installed: {exc}") from exc
        app = self.settings.app(executor)
        try:
            fn = modal.Function.from_name(app, name)
            fn.hydrate()
        except Exception as exc:  # not deployed, no credentials, network
            raise DispatchUnavailableError(
                f"Modal function {app}.{name} not deployed or not reachable: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        return fn

    def _progress_store(self) -> Any:
        try:
            import modal

            return modal.Dict.from_name(self.settings.progress_dict)
        except Exception:  # progress is optional; completion still arrives
            return None

    def run(self, job: DispatchJob, progress: Progress) -> dict[str, Any]:
        return self.wait(job, self.spawn(job), progress)

    def spawn(self, job: DispatchJob) -> dict[str, Any]:
        """Starts `pah-gpu-<executor>.predict` and returns its handle without waiting."""
        ex = job.executor.id
        predict = self._function(ex, self.settings.predict_function)
        try:
            call = predict.spawn(job.run_id, job.request.wire())
        except Exception as exc:  # quota, auth or network at submission
            raise DispatchUnavailableError(
                f"{self.settings.app(ex)}.{self.settings.predict_function}: spawn failed: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        return {
            "callId": str(call.object_id),
            "app": self.settings.app(ex),
            "function": self.settings.predict_function,
        }

    def _call(self, call_id: str) -> Any:
        try:
            import modal

            return modal.FunctionCall.from_id(call_id)
        except Exception as exc:  # recorded as the executor's skip reason
            raise DispatchUnavailableError(
                f"Modal call {call_id} not readable: {type(exc).__name__}: {exc}"
            ) from exc

    def wait(
        self, job: DispatchJob, handle: Mapping[str, Any], progress: Progress
    ) -> dict[str, Any]:
        """Polls a spawned call (progress from the `pah-gpu-progress` Dict) until it returns,
        then reads its outputs back into `job.dest`."""
        ex = job.executor.id
        call = self._call(str(handle["callId"]))
        store = self._progress_store()
        key = f"{job.run_id}/{ex}"
        deadline = time.monotonic() + job.executor.timeout_s + 600
        record: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            try:
                record = call.get(timeout=self.poll_s)
                break
            except Exception as exc:  # poll timeout, or the call failed, timed out or expired
                kind = type(exc).__name__
                if kind in _CALL_ENDED:
                    return {"status": "failed", "error": f"{kind}: {exc}"}
                if kind != "TimeoutError":
                    raise
            if store is not None:
                try:
                    state = store.get(key)
                except Exception:  # a missed snapshot is caught up by the next one
                    state = None
                if isinstance(state, Mapping):
                    progress(state)
        if record is None:
            call.cancel()
            return {"status": "failed", "error": f"no result within {job.executor.timeout_s} s"}
        self._fetch(ex, job.run_id, job.dest)
        return dict(record)

    def _fetch(self, executor: str, run_id: str, dest: Path) -> list[Path]:
        lister = self._function(executor, self.settings.list_function)
        reader = self._function(executor, self.settings.read_function)
        files = lister.remote(run_id)
        limit = self.settings.read_batch_bytes
        batches: list[list[tuple[str, int, int]]] = []
        batch: list[tuple[str, int, int]] = []
        size = 0
        for f in files:
            total = int(f["bytes"])
            for start in range(0, max(total, 1), limit):
                n = min(limit, total - start)
                if batch and size + n > limit:
                    batches.append(batch)
                    batch, size = [], 0
                batch.append((str(f["path"]), start, n))
                size += n
        if batch:
            batches.append(batch)
        parts: dict[str, list[bytes]] = {}
        for b in batches:
            for (rel, _, _), data in zip(b, reader.remote(run_id, b), strict=True):
                parts.setdefault(rel, []).append(data)
        root = dest.resolve()
        written: list[Path] = []
        for rel, chunks in parts.items():
            target = (root / rel).resolve()
            if not target.is_relative_to(root):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"".join(chunks))
            written.append(target)
        return written


class UnavailableDispatcher:
    """A route this server cannot use (offline profile, no client): every job is skipped with
    the reason, so the gap is recorded and never silent."""

    def __init__(self, reason: str) -> None:
        self.reason = reason

    def run(self, job: DispatchJob, progress: Progress) -> dict[str, Any]:
        raise DispatchUnavailableError(self.reason)


class LocalVinaDispatcher:
    """AutoDock Vina on this host through `pah dock` in a child process.

    A child process, not this one: Vina's SWIG bindings loaded next to Open Babel's (PLIP, in the
    layer 4 checks) abort the process on the first Open Babel iterator (`terminate called after
    throwing an instance of 'swig::stop_iteration'`), so the API process never imports vina."""

    def __init__(self, profile: Any, python: str | None = None) -> None:
        self.profile = profile
        self.python = python or sys.executable

    def command(self, job: DispatchJob) -> list[str]:
        assert job.manifest_path is not None
        redock = bool(job.executor.options.get("redock", False))
        return [
            self.python, "-m", "pah.interfaces.cli", "dock", str(job.manifest_path),
            "--out", str(job.dest), "--profile", str(self.profile.name),
            "--seeds", ",".join(str(s) for s in job.request.seeds),
            "--exhaustiveness", str(int(job.executor.options.get("exhaustiveness", 8))),
            "--redock" if redock else "--no-redock", "--format", "jsonl",
        ]  # fmt: skip

    def run(self, job: DispatchJob, progress: Progress) -> dict[str, Any]:
        import subprocess

        if job.manifest_path is None:
            raise DispatchUnavailableError("vina: no manifest file to dock from")
        argv = self.command(job)
        progress({"phase": "running", "route": "local", "gpu": None,
                  "message": f"vina, {len(job.request.seeds)} seed(s): pah dock"})  # fmt: skip
        t0 = time.monotonic()
        try:
            proc = subprocess.run(
                argv, capture_output=True, text=True, timeout=job.executor.timeout_s, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"status": "failed", "route": "local",
                    "error": f"pah dock: {type(exc).__name__}: {exc}"}  # fmt: skip
        (job.dest / "dock.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
        out = job.dest / "manifest.yaml"
        data = yaml.safe_load(out.read_text(encoding="utf-8")) if out.is_file() else None
        preds = [p for p in (data or {}).get("predictions") or [] if p.get("executor") == "vina"]
        error = None
        if not preds:
            tail = (proc.stderr or proc.stdout).strip().splitlines()[-3:]
            error = f"pah dock exit {proc.returncode}, no vina predictions: {' | '.join(tail)}"
        ms = int((time.monotonic() - t0) * 1000)
        phase = "done" if preds else "failed"
        per_seed = ms // max(1, len(job.request.seeds))  # one process docks the seeds in turn
        return {
            "status": phase,
            "route": "local",
            "elapsedMs": ms,
            "seeds": [{"seed": s, "phase": phase, "ms": per_seed} for s in job.request.seeds],
            "predictions": preds,
            "error": error,
        }


# --------------------------------------------------------------------------- stage


Emit = Callable[[str, Mapping[str, Any]], None]
"""(message, data) appended to the run's events."""


@dataclass
class ExecuteOutcome:
    manifest: dict[str, Any]
    executions: list[dict[str, Any]]


CallSink = Callable[[Mapping[str, Mapping[str, Any]]], None]
"""Receives every executor's call record (runs/<id>/dispatch.json `calls`) when one changes."""

# Execution row fields that progress snapshots and records may set (UiExecution).
_ROW_FIELDS = ("gpu", "route", "routeNote", "startedAt", "mode", "kit", "kitVersion")


@dataclass
class _Planned:
    spec: ExecutorDispatch
    request: ExecRequest


def _utc() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class ExecuteStage:
    """Runs the selected executors of one run and returns the manifest with predictions.

    GPU executors whose dispatcher can spawn are started detached (`SpawningDispatcher.spawn`),
    their handles go to `on_call` at once (the caller stores them in runs/<id>/dispatch.json),
    and the stage then follows them; `resume` follows stored handles again after a restart."""

    def __init__(
        self,
        config: DispatchConfig,
        dispatchers: Mapping[str, Dispatcher],
        emit: Emit,
        *,
        slots: threading.BoundedSemaphore | None = None,
        on_change: Callable[[list[dict[str, Any]]], None] | None = None,
        on_call: CallSink | None = None,
        run_eta_ms: int | None = None,
    ) -> None:
        self.config = config
        self.dispatchers = dispatchers
        self.emit = emit
        self.slots = slots or gpu_slots(config.guard.max_concurrent_gpu_runs)
        self.on_change = on_change
        self.on_call = on_call
        self.run_eta_ms = run_eta_ms
        self._lock = threading.Lock()
        self._rows: dict[str, dict[str, Any]] = {}
        self._calls: dict[str, dict[str, Any]] = {}

    # one row per executor, the UiExecution shape (web/lib/types.ts)
    def _row(self, eid: str) -> dict[str, Any]:
        spec = self.config.executors.get(eid)
        return self._rows.setdefault(
            eid,
            {
                "executor": eid,
                "name": eid,
                "phase": "queued",
                "gpu": spec.gpu if spec else None,
                "route": None,
                "routeNote": None,
                "mode": None,
                "kit": None,
                "kitVersion": None,
                "startedAt": None,
                "elapsedMs": None,
                "etaMs": None,
                "callId": None,
                "seeds": [],
                "message": None,
            },
        )

    def _event(
        self, eid: str, phase: str, message: str, seed: int | None = None, **extra: Any
    ) -> None:
        with self._lock:
            row = self._row(eid)
            row.update({k: v for k, v in extra.items() if k in row})
            row["phase"], row["message"] = phase, message
            data = {
                "stage": "execute",
                "executor": eid,
                "phase": phase,
                "gpu": row.get("gpu"),
                "route": row.get("route"),
                "routeNote": row.get("routeNote"),
                "mode": row.get("mode"),
                "kit": row.get("kit"),
                "kitVersion": row.get("kitVersion"),
                "seed": seed,
                "elapsedMs": row.get("elapsedMs"),
                "etaMs": row.get("etaMs"),
                "runEtaMs": self.run_eta_ms,
                "callId": row.get("callId"),
                "message": message,
            }
            self.emit(f"execute {eid}: {phase}" + (f" seed {seed}" if seed is not None else "")
                      + f" ({message})", data)  # fmt: skip
            rows = [dict(r) for r in self._rows.values()]
        if self.on_change is not None:
            self.on_change(rows)

    def _store_call(self, eid: str, **changes: Any) -> None:
        with self._lock:
            self._calls.setdefault(eid, {}).update(changes)
            calls = {k: dict(v) for k, v in self._calls.items()}
        if self.on_call is not None:
            self.on_call(calls)

    def run(
        self,
        manifest: Mapping[str, Any],
        tools: Sequence[str],
        run_id: str,
        run_dir: Path,
        *,
        structures: StructureSource | None = None,
        manifest_path: Path | None = None,
        names: Mapping[str, str] | None = None,
    ) -> ExecuteOutcome:
        out = dict(manifest)
        model = out.get("model") if isinstance(out.get("model"), Mapping) else {}
        assert isinstance(model, Mapping)
        all_seeds = [int(s) for s in model.get("seeds") or [0]]
        planned: list[_Planned] = []
        for eid in dict.fromkeys(tools):
            self._row(eid)["name"] = (names or {}).get(eid, eid)
            p = self._plan(out, eid, all_seeds, structures)
            if p is not None:
                planned.append(p)
        preds = self._execute(planned, run_id, run_dir, manifest_path, {})
        return self._outcome(out, model, preds)

    def _plan(
        self,
        manifest: Mapping[str, Any],
        eid: str,
        all_seeds: list[int],
        structures: StructureSource | None,
    ) -> _Planned | None:
        spec = self.config.executors.get(eid)
        if spec is None:
            self._event(eid, "skipped", "no entry in configs/dispatch.yaml")
            return None
        if spec.route not in self.dispatchers:
            self._event(eid, "skipped", spec.reason or f"route {spec.route} not available here")
            return None
        seeds = seeds_for(self.config, spec, all_seeds)
        cap = len(seeds)
        note = f"; seeds capped at {cap}" if len(all_seeds) > cap else ""
        builder = BUILDERS.get(spec.input or "")
        if spec.route != "local" and builder is None:
            self._event(eid, "skipped", f"no input builder {spec.input!r}")
            return None
        try:
            ctx = BuildContext(manifest, seeds, spec.options, spec.params, structures)
            request = builder(ctx) if builder else ExecRequest(ctx.name(), {}, {}, seeds)
        except BuildError as exc:
            self._event(eid, "skipped", f"inputs: {exc}")
            return None
        except Exception as exc:  # a builder bug skips this executor only
            self._event(eid, "skipped", f"inputs: {type(exc).__name__}: {exc}")
            return None
        request.params = {**spec.params, **request.params}
        request.ligand = str(ctx.ligand["id"]) if ctx.ligand and ctx.ligand.get("id") else None
        eta = spec.eta_ms(len(seeds))
        with self._lock:
            self._row(eid)["seeds"] = [{"seed": s, "phase": "queued", "ms": None} for s in seeds]
        basis = f"; estimate {round(eta / 1000)} s ({spec.eta.basis})" if eta and spec.eta else ""
        self._event(eid, "queued", f"{spec.route}, {len(seeds)} seed(s){note}{basis}", etaMs=eta)
        return _Planned(spec, request)

    def resume(
        self,
        manifest: Mapping[str, Any],
        calls: Mapping[str, Mapping[str, Any]],
        run_id: str,
        run_dir: Path,
        *,
        manifest_path: Path | None = None,
        rows: Sequence[Mapping[str, Any]] = (),
    ) -> ExecuteOutcome:
        """Follows the calls a previous process spawned (dispatch.json) to their end."""
        out = dict(manifest)
        model = out.get("model") if isinstance(out.get("model"), Mapping) else {}
        assert isinstance(model, Mapping)
        for r in rows:
            if r.get("executor"):
                self._row(str(r["executor"])).update(dict(r))
        self._calls = {k: dict(v) for k, v in calls.items()}
        planned: list[_Planned] = []
        handles: dict[str, Mapping[str, Any]] = {}
        preds: list[dict[str, Any]] = []
        for eid, call in calls.items():
            status = call.get("status")
            if status == "done":
                preds += [dict(e) for e in call.get("entries") or [] if isinstance(e, Mapping)]
                continue
            if status != "spawned":
                continue
            spec = self.config.executors.get(eid)
            if spec is None or spec.route not in self.dispatchers:
                self._event(eid, "failed", f"cannot resume call {call.get('callId')}: no route")
                self._store_call(eid, status="failed", endedAt=_utc())
                continue
            seeds = [int(s) for s in call.get("seeds") or [0]]
            params = dict(call.get("params") or {})
            ligand = str(call["ligand"]) if call.get("ligand") else None
            request = ExecRequest(str(call.get("name") or eid), {}, params, seeds, ligand)
            planned.append(_Planned(spec, request))
            handles[eid] = call
        preds += self._execute(planned, run_id, run_dir, manifest_path, handles)
        return self._outcome(out, model, preds)

    def _execute(
        self,
        planned: list[_Planned],
        run_id: str,
        run_dir: Path,
        manifest_path: Path | None,
        handles: Mapping[str, Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        """Local executors run while the GPU executors (one GPU run per server) are followed."""
        preds: list[dict[str, Any]] = []
        if not planned:
            return preds
        gpu = [p for p in planned if p.spec.route != "local"]
        local = [p for p in planned if p.spec.route == "local"]

        def go(p: _Planned) -> list[dict[str, Any]]:
            handle = handles.get(p.spec.id)
            return self._dispatch(p.spec, p.request, run_id, run_dir, manifest_path, handle)

        with ThreadPoolExecutor(max_workers=len(planned), thread_name_prefix="pah-exec") as pool:
            local_futures = [pool.submit(go, p) for p in local]
            if gpu:
                with self._gpu_slot([p.spec.id for p in gpu]):
                    for f in [pool.submit(go, p) for p in gpu]:
                        preds += f.result()
            for f in local_futures:
                preds += f.result()
        return preds

    def _outcome(
        self, out: dict[str, Any], model: Mapping[str, Any], preds: list[dict[str, Any]]
    ) -> ExecuteOutcome:
        if preds:
            primary = model.get("executor")
            ordered = sorted(preds, key=lambda p: p["executor"] != primary)
            for i, p in enumerate(ordered):
                p["role"] = "primary" if i == 0 else "secondary"
            out["predictions"] = [*(out.get("predictions") or []), *ordered]
        with self._lock:
            rows = [dict(r) for r in self._rows.values()]
        return ExecuteOutcome(out, rows)

    @contextmanager
    def _gpu_slot(self, eids: list[str]) -> Iterator[None]:
        if not self.slots.acquire(blocking=False):
            for eid in eids:
                self._event(eid, "queued", "waiting for the GPU slot (one GPU run at a time)")
            self.slots.acquire()
        try:
            yield
        finally:
            self.slots.release()

    def _dispatch(
        self,
        spec: ExecutorDispatch,
        request: ExecRequest,
        run_id: str,
        run_dir: Path,
        manifest_path: Path | None,
        handle: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        eid = spec.id
        dest = run_dir / "predictions" / eid
        dest.mkdir(parents=True, exist_ok=True)
        for fname, text in request.files.items():
            (dest / "inputs").mkdir(exist_ok=True)
            (dest / "inputs" / fname).write_text(text, encoding="utf-8")
        spawned = float(handle["spawnedEpoch"]) if handle and handle.get("spawnedEpoch") else None
        t0 = time.monotonic() - (time.time() - spawned if spawned else 0.0)
        seen: dict[str, Any] = {}

        def elapsed() -> int:
            return int((time.monotonic() - t0) * 1000)

        def progress(state: Mapping[str, Any]) -> None:
            phase = str(state.get("phase") or "running")
            phase = phase if phase in ("building", "running") else "running"
            extra = {k: state[k] for k in _ROW_FIELDS if k in state}
            seeds = state.get("seeds") if isinstance(state.get("seeds"), list) else None
            changed = (phase, state.get("message")) != seen.get("phase")
            if seeds is not None:
                with self._lock:
                    self._row(eid)["seeds"] = [dict(s) for s in seeds]
                for s in seeds:
                    sid, sp = s.get("seed"), s.get("phase")
                    if seen.get(f"seed{sid}") != sp and sp in ("running", "done", "failed"):
                        seen[f"seed{sid}"] = sp
                        self._event(
                            eid, phase, f"seed {sid} {sp}", seed=sid, elapsedMs=elapsed(), **extra
                        )
                        changed = False
            if changed:
                seen["phase"] = (phase, state.get("message"))
                self._event(
                    eid, phase, str(state.get("message") or phase), elapsedMs=elapsed(), **extra
                )

        job = DispatchJob(spec, run_id, request, dest, manifest_path)
        dispatcher = self.dispatchers[spec.route]
        try:
            if can_spawn(dispatcher):
                record = self._spawned(dispatcher, job, handle, progress)
            else:
                record = dispatcher.run(job, progress)
        except DispatchUnavailableError as exc:
            self._event(eid, "skipped", str(exc))
            if eid in self._calls:
                self._store_call(eid, status="skipped", endedAt=_utc(), error=str(exc))
            return []
        except Exception as exc:  # recorded; the run continues with the other executors
            error = f"{type(exc).__name__}: {exc}"
            self._event(eid, "failed", error, elapsedMs=elapsed())
            if eid in self._calls:
                self._store_call(eid, status="failed", endedAt=_utc(), error=error)
            return []
        extra = {k: record[k] for k in _ROW_FIELDS if k in record and k != "startedAt"}
        if isinstance(record.get("seeds"), list):
            with self._lock:
                self._row(eid)["seeds"] = [dict(s) for s in record["seeds"]]
        if record.get("status") != "done":
            error = str(record.get("error") or "no outputs")
            self._event(eid, "failed", error, elapsedMs=elapsed(), **extra)
            if eid in self._calls:
                self._store_call(eid, status="failed", endedAt=_utc(), error=error)
            return []
        self._event(eid, "done", f"outputs in predictions/{eid}", elapsedMs=elapsed(), **extra)
        if "predictions" in record:  # the local route declares its own entries
            entries = [self._relocate(p, dest, run_dir) for p in record["predictions"]]
        else:
            entries = self._entries(spec, request, record, run_dir)
        if eid in self._calls:
            self._store_call(eid, status="done", endedAt=_utc(), entries=entries)
        return entries

    def _spawned(
        self,
        dispatcher: Dispatcher,
        job: DispatchJob,
        handle: Mapping[str, Any] | None,
        progress: Progress,
    ) -> dict[str, Any]:
        """Spawns the call (or takes the stored handle), records it, then follows it."""
        sp: Any = dispatcher
        eid = job.executor.id
        if handle is None:
            handle = dict(sp.spawn(job))
            self._store_call(
                eid,
                **handle,
                status="spawned",
                spawnedAt=_utc(),
                spawnedEpoch=time.time(),
                seeds=list(job.request.seeds),
                name=job.request.name,
                ligand=job.request.ligand,
                params=dict(job.request.params),
                etaMs=job.executor.eta_ms(len(job.request.seeds)),
            )
            self._event(
                eid,
                "queued",
                f"spawned {handle.get('app')}.{handle.get('function')} (call {handle['callId']})",
                callId=handle["callId"],
            )
        else:
            self._event(eid, "running", f"following call {handle['callId']} after a restart",
                        callId=handle["callId"])  # fmt: skip
        result: dict[str, Any] = sp.wait(job, handle, progress)
        return result

    @staticmethod
    def _relocate(entry: Mapping[str, Any], dest: Path, run_dir: Path) -> dict[str, Any]:
        out = dict(entry)
        for key in ("path", "receptor"):
            if out.get(key):
                out[key] = os.path.relpath((dest / str(out[key])).resolve(), run_dir.resolve())
        return out

    def _entries(
        self, spec: ExecutorDispatch, request: ExecRequest, record: Mapping[str, Any], run_dir: Path
    ) -> list[dict[str, Any]]:
        base = f"predictions/{spec.id}"
        template = spec.prediction.get("path", ".")
        per_seed = "{seed}" in template
        groups = [[s] for s in request.seeds] if per_seed else [request.seeds]
        settings = {
            k: v
            for k, v in {
                "route": record.get("route"),
                "route_note": record.get("routeNote"),
                "gpu": record.get("gpu"),
                "kit": record.get("kit"),
                "mode": record.get("mode"),
                "kit_version": record.get("kitVersion"),
                "modal_image": (record.get("modal") or {}).get("MODAL_IMAGE_ID"),
                "modal_call": record.get("callId"),
            }.items()
            if isinstance(v, str | int | float | bool)
        }
        entries: list[dict[str, Any]] = []
        for seeds in groups:
            path = template.format(seed=seeds[0]).strip("/")
            rel = base if path in ("", ".") else f"{base}/{path}"
            if not (run_dir / rel).exists():
                continue
            entry: dict[str, Any] = {"executor": spec.id, "path": rel, "seeds": list(seeds)}
            if record.get("version"):
                entry["version"] = str(record["version"])
            if request.ligand:
                entry["ligand"] = request.ligand
            if spec.prediction.get("receptor"):
                entry["receptor"] = f"{base}/{spec.prediction['receptor']}"
            entry["settings"] = settings
            entries.append(entry)
        return entries
