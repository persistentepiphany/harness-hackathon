// @vitest-environment node
import { afterEach, describe, expect, it, vi } from 'vitest';
import { NextRequest } from 'next/server';
import { GET, POST } from '@/app/api/harness/[...path]/route';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('harness proxy route', () => {
  it('drops modal-* headers in both directions', async () => {
    const seen: Headers[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: unknown, init: RequestInit) => {
        seen.push(new Headers(init.headers));
        return new Response('{"ok":true}', {
          status: 200,
          headers: { 'content-type': 'application/json', 'modal-function-call-id': 'fc-1', 'x-kept': '1' },
        });
      }),
    );
    const req = new NextRequest('http://localhost/api/harness/ui/jobs', {
      headers: { 'modal-trace': 't', accept: 'application/json' },
    });
    const res = await GET(req, { params: Promise.resolve({ path: ['ui', 'jobs'] }) });
    expect(res.status).toBe(200);
    expect(res.headers.get('modal-function-call-id')).toBeNull();
    expect(res.headers.get('x-kept')).toBe('1');
    expect(seen[0].get('modal-trace')).toBeNull();
    expect(seen[0].get('accept')).toBe('application/json');
    expect(await res.json()).toEqual({ ok: true });
  });

  it('drops Expect and sends the body read in full', async () => {
    const seen: { headers: Headers; body: unknown }[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: unknown, init: RequestInit) => {
        seen.push({ headers: new Headers(init.headers), body: init.body });
        return new Response('{"files":[]}', { status: 200, headers: { 'content-type': 'application/json' } });
      }),
    );
    const req = new NextRequest('http://localhost/api/harness/ui/uploads', {
      method: 'POST',
      headers: { expect: '100-continue', 'content-type': 'application/octet-stream' },
      body: new Uint8Array([1, 2, 3]),
    });
    const res = await POST(req, { params: Promise.resolve({ path: ['ui', 'uploads'] }) });
    expect(res.status).toBe(200);
    expect(seen[0].headers.get('expect')).toBeNull();
    expect(seen[0].body).toBeInstanceOf(ArrayBuffer);
    expect((seen[0].body as ArrayBuffer).byteLength).toBe(3);
  });
});
