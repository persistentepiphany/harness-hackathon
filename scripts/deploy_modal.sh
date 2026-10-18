#!/usr/bin/env bash
# Deploys the harness on Modal: pah-api, then the web UI built against it as pah-web.
# Prints both URLs and writes them to deploy/modal/urls.json (URLs only, no credentials).
#
#   scripts/deploy_modal.sh              # api and web
#   SKIP_WEB=1 scripts/deploy_modal.sh   # api only
#
# Needs MODAL_TOKEN_ID and MODAL_TOKEN_SECRET (or ~/.modal.toml); MODAL_API_TOKEN_ID and
# MODAL_API_TOKEN_SECRET are used when the first pair is unset. Behind an HTTPS proxy the modal
# client needs python-socks: uv pip install --python .venv/bin/python 'modal[api-proxy-support]'.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PY:-$ROOT/.venv/bin/python}"
MODAL="${MODAL:-$ROOT/.venv/bin/modal}"
URLS="$ROOT/deploy/modal/urls.json"

if [[ -z "${MODAL_TOKEN_ID:-}" && -n "${MODAL_API_TOKEN_ID:-}" ]]; then
  export MODAL_TOKEN_ID="$MODAL_API_TOKEN_ID"
  export MODAL_TOKEN_SECRET="${MODAL_API_TOKEN_SECRET:-}"
fi

cd "$ROOT"
"$MODAL" deploy deploy/modal/api_app.py
API_URL="$("$PY" deploy/modal/api_app.py --url)"
health_s="$(curl -fsS -o /dev/null -w '%{time_total}' --max-time 300 "$API_URL/health")"
echo "api: $API_URL (first /health after deploy: ${health_s} s)"

WEB_URL=""
if [[ "${SKIP_WEB:-0}" != 1 ]]; then
  DIST_DIR="$("$PY" -c 'import yaml
print(yaml.safe_load(open("configs/profiles/modal.yaml"))["modal"]["web"]["dist_dir"])')"
  (
    cd web
    [[ -d node_modules ]] || npm ci
    NEXT_OUTPUT=standalone NEXT_DIST_DIR="$DIST_DIR" HARNESS_API_URL="$API_URL" \
      NEXT_PUBLIC_HARNESS_MODE=live npm run build
  )
  HARNESS_API_URL="$API_URL" "$MODAL" deploy deploy/modal/web_app.py
  WEB_URL="$(HARNESS_API_URL="$API_URL" "$PY" deploy/modal/web_app.py --url)"
fi

"$PY" - "$URLS" "$API_URL" "$WEB_URL" <<'EOF'
import datetime
import json
import sys
from pathlib import Path

path, api, web = sys.argv[1:4]
data = {
    "api": api,
    "web": web or None,
    "deployedAt": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
}
Path(path).write_text(json.dumps(data, indent=2) + "\n")
EOF
echo "api: $API_URL"
echo "web: ${WEB_URL:-not deployed}"
echo "urls: $URLS"
