import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { setHarnessApiForTests, type HarnessApi } from '@/lib/harness-api';
import { resetHookStoreForTests, useEntities, useJobLog, useJobs, useResolvedRunId } from '@/lib/hooks';
import { createMockHarnessApi } from '@/lib/mock/mock-api';
import type { EntityGroup } from '@/lib/types';

afterEach(() => {
  resetHookStoreForTests();
  setHarnessApiForTests(null);
  vi.useRealTimers();
});

describe('useEntities', () => {
  it('debounces input, aborts the previous request and ignores stale answers', async () => {
    vi.useFakeTimers();
    const calls: { q: string; signal?: AbortSignal }[] = [];
    const fake = {
      lookupEntities: (q: string, o?: { signal?: AbortSignal }) => {
        calls.push({ q, signal: o?.signal });
        return Promise.resolve([{ key: q, kind: 'protein', title: q, source: 'UniProt', query: q, ms: 0, rows: [] }] as EntityGroup[]);
      },
    } as unknown as HarnessApi;
    setHarnessApiForTests(fake);
    const { result, rerender } = renderHook(({ q }) => useEntities(q), { initialProps: { q: 'ab' } });
    expect(result.current.loading).toBe(true);
    rerender({ q: 'abl' });
    rerender({ q: 'abl1' });
    await act(async () => {
      vi.advanceTimersByTime(299);
    });
    expect(calls).toHaveLength(0);
    await act(async () => {
      vi.advanceTimersByTime(1);
    });
    expect(calls.map((c) => c.q)).toEqual(['abl1']);
    expect(result.current.loading).toBe(false);
    expect(result.current.data?.[0].key).toBe('abl1');
    rerender({ q: '' });
    expect(result.current).toEqual({ data: [], error: null, loading: false });
  });
});

describe('watch hooks with the mock API', () => {
  it('useJobs shares one subscription and returns jobs newest first', async () => {
    setHarnessApiForTests(createMockHarnessApi({ seed: 9, latencyMs: 0, autoStart: false }));
    const a = renderHook(() => useJobs());
    const b = renderHook(() => useJobs());
    await waitFor(() => expect(a.result.current.data).toHaveLength(3));
    expect(b.result.current.data).toBe(a.result.current.data);
    expect(a.result.current.data?.map((j) => j.status)).toEqual(['done', 'running', 'queued']);
  });

  it('useResolvedRunId resolves latest to the newest done job', async () => {
    const api = createMockHarnessApi({ seed: 9, latencyMs: 0, autoStart: false });
    setHarnessApiForTests(api);
    const { result } = renderHook(() => useResolvedRunId('latest'));
    await waitFor(() => expect(result.current.data).toMatch(/^run_/));
    const jobs = await api.listJobs();
    expect(result.current.data).toBe(jobs.find((j) => j.status === 'done')?.runId);
    const direct = renderHook(() => useResolvedRunId('run_x'));
    expect(direct.result.current.data).toBe('run_x');
  });

  it('useJobLog accumulates a done job log and reports the end', async () => {
    const api = createMockHarnessApi({ seed: 9, latencyMs: 0, autoStart: false });
    setHarnessApiForTests(api);
    const jobs = await api.listJobs();
    const done = jobs.find((j) => j.status === 'done')!;
    const { result } = renderHook(() => useJobLog(done.id));
    await waitFor(() => expect(result.current.ended).toBe(true));
    expect(result.current.data.length).toBeGreaterThan(10);
    expect(result.current.status).toBe('ended');
  });
});
