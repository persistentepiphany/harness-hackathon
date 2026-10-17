'use client';

// Data hooks for the screens. Each returns { data, error, loading } (plus extras) and is race-safe:
// responses for a previous key or an unmounted component are ignored, in-flight requests are
// aborted on key change / unmount. Watches (jobs, job, record, agent tasks, health) are shared
// between components through a small ref-counted store, so the nav and a page reuse one poll.

import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { ApiError, isAbortError, toApiError } from './api-client';
import { harnessMode } from './config';
import { getHarnessApi, poll, type HarnessApi, type WatchHandlers } from './harness-api';
import type { StreamStatus, Unsubscribe } from './sse';
import type { AgentStep, AgentTask, Catalog, EntityGroup, Health, Job, LogLine, Task, Tool, UiRunRecord } from './types';

export interface QueryResult<T> {
  data: T | undefined;
  error: ApiError | null;
  /** True until the first data or error for the current key arrives. */
  loading: boolean;
}

export interface ReloadableResult<T> extends QueryResult<T> {
  /** Refetch / restart the watch (for an ErrorState retry button). */
  reload: () => void;
}

// ---------------------------------------------------------------- shared store

type Starter<T> = (h: WatchHandlers<T>) => Unsubscribe;

interface Entry<T> {
  state: QueryResult<T>;
  listeners: Set<() => void>;
  unsub: Unsubscribe | null;
  stopTimer: ReturnType<typeof setTimeout> | null;
  start: Starter<T>;
  /** One-shot query: do not refetch once data arrived. */
  once: boolean;
  done: boolean;
}

const IDLE: QueryResult<never> = { data: undefined, error: null, loading: false };
const LOADING: QueryResult<never> = { data: undefined, error: null, loading: true };
const store = new Map<string, Entry<unknown>>();
const STOP_GRACE_MS = 1500;

function entryFor<T>(key: string, start: Starter<T>, once: boolean): Entry<T> {
  let e = store.get(key) as Entry<T> | undefined;
  if (!e) {
    e = { state: LOADING, listeners: new Set(), unsub: null, stopTimer: null, start, once, done: false };
    store.set(key, e as Entry<unknown>);
  }
  return e;
}

function setEntry<T>(e: Entry<T>, next: QueryResult<T>) {
  e.state = next;
  e.listeners.forEach((l) => l());
}

function runEntry<T>(e: Entry<T>) {
  if (e.unsub || (e.once && e.done)) return;
  let alive = true;
  const unsub = e.start({
    onData: (data) => {
      if (!alive) return;
      e.done = true;
      setEntry(e, { data, error: null, loading: false });
    },
    onError: (err) => {
      if (!alive) return;
      setEntry(e, { data: e.state.data, error: err, loading: false });
    },
  });
  e.unsub = () => {
    alive = false;
    unsub();
  };
}

function subscribeEntry<T>(e: Entry<T>, listener: () => void): () => void {
  e.listeners.add(listener);
  if (e.stopTimer) {
    clearTimeout(e.stopTimer);
    e.stopTimer = null;
  }
  runEntry(e);
  return () => {
    e.listeners.delete(listener);
    if (e.listeners.size === 0 && !e.stopTimer) {
      e.stopTimer = setTimeout(() => {
        e.stopTimer = null;
        if (e.listeners.size === 0) {
          e.unsub?.();
          e.unsub = null;
        }
      }, STOP_GRACE_MS);
    }
  };
}

function restartEntry<T>(e: Entry<T>) {
  e.unsub?.();
  e.unsub = null;
  e.done = false;
  setEntry(e, { data: e.state.data, error: null, loading: e.state.data === undefined });
  if (e.listeners.size) runEntry(e);
}

/** Subscribe to a shared watch identified by `key` (null = idle). */
export function useSharedWatch<T>(key: string | null, start: Starter<T>, once = false): ReloadableResult<T> {
  const startRef = useRef(start);
  useEffect(() => {
    startRef.current = start;
  });
  const subscribe = useCallback(
    (listener: () => void) => {
      if (!key) return () => undefined;
      return subscribeEntry(entryFor<T>(key, (h) => startRef.current(h), once), listener);
    },
    [key, once],
  );
  const getSnapshot = useCallback((): QueryResult<T> => {
    if (!key) return IDLE;
    const e = store.get(key) as Entry<T> | undefined;
    return e ? e.state : LOADING;
  }, [key]);
  const getServerSnapshot = useCallback((): QueryResult<T> => (key ? LOADING : IDLE), [key]);
  const state = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const reload = useCallback(() => {
    if (!key) return;
    const e = store.get(key) as Entry<T> | undefined;
    if (e) restartEntry(e);
  }, [key]);
  return useMemo(() => ({ ...state, reload }), [state, reload]);
}

