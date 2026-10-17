// The only module that knows which data mode is active (docs/UI.md "Processes and ports").
// Every view renders through `HarnessApi`; live goes through the Next.js proxy at /api/harness,
// mock runs the prototype's simulator in the browser (lib/mock).

import { ApiClient, ApiError, isAbortError, toApiError } from './api-client';
import { API_BASE, harnessMode, mockOptions } from './config';
import { createMockHarnessApi } from './mock/mock-api';
import { resolveFileUrl } from './files';
import { openSseStream, type StreamCallbacks, type Unsubscribe } from './sse';
import type {
  AddToolSpec,
  AgentStep,
  AgentTask,
  Catalog,
  EntityGroup,
  ExampleManifest,
  HarnessMode,
  Health,
  InterpretResult,
  Job,
  LogLine,
  RunSettings,
  StartRunResult,
  Task,
  Tool,
  UiRunRecord,
  UploadResult,
} from './types';

export { ApiError, isAbortError, toApiError } from './api-client';
export type { StreamStatus, Unsubscribe } from './sse';
export { resolveFileUrl } from './files';

export interface CallOptions {
  signal?: AbortSignal;
}

export interface WatchHandlers<T> {
  onData: (data: T) => void;
  onError?: (err: ApiError) => void;
}

export interface LogStreamHandlers extends StreamCallbacks {
  onLine: (line: LogLine) => void;
}

export interface StepStreamHandlers extends StreamCallbacks {
  onStep: (step: AgentStep) => void;
}

export interface HarnessApi {
  readonly mode: HarnessMode;

  health(opts?: CallOptions): Promise<Health>;

  listJobs(opts?: CallOptions): Promise<Job[]>;
  getJob(jobId: string, opts?: CallOptions): Promise<Job>;
  /** Live: polls every 2 s while a job is queued or running, every 10 s otherwise. Mock: pushes on every simulator tick. */
  watchJobs(h: WatchHandlers<Job[]>): Unsubscribe;
  watchJob(jobId: string, h: WatchHandlers<Job>): Unsubscribe;

  /** Whole log as JSON (`?format=json`). */
  getJobLog(jobId: string, opts?: CallOptions): Promise<LogLine[]>;
  /** SSE: replays the log, then tails it until the run ends. Lines are deduplicated by seq. */
  streamJobLog(jobId: string, h: LogStreamHandlers): Unsubscribe;

  getRunRecord(runId: string, opts?: CallOptions): Promise<UiRunRecord>;
  /** Re-reads the record while any layer is running or pending. */
  watchRunRecord(runId: string, h: WatchHandlers<UiRunRecord>): Unsubscribe;
  /** Browser URL of a file inside runs/<runId>/ (native route /runs/{id}/files/{rel}). Mock mode has no files. */
  fileUrl(runId: string, path: string): string;
  /** Browser URL for a native API path from a record (structures[].url, renders[].png, report.figures[].url). */
  assetUrl(pathOrUrl: string): string;

  startRun(settings: RunSettings, opts?: CallOptions): Promise<StartRunResult>;
  interpret(text: string, opts?: CallOptions): Promise<InterpretResult>;
  lookupEntities(q: string, opts?: CallOptions): Promise<EntityGroup[]>;
  getCatalog(opts?: CallOptions): Promise<Catalog>;
  listTools(opts?: CallOptions): Promise<Tool[]>;
  /** Live: `POST /ui/tools` (the API answers 501 not_implemented). Mock: adds a custom entry to the session's register. */
  addTool(spec: AddToolSpec, opts?: CallOptions): Promise<Tool>;
  listTasks(opts?: CallOptions): Promise<Task[]>;
  listExamples(opts?: CallOptions): Promise<ExampleManifest[]>;
  uploadFiles(files: File[], opts?: CallOptions): Promise<UploadResult>;

