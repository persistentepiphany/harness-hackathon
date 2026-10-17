import pytest

from pah.runtimes.accel import (
    AccelUnavailableError,
    Availability,
    RuntimeUnavailableError,
    decide,
    parse_kit_line,
    select_card,
)
from pah.runtimes.hardware import Gpu
from pah.runtimes.models import Policy, Route
from pah.runtimes.registry import load_accel, load_runtimes

REG = load_runtimes()
CFG = load_accel()
OK = Availability(True, "here")
NO = Availability(False, "absent")

H100 = Gpu(0, "NVIDIA H100 80GB HBM3", 9.0, 81559, "580.65.06")
H200 = Gpu(0, "NVIDIA H200", 9.0, 143771, "580.65.06")
L40S = Gpu(0, "NVIDIA L40S", 8.9, 46068, "580.65.06")
V100 = Gpu(0, "Tesla V100-SXM2-32GB", 7.0, 32768, "580.65.06")
OLD_DRIVER = Gpu(0, "NVIDIA A100-SXM4-80GB", 8.0, 81920, "550.54.15")


def _decide(
    eid: str,
    gpus: list[Gpu],
    *,
    policy: Policy = Policy.AUTO,
    mode: str = "fast",
    kit: Availability = OK,
    native: Availability = OK,
):  # type: ignore[no-untyped-def]
    return decide(REG.get(eid), CFG, policy=policy, mode=mode, gpus=gpus, kit=kit, native=native)


def test_defaults_are_auto_and_fast() -> None:
    assert CFG.policy is Policy.AUTO and CFG.mode == "fast"


def test_kit_engages_on_h100() -> None:
    d = _decide("boltz2", [H100])
    assert d.route is Route.KIT and d.card == "h100" and d.mode == "fast" and d.accelerated
    assert d.reasons == ()


def test_name_rule_picks_h200() -> None:
    assert select_card(H200, REG.get("protenix_v2").accel, CFG) == "h200"  # type: ignore[arg-type]


def test_ada_card_uses_a100_config() -> None:
    assert _decide("chai1", [L40S]).card == "a100"


def test_low_compute_capability_runs_stock_in_kit_image() -> None:
    d = _decide("boltz2", [V100])
    assert d.route is Route.KIT_OFF and d.mode == "off"
    assert any("compute capability 7.0" in r for r in d.reasons)


def test_old_driver_runs_native() -> None:
    d = _decide("boltz2", [OLD_DRIVER])
    assert d.route is Route.NATIVE
    assert any("driver 550.54.15" in r for r in d.reasons)


def test_kit_missing_falls_back_and_says_why() -> None:
    d = _decide("protenix", [H100], kit=NO)
    assert d.route is Route.NATIVE
    assert any("not available: absent" in r for r in d.reasons)


def test_policy_kit_refuses_instead_of_falling_back() -> None:
    with pytest.raises(AccelUnavailableError, match="no NVIDIA GPU"):
        _decide("boltz2", [], policy=Policy.KIT)


def test_policy_stock_skips_kit() -> None:
    d = _decide("boltz2", [H100], policy=Policy.STOCK)
    assert d.route is Route.KIT_OFF and d.reasons == ("policy stock",)


def test_mode_off_is_stock() -> None:
    assert _decide("chai1", [H100], mode="off").route is Route.KIT_OFF


def test_exact_mode_passes_through() -> None:
    d = _decide("chai1", [H100], mode="exact")
    assert d.route is Route.KIT and d.mode == "exact"


def test_unknown_mode_rejected() -> None:
    with pytest.raises(ValueError, match="unknown kit mode"):
        _decide("boltz2", [H100], mode="turbo")


def test_alphafold3_never_uses_of3_kit() -> None:
    d = _decide("alphafold3", [H100])
    assert d.route is Route.NATIVE and d.kit is None
    assert "different model" in d.reasons[0]


def test_no_kit_executor_runs_native() -> None:
    d = _decide("diffdock", [H100])
    assert d.route is Route.NATIVE


def test_nothing_available_raises() -> None:
    with pytest.raises(RuntimeUnavailableError, match="nothing to run"):
        _decide("gnina", [H100], native=NO)


def test_kit_only_executor_without_kit_raises() -> None:
    with pytest.raises(RuntimeUnavailableError):
        _decide("alphafold3_of3", [H100], kit=NO, native=NO)


@pytest.mark.parametrize(
    ("line", "active"),
    [
        ("[boltz2-opt] ACTIVE mode=fast card=h100 levers=a+b", True),
        ("[boltz2-opt] NOT ACTIVE: reason=core_missing:opt_core", False),
        ("[protenix-v1-opt] ACTIVE mode=exact", True),
        ("[af3-jax-opt] NOT ACTIVE mode=big reason=cc", False),
        ("[chai1-opt] NOT ACTIVE mode=off (stock: nothing applied)", False),
    ],
)
def test_parse_kit_line(line: str, active: bool) -> None:
    status = parse_kit_line(line)
    assert status is not None and status.active is active


def test_parse_kit_line_ignores_other_output() -> None:
    assert parse_kit_line("Predicting structures: 100%") is None
