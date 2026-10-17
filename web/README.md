# Harness web UI

Next.js 16 (App Router, TypeScript, Tailwind CSS v4) port of `design/prototype/Harness v2.dc.html`.
The contract is `../docs/UI.md`; routes, components and tokens follow `design/prototype/HANDOFF.md`.
Screenshots of each prototype view at 1440x900 are in `design/reference-shots/<view>.png`.

## Modes

| Mode | Data | Set with |
| --- | --- | --- |
| live (default) | `pah serve` through the proxy `/api/harness/*` → `${HARNESS_API_URL}/*` | `HARNESS_API_URL` |
| mock | prototype data and simulator in the browser (`lib/mock/`) | `NEXT_PUBLIC_HARNESS_MODE=mock` |

Live mode never falls back to mock: when `/health` fails the nav shows `disconnected` and pages show the
API error with a retry. Mock options: `?seed=7` (or `NEXT_PUBLIC_MOCK_SEED`) fixes ids and timings,
`?simSpeed=2` (`NEXT_PUBLIC_MOCK_SIM_SPEED`), `?maxConcurrent=1`, and `window.__harnessMock` exposes
`pause()`, `resume()`, `advance(ms)` and `setSimSpeed(n)` for tests and recordings.

## Run

```bash
npm install                                    # once; versions are pinned
NEXT_PUBLIC_HARNESS_MODE=mock npm run dev -- -p 3100
HARNESS_API_URL=http://127.0.0.1:8000 npm run dev            # live, port 3000
NEXT_DIST_DIR=.next-mine npx next dev -p 3105  # separate build dir for a parallel server
npm run build && npm start                     # production; NEXT_OUTPUT=standalone for Modal
```

| Variable | Where | Meaning |
| --- | --- | --- |
| `HARNESS_API_URL` | server, read per request | Base URL of `pah serve` (local or the Modal endpoint) |
| `HARNESS_PROXY_TIMEOUT_MS` | server | Wait for the first byte from the API, default 60000 (Modal cold starts take about 30 s) |
| `NEXT_PUBLIC_HARNESS_MODE` | build time | `live` or `mock` |
| `NEXT_DIST_DIR` | build and dev | Build directory, default `.next` |

The proxy (`app/api/harness/[...path]/route.ts`) streams SSE unbuffered and returns
`{"error": {"code": "upstream_timeout" | "upstream_unreachable", "message"}}` with 504 or 502.
Behind an HTTP proxy, start Node with `NODE_USE_ENV_PROXY=1` so the server-side fetch uses it.

Vercel (`vercel.json`): set `NEXT_PUBLIC_HARNESS_MODE=mock` in the project for a demo without a
backend, or `HARNESS_API_URL` to the Modal endpoint for live data. Nothing is deployed from here.

## Test

```bash
npm run typecheck && npm run lint && npm test  # tsc, eslint, vitest (unit + live fixtures)
npm run e2e:mock                               # Playwright, mock dev server on 3100
E2E_PROJECT=live HARNESS_API_URL=http://127.0.0.1:8000 npx playwright test --project=live
```
