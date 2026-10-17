#!/usr/bin/env bash
# Quick health check for the skills in .claude/skills.
set -uo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
fail=0
ok() { echo "PASS $*"; }
bad() { echo "FAIL $*"; fail=1; }

for file in .claude/skills/*/SKILL.md; do
  dir=$(basename "$(dirname "$file")")
  head=$(awk 'NR==1 && $0!="---"{exit} NR>1 && $0=="---"{exit} NR>1{print}' "$file")
  name=$(printf '%s\n' "$head" | sed -n 's/^name: *//p')
  if [ "$name" = "$dir" ] && printf '%s\n' "$head" | grep -q '^description:'; then ok "skill $dir"; else bad "skill $dir: frontmatter needs name: $dir and a description"; fi
done

npx --no-install playwright-cli --version >/dev/null 2>&1 && ok "playwright-cli $(npx --no-install playwright-cli --version)" || bad "playwright-cli not installed (npm run setup)"
(cd .claude/skills/presentation-skill && npm run --silent doctor >/dev/null 2>&1) && ok "presentation-skill runtime" || bad "presentation-skill runtime (npm run setup)"
for tool in bun uv ffmpeg soffice; do
  command -v "$tool" >/dev/null && ok "$tool" || bad "$tool missing"
done
[ -n "${EACHLABS_API_KEY:-}" ] && ok "EACHLABS_API_KEY set" || echo "WARN EACHLABS_API_KEY not set (sound-effects cannot generate)"
exit $fail
