# Modal deployment

Modal is the default deployment target. All apps read `configs/profiles/modal.yaml`.

| App | File | What it runs |
| --- | --- | --- |
| `pah-api` | `api_app.py` | HTTP API with `/ui` routes (`create_app_from_env`), runs in threads, CPU |
| `pah-web` | `web_app.py` | Next.js UI from a standalone build, used when Vercel is not |
| `pah-<executor>` | `executors_app.py` | One executor on a GPU (see `docs/RUNTIMES.md`) |
| `pah-doctor` | `doctor_app.py` | `pah doctor --profile modal` |

## Deploy

```bash
uv pip install --python .venv/bin/python 'modal[api-proxy-support]>=0.64'
modal deploy deploy/modal/api_app.py    # API only; prints the endpoint URL
scripts/deploy_modal.sh                 # API, web build against it, web deploy, urls.json
```

Credentials come from `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET` or `~/.modal.toml`. Behind an
HTTPS proxy the client needs python-socks, from the `api-proxy-support` extra.

## URLs and volumes

Endpoints have the form `https://<workspace>--pah-api.<region>.modal.run` (and `--pah-web`), are
public with no authentication, and the last deployed pair is in `deploy/modal/urls.json`.

Volumes `pah-runs` (at `/runs`) and `pah-cache` (at `/cache`) are created on first deploy, reloaded
when a container starts, and committed after each write reported through `pah.webui.persistence`
and every 10 s. `modal volume get pah-runs <id> runs/<id>` copies a run to this machine.

## Containers and cold start

The API runs in one container (`max_containers=1`, 100 concurrent inputs), so SSE tails and the
runs they follow share a process. With `min_containers=0`, the first request after an idle period
starts a container (7.2 s for `/health` on 2026-10-17). It stays up 60 min after its last request
(`scaledown_window_s`). A run in progress is lost when the container stops or a redeploy replaces
it. An SSE response ends at the 3600 s input timeout and the client reconnects.

## Vercel

Set `HARNESS_API_URL` in the Vercel project to the `api` URL from `urls.json` and redeploy; the
`/api/harness/*` route reads it on each request. The API accepts CORS from localhost:3000,
`https://*.vercel.app` and the `pah-web` endpoint; `PAH_CORS_ORIGINS` at deploy time replaces the
list (comma-separated, `*` matches one DNS label).

## Executors on GPU

`pah-api` runs layers 0 and 1 and the renders on CPU. Co-folding and docking run in the GPU apps
of `executors_app.py`, which write to `pah-runs`; the API serves them after its next start.
