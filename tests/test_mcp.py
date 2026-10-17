import asyncio
import json
from typing import Any

import pytest

from pah.config import Profile
from tests.conftest import ROOT

mcp = pytest.importorskip("mcp")
from mcp.client.client import Client  # noqa: E402

from pah.interfaces.mcp_server import build_server  # noqa: E402


def _call(server: Any, name: str, args: dict[str, Any], progress: list[Any] | None = None) -> Any:
    async def go() -> Any:
        async def on_progress(p: float, total: float | None, message: str | None) -> None:
            if progress is not None:
                progress.append((p, total, message))

        async with Client(server) as client:
            return await client.call_tool(name, args, progress_callback=on_progress)

    return asyncio.run(go())


def _payload(result: Any) -> Any:
    assert not result.is_error, result.content
    if result.structured_content is not None:
        data = result.structured_content
        return (
            data.get("result", data) if isinstance(data, dict) and set(data) == {"result"} else data
        )
    return json.loads(result.content[0].text)


def test_tools_listed(offline_profile: Profile) -> None:
    async def go() -> list[str]:
        async with Client(build_server(offline_profile)) as client:
            tools = await client.list_tools()
            return [t.name for t in tools.tools]

    names = asyncio.run(go())
    assert {
        "pah_run",
        "pah_batch",
        "pah_doctor",
        "pah_list_tasks",
        "pah_get_report",
        "pah_get_findings",
    } <= set(names)


def test_run_streams_progress_and_returns_verdict(offline_profile: Profile) -> None:
    server = build_server(offline_profile)
    progress: list[Any] = []
    path = str(ROOT / "examples/3ptb_ligand_pose/manifest.yaml")
    summary = _payload(_call(server, "pah_run", {"manifest_path": path}, progress))
    assert summary["verdict"] == "pass_with_warnings"
    assert summary["warnings"][0]["check"] == "l1.ligand.stereo_defined"
    assert len(progress) == 13 and progress[-1][1] == 13

    report = _call(server, "pah_get_report", {"run_id": summary["run_id"]})
    assert "## Layers" in report.content[0].text

    stops = _payload(
        _call(server, "pah_get_findings", {"run_id": summary["run_id"], "gate": "warn"})
    )
    assert [f["check_id"] for f in stops] == ["l1.ligand.stereo_defined"]


def test_run_inline_manifest(offline_profile: Profile) -> None:
    manifest = {
        "task": "virtual_screening",
        "ligands": [{"id": "benzamidine", "ccd": "BEN", "smiles": "NC(=N)c1ccccc1"}],
        "model": {"executor": "gnina", "version": "1.3"},
    }
    summary = _payload(
        _call(build_server(offline_profile), "pah_run", {"manifest": manifest, "report": False})
    )
    assert summary["verdict"] in {"pass", "pass_with_warnings"} and summary["stops"] == []
    assert summary["report_md"] is None


def test_bad_manifest_is_a_tool_error(offline_profile: Profile) -> None:
    result = _call(
        build_server(offline_profile),
        "pah_run",
        {"manifest": {"task": "ligand_pose", "ligands": [{"id": "x"}]}},
    )
    assert result.is_error


def test_resources(offline_profile: Profile) -> None:
    async def go() -> tuple[str, str]:
        async with Client(build_server(offline_profile)) as client:
            task = await client.read_resource("pah://tasks/ligand_pose")
            schema = await client.read_resource("pah://schemas/manifest")
            return task.contents[0].text, schema.contents[0].text  # type: ignore[union-attr]

    task, schema = asyncio.run(go())
    assert json.loads(task)["claim"] == "Pose within stated uncertainty"
    assert "proteins" in json.loads(schema)["properties"]


def test_ui_record_resource_and_html_report(profile: Profile) -> None:
    pytest.importorskip("numpy")
    pytest.importorskip("matplotlib")
    from pah.config import resolve_path
    from pah.report import write_run_report
    from tests.conftest import FakeRenderer
    from tests.synthetic import write_synthetic_run

    run = write_synthetic_run(resolve_path(profile.runs_dir) / "synthetic")
    write_run_report(run, renderer=FakeRenderer())
    server = build_server(profile)

    async def go() -> str:
        async with Client(server) as client:
            res = await client.read_resource("pah://runs/synthetic/ui_record.json")
            return res.contents[0].text  # type: ignore[union-attr]

    ui = json.loads(asyncio.run(go()))
    assert ui["source"] == "pah" and ui["verdict"]["outcome"] == "narrowed"
    html = _call(server, "pah_get_report", {"run_id": "synthetic", "format": "html"})
    assert 'data-testid="verdict"' in html.content[0].text
