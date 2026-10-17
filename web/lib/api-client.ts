// One central HTTP client for the harness API (live mode). Patterns:
// - ApiError carries status, code and the parsed payload ({"error": {code, message}} from pah serve),
// - 204 / empty bodies resolve to undefined, non-JSON bodies resolve to text,
// - per-request timeout (the Next.js proxy times out first, with a clear upstream_timeout error),
// - retry with exponential backoff and full jitter only for idempotent GETs, only on network
//   errors and 5xx (never 4xx), honouring Retry-After, within a total deadline,
// - identical in-flight GETs are deduplicated by key; the shared fetch is aborted only when every
//   caller has aborted,
// - AbortSignal support everywhere. No credentials or secrets are sent from the browser.

export class ApiError extends Error {
  /** HTTP status, or 0 when no response arrived (network error, timeout). */
  readonly status: number;
  /** `error.code` from the payload, or a client code: network_error, timeout, http_<status>. */
  readonly code: string;
  readonly payload: unknown;
  readonly url: string;

  constructor(opts: { status: number; code: string; message: string; payload?: unknown; url?: string }) {
    super(opts.message);
    this.name = 'ApiError';
    this.status = opts.status;
    this.code = opts.code;
    this.payload = opts.payload;
    this.url = opts.url ?? '';
  }

  /** Network failures and 5xx are worth retrying for idempotent requests; 4xx never are. */
  get retryable(): boolean {
    return this.status === 0 ? this.code !== 'timeout' : this.status >= 500 && this.status !== 501;
  }
}

export function isAbortError(e: unknown): boolean {
  return (
    (e instanceof DOMException && e.name === 'AbortError') ||
    (typeof e === 'object' && e !== null && (e as { name?: string }).name === 'AbortError')
  );
}

export function toApiError(e: unknown, url = ''): ApiError {
  if (e instanceof ApiError) return e;
  const message = e instanceof Error ? e.message : String(e);
  return new ApiError({ status: 0, code: 'network_error', message: message || 'Network error', url });
}

export interface RetryPolicy {
  /** Maximum number of retries after the first attempt. */
  retries: number;
  baseMs: number;
  maxDelayMs: number;
  /** No new attempt starts after this many ms since the first one. */
  deadlineMs: number;
}

export const DEFAULT_RETRY: RetryPolicy = { retries: 3, baseMs: 400, maxDelayMs: 4000, deadlineMs: 20000 };

/** Longer than the proxy's upstream timeout (60 s) so the proxy's error reaches the UI first. */
export const DEFAULT_TIMEOUT_MS = 70000;

export type QueryValue = string | number | boolean | null | undefined;

export interface RequestOptions {
  signal?: AbortSignal;
  query?: Record<string, QueryValue>;
  /** JSON-serialised unless it is FormData, Blob or a string. */
  body?: unknown;
  headers?: Record<string, string>;
  timeoutMs?: number;
  /** GET only. `false` disables retries. */
  retry?: Partial<RetryPolicy> | false;
  /** GET only, default true. */
  dedupe?: boolean;
}

export interface ApiClientDeps {
  fetch?: typeof fetch;
  sleep?: (ms: number, signal?: AbortSignal) => Promise<void>;
  random?: () => number;
  now?: () => number;
}

const abortError = () => new DOMException('The operation was aborted.', 'AbortError');

export function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(abortError());
    const t = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(t);
      reject(abortError());
    };
    signal?.addEventListener('abort', onAbort, { once: true });
  });
}

/** Retry-After as seconds or HTTP date, in ms; null when absent or unparsable. */
export function parseRetryAfter(value: string | null, now = Date.now()): number | null {
  if (!value) return null;
  const s = Number(value);
  if (Number.isFinite(s)) return Math.max(0, s * 1000);
  const d = Date.parse(value);
  return Number.isFinite(d) ? Math.max(0, d - now) : null;
}

