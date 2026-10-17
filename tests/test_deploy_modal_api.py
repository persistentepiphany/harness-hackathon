"""Static checks of the Modal API and web apps; the modal SDK is not imported."""

import ast
import fnmatch
import re
import subprocess
import sys
import time
import types
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
API_APP = ROOT / "deploy/modal/api_app.py"
WEB_APP = ROOT / "deploy/modal/web_app.py"
SCRIPT = ROOT / "scripts/deploy_modal.sh"
README = ROOT / "deploy/modal/README.md"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text())


def _assigned(path: Path, name: str) -> Any:
    for node in _tree(path).body:
        targets = node.targets if isinstance(node, ast.Assign) else []
        if isinstance(node, ast.AnnAssign):
            targets = [node.target]
        if any(isinstance(t, ast.Name) and t.id == name for t in targets):
            assert node.value is not None
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not assigned in {path.name}")


def _defines(node: ast.stmt, names: tuple[str, ...]) -> bool:
    if isinstance(node, ast.FunctionDef | ast.ClassDef):
        return node.name in names
    if isinstance(node, ast.Assign):
        return any(isinstance(t, ast.Name) and t.id in names for t in node.targets)
    return False


def _load(path: Path, *names: str) -> dict[str, Any]:
    """Executes the module's imports (except modal and yaml) and the named top-level defs."""
    keep: list[ast.stmt] = []
    for node in _tree(path).body:
        if isinstance(node, ast.Import | ast.ImportFrom):
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module]
            if not {"modal", "yaml"} & set(mods):
                keep.append(node)
        elif _defines(node, names):
            keep.append(node)
    namespace: dict[str, Any] = {}
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


def _decorators(path: Path, func: str) -> dict[str, dict[str, ast.expr]]:
    """`{"app.function": {keyword: node}, ...}` for the decorators of a top-level function."""
    for node in _tree(path).body:
        if isinstance(node, ast.FunctionDef) and node.name == func:
            out: dict[str, dict[str, ast.expr]] = {}
            for dec in node.decorator_list:
                assert isinstance(dec, ast.Call)
                out[ast.unparse(dec.func)] = {k.arg: k.value for k in dec.keywords if k.arg}
            return out
    raise AssertionError(f"{func} not defined in {path.name}")


def _modal_profile() -> dict[str, Any]:
    data = yaml.safe_load((ROOT / "configs/profiles/modal.yaml").read_text())
    assert isinstance(data, dict)
    return data


def test_profile_has_api_and_web_settings() -> None:
    prof = _modal_profile()
    api, web = prof["modal"]["api"], prof["modal"]["web"]
    assert (api["app_name"], api["label"]) == ("pah-api", "pah-api")
    assert (web["app_name"], web["label"], web["port"]) == ("pah-web", "pah-web", 3000)
    # SSE pings every 15 s; a stream lives as long as the input timeout.
    assert api["timeout_s"] >= 900 and api["commit_interval_s"] <= 10
    assert 2 <= api["scaledown_window_s"] <= 3600
    assert (prof["runs_dir"], prof["cache_dir"]) == ("/runs", "/cache")
    assert (prof["modal"]["volume_runs"], prof["modal"]["volume_cache"]) == (
        "pah-runs",
        "pah-cache",
    )


def test_profile_still_loads() -> None:
    from pah.config import load_profile

    assert load_profile("modal").backend == "modal"


def test_api_function_is_one_concurrent_asgi_container() -> None:
    decs = _decorators(API_APP, "api")
    fn = decs["app.function"]
    assert ast.literal_eval(fn["max_containers"]) == 1
    assert ast.literal_eval(fn["min_containers"]) == 0
    assert ast.unparse(fn["volumes"]) == "VOLUMES"
    assert "timeout_s" in ast.unparse(fn["timeout"])
    assert "PAH_CORS_ORIGINS" in ast.unparse(fn["env"])
    assert "max_inputs" in ast.unparse(decs["modal.concurrent"]["max_inputs"])
    assert "label" in ast.unparse(decs["modal.asgi_app"]["label"])


def test_api_serves_create_app_and_persists() -> None:
    source = API_APP.read_text()
    body = next(
        ast.unparse(n)
        for n in _tree(API_APP).body
        if isinstance(n, ast.FunctionDef) and n.name == "api"
    )
    assert "create_app_from_env()" in body
    assert "committer.reload()" in body and "committer.start()" in body
    assert "register_persist_hook(committer.request)" in body
    assert "CORSMiddleware" not in body  # one CORS layer, added by pah.webui.settings
    assert source.count("create_if_missing=True") == 2
    assert 'PROFILE_DATA["runs_dir"]: runs' in source
    assert 'PROFILE_DATA["cache_dir"]: cache' in source
    assert _assigned(API_APP, "PERSISTENCE_HOOKS")[0] == "pah.webui.persistence"


def test_api_image_has_checks_report_and_api_extras() -> None:
    source = API_APP.read_text()
    assert 'modal.Image.debian_slim(python_version="3.12")' in source
    assert set(_assigned(API_APP, "EXTRAS")) == {"checks", "report", "api"}
    assert "libgl1" in _assigned(API_APP, "APT_PACKAGES")
    for key in ('"PAH_CONFIG_DIR"', '"PAH_PROFILE": PROFILE', ".workdir(REMOTE_REPO)"):
        assert key in source
    assert _assigned(API_APP, "PROFILE") == "modal"
    import tomllib

    meta = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    reqs = [r for e in ("checks", "report", "api") for r in meta["optional-dependencies"][e]]
    for name in ("rdkit", "gemmi", "pymol-open-source-whl", "fastapi", "sse-starlette"):
        assert any(r.startswith(name) for r in reqs), name


