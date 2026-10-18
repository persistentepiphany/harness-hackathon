"""Serves the Next.js web UI from Modal, for use when no Vercel token is configured.

    scripts/deploy_modal.sh                                 # api, web build, web deploy, URLs
    HARNESS_API_URL=https://<ws>--pah-api.<region>.modal.run modal deploy deploy/modal/web_app.py
    python deploy/modal/web_app.py --url                    # URL of the deployed UI

The image ships a Next.js standalone build made on this machine before deploying:

    cd web && NEXT_OUTPUT=standalone NEXT_DIST_DIR=.next-modal \\
        HARNESS_API_URL=<api url> NEXT_PUBLIC_HARNESS_MODE=live npm run build

The proxy route (`web/app/api/harness/[...path]/route.ts`) reads HARNESS_API_URL per request from
the function environment; `NEXT_PUBLIC_*` variables are inlined at build time. If a build carries a
next.config rewrite for `/api/harness/:path*`, the app refuses to deploy it with a different API
URL. Settings come from the `modal.web` block of configs/profiles/modal.yaml.

    HARNESS_API_URL   base URL of pah-api (default: `api` in deploy/modal/urls.json)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import modal

REMOTE_REPO = "/root/harness"
REMOTE_APP = "/app"
# The Node image has no checkout and no PyYAML: settings reach the container as PAH_WEB_SETTINGS.
REPO = Path(__file__).resolve().parents[2] if modal.is_local() else Path(REMOTE_REPO)
SETTINGS_ENV = "PAH_WEB_SETTINGS"
PROFILE = "modal"
NODE_IMAGE = "node:22-slim"
REWRITE_SOURCE = "/api/harness/:path*"
URLS_FILE = REPO / "deploy" / "modal" / "urls.json"


def _web_settings() -> dict[str, Any]:
    if not modal.is_local():
        return dict(json.loads(os.environ[SETTINGS_ENV]))
    import yaml

    data = yaml.safe_load((REPO / "configs" / "profiles" / f"{PROFILE}.yaml").read_text())
    return dict(data["modal"]["web"])


def server_dir(standalone: Path) -> Path | None:
    """Directory holding the standalone `server.js` (nested when Next traces from a parent)."""
    found = [
        p.parent
        for p in standalone.rglob("server.js")
        if "node_modules" not in p.relative_to(standalone).parts
    ]
    return min(found, key=lambda p: len(p.parts)) if found else None


def built_api_url(dist: Path) -> str | None:
    """Destination origin of the harness rewrite in a build's routes manifest, if present."""
    try:
        manifest = json.loads((dist / "routes-manifest.json").read_text())
    except (OSError, ValueError):
        return None
    rewrites = manifest.get("rewrites", [])
    if isinstance(rewrites, dict):
        rewrites = [r for group in rewrites.values() for r in group]
    for rule in rewrites:
        if rule.get("source") == REWRITE_SOURCE:
            dest = str(rule.get("destination", ""))
            return dest.removesuffix("/:path*")
    return None


def api_url() -> str:
    url = os.environ.get("HARNESS_API_URL", "")
    if not url and URLS_FILE.is_file():
        url = json.loads(URLS_FILE.read_text()).get("api", "")
    return url.rstrip("/")


WEB = _web_settings()
DIST_DIR = str(WEB["dist_dir"])
API_URL = api_url()


def _image() -> tuple[modal.Image, str]:
    """Node 22 image with the standalone build, and the server directory inside it."""
    base = modal.Image.from_registry(NODE_IMAGE, add_python="3.12").env(
        {"NODE_ENV": "production", "NEXT_TELEMETRY_DISABLED": "1"}
    )
    if not modal.is_local():
        return base, os.environ.get("PAH_WEB_SERVER_DIR", REMOTE_APP)
    dist = REPO / "web" / DIST_DIR
    standalone = dist / "standalone"
    server = server_dir(standalone) if standalone.is_dir() else None
    if server is None:
        raise SystemExit(
            f"{standalone}/server.js missing: build with NEXT_OUTPUT=standalone "
            f"NEXT_DIST_DIR={DIST_DIR} (next.config must set output: 'standalone')"
        )
    if not API_URL:
        raise SystemExit("set HARNESS_API_URL to the pah-api URL (or deploy api_app.py first)")
    built = built_api_url(dist)
    if built is not None and built.rstrip("/") != API_URL:
        raise SystemExit(f"build rewrites to {built}, not {API_URL}: rebuild web/ first")
    remote_server = f"{REMOTE_APP}/{server.relative_to(standalone).as_posix()}".rstrip("/.")
    image = base.add_local_dir(standalone, REMOTE_APP, ignore=["**/.env*"])
    image = image.add_local_dir(dist / "static", f"{remote_server}/{DIST_DIR}/static")
    if (REPO / "web" / "public").is_dir():
        image = image.add_local_dir(REPO / "web" / "public", f"{remote_server}/public")
    return image, remote_server


image, SERVER_DIR = _image()
app = modal.App(WEB["app_name"], image=image)


@app.function(
    cpu=float(WEB["cpu"]),
    memory=int(WEB["memory_mb"]),
    timeout=int(WEB["timeout_s"]),
    min_containers=0,
    max_containers=1,
    scaledown_window=int(WEB["scaledown_window_s"]),
    env={
        "HARNESS_API_URL": API_URL,
        "NEXT_PUBLIC_HARNESS_MODE": "live",
        "PAH_WEB_SERVER_DIR": SERVER_DIR,
        SETTINGS_ENV: json.dumps(WEB, sort_keys=True),
    },
)
@modal.concurrent(max_inputs=int(WEB["max_inputs"]))
@modal.web_server(port=int(WEB["port"]), startup_timeout=60, label=WEB["label"])
def web() -> None:
    env = {**os.environ, "PORT": str(WEB["port"]), "HOSTNAME": "0.0.0.0"}
    print(f"pah-web: node server.js in {SERVER_DIR}, HARNESS_API_URL={API_URL}", flush=True)
    subprocess.Popen(["node", "server.js"], cwd=SERVER_DIR, env=env)


def deployed_url() -> str:
    url = modal.Function.from_name(WEB["app_name"], "web").get_web_url()
    if not url:
        raise SystemExit(f"{WEB['app_name']}: no web URL; deploy the app first")
    return str(url)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy pah-web to Modal and print its URL.")
    parser.add_argument("--url", action="store_true", help="only print the deployed URL")
    if not parser.parse_args().url:
        with modal.enable_output():
            app.deploy()
    print(deployed_url())