async function readBody(res: Response): Promise<unknown> {
  if (res.status === 204 || res.status === 205 || res.status === 304) return undefined;
  const text = await res.text();
  if (!text) return undefined;
  const type = res.headers.get('content-type') || '';
  if (type.includes('json') || /^[\s]*[[{]/.test(text)) {
    try {
      return JSON.parse(text) as unknown;
    } catch {
      if (type.includes('json')) {
        throw new ApiError({ status: res.status, code: 'parse_error', message: 'Response is not valid JSON', payload: text, url: res.url });
      }
    }
  }
  return text;
}

function errorFromResponse(res: Response, payload: unknown, url: string): ApiError {
  const err = (payload as { error?: { code?: unknown; message?: unknown } } | undefined)?.error;
  const detail = (payload as { detail?: unknown } | undefined)?.detail;
  const code = typeof err?.code === 'string' ? err.code : `http_${res.status}`;
  const message =
    typeof err?.message === 'string'
      ? err.message
      : typeof detail === 'string'
        ? detail
        : typeof payload === 'string' && payload.length < 300 && payload.trim()
          ? payload.trim()
          : `${res.status} ${res.statusText || 'error'}`;
  return new ApiError({ status: res.status, code, message, payload, url });
}

interface Inflight {
  promise: Promise<unknown>;
  controller: AbortController;
  refs: number;
}

export class ApiClient {
  readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;
  private readonly sleepImpl: (ms: number, signal?: AbortSignal) => Promise<void>;
  private readonly random: () => number;
  private readonly now: () => number;
  private readonly inflight = new Map<string, Inflight>();

  constructor(baseUrl: string, deps: ApiClientDeps = {}) {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
    this.fetchImpl = deps.fetch ?? ((input, init) => fetch(input, init));
    this.sleepImpl = deps.sleep ?? sleep;
    this.random = deps.random ?? Math.random;
    this.now = deps.now ?? Date.now;
  }

  url(path: string, query?: Record<string, QueryValue>): string {
    const p = path.startsWith('/') ? path : `/${path}`;
    const qs = query
      ? Object.entries(query)
          .filter(([, v]) => v !== undefined && v !== null)
          .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
          .join('&')
      : '';
    return `${this.baseUrl}${p}${qs ? `?${qs}` : ''}`;
  }

  get<T>(path: string, opts: RequestOptions = {}): Promise<T> {
    return this.request<T>('GET', path, opts);
  }

  post<T>(path: string, body?: unknown, opts: RequestOptions = {}): Promise<T> {
    return this.request<T>('POST', path, { ...opts, body });
  }

  request<T>(method: string, path: string, opts: RequestOptions = {}): Promise<T> {
    const url = this.url(path, opts.query);
    const isGet = method === 'GET';
    if (!isGet || opts.dedupe === false) {
      return this.execute<T>(method, url, opts, opts.signal);
    }
    const key = `${method} ${url}`;
    let entry = this.inflight.get(key);
    if (!entry) {
      const controller = new AbortController();
      const created: Inflight = {
        controller,
        refs: 0,
        promise: this.execute<unknown>(method, url, opts, controller.signal).finally(() => {
          if (this.inflight.get(key) === created) this.inflight.delete(key);
        }),
      };
      // keep unhandled rejections off the shared promise; callers get their own chain
      created.promise.catch(() => undefined);
      this.inflight.set(key, created);
      entry = created;
    }
    return this.join<T>(key, entry, opts.signal);
  }

  /** Number of GETs currently in flight (deduplicated). For tests. */
  get inflightCount(): number {
    return this.inflight.size;
  }

  private join<T>(key: string, entry: Inflight, signal?: AbortSignal): Promise<T> {
    entry.refs += 1;
    return new Promise<T>((resolve, reject) => {
      let settled = false;
      const release = () => {
        entry.refs -= 1;
        if (entry.refs <= 0) {
          entry.controller.abort();
          if (this.inflight.get(key) === entry) this.inflight.delete(key);
        }
      };
      const onAbort = () => {
        if (settled) return;
        settled = true;
        release();
        reject(abortError());
      };
      if (signal?.aborted) return onAbort();
      signal?.addEventListener('abort', onAbort, { once: true });
      entry.promise.then(
        (v) => {
          if (settled) return;
          settled = true;
          signal?.removeEventListener('abort', onAbort);
          entry.refs -= 1;
          resolve(v as T);
        },
        (e: unknown) => {
          if (settled) return;
          settled = true;
          signal?.removeEventListener('abort', onAbort);
          entry.refs -= 1;
          reject(e);
        },
      );
    });
  }

  private async execute<T>(method: string, url: string, opts: RequestOptions, signal?: AbortSignal): Promise<T> {
    const policy: RetryPolicy | null =
      method === 'GET' && opts.retry !== false ? { ...DEFAULT_RETRY, ...(opts.retry || {}) } : null;
    const started = this.now();
    let attempt = 0;
    for (;;) {
      try {
        return await this.once<T>(method, url, opts, signal);
      } catch (e) {
        if (isAbortError(e) || signal?.aborted) throw e;
        const err = toApiError(e, url);
        if (!policy || !err.retryable || attempt >= policy.retries) throw err;
        const retryAfter =
          err.status === 503 || err.status === 429
            ? parseRetryAfter(((err.payload as { __retryAfter?: string } | undefined)?.__retryAfter) ?? null, this.now())
            : null;
        const backoff = Math.min(policy.maxDelayMs, policy.baseMs * 2 ** attempt) * this.random();
        const delay = retryAfter ?? backoff;
        if (this.now() - started + delay > policy.deadlineMs) throw err;
        attempt += 1;
        await this.sleepImpl(delay, signal);
      }
    }
  }

  private async once<T>(method: string, url: string, opts: RequestOptions, signal?: AbortSignal): Promise<T> {
    const timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    const controller = new AbortController();
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);
    const onAbort = () => controller.abort();
    if (signal?.aborted) controller.abort();
    signal?.addEventListener('abort', onAbort, { once: true });

    const headers: Record<string, string> = { Accept: 'application/json', ...(opts.headers || {}) };
    let body: BodyInit | undefined;
    if (opts.body !== undefined && method !== 'GET' && method !== 'HEAD') {
      if (
        (typeof FormData !== 'undefined' && opts.body instanceof FormData) ||
        (typeof Blob !== 'undefined' && opts.body instanceof Blob) ||
        typeof opts.body === 'string'
      ) {
        body = opts.body as BodyInit;
      } else {
        body = JSON.stringify(opts.body);
        headers['Content-Type'] = 'application/json';
      }
    }

    try {
      let res: Response;
      try {
        res = await this.fetchImpl(url, { method, headers, body, signal: controller.signal, cache: 'no-store' });
      } catch (e) {
        if (timedOut) {
          throw new ApiError({ status: 0, code: 'timeout', message: `No response from the harness API within ${Math.round(timeoutMs / 1000)} s`, url });
        }
        if (isAbortError(e)) throw e;
        throw new ApiError({ status: 0, code: 'network_error', message: 'Cannot reach the harness API', url, payload: String(e) });
      }
      let payload: unknown;
      try {
        payload = await readBody(res);
      } catch (e) {
        if (timedOut) {
          throw new ApiError({ status: 0, code: 'timeout', message: `Response from the harness API did not finish within ${Math.round(timeoutMs / 1000)} s`, url });
        }
        throw e;
      }
      if (!res.ok) {
        const err = errorFromResponse(res, payload, url);
        const ra = res.headers.get('retry-after');
        if (ra) {
          // keep Retry-After with the error for the retry loop
          return Promise.reject(
            new ApiError({
              status: err.status,
              code: err.code,
              message: err.message,
              url,
              payload: typeof payload === 'object' && payload !== null ? { ...(payload as object), __retryAfter: ra } : { body: payload, __retryAfter: ra },
            }),
          );
        }
        throw err;
      }
      return payload as T;
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener('abort', onAbort);
    }
  }
}
