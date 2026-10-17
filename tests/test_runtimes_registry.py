import pytest

from pah.runtimes.hardware import detect_gpus, parse_nvidia_smi
from pah.runtimes.registry import (
    MissingParameterError,
    fill,
    load_accel,
    load_runtimes,
    placeholders,
)

REG = load_runtimes()
CFG = load_accel()

# Placeholders the runner fills itself; everything else comes from --param or defaults.
RUNTIME = {"out_dir", "weights", "kit", "kit_dir", "card", "mode"}
# Inputs a caller passes per run, by executor family.
INPUTS = {"input", "receptor", "ligand", "box_ligand", "box", "maps_fld", "name"}

REQUESTED = {
    "protenix",
    "boltz2",
    "boltz1",
    "chai1",
    "diffdock",
    "vina",
    "autodock_gpu",
    "alphafold3",
}


def test_requested_tools_present() -> None:
    assert {rt.id for rt in REG.executors} >= REQUESTED


def test_executor_ids_match_executors_yaml() -> None:
    from pah.config import load_yaml

    known = {e["id"] for e in load_yaml("executors.yaml")["executors"]}
    ours = {rt.id for rt in REG.executors}
    # Runtime-only entries: protenix_v2, alphafold3_of3, openfold3 and autodock_gpu have kits or
    # images but no reachability probes in executors.yaml yet.
    assert ours - known <= {"protenix_v2", "alphafold3_of3", "openfold3", "autodock_gpu"}


@pytest.mark.parametrize("rt", REG.executors, ids=lambda rt: rt.id)
def test_every_executor_has_a_route(rt) -> None:  # type: ignore[no-untyped-def]
    assert rt.native is not None or rt.accel is not None


@pytest.mark.parametrize("rt", REG.executors, ids=lambda rt: rt.id)
def test_templates_only_use_known_placeholders(rt) -> None:  # type: ignore[no-untyped-def]
    allowed = RUNTIME | INPUTS | set(rt.defaults)
    templates = []
    if rt.native:
        templates += [rt.native.command, *rt.native.env.values()]
    if rt.accel:
        templates += [rt.accel.command, *rt.accel.env.values()]
    for t in templates:
        items = [t] if isinstance(t, str) else list(t)
        assert placeholders(items) <= allowed, (rt.id, placeholders(items) - allowed)


@pytest.mark.parametrize("rt", [r for r in REG.executors if r.accel], ids=lambda rt: rt.id)
def test_kit_specs(rt) -> None:  # type: ignore[no-untyped-def]
    spec = rt.accel
    assert set(spec.modes) == {"off", "exact", "fast", "big"}
    assert set(spec.configs) <= {"a100", "h100", "h200", "b200", "b300"}
    assert spec.outputs_kit and spec.outputs_off


def test_stock_versions_match_kit_pins() -> None:
    for rt in REG.executors:
        if rt.accel and rt.native:
            assert rt.native.version in rt.accel.stock, rt.id


def test_kit_commit_is_pinned() -> None:
    assert len(CFG.commit) == 40


def test_profiles_cover_deploy_targets() -> None:
    assert {"local", "csf3", "modal"} <= set(REG.profiles)
    assert REG.profile("csf3").launcher == "apptainer"


def test_fill() -> None:
    assert fill(["a", "{x}-{y}"], {"x": 1, "y": "b"}) == ("a", "1-b")
    with pytest.raises(MissingParameterError, match="z"):
        fill(["{z}"], {})


SMI = """0, NVIDIA H100 80GB HBM3, 9.0, 81559, 580.65.06
1, NVIDIA L40S, 8.9, 46068, 580.65.06
garbage line
"""


def test_parse_nvidia_smi() -> None:
    gpus = parse_nvidia_smi(SMI)
    assert [g.name for g in gpus] == ["NVIDIA H100 80GB HBM3", "NVIDIA L40S"]
    assert gpus[1].compute_capability == 8.9 and gpus[0].driver_major == 580


def test_detect_gpus_handles_failures() -> None:
    assert detect_gpus(runner=lambda argv: "") == []

    def boom(argv: list[str]) -> str:
        raise OSError("no device")

    assert detect_gpus(runner=boom) == []
    assert len(detect_gpus(runner=lambda argv: SMI)) == 2