/** One-shot shared query cached for the session (catalog, tools, tasks). */
export function useSharedQuery<T>(key: string | null, fetcher: (api: HarnessApi, signal: AbortSignal) => Promise<T>): ReloadableResult<T> {
  const start = useCallback<Starter<T>>(
    (h) => {
      const c = new AbortController();
      fetcher(getHarnessApi(), c.signal).then(h.onData, (e: unknown) => {
        if (!isAbortError(e)) h.onError?.(toApiError(e));
      });
      return () => c.abort();
    },
    // fetcher identity is irrelevant: the key names the query
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [key],
  );
  return useSharedWatch<T>(key, start, true);
}

/** Tests only: drop every shared watch and cached value. */
export function resetHookStoreForTests(): void {
  store.forEach((e) => {
    e.unsub?.();
    if (e.stopTimer) clearTimeout(e.stopTimer);
  });
  store.clear();
}

// ---------------------------------------------------------------- watches

/** All jobs, newest first. Live: polled every 2 s while a job is running. */
export function useJobs(): ReloadableResult<Job[]> {
  return useSharedWatch<Job[]>('jobs', (h) => getHarnessApi().watchJobs(h));
}

export function useJob(jobId: string | null | undefined): ReloadableResult<Job> {
  return useSharedWatch<Job>(jobId ? `job:${jobId}` : null, (h) => getHarnessApi().watchJob(jobId as string, h));
}

/** The UI run record; re-read while layers are running. */
export function useRunRecord(runId: string | null | undefined): ReloadableResult<UiRunRecord> {
  return useSharedWatch<UiRunRecord>(runId ? `record:${runId}` : null, (h) => getHarnessApi().watchRunRecord(runId as string, h));
}

export function useAgentTasks(): ReloadableResult<AgentTask[]> {
  return useSharedWatch<AgentTask[]>('agentTasks', (h) => getHarnessApi().watchAgentTasks(h));
}

export function useCatalog(): ReloadableResult<Catalog> {
  return useSharedQuery<Catalog>('catalog', (api, signal) => api.getCatalog({ signal }));
}

export function useTools(): ReloadableResult<Tool[]> {
  return useSharedQuery<Tool[]>('tools', (api, signal) => api.listTools({ signal }));
}

export function useTasks(): ReloadableResult<Task[]> {
  return useSharedQuery<Task[]>('tasks', (api, signal) => api.listTasks({ signal }));
}

export type ConnectionState = 'mock' | 'checking' | 'connected' | 'disconnected';

export interface HealthResult extends ReloadableResult<Health> {
  connection: ConnectionState;
}

/** API reachability. Live: /health every 5 s (backing off while it fails). Mock: always "mock". */
export function useHealth(): HealthResult {
  const r = useSharedWatch<Health>('health', (h) => {
    const api = getHarnessApi();
    return poll(h, {
      fetch: (signal) => api.health({ signal }),
      nextDelay: () => (api.mode === 'mock' ? null : 5000),
      errorDelay: (n) => Math.min(15000, 2000 * 2 ** (n - 1)),
    });
  });
  const mode = harnessMode();
  const connection: ConnectionState =
    mode === 'mock' || r.data?.mode === 'mock'
      ? 'mock'
      : r.error
        ? 'disconnected'
        : r.data && (r.data.ok === true || r.data.status === 'ok')
          ? 'connected'
          : r.data
            ? 'disconnected'
            : 'checking';
  return useMemo(() => ({ ...r, connection }), [r, connection]);
}

// ---------------------------------------------------------------- derived

/** Newest done job's runId (jobs are newest first). null when no run has finished. */
export function useLatestRunId(): QueryResult<string | null> & { reload: () => void } {
  const jobs = useJobs();
  const runId = jobs.data ? (jobs.data.find((j) => j.status === 'done')?.runId ?? null) : undefined;
  return { data: runId, error: jobs.data ? null : jobs.error, loading: jobs.loading, reload: jobs.reload };
}

/** Resolves the `latest` route alias to a concrete runId; other values pass through. */
export function useResolvedRunId(param: string | null | undefined): QueryResult<string | null> & { isAlias: boolean; reload: () => void } {
  const isAlias = param === 'latest';
  const latest = useLatestRunId();
  if (!isAlias) return { data: param ?? null, error: null, loading: false, isAlias, reload: () => undefined };
  return { ...latest, isAlias };
}

// ---------------------------------------------------------------- streams

export interface StreamResult<T> {
  data: T[];
  error: ApiError | null;
  /** True until the stream opened or delivered its first item. */
  loading: boolean;
  status: StreamStatus | 'idle';
  ended: boolean;
}

interface StreamState<T> {
  key: string | null;
  items: T[];
  error: ApiError | null;
  status: StreamStatus | 'idle';
  ended: boolean;
}

