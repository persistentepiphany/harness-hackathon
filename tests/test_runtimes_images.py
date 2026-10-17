from pathlib import Path

import pytest

from pah.runtimes.images import (
    RecipeError,
    build_image,
    fetch_kits,
    install_native_host,
    native_image_ref,
    render_native_apptainer,
    render_native_dockerfile,
)
from pah.runtimes.models import Route, RuntimeProfile
from pah.runtimes.registry import load_accel, load_runtimes

REG = load_runtimes()


@pytest.fixture
def prof(tmp_path: Path) -> RuntimeProfile:
    return RuntimeProfile(
        launcher="host",
        envs_root=str(tmp_path / "envs"),
        kits_root=str(tmp_path / "kits"),
        images_root=str(tmp_path / "images"),
        weights_root=str(tmp_path / "weights"),
    )


def test_pip_install_pins_the_kit_stock_version(prof: RuntimeProfile) -> None:
    recipe = install_native_host(REG, REG.get("boltz2"), prof)
    assert recipe.commands[0][:3] == ("uv", "venv", "--python")
    assert "boltz[cuda]==2.2.1" in recipe.commands[1]


def test_binary_install_checks_digest(prof: RuntimeProfile) -> None:
    text = install_native_host(REG, REG.get("vina"), prof).render()
    assert "vina_1.2.5_linux_x86_64" in text and "sha256sum -c" in text


def test_image_only_tool_has_no_host_install(prof: RuntimeProfile) -> None:
    with pytest.raises(RecipeError, match="ships as an image"):
        install_native_host(REG, REG.get("diffdock"), prof)


def test_kit_only_tool_has_no_native_route(prof: RuntimeProfile) -> None:
    with pytest.raises(RecipeError, match="no native route"):
        install_native_host(REG, REG.get("alphafold3_of3"), prof)


def test_rendered_dockerfile_and_def_share_steps() -> None:
    rt = REG.get("chai1")
    docker = render_native_dockerfile(REG, rt)
    definition = render_native_apptainer(REG, rt)
    assert docker.startswith(f"FROM {REG.native_image.base}")
    assert "chai_lab==0.6.1" in docker and "chai_lab==0.6.1" in definition
    assert definition.startswith("Bootstrap: docker")


def test_autodock_gpu_recipe_builds_from_pinned_commit() -> None:
    docker = render_native_dockerfile(REG, REG.get("autodock_gpu"))
    assert "nvidia/cuda:12.6.3-devel" in docker
    assert "e63e6f6280ebfad18caa3e8f48afdc269e79e063" in docker and "DEVICE=CUDA" in docker


def test_kit_image_build(prof: RuntimeProfile) -> None:
    recipe = build_image(REG, REG.get("boltz2"), prof, Route.KIT, "apptainer")
    text = recipe.render()
    assert "boltz2/environment/Dockerfile -t boltz2-kit:dev" in text
    assert "boltz2-kit.sif" in text and "boltz2/environment/apptainer.def" in text


def test_pulled_image_to_sif(prof: RuntimeProfile) -> None:
    text = build_image(REG, REG.get("diffdock"), prof, Route.NATIVE, "apptainer").render()
    assert "docker://docker.io/rbgcsail/diffdock:v1.1.3@sha256:" in text


def test_upstream_build_for_alphafold3(prof: RuntimeProfile) -> None:
    text = build_image(REG, REG.get("alphafold3"), prof, Route.NATIVE, "docker").render()
    assert "checkout --detach 03f4f48867748c164ae6d5144ae0529477df02e3" in text
    assert native_image_ref(REG.get("alphafold3")) == "alphafold3:03f4f48"


def test_rendered_build_writes_files(prof: RuntimeProfile) -> None:
    recipe = build_image(REG, REG.get("gnina"), prof, Route.NATIVE, "apptainer")
    assert any(p.suffix == ".def" for p in recipe.files)
    assert recipe.commands[0][:3] == ("apptainer", "build", "--fakeroot")


def test_no_kit_build_raises(prof: RuntimeProfile) -> None:
    with pytest.raises(RecipeError, match="no optimisation kit"):
        build_image(REG, REG.get("vina"), prof, Route.KIT, "docker")


def test_fetch_kits_sparse_checkout(prof: RuntimeProfile) -> None:
    cfg = load_accel()
    cmds = fetch_kits(cfg, REG, prof).commands
    assert cmds[0][-2] == cfg.repo
    assert {"common", "boltz2", "chai1", "protenix_v1", "af3_jax"} <= set(cmds[1])
    assert cmds[2][-1] == cfg.commit
