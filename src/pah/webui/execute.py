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
        )
    return DispatchConfig(guard, modal, executors)


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
        ex = job.executor.id
        predict = self._function(ex, self.settings.predict_function)
        store = self._progress_store()
        key = f"{job.run_id}/{ex}"
        call = predict.spawn(job.run_id, job.request.wire())
        deadline = time.monotonic() + job.executor.timeout_s + 600
        record: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            try:
                record = call.get(timeout=self.poll_s)
                break
            except TimeoutError:
                pass
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
    """AutoDock Vina in this process through `pah.service.dock_manifest`."""

    def __init__(self, profile: Any) -> None:
        self.profile = profile

    def run(self, job: DispatchJob, progress: Progress) -> dict[str, Any]:
        from pah.service import dock_manifest

        if job.manifest_path is None:
            raise DispatchUnavailableError("vina: no manifest file to dock from")
        progress({"phase": "running", "route": "local", "gpu": None,
                  "message": f"vina, {len(job.request.seeds)} seeds"})  # fmt: skip
        t0 = time.monotonic()
        out = dock_manifest(
            job.manifest_path,
            self.profile,
            job.dest,
            seeds=job.request.seeds,
            exhaustiveness=int(job.executor.options.get("exhaustiveness", 8)),
            redock=bool(job.executor.options.get("redock", False)),
        )
        data = yaml.safe_load(out.read_text(encoding="utf-8")) or {}
        preds = [p for p in data.get("predictions") or [] if p.get("executor") == "vina"]
        return {
            "status": "done" if preds else "failed",
            "route": "local",
            "elapsedMs": int((time.monotonic() - t0) * 1000),
            "predictions": preds,
            "error": None if preds else "dock_manifest declared no vina predictions",
        }


# --------------------------------------------------------------------------- stage


Emit = Callable[[str, Mapping[str, Any]], None]
"""(message, data) appended to the run's events."""


@dataclass
class ExecuteOutcome:
    manifest: dict[str, Any]
    executions: list[dict[str, Any]]