function useSeqStream<T extends { seq: number }>(
  key: string | null,
  open: (push: (item: T) => void, cb: { onEnd: () => void; onError: (e: ApiError) => void; onStatus: (s: StreamStatus) => void }) => Unsubscribe,
): StreamResult<T> {
  const [state, setState] = useState<StreamState<T>>({ key: null, items: [], error: null, status: 'idle', ended: false });
  const openRef = useRef(open);
  useEffect(() => {
    openRef.current = open;
  });

  useEffect(() => {
    if (!key) return;
    let active = true;
    let buffer: T[] = [];
    let timer: ReturnType<typeof setTimeout> | null = null;
    const update = (fn: (s: StreamState<T>) => StreamState<T>) => {
      if (!active) return;
      setState((s) => fn(s.key === key ? s : { key, items: [], error: null, status: 'connecting', ended: false }));
    };
    const flush = () => {
      timer = null;
      if (!buffer.length) return;
      const add = buffer;
      buffer = [];
      update((s) => {
        const last = s.items.length ? s.items[s.items.length - 1].seq : -Infinity;
        const fresh = add.filter((x) => x.seq > last);
        return fresh.length ? { ...s, items: s.items.concat(fresh), error: null } : s;
      });
    };
    const unsub = openRef.current(
      (item) => {
        buffer.push(item);
        if (!timer) timer = setTimeout(flush, 16);
      },
      {
        onEnd: () => {
          flush();
          update((s) => ({ ...s, ended: true, status: 'ended' }));
        },
        onError: (e) => {
          flush();
          update((s) => ({ ...s, error: e }));
        },
        onStatus: (st) => update((s) => ({ ...s, status: st })),
      },
    );
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
      unsub();
    };
  }, [key]);

  const current = state.key === key ? state : null;
  return {
    data: current?.items ?? [],
    error: current?.error ?? null,
    loading: !!key && (!current || (current.items.length === 0 && (current.status === 'connecting' || current.status === 'idle'))),
    status: key ? (current?.status ?? 'connecting') : 'idle',
    ended: current?.ended ?? false,
  };
}

/** Live log of a job: replay, then tail until the run ends. Deduplicated by seq. */
export function useJobLog(jobId: string | null | undefined): StreamResult<LogLine> {
  return useSeqStream<LogLine>(jobId ?? null, (push, cb) => getHarnessApi().streamJobLog(jobId as string, { onLine: push, ...cb }));
}

/** Step timeline of an agent task: replay, then tail until the task finishes. */
export function useAgentSteps(taskId: string | null | undefined): StreamResult<AgentStep> {
  return useSeqStream<AgentStep>(taskId ?? null, (push, cb) => getHarnessApi().streamAgentSteps(taskId as string, { onStep: push, ...cb }));
}

// ---------------------------------------------------------------- input-driven lookups

interface KeyedResult<T> extends QueryResult<T> {
  key: string | null;
}

/** Entity lookup for the Sources panel: debounced (300 ms), previous request aborted. */
export function useEntities(q: string, delayMs = 300): QueryResult<EntityGroup[]> {
  const text = q.trim();
  const [state, setState] = useState<KeyedResult<EntityGroup[]>>({ key: null, data: undefined, error: null, loading: false });
  useEffect(() => {
    if (!text) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      getHarnessApi()
        .lookupEntities(text, { signal: controller.signal })
        .then(
          (data) => {
            if (!controller.signal.aborted) setState({ key: text, data, error: null, loading: false });
          },
          (e: unknown) => {
            if (controller.signal.aborted || isAbortError(e)) return;
            setState((s) => ({ key: text, data: s.data, error: toApiError(e), loading: false }));
          },
        );
    }, delayMs);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [text, delayMs]);
  if (!text) return { data: [], error: null, loading: false };
  if (state.key === text) return { data: state.data, error: state.error, loading: false };
  // a newer query is pending: keep showing the previous groups while it loads
  return { data: state.data, error: null, loading: true };
}

// ---------------------------------------------------------------- actions (POSTs)

export interface ActionResult<R> {
  data: R | undefined;
  error: ApiError | null;
  loading: boolean;
  /** Runs `fn`; a newer call or unmount aborts the previous one. Resolves undefined when aborted or failed. */
  run: (fn: (api: HarnessApi, signal: AbortSignal) => Promise<R>) => Promise<R | undefined>;
  reset: () => void;
}

/** For submit-style calls (startRun, interpret, uploadFiles, createAgentTask). */
export function useAction<R>(): ActionResult<R> {
  const [state, setState] = useState<QueryResult<R>>(IDLE);
  const ctrl = useRef<AbortController | null>(null);
  useEffect(() => () => ctrl.current?.abort(), []);
  const run = useCallback(async (fn: (api: HarnessApi, signal: AbortSignal) => Promise<R>) => {
    ctrl.current?.abort();
    const c = new AbortController();
    ctrl.current = c;
    setState((s) => ({ data: s.data, error: null, loading: true }));
    try {
      const data = await fn(getHarnessApi(), c.signal);
      if (c.signal.aborted) return undefined;
      setState({ data, error: null, loading: false });
      return data;
    } catch (e) {
      if (c.signal.aborted || isAbortError(e)) return undefined;
      setState((s) => ({ data: s.data, error: toApiError(e), loading: false }));
      return undefined;
    }
  }, []);
  const reset = useCallback(() => {
    ctrl.current?.abort();
    setState(IDLE);
  }, []);
  return { ...state, run, reset };
}
