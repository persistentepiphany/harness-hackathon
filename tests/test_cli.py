import json

from typer.testing import CliRunner

from pah import __version__
from pah.interfaces.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0 and __version__ in result.stdout


def test_doctor_dry_run_jsonl() -> None:
    result = runner.invoke(app, ["doctor", "--dry-run", "--only", "skills", "--format", "jsonl"])
    assert result.exit_code == 0, result.output
    events = [json.loads(line) for line in result.stdout.splitlines()]
    assert events[-1]["kind"] == "run_end"
    assert any("humanizer.remote" in e["message"] for e in events)


def test_doctor_dry_run_profiles() -> None:
    for profile in ("csf3", "modal"):
        result = runner.invoke(app, ["doctor", "--dry-run", "--profile", profile])
        assert result.exit_code == 0, result.output
