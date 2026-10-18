import { describe, expect, it, vi } from 'vitest';
import { ApiClient, ApiError, isAbortError, parseRetryAfter } from '@/lib/api-client';

const json = (status: number, body: unknown, headers: Record<string, string> = {}) =>
  new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json', ...headers },
  });

function client(fetchImpl: (url: string, init?: RequestInit) => Promise<Response>) {
  const sleeps: number[] = [];
  const c = new ApiClient('/api/harness', {
    fetch: fetchImpl as unknown as typeof fetch,
    sleep: async (ms) => {
      sleeps.push(ms);
    },
    random: () => 1,
  });
  return { c, sleeps };
}

describe('ApiClient', () => {
  it('builds URLs with encoded query values and drops empty ones', () => {
    const { c } = client(async () => json(200, {}));
    expect(c.url('/ui/entities', { q: 'abl1 imatinib', x: undefined })).toBe('/api/harness/ui/entities?q=abl1%20imatinib');
  });

  it('resolves 204 and empty bodies to undefined', async () => {
    const { c } = client(async () => new Response(null, { status: 204 }));
    await expect(c.post('/ui/agent/tasks/x/finish', {})).resolves.toBeUndefined();
    const { c: c2 } = client(async () => new Response('', { status: 200 }));
    await expect(c2.get('/empty')).resolves.toBeUndefined();
  });

  it('turns an error payload into ApiError with status and code', async () => {
    const { c } = client(async () => json(404, { error: { code: 'not_found', message: 'no such job' } }));
    const err = await c.get('/ui/jobs/x').catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(404);
    expect((err as ApiError).code).toBe('not_found');
    expect((err as ApiError).message).toBe('no such job');
  });

  it('retries GETs on 5xx with backoff, never on 4xx', async () => {
    let calls = 0;
    const { c, sleeps } = client(async () => (++calls < 3 ? json(502, { error: { code: 'upstream_unreachable', message: 'down' } }) : json(200, [1])));
    await expect(c.get('/ui/jobs')).resolves.toEqual([1]);
    expect(calls).toBe(3);
    expect(sleeps).toEqual([400, 800]);

    let calls4 = 0;
    const { c: c4 } = client(async () => {
      calls4++;
      return json(422, { error: { code: 'invalid', message: 'bad' } });
    });
    await expect(c4.get('/ui/jobs')).rejects.toMatchObject({ status: 422 });
    expect(calls4).toBe(1);
  });

  it('does not retry POSTs', async () => {
    let calls = 0;
    const { c } = client(async () => {
      calls++;
      return json(503, { error: { code: 'busy', message: 'busy' } });
    });
    await expect(c.post('/ui/runs', {})).rejects.toMatchObject({ status: 503 });
    expect(calls).toBe(1);
  });

  it('honours Retry-After on 503', async () => {
    let calls = 0;
    const { c, sleeps } = client(async () => (++calls === 1 ? json(503, { error: { code: 'busy', message: 'busy' } }, { 'retry-after': '2' }) : json(200, { ok: true })));
    await expect(c.get('/health')).resolves.toEqual({ ok: true });
    expect(sleeps).toEqual([2000]);
  });

  it('stops retrying at the deadline', async () => {
    const { c } = client(async () => json(500, {}));
    await expect(c.get('/x', { retry: { retries: 10, baseMs: 15000, deadlineMs: 20000 } })).rejects.toMatchObject({ status: 500 });
  });

  it('reports network failures as status 0', async () => {
    const { c } = client(async () => {
      throw new TypeError('fetch failed');
    });
    await expect(c.get('/x', { retry: false })).rejects.toMatchObject({ status: 0, code: 'network_error' });
  });

  it('deduplicates identical in-flight GETs', async () => {
    let calls = 0;
    let release: (r: Response) => void = () => undefined;
    const { c } = client(() => {
      calls++;
      return new Promise<Response>((r) => {
        release = r;
      });
    });
    const a = c.get('/ui/jobs');
    const b = c.get('/ui/jobs');
    expect(c.inflightCount).toBe(1);
    release(json(200, [1, 2]));
    await expect(Promise.all([a, b])).resolves.toEqual([[1, 2], [1, 2]]);
    expect(calls).toBe(1);
    expect(c.inflightCount).toBe(0);
  });

  it('aborting one caller keeps the shared request for the other', async () => {
    let signal: AbortSignal | undefined;
    let release: (r: Response) => void = () => undefined;
    const { c } = client((_url, init) => {
      signal = init?.signal ?? undefined;
      return new Promise<Response>((r) => {
        release = r;
      });
    });
    const ctl = new AbortController();
    const a = c.get('/ui/jobs', { signal: ctl.signal });
    const b = c.get('/ui/jobs');
    ctl.abort();
    await expect(a).rejects.toSatisfy(isAbortError);
    expect(signal?.aborted).toBe(false);
    release(json(200, 'ok'));
    await expect(b).resolves.toBe('ok');
  });

  it('aborts the shared fetch when every caller aborted', async () => {
    let signal: AbortSignal | undefined;
    const { c } = client((_url, init) => {
      signal = init?.signal ?? undefined;
      return new Promise<Response>(() => undefined);
    });
    const ctl = new AbortController();
    const a = c.get('/slow', { signal: ctl.signal });
    ctl.abort();
    await expect(a).rejects.toSatisfy(isAbortError);
    await vi.waitFor(() => expect(signal?.aborted).toBe(true));
  });

  it('times out with a clear error', async () => {
    const { c } = client((_url, init) => new Promise<Response>((_r, reject) => init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))));
    await expect(c.get('/slow', { timeoutMs: 20 })).rejects.toMatchObject({ status: 0, code: 'timeout' });
  });

  it('parses Retry-After seconds and dates', () => {
    expect(parseRetryAfter('3')).toBe(3000);
    expect(parseRetryAfter(new Date(10_000).toUTCString(), 4_000)).toBe(6000);
    expect(parseRetryAfter(null)).toBeNull();
  });
});
