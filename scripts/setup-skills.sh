#!/usr/bin/env bash
# Installs what the skills in .claude/skills need. Safe to run repeatedly.
# Runs as the SessionStart hook, or by hand with `npm run setup`.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

log() { echo "[setup-skills] $*" >&2; }

# Playwright CLI (pinned in package.json).
if [ ! -x node_modules/.bin/playwright-cli ]; then
  log "installing @playwright/cli"
  npm install --no-audit --no-fund --loglevel=error
fi

# presentation-skill: Node deps plus its pinned Python runtime in .venv.
pres=.claude/skills/presentation-skill
if [ ! -d "$pres/node_modules" ]; then
  log "installing presentation-skill node deps"
  (cd "$pres" && npm ci --no-audit --no-fund --loglevel=error)
fi
if [ ! -x "$pres/.venv/bin/python" ]; then
  log "setting up presentation-skill python runtime"
  (cd "$pres" && npm run --silent setup:python >/dev/null)
fi

# Browsers. Cloud sessions ship a Chromium under /opt/pw-browsers and block
# browser downloads, so point Playwright and Remotion at it for this session.
if [ "${PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD:-}" = "1" ] && [ -x /opt/pw-browsers/chromium ]; then
  shell=$(ls -d /opt/pw-browsers/chromium_headless_shell-*/chrome-linux/headless_shell 2>/dev/null | tail -1 || true)
  if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
    echo "export PLAYWRIGHT_MCP_EXECUTABLE_PATH=/opt/pw-browsers/chromium" >> "$CLAUDE_ENV_FILE"
    [ -n "$shell" ] && echo "export REMOTION_BROWSER_EXECUTABLE=$shell" >> "$CLAUDE_ENV_FILE"
  fi
  log "using preinstalled Chromium in /opt/pw-browsers"
else
  npx --no-install playwright-cli install-browser chromium >/dev/null 2>&1 || log "could not install Chromium; run: npx playwright-cli install-browser chromium"
fi

# Tools the product-film scripts call.
for tool in bun uv ffmpeg; do
  command -v "$tool" >/dev/null || log "missing $tool (needed by product-film)"
done
log "done"
