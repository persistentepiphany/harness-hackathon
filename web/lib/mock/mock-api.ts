// HarnessApi backed by the in-browser simulator (mock mode). Same interface and streaming
// semantics as the live client: watches push snapshots, streams replay then tail, dedupe by seq.

import { ApiError } from '../api-client';
import { API_BASE, type MockOptions } from '../config';
import { resolveFileUrl } from '../files';
import type { CallOptions, HarnessApi, LogStreamHandlers, StepStreamHandlers, WatchHandlers } from '../harness-api';
import type { Unsubscribe } from '../sse';
import type { AgentTask, Catalog, ExampleManifest, Health, InterpretResult, Job, Task, Tool, UiGlossary, UploadedFile, UploadResult } from '../types';
import { CATALOG, GLOSSARY, TASKS, formFromSettings, interpretRun, lookupEntities, mockTools, registerMockTool } from './data';
import { Simulator, type SimJob } from './simulator';

export interface MockControls {
  readonly simulator: Simulator;
  setSimSpeed(speed: number): void;
  setMaxConcurrent(n: number): void;
  pause(): void;
  resume(): void;
  /** Advance the simulation by `ms` synchronously (paused or not). */
  advance(ms: number): void;
}

export type MockHarnessApi = HarnessApi & { readonly mock: MockControls };

const abortError = () => new DOMException('The operation was aborted.', 'AbortError');

const clone = <T>(v: T): T => (typeof structuredClone === 'function' ? structuredClone(v) : (JSON.parse(JSON.stringify(v)) as T));

const notFound = (what: string, id: string) =>
  new ApiError({ status: 404, code: 'not_found', message: `No ${what} with id ${id}`, payload: { error: { code: 'not_found', message: `No ${what} with id ${id}` } } });

const FILE_KINDS: Record<string, string> = { pdb: 'receptor', cif: 'receptor', mmcif: 'receptor', fasta: 'sequence', fa: 'sequence', sdf: 'ligand', mol: 'ligand', mol2: 'ligand', smi: 'ligand', csv: 'series', json: 'manifest' };
const PARSED: Record<string, string> = { receptor: 'receptor · chains A,B · 0 gaps', sequence: 'sequence · 1 chain', ligand: 'ligand · sanitised · InChIKey ok', series: 'series · 12 members', manifest: 'manifest' };

async function sha256Hex(file: File): Promise<string> {
  try {
    const buf = await file.arrayBuffer();
    const digest = await crypto.subtle.digest('SHA-256', buf);
    return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, '0')).join('');
  } catch {
    return '';
  }
}

export interface CreateMockOptions extends Partial<MockOptions> {
  /** Start the 110 ms interval (default: true in a browser, false elsewhere). */
  autoStart?: boolean;
}