class ExecuteStage:
    """Runs the selected executors of one run and returns the manifest with predictions."""

    def __init__(
        self,
        config: DispatchConfig,
        dispatchers: Mapping[str, Dispatcher],
        emit: Emit,
        *,
        slots: threading.BoundedSemaphore | None = None,
        on_change: Callable[[list[dict[str, Any]]], None] | None = None,
    ) -> None:
        self.config = config
        self.dispatchers = dispatchers
        self.emit = emit
        self.slots = slots or gpu_slots(config.guard.max_concurrent_gpu_runs)
        self.on_change = on_change
        self._lock = threading.Lock()
        self._rows: dict[str, dict[str, Any]] = {}

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
                "startedAt": None,
                "elapsedMs": None,
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
                "seed": seed,
                "elapsedMs": row.get("elapsedMs"),
                "message": message,
            }
            self.emit(f"execute {eid}: {phase}" + (f" seed {seed}" if seed is not None else "")
                      + f" ({message})", data)  # fmt: skip
            rows = [dict(r) for r in self._rows.values()]
        if self.on_change is not None:
            self.on_change(rows)

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
        jobs: list[tuple[ExecutorDispatch, ExecRequest]] = []
        for eid in dict.fromkeys(tools):
            self._row(eid)["name"] = (names or {}).get(eid, eid)
            spec = self.config.executors.get(eid)
            if spec is None:
                self._event(eid, "skipped", "no entry in configs/dispatch.yaml")
                continue
            if spec.route not in self.dispatchers:
                self._event(eid, "skipped", spec.reason or f"route {spec.route} not available here")
                continue
            cap = min(self.config.guard.max_seeds, spec.max_seeds or self.config.guard.max_seeds)
            seeds = all_seeds[:cap] or [0]
            note = f"; seeds capped at {cap}" if len(all_seeds) > cap else ""
            builder = BUILDERS.get(spec.input or "")
            if spec.route != "local" and builder is None:
                self._event(eid, "skipped", f"no input builder {spec.input!r}")
                continue
            try:
                ctx = BuildContext(out, seeds, spec.options, spec.params, structures)
                request = builder(ctx) if builder else ExecRequest(ctx.name(), {}, {}, seeds)
            except BuildError as exc:
                self._event(eid, "skipped", f"inputs: {exc}")
                continue
            except Exception as exc:  # a builder bug skips this executor only
                self._event(eid, "skipped", f"inputs: {type(exc).__name__}: {exc}")
                continue
            request.params = {**spec.params, **request.params}
            request.ligand = str(ctx.ligand["id"]) if ctx.ligand and ctx.ligand.get("id") else None
            with self._lock:
                self._row(eid)["seeds"] = [
                    {"seed": s, "phase": "queued", "ms": None} for s in seeds
                ]
            self._event(eid, "queued", f"{spec.route}, {len(seeds)} seed(s){note}")
            jobs.append((spec, request))
        preds: list[dict[str, Any]] = []
        gpu = [(s, r) for s, r in jobs if s.route != "local"]
        local = [(s, r) for s, r in jobs if s.route == "local"]
        for spec, request in local:
            preds += self._dispatch(spec, request, run_id, run_dir, manifest_path)
        if gpu:
            with (
                self._gpu_slot([s.id for s, _ in gpu]),
                ThreadPoolExecutor(max_workers=len(gpu), thread_name_prefix="pah-exec") as pool,
            ):
                futures = [
                    pool.submit(self._dispatch, s, r, run_id, run_dir, manifest_path)
                    for s, r in gpu
                ]
                for f in futures:
                    preds += f.result()
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
    ) -> list[dict[str, Any]]:
        eid = spec.id
        dest = run_dir / "predictions" / eid
        dest.mkdir(parents=True, exist_ok=True)
        for fname, text in request.files.items():
            (dest / "inputs").mkdir(exist_ok=True)
            (dest / "inputs" / fname).write_text(text, encoding="utf-8")
        t0 = time.monotonic()
        seen: dict[str, Any] = {}

        def progress(state: Mapping[str, Any]) -> None:
            elapsed = int((time.monotonic() - t0) * 1000)
            phase = str(state.get("phase") or "running")
            phase = phase if phase in ("building", "running") else "running"
            extra = {k: state[k] for k in ("gpu", "route", "routeNote", "startedAt") if k in state}
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
                            eid, phase, f"seed {sid} {sp}", seed=sid, elapsedMs=elapsed, **extra
                        )
                        changed = False
            if changed:
                seen["phase"] = (phase, state.get("message"))
                self._event(
                    eid, phase, str(state.get("message") or phase), elapsedMs=elapsed, **extra
                )

        job = DispatchJob(spec, run_id, request, dest, manifest_path)
        dispatcher = self.dispatchers[spec.route]
        try:
            record = dispatcher.run(job, progress)
        except DispatchUnavailableError as exc:
            self._event(eid, "skipped", str(exc))
            return []
        except Exception as exc:  # recorded; the run continues with the other executors
            self._event(eid, "failed", f"{type(exc).__name__}: {exc}",
                        elapsedMs=int((time.monotonic() - t0) * 1000))  # fmt: skip
            return []
        elapsed = int((time.monotonic() - t0) * 1000)
        extra = {k: record[k] for k in ("gpu", "route", "routeNote") if k in record}
        if isinstance(record.get("seeds"), list):
            with self._lock:
                self._row(eid)["seeds"] = [dict(s) for s in record["seeds"]]
        if record.get("status") != "done":
            self._event(
                eid, "failed", str(record.get("error") or "no outputs"), elapsedMs=elapsed, **extra
            )
            return []
        self._event(eid, "done", f"outputs in predictions/{eid}", elapsedMs=elapsed, **extra)
        if "predictions" in record:  # the local route declares its own entries
            return [self._relocate(p, dest, run_dir) for p in record["predictions"]]
        return self._entries(spec, request, record, run_dir)

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
                "modal_image": (record.get("modal") or {}).get("MODAL_IMAGE_ID"),
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