  listAgentTasks(opts?: CallOptions): Promise<AgentTask[]>;
  /** Live: polls every 2 s while a task is queued or running, every 3 s otherwise. */
  watchAgentTasks(h: WatchHandlers<AgentTask[]>): Unsubscribe;
  createAgentTask(goal: string, opts?: CallOptions): Promise<AgentTask>;
  /** SSE: replays the steps, then tails them until the task finishes. Deduplicated by seq. */
  streamAgentSteps(taskId: string, h: StepStreamHandlers): Unsubscribe;
}

// ---------------------------------------------------------------- polling helper

export interface PollOptions<T> {
  fetch: (signal: AbortSignal) => Promise<T>;
  /** Delay before the next poll given the last data; null stops polling. */
  nextDelay: (data: T) => number | null;
  /** Delay after an error (grows with consecutive errors). */
  errorDelay?: (consecutiveErrors: number) => number;
}

export function poll<T>(h: WatchHandlers<T>, p: PollOptions<T>): Unsubscribe {
  let stopped = false;
  let controller: AbortController | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let errors = 0;
  const errorDelay = p.errorDelay ?? ((n: number) => Math.min(30000, 2000 * 2 ** (n - 1)));

  const schedule = (ms: number | null) => {
    if (stopped || ms === null) return;
    const hidden = typeof document !== 'undefined' && document.visibilityState === 'hidden';
    timer = setTimeout(run, hidden ? Math.max(ms, 10000) : ms);
  };
  const run = async () => {
    if (stopped) return;
    controller = new AbortController();
    try {
      const data = await p.fetch(controller.signal);
      if (stopped) return;
      errors = 0;
      h.onData(data);
      schedule(p.nextDelay(data));
    } catch (e) {
      if (stopped || isAbortError(e)) return;
      errors += 1;
      h.onError?.(toApiError(e));
      schedule(errorDelay(errors));
    }
  };
  void run();
  return () => {
    stopped = true;
    controller?.abort();
    if (timer) clearTimeout(timer);
  };
}

const anyActive = (items: { status: string }[]) => items.some((j) => j.status === 'running' || j.status === 'queued');

/**
 * A record still being written: run status running/queued, a layer running or pending, or a
 * finished run whose report stage (renders, figures, graph) is still running.
 */
export function isRecordActive(r: UiRunRecord): boolean {
  if (r.status === 'done' || r.status === 'failed') return r.report?.status === 'running';
  return r.status === 'running' || r.status === 'queued' || r.layers.some((l) => l.status === 'running' || l.status === 'pending');
}

const enc = encodeURIComponent;

// ---------------------------------------------------------------- live implementation

export interface LiveOptions {
  baseUrl?: string;
  client?: ApiClient;
  EventSourceImpl?: typeof EventSource;
}

