// @vitest-environment node
import { afterEach, describe, expect, it, vi } from 'vitest';
import { NextRequest } from 'next/server';
import { GET } from '@/app/api/harness/[...path]/route';

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
});
