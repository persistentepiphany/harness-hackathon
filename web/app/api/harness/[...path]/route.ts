// Streaming proxy: /api/harness/<path> → ${HARNESS_API_URL}/<path> (docs/UI.md).
//
// A route handler rather than a next.config rewrite because (1) rewrite destinations are fixed at
// build time while HARNESS_API_URL is read here per request, (2) SSE must pass through unbuffered
// (`Cache-Control: no-transform` keeps Next's gzip off the stream), (3) an upstream that takes long
// to send its first byte (a Modal cold start, up to ~30 s) needs its own timeout and an error
// body the UI can show: {"error": {"code": "upstream_timeout" | "upstream_unreachable", ...}}.
// A request body is read in full before the upstream request starts, so the first-byte timer
// measures the API, not the client's upload; uploads and entity lookups get a longer limit
// because the API parses files or queries sources before it answers.

import type { NextRequest } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
// Vercel: allow long-lived SSE tails; the browser reconnects with Last-Event-ID when cut.
export const maxDuration = 300;

const DEFAULT_UPSTREAM = 'http://127.0.0.1:8000';
const DEFAULT_TIMEOUT_MS = 60000;
/** First-byte limit for requests the API processes before answering (uploads, entity lookups). */
const SLOW_TIMEOUT_MS = 240000;
const SLOW_PATHS = new Set(['ui/uploads', 'ui/entities']);
/** Header the API checks before it starts executors (configs/dispatch.yaml guard.header). */
const EXEC_TOKEN_HEADER = 'x-pah-exec-token';

// Hop-by-hop and origin-specific headers that must not be forwarded. Platform headers
// (`modal-*` on Modal) are dropped in both directions: Modal rejects a response that carries one.
const isPlatformHeader = (key: string): boolean => key.startsWith('modal-');
// `expect` (curl sends `Expect: 100-continue` for large bodies) and `http2-settings` make Node's
// fetch throw UND_ERR_NOT_SUPPORTED.
const DROP_REQUEST = new Set(['host', 'connection', 'keep-alive', 'transfer-encoding', 'te', 'trailer', 'upgrade', 'proxy-authorization', 'proxy-connection', 'content-length', 'accept-encoding', 'cookie', 'origin', 'referer', 'expect', 'http2-settings']);
const DROP_RESPONSE = new Set(['connection', 'keep-alive', 'transfer-encoding', 'te', 'trailer', 'upgrade', 'content-encoding', 'content-length', 'set-cookie']);

function upstreamBase(): string {
  return (process.env.HARNESS_API_URL || DEFAULT_UPSTREAM).replace(/\/+$/, '');
}

function timeoutMs(): number {
  const v = Number(process.env.HARNESS_PROXY_TIMEOUT_MS);
  return Number.isFinite(v) && v > 0 ? v : DEFAULT_TIMEOUT_MS;
}

function errorResponse(status: number, code: string, message: string): Response {
  return Response.json(
    { error: { code, message } },
    { status, headers: { 'cache-control': 'no-store', 'x-harness-proxy': 'error' } },
  );
}

async function proxy(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }): Promise<Response> {
  const { path } = await ctx.params;
  const segments = (path || []).filter((s) => s !== '.' && s !== '..');
  const base = upstreamBase();
  let target: URL;
  try {
    target = new URL(`${base}/${segments.map(encodeURIComponent).join('/')}`);
  } catch {
    return errorResponse(500, 'proxy_misconfigured', `HARNESS_API_URL is not a valid URL: ${base}`);
  }
  target.search = req.nextUrl.search;

  const headers = new Headers();
  req.headers.forEach((value, key) => {
    const k = key.toLowerCase();
    if (!DROP_REQUEST.has(k) && !isPlatformHeader(k)) headers.set(key, value);
  });
  // The execution token (PAH_EXEC_TOKEN, configs/dispatch.yaml guard) is added here, server
  // side, from the proxy's own environment; a client-supplied value is never forwarded.
  headers.delete(EXEC_TOKEN_HEADER);
  const execToken = process.env.PAH_EXEC_TOKEN;
  if (execToken) headers.set(EXEC_TOKEN_HEADER, execToken);
  // Stream bytes as they come; a compressed upstream body would be decoded by fetch anyway.
  headers.set('accept-encoding', 'identity');
  headers.set('x-forwarded-host', req.headers.get('host') || '');

  const method = req.method.toUpperCase();
  const hasBody = method !== 'GET' && method !== 'HEAD';
  // read the body first: the first-byte timer then starts when the upload is complete
  let payload: ArrayBuffer | undefined;
  if (hasBody) {
    try {
      payload = await req.arrayBuffer();
    } catch {
      if (req.signal.aborted) return new Response(null, { status: 499 });
      return errorResponse(400, 'bad_request_body', 'The request body could not be read.');
    }
  }

  const slow = SLOW_PATHS.has(segments.join('/'));
  const limit = slow ? Math.max(timeoutMs(), SLOW_TIMEOUT_MS) : timeoutMs();
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, limit);
  // The client went away: stop the upstream request (ends SSE tails on the API side too).
  const onClientAbort = () => controller.abort();
  req.signal.addEventListener('abort', onClientAbort, { once: true });

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method,
      headers,
      body: payload,
      redirect: 'manual',
      cache: 'no-store',
      signal: controller.signal,
    } as RequestInit);
  } catch (e) {
    clearTimeout(timer);
    req.signal.removeEventListener('abort', onClientAbort);
    if (timedOut) {
      const sent = payload ? ` after the ${payload.byteLength.toLocaleString('en-US')}-byte request body was sent; the API may still be processing it` : '';
      return errorResponse(504, 'upstream_timeout', `The harness API at ${target.origin} sent no response within ${Math.round(limit / 1000)} s${sent}. A cold start can take about 30 s; retry shortly.`);
    }
    if (req.signal.aborted) return new Response(null, { status: 499 });
    const cause = e instanceof Error ? ((e as Error & { cause?: { code?: string } }).cause?.code ?? e.message) : String(e);
    return errorResponse(502, 'upstream_unreachable', `Cannot reach the harness API at ${target.origin} (${cause}).`);
  }
  // Headers arrived: the first-byte timeout no longer applies (streams may stay open for minutes).
  clearTimeout(timer);

  const out = new Headers();
  upstream.headers.forEach((value, key) => {
    const k = key.toLowerCase();
    if (!DROP_RESPONSE.has(k) && !isPlatformHeader(k)) out.set(key, value);
  });
  const type = upstream.headers.get('content-type') || '';
  if (type.includes('text/event-stream')) {
    out.set('cache-control', 'no-cache, no-transform');
    out.set('x-accel-buffering', 'no');
  } else if (!out.has('cache-control')) {
    out.set('cache-control', 'no-store');
  }

  const body = upstream.body;
  if (!body || method === 'HEAD' || upstream.status === 204 || upstream.status === 304) {
    req.signal.removeEventListener('abort', onClientAbort);
    return new Response(null, { status: upstream.status, statusText: upstream.statusText, headers: out });
  }
  // Pass the body through chunk by chunk; release listeners when it ends either way.
  const passthrough = body.pipeThrough(
    new TransformStream<Uint8Array, Uint8Array>({
      flush() {
        req.signal.removeEventListener('abort', onClientAbort);
      },
    }),
  );
  return new Response(passthrough, { status: upstream.status, statusText: upstream.statusText, headers: out });
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as PATCH, proxy as DELETE, proxy as HEAD, proxy as OPTIONS };
