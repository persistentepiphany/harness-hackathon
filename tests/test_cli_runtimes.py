import json

from typer.testing import CliRunner

from pah.interfaces.cli import app

runner = CliRunner()


def test_list_jsonl() -> None:
    result = runner.invoke(app, ["runtimes", "list", "--format", "jsonl"])
    assert result.exit_code == 0, result.output
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    kits = {r["id"]: r["kit"] for r in rows}
    assert kits["boltz2"] == "boltz2" and kits["protenix"] == "protenix_v1" and kits["vina"] is None


def test_build_dry_run() -> None:
    result = runner.invoke(
        app,
        ["runtimes", "build", "chai1", "--target", "apptainer", "--profile", "csf3", "--dry-run"],
    )
    assert result.exit_code == 0, result.output
    assert "docker build" in result.stdout and "chai1-kit.sif" in result.stdout


def test_install_dry_run() -> None:
    result = runner.invoke(app, ["runtimes", "install", "protenix", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "protenix==1.1.0" in result.stdout


def test_install_image_only_tool_fails_cleanly() -> None:
    result = runner.invoke(app, ["runtimes", "install", "alphafold3", "--dry-run"])
    assert result.exit_code == 2


def test_kits_fetch_dry_run(tmp_path: object) -> None:
    result = runner.invoke(app, ["runtimes", "kits", "fetch", "--profile", "csf3", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "sparse-checkout" in result.stdout or "checking out" in result.stdout