export function createLiveHarnessApi(opts: LiveOptions = {}): HarnessApi {
  const base = opts.baseUrl ?? API_BASE;
  const http = opts.client ?? new ApiClient(base);
  const sse = { EventSourceImpl: opts.EventSourceImpl };

  return {
    mode: 'live',

    health: (o) => http.get<Health>('/health', { signal: o?.signal, retry: false }),

    listJobs: (o) => http.get<Job[]>('/ui/jobs', { signal: o?.signal }),
    getJob: (id, o) => http.get<Job>(`/ui/jobs/${enc(id)}`, { signal: o?.signal }),
    watchJobs: (h) =>
      poll(h, {
        fetch: (signal) => http.get<Job[]>('/ui/jobs', { signal }),
        nextDelay: (jobs) => (anyActive(jobs) ? 2000 : 10000),
      }),
    watchJob: (id, h) =>
      poll(h, {
        fetch: (signal) => http.get<Job>(`/ui/jobs/${enc(id)}`, { signal }),
        // a done job keeps polling while its report stage runs, so reportStatus settles
        nextDelay: (job) => (job.status === 'running' || job.status === 'queued' || job.reportStatus === 'running' ? 2000 : null),
      }),

    getJobLog: (id, o) => http.get<LogLine[]>(`/ui/jobs/${enc(id)}/log`, { signal: o?.signal, query: { format: 'json' } }),
    streamJobLog: (id, h) => openSseStream<LogLine>(http.url(`/ui/jobs/${enc(id)}/log`), 'line', h.onLine, h, sse),

    getRunRecord: (runId, o) => http.get<UiRunRecord>(`/ui/runs/${enc(runId)}/record`, { signal: o?.signal }),
    watchRunRecord: (runId, h) => {
      let unchanged = 0;
      let last = '';
      return poll(h, {
        fetch: (signal) => http.get<UiRunRecord>(`/ui/runs/${enc(runId)}/record`, { signal }),
        nextDelay: (r) => {
          if (!isRecordActive(r)) return null;
          const key = JSON.stringify([r.layers.map((l) => [l.status, l.checks.length]), r.report?.status, r.renders?.length ?? 0]);
          unchanged = key === last ? unchanged + 1 : 0;
          last = key;
          return unchanged > 15 ? 10000 : 2000;
        },
      });
    },
    fileUrl: (runId, path) => resolveFileUrl(http.baseUrl, runId, path),
    assetUrl: (pathOrUrl) => resolveFileUrl(http.baseUrl, '', pathOrUrl),

    startRun: (settings, o) => http.post<StartRunResult>('/ui/runs', settings, { signal: o?.signal }),
    interpret: (text, o) => http.post<InterpretResult>('/ui/interpret', { text }, { signal: o?.signal }),
    lookupEntities: (q, o) => http.get<EntityGroup[]>('/ui/entities', { signal: o?.signal, query: { q } }),
    getCatalog: (o) => http.get<Catalog>('/ui/catalog', { signal: o?.signal }),
    listTools: (o) => http.get<Tool[]>('/ui/tools', { signal: o?.signal }),
    addTool: (spec, o) => http.post<Tool>('/ui/tools', spec, { signal: o?.signal }),
    listTasks: (o) => http.get<Task[]>('/ui/tasks', { signal: o?.signal }),
    listExamples: (o) => http.get<ExampleManifest[]>('/ui/examples', { signal: o?.signal }),
    uploadFiles: (files, o) => {
      const form = new FormData();
      files.forEach((f) => form.append('files', f, f.name));
      return http.post<UploadResult>('/ui/uploads', form, { signal: o?.signal, timeoutMs: 300000 });
    },

    listAgentTasks: (o) => http.get<AgentTask[]>('/ui/agent/tasks', { signal: o?.signal }),
    watchAgentTasks: (h) =>
      poll(h, {
        fetch: (signal) => http.get<AgentTask[]>('/ui/agent/tasks', { signal }),
        // idle: 3 s, so a task an agent starts with `pah agent-log start` shows up promptly
        nextDelay: (tasks) => (anyActive(tasks) ? 2000 : 3000),
      }),
    createAgentTask: (goal, o) => http.post<AgentTask>('/ui/agent/tasks', { goal }, { signal: o?.signal }),
    streamAgentSteps: (id, h) => openSseStream<AgentStep>(http.url(`/ui/agent/tasks/${enc(id)}/steps`), 'step', h.onStep, h, sse),
  };
}

// ---------------------------------------------------------------- singleton

let instance: HarnessApi | null = null;

/** The API for the configured mode (NEXT_PUBLIC_HARNESS_MODE). Call from effects / handlers only. */
export function getHarnessApi(): HarnessApi {
  if (!instance) {
    instance = harnessMode() === 'mock' ? createMockHarnessApi(mockOptions()) : createLiveHarnessApi();
  }
  return instance;
}

/** Tests only: replace the singleton. */
export function setHarnessApiForTests(api: HarnessApi | null): void {
  instance = api;
}