def test_api_image_ignore_keeps_configs_and_examples() -> None:
    ignore = _assigned(API_APP, "IGNORE")
    for pattern in (".venv", ".git", "runs", "cache", "web", "node_modules", "third_party"):
        assert pattern in ignore
    for kept in ("configs", "examples", "src", "pyproject.toml", "schemas"):
        assert not any(fnmatch.fnmatch(kept, p) for p in ignore), kept


def test_repo_path_guarded_for_container() -> None:
    source = API_APP.read_text() + WEB_APP.read_text()
    assert source.count("if modal.is_local() else Path(REMOTE_REPO)") == 2


def test_default_cors_covers_vercel_and_modal_web() -> None:
    defaults = _assigned(API_APP, "DEFAULT_CORS_ORIGINS")
    assert "http://localhost:3000" in defaults
    assert "https://*.vercel.app" in defaults
    assert "https://*--pah-web.*.modal.run" in defaults
    from pah.webui.settings import cors_config

    plain, regex = cors_config(defaults)
    assert regex is not None and "http://localhost:3000" in plain
    pattern = re.compile(regex)
    assert pattern.match("https://harness-git-main-team.vercel.app")
    assert pattern.match("https://ws--pah-web.us-east.modal.run")
    assert pattern.match("https://ws--pah-web.modal.run")
    assert not pattern.match("https://evil.example")
    assert not pattern.match("https://ws--pah-api.us-east.modal.run")


class _FakeVolume:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.commits = 0
        self.reloads = 0

    def commit(self) -> None:
        self.commits += 1
        if self.fail:
            raise RuntimeError("commit refused")

    def reload(self) -> None:
        self.reloads += 1
        if self.fail:
            raise RuntimeError("open files")


def test_volume_committer_commits_on_request_and_survives_failures() -> None:
    ns = _load(API_APP, "VolumeCommitter")
    ns["atexit"] = types.SimpleNamespace(register=lambda fn: fn)  # no final commit at pytest exit
    committer_cls = ns["VolumeCommitter"]
    good, bad = _FakeVolume(), _FakeVolume(fail=True)
    committer = committer_cls({"/runs": good, "/cache": bad}, interval_s=60.0, min_gap_s=0.01)
    committer.reload()
    assert (good.reloads, bad.reloads) == (1, 1)
    committer.start()
    committer.request()
    deadline = time.monotonic() + 5
    while good.commits == 0 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert good.commits >= 1 and bad.commits >= 1


def test_register_persist_hook_uses_first_module(monkeypatch: pytest.MonkeyPatch) -> None:
    ns = _load(API_APP, "PERSISTENCE_HOOKS", "register_persist_hook")
    registered: list[object] = []
    fake = types.ModuleType("pah.webui.persistence")
    fake.on_persist = registered.append  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pah.webui.persistence", fake)
    callback = object()
    assert ns["register_persist_hook"](callback) == "pah.webui.persistence"
    assert registered == [callback]


def test_web_app_serves_node_standalone_build() -> None:
    decs = _decorators(WEB_APP, "web")
    assert ast.literal_eval(decs["app.function"]["max_containers"]) == 1
    assert "port" in ast.unparse(decs["modal.web_server"]["port"])
    env = ast.unparse(decs["app.function"]["env"])
    assert "'HARNESS_API_URL': API_URL" in env
    assert "'NEXT_PUBLIC_HARNESS_MODE': 'live'" in env
    assert _assigned(WEB_APP, "NODE_IMAGE").startswith("node:22")
    assert '"node", "server.js"' in WEB_APP.read_text()


def test_web_server_dir_and_built_api_url(tmp_path: Path) -> None:
    ns = _load(WEB_APP, "REWRITE_SOURCE", "server_dir", "built_api_url")
    standalone = tmp_path / "standalone"
    (standalone / "web").mkdir(parents=True)
    (standalone / "web" / "server.js").write_text("")
    (standalone / "node_modules" / "x").mkdir(parents=True)
    (standalone / "node_modules" / "x" / "server.js").write_text("")
    assert ns["server_dir"](standalone) == standalone / "web"
    assert ns["built_api_url"](tmp_path) is None
    manifest = {
        "rewrites": {
            "beforeFiles": [],
            "afterFiles": [
                {"source": "/api/harness/:path*", "destination": "https://x.modal.run/:path*"}
            ],
            "fallback": [],
        }
    }
    (tmp_path / "routes-manifest.json").write_text(__import__("json").dumps(manifest))
    assert ns["built_api_url"](tmp_path) == "https://x.modal.run"


def test_deploy_script() -> None:
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
    text = SCRIPT.read_text()
    assert "deploy/modal/api_app.py" in text and "deploy/modal/web_app.py" in text
    assert "deploy/modal/urls.json" in text
    assert "NEXT_OUTPUT=standalone" in text and "NEXT_PUBLIC_HARNESS_MODE=live" in text
    for line in text.splitlines():
        if "echo" in line or "printf" in line:
            assert "TOKEN" not in line, line


def test_readme_length_and_style() -> None:
    text = README.read_text()
    assert 30 <= len(text.splitlines()) <= 50
    assert "—" not in text
    assert "modal deploy deploy/modal/api_app.py" in text