export function createMockHarnessApi(opts: CreateMockOptions = {}): MockHarnessApi {
  const sim = new Simulator({ seed: opts.seed, simSpeed: opts.simSpeed, maxConcurrent: opts.maxConcurrent });
  const latency = opts.latencyMs ?? 120;
  const autoStart = opts.autoStart ?? typeof window !== 'undefined';
  if (autoStart) sim.start();

  /** Resolve after the simulated latency, unless aborted. */
  function respond<T>(make: () => T, o?: CallOptions, ms = latency): Promise<T> {
    return new Promise<T>((resolve, reject) => {
      if (o?.signal?.aborted) return reject(abortError());
      const t = setTimeout(() => {
        o?.signal?.removeEventListener('abort', onAbort);
        try {
          resolve(make());
        } catch (e) {
          reject(e);
        }
      }, ms);
      const onAbort = () => {
        clearTimeout(t);
        reject(abortError());
      };
      o?.signal?.addEventListener('abort', onAbort, { once: true });
    });
  }

  const findJob = (id: string): SimJob => {
    const j = sim.jobs.find((x) => x.id === id || x.record.id === id);
    if (!j) throw notFound('job', id);
    return j;
  };

  /** Push `make()` now (async) and whenever the simulator changes and `key()` differs. */
  function watch<T>(h: WatchHandlers<T>, make: () => T, key: () => string): Unsubscribe {
    let last: string | null = null;
    let disposed = false;
    const emit = () => {
      if (disposed) return;
      let k: string;
      try {
        k = key();
      } catch (e) {
        h.onError?.(e instanceof ApiError ? e : new ApiError({ status: 500, code: 'mock_error', message: String(e) }));
        return;
      }
      if (k === last) return;
      last = k;
      try {
        h.onData(make());
      } catch (e) {
        h.onError?.(e instanceof ApiError ? e : new ApiError({ status: 500, code: 'mock_error', message: String(e) }));
      }
    };
    const t = setTimeout(emit, Math.min(latency, 60));
    const unsub = sim.subscribe(emit);
    return () => {
      disposed = true;
      clearTimeout(t);
      unsub();
    };
  }

  const jobsKey = () => sim.jobs.map((j) => `${j.id}:${j.version}`).join('|');
  const agentKey = () => sim.agentTasks.map((t) => `${t.id}:${t.version}`).join('|');

  const api: MockHarnessApi = {
    mode: 'mock',

    health: (o) => respond<Health>(() => ({ ok: true, version: 'mock', runs_dir: '(mock: in-browser simulator)', mode: 'mock' }), o, 10),

    listJobs: (o) => respond(() => sim.jobs.map((j) => sim.jobSnapshot(j)), o),
    getJob: (id, o) => respond(() => sim.jobSnapshot(findJob(id)), o),
    watchJobs: (h) => watch<Job[]>(h, () => sim.jobs.map((j) => sim.jobSnapshot(j)), jobsKey),
    watchJob: (id, h) =>
      watch<Job>(
        h,
        () => sim.jobSnapshot(findJob(id)),
        () => {
          const j = findJob(id);
          return `${j.version}`;
        },
      ),

    getJobLog: (id, o) => respond(() => findJob(id).log.map((l) => ({ ...l })), o),
    streamJobLog: (id, h: LogStreamHandlers) => {
      let lastSeq = 0;
      let ended = false;
      let disposed = false;
      const flush = () => {
        if (disposed || ended) return;
        let j: SimJob;
        try {
          j = findJob(id);
        } catch (e) {
          ended = true;
          h.onStatus?.('failed');
          h.onError?.(e as ApiError);
          return;
        }
        for (const line of j.log) {
          if (line.seq > lastSeq) {
            lastSeq = line.seq;
            h.onLine({ ...line });
          }
        }
        if (j.status === 'done') {
          ended = true;
          h.onStatus?.('ended');
          h.onEnd?.();
        }
      };
      h.onStatus?.('connecting');
      const t = setTimeout(() => {
        if (disposed) return;
        h.onStatus?.('open');
        flush();
      }, Math.min(latency, 60));
      const unsub = sim.subscribe(flush);
      return () => {
        disposed = true;
        clearTimeout(t);
        unsub();
      };
    },

    getRunRecord: (runId, o) => respond(() => clone(sim.recordSnapshot(findJob(runId))), o),
    watchRunRecord: (runId, h) =>
      watch(
        h,
        () => clone(sim.recordSnapshot(findJob(runId))),
        () => {
          const j = findJob(runId);
          return `${j.status}|${j.layerIdx}|${j.log.length}`;
        },
      ),
    fileUrl: (runId, path) => resolveFileUrl(API_BASE, runId, path),
    assetUrl: (pathOrUrl) => resolveFileUrl(API_BASE, '', pathOrUrl),

    startRun: (settings, o) =>
      respond(() => {
        if (!settings.task || !settings.target) {
          throw new ApiError({ status: 422, code: 'invalid_settings', message: 'task and target are required' });
        }
        const job = sim.submit(formFromSettings(settings), settings.name);
        return { jobId: job.id, runId: job.record.id };
      }, o),
    interpret: (text, o) =>
      respond<InterpretResult>(() => {
        const r = interpretRun(text);
        return { settings: { task: r.task, tools: r.tools, target: r.target, partner: r.partner, ligand: r.ligand, reference: r.reference, ph: r.ph, seeds: r.seeds }, steps: r.steps, warnings: r.warnings };
      }, o),
    lookupEntities: (q, o) => respond(() => lookupEntities(q), o, Math.max(latency, 350)),
    getCatalog: (o) => respond<Catalog>(() => clone(CATALOG), o),
    listTools: (o) => respond<Tool[]>(() => clone(mockTools()), o),
    addTool: (spec, o) =>
      respond<Tool>(() => {
        const name = spec.name.trim();
        const id = name.toLowerCase().replace(/[^a-z0-9]/g, '');
        if (!id) throw new ApiError({ status: 422, code: 'invalid_tool', message: 'tool name is required' });
        const tool: Tool = { id, name, family: /dock/i.test(name) ? 'docking' : 'co-folding', role: 'Executor', version: spec.version || 'latest', available: true, outputs: [], custom: true };
        // Session register in data.ts: makeRunRecord resolves the run's tools from it.
        return clone(registerMockTool(tool));
      }, o),
    listTasks: (o) => respond<Task[]>(() => clone(TASKS), o),
    listExamples: (o) => respond<ExampleManifest[]>(() => [], o),
    getGlossary: (o) => respond<UiGlossary>(() => clone(GLOSSARY), o),
    uploadFiles: async (files, o) => {
      const out: UploadedFile[] = [];
      for (const f of files) {
        const ext = (f.name.split('.').pop() || '').toLowerCase();
        const kind = FILE_KINDS[ext] || 'file';
        out.push({ name: f.name, size: f.size, sha256: await sha256Hex(f), kind, status: 'ok', detail: PARSED[kind] || `${(f.size / 1024).toFixed(0)} kB` });
      }
      return respond<UploadResult>(() => ({ files: out }), o, 500);
    },

    listAgentTasks: (o) => respond(() => sim.agentTasks.map((t) => sim.agentSnapshot(t)), o),
    watchAgentTasks: (h) => watch<AgentTask[]>(h, () => sim.agentTasks.map((t) => sim.agentSnapshot(t)), agentKey),
    createAgentTask: (goal, o) => respond(() => sim.agentSnapshot(sim.addAgentTask(goal)), o),
    streamAgentSteps: (id, h: StepStreamHandlers) => {
      let lastSeq = 0;
      let ended = false;
      let disposed = false;
      const flush = () => {
        if (disposed || ended) return;
        const t = sim.agentTasks.find((x) => x.id === id);
        if (!t) {
          ended = true;
          h.onStatus?.('failed');
          h.onError?.(notFound('agent task', id));
          return;
        }
        for (const s of sim.revealedSteps(t)) {
          if (s.seq > lastSeq) {
            lastSeq = s.seq;
            h.onStep(s);
          }
        }
        if (t.status === 'done') {
          ended = true;
          h.onStatus?.('ended');
          h.onEnd?.();
        }
      };
      h.onStatus?.('connecting');
      const timer = setTimeout(() => {
        if (disposed) return;
        h.onStatus?.('open');
        flush();
      }, Math.min(latency, 60));
      const unsub = sim.subscribe(flush);
      return () => {
        disposed = true;
        clearTimeout(timer);
        unsub();
      };
    },

    mock: {
      simulator: sim,
      setSimSpeed: (speed) => {
        sim.simSpeed = speed;
      },
      setMaxConcurrent: (n) => {
        sim.maxConcurrent = n;
      },
      pause: () => sim.stop(),
      resume: () => sim.start(),
      advance: (ms) => sim.advance(ms),
    },
  };

  if (typeof window !== 'undefined') {
    (window as unknown as { __harnessMock?: MockControls }).__harnessMock = api.mock;
  }
  return api;
}
