// Port of the job and agent simulator in web/design/prototype/logic-v2.js (makeJob, startLines,
// suggestName, linesFor, emitLayer, tick, agent step playback). Same timing model: a 110 ms
// interval advances running jobs by dt * simSpeed through each layer's durationMs, emitting the
// layer's log lines proportionally; at most `maxConcurrent` jobs run at once; agent tasks reveal a
// step once its `ms` has elapsed, one task running at a time.
//
// With a seed, the clock is virtual (fixed base time + simulated ms) and each tick advances exactly
// 110 ms, so record ids, timings and logs repeat across page loads (tests, video recording).

import type { AgentStep, AgentTask, Job, JobLayer, LogKind, LogLine, Result, UiCheck, UiRunRecord } from '../types';
import {
  AGENT_TASKS,
  CATALOG,
  PRESET_JOBS,
  TASKS,
  countResults,
  makeRunRecord,
  resetMockCounters,
  type MockAgentTask,
  type MockForm,
} from './data';

export const TICK_MS = 110;
/** Base of the virtual clock for seeded sessions: 2026-10-17 12:00:00 UTC. */
export const SEED_BASE_TIME = Date.UTC(2026, 9, 17, 12, 0, 0);

export interface SimulatorOptions {
  seed?: number;
  simSpeed?: number;
  maxConcurrent?: number;
}

interface ProtoLine {
  layer: number | null;
  kind: LogKind;
  result?: Result | null;
  t?: string;
  text: string;
  plain: string;
}

export interface SimJob {
  id: string;
  name: string;
  form: MockForm;
  record: UiRunRecord;
  status: 'queued' | 'running' | 'done';
  layerIdx: number;
  progress: number;
  elapsedMs: number;
  log: LogLine[];
  emitted: Record<number, number>;
  createdAt: number;
  /** Bumped on every change, for cheap change detection by subscribers. */
  version: number;
}

export interface SimAgentTask extends MockAgentTask {
  total: number;
  elapsedMs: number;
  startedAt: number;
  version: number;
}

const worst = (checks: UiCheck[]): Result =>
  checks.some((c) => c.result === 'stop') ? 'stop' : checks.some((c) => c.result === 'warn') ? 'warn' : 'pass';

export class Simulator {
  jobs: SimJob[] = [];
  agentTasks: SimAgentTask[] = [];
  simSpeed: number;
  maxConcurrent: number;
  readonly seed: number | undefined;
  /** Incremented on every tick that changed something. */
  tickCount = 0;

  private virtualNow: number;
  private last = 0;
  private timer: ReturnType<typeof setInterval> | null = null;
  private listeners = new Set<() => void>();
  private agentCounter = 0;

  constructor(opts: SimulatorOptions = {}) {
    this.seed = opts.seed;
    this.simSpeed = opts.simSpeed ?? 1;
    this.maxConcurrent = opts.maxConcurrent ?? 3;
    this.virtualNow = SEED_BASE_TIME + (opts.seed ?? 0) * 60000;
    if (this.seed !== undefined) resetMockCounters();
    const now = this.now();
    this.jobs = PRESET_JOBS.map((p, i) => this.makeJob(p.form, p.name, now - (3 - i) * 95000, p.status, p.layerIdx));
    this.agentTasks = AGENT_TASKS.map((t) => {
      const total = t.steps.reduce((a, s) => a + s.ms, 0);
      const elapsed = t.status === 'done' ? total : t.status === 'running' ? Math.round(total * 0.45) : 0;
      return { ...t, steps: [...t.steps], total, elapsedMs: elapsed, startedAt: now - elapsed, version: 0 };
    });
  }

  /** Wall clock, or the virtual clock in a seeded session. */
  now(): number {
    return this.seed !== undefined ? this.virtualNow : Date.now();
  }

  get running(): boolean {
    return this.timer !== null;
  }

  start(): void {
    if (this.timer) return;
    this.last = typeof performance !== 'undefined' ? performance.now() : Date.now();
    this.timer = setInterval(() => this.tick(), TICK_MS);
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  }

  /** Run ticks synchronously until `ms` of simulated wall time has passed (tests, video). */
  advance(ms: number): void {
    let left = ms;
    while (left > 0) {
      const dt = Math.min(TICK_MS, left);
      this.step(dt);
      left -= dt;
    }
  }

  subscribe(fn: () => void): () => void {
    this.listeners.add(fn);
    return () => {
      this.listeners.delete(fn);
    };
  }

  // ---------- jobs ----------

  suggestName(form: MockForm): string {
    const t = TASKS.find((x) => x.id === form.task);
    const p = CATALOG.proteins.find((pp) => pp.accession === form.target);
    return `${p ? p.label : form.target} · ${t ? t.name.toLowerCase() : 'run'}`;
  }

  makeJob(form: MockForm, name: string | undefined, createdAt: number, status: SimJob['status'] = 'queued', layerIdx = 0): SimJob {
    const record = makeRunRecord(form, createdAt);
    const job: SimJob = {
      id: record.id,
      name: name || this.suggestName(form),
      form,
      record,
      status,
      layerIdx: status === 'done' ? 6 : layerIdx,
      progress: 0,
      elapsedMs: 0,
      log: [],
      emitted: {},
      createdAt,
      version: 0,
    };
    if (status !== 'queued') {
      this.startLines(job);
      const n = status === 'done' ? 6 : layerIdx;
      for (let i = 0; i < n; i++) {
        job.elapsedMs += record.layers[i].durationMs ?? 0;
        this.emitLayer(job, i, 1);
      }
    }
    return job;
  }

  /** Queue a new job at the top of the list (prototype `submit()`). */
  submit(form: MockForm, name?: string): SimJob {
    const job = this.makeJob({ ...form, seeds: +form.seeds || 5, ph: +form.ph || 7.4 }, name || this.suggestName(form), this.now(), 'queued');
    this.jobs = [job, ...this.jobs];
    this.notify();
    return job;
  }

  private push(job: SimJob, line: ProtoLine): void {
    const seq = job.log.length + 1;
    const out: LogLine = {
      seq,
      ts: new Date(job.createdAt + job.elapsedMs).toISOString(),
      t: line.t ?? `${(job.elapsedMs / 1000).toFixed(1)}s`,
      layer: line.layer,
      kind: line.kind,
      text: line.text,
      plain: line.plain,
    };
    if (line.result) out.result = line.result;
    job.log.push(out);
  }

  startLines(job: SimJob): void {
    this.push(job, {
      layer: 0,
      kind: 'exec',
      t: '0.0s',
      text: `slot acquired · ${job.record.tools.map((t) => t.container).join(' ')}`,
      plain: `Started. ${job.record.tools.map((t) => t.name).join(' and ')} outputs are precomputed; checks run live.`,
    });
    (job.record.execution || []).forEach((e) => this.push(job, { layer: 0, kind: 'exec', t: '0.0s', text: e.text, plain: e.plain }));
  }

  linesFor(job: SimJob, i: number): ProtoLine[] {
    const rec = job.record;
    const chk = (c: UiCheck): ProtoLine => ({
      layer: i,
      kind: 'check',
      result: c.result,
      text: `${c.id} [${c.tool}] → ${c.result} · ${c.evidence} · ${c.ms} ms`,
      plain: `${c.name}: ${c.evidence}`,
    });
    if (i === 0) {
      return rec.sources
        .map((s): ProtoLine => ({
          layer: 0,
          kind: s.cached ? 'cache' : 'fetch',
          result: null,
          text: `${s.cached ? 'cache' : 'GET'} ${s.source} ${s.accession} · ${s.release} · sha256 ${s.sha256.slice(0, 10)}… · ${s.ms} ms`,
          plain: `${s.cached ? 'Used cached' : 'Fetched'} ${(s.supplies || '').toLowerCase()} from ${s.source} (${s.accession}, ${s.release}) in ${s.ms} ms`,
        }))
        .concat(rec.layers[0].checks.map(chk));
    }
    return rec.layers[i].checks.map(chk);
  }

  emitLayer(job: SimJob, i: number, frac: number): void {
    const lines = this.linesFor(job, i);
    const want = Math.min(lines.length, Math.floor(frac * lines.length + 1e-6));
    const have = job.emitted[i] || 0;
    for (let k = have; k < want; k++) this.push(job, { ...lines[k], t: `${(job.elapsedMs / 1000).toFixed(1)}s` });
    job.emitted[i] = Math.max(have, want);
    if (frac >= 1 && !job.log.some((l) => l.kind === 'layer' && l.layer === i)) {
      const L = job.record.layers[i];
      const chk = L.checks;
      const stops = chk.filter((c) => c.result === 'stop').length;
      const warns = chk.filter((c) => c.result === 'warn').length;
      this.push(job, {
        layer: i,
        kind: 'layer',
        result: stops ? 'stop' : warns ? 'warn' : 'pass',
        t: `${(job.elapsedMs / 1000).toFixed(1)}s`,
        text: `── ${L.name.toLowerCase()} · ${chk.length} checks · ${stops ? stops + ' stop' : warns ? warns + ' warn' : 'clean'} · ${L.durationMs} ms`,
        plain: `${L.name} finished in ${((L.durationMs ?? 0) / 1000).toFixed(1)} s: ${chk.length} checks, ${stops ? stops + ' stopped the claim' : warns ? warns + ' warned' : 'all clean'}.`,
      });
    }
  }

  tick(): void {
    const nowP = typeof performance !== 'undefined' ? performance.now() : Date.now();
    const measured = Math.min(400, nowP - this.last);
    this.last = nowP;
    this.step(this.seed !== undefined ? TICK_MS : measured);
  }

  /** One simulator step of `dt` wall ms (prototype `tick()`). */
  step(dt: number): void {
    if (this.seed !== undefined) this.virtualNow += dt;
    const speed = this.simSpeed;
    const maxC = this.maxConcurrent;
    let changed = false;
    let running = this.jobs.filter((j) => j.status === 'running').length;
    for (const j of this.jobs) {
      if (j.status === 'queued' && running < maxC) {
        j.status = 'running';
        this.startLines(j);
        running++;
        changed = true;
        j.version++;
      }
      if (j.status !== 'running') continue;
      changed = true;
      j.version++;
      j.elapsedMs += dt * speed;
      j.progress += (dt * speed) / (j.record.layers[j.layerIdx].durationMs || 1);
      if (j.progress >= 1) {
        this.emitLayer(j, j.layerIdx, 1);
        j.layerIdx += 1;
        j.progress = 0;
        if (j.layerIdx >= 6) {
          j.status = 'done';
          const o = j.record.verdict.outcome;
          this.push(j, {
            layer: 5,
            kind: 'layer',
            result: o === 'refused' ? 'stop' : o === 'narrowed' ? 'warn' : 'pass',
            t: `${(j.elapsedMs / 1000).toFixed(1)}s`,
            text: `verdict · ${o} · ${(j.elapsedMs / 1000).toFixed(1)} s total · report generated`,
            plain: `Verdict: ${o} after ${(j.elapsedMs / 1000).toFixed(1)} s. The report is ready.`,
          });
        }
      } else this.emitLayer(j, j.layerIdx, j.progress);
    }
    if (this.agentTasks.length) {
      let anyRunning = this.agentTasks.some((t) => t.status === 'running');
      for (const t of this.agentTasks) {
        if (t.status === 'queued' && !anyRunning) {
          t.status = 'running';
          t.startedAt = this.now() - t.elapsedMs;
          anyRunning = true;
          changed = true;
          t.version++;
        }
        if (t.status !== 'running') continue;
        t.elapsedMs += dt * speed;
        changed = true;
        t.version++;
        if (t.elapsedMs >= t.total) {
          t.elapsedMs = t.total;
          t.status = 'done';
          anyRunning = false;
        }
      }
    }
    if (changed) {
      this.tickCount++;
      this.notify();
    }
  }

  private notify(): void {
    this.listeners.forEach((fn) => {
      try {
        fn();
      } catch {
        /* a failing subscriber never stops the simulator */
      }
    });
  }

  // ---------- agent ----------

  addAgentTask(goal: string): SimAgentTask {
    this.agentCounter += 1;
    const t: SimAgentTask = {
      id: `agent_new_${String(this.agentCounter).padStart(2, '0')}`,
      goal,
      status: 'queued',
      steps: [],
      outcome: { label: 'Completed', detail: 'no steps reported', runs: 0, reports: 0 },
      total: 0,
      elapsedMs: 0,
      startedAt: this.now(),
      version: 0,
    };
    this.agentTasks = [...this.agentTasks, t];
    this.notify();
    return t;
  }

  // ---------- snapshots (wire shapes) ----------

  jobSnapshot(j: SimJob): Job {
    const task = TASKS.find((t) => t.id === j.form.task);
    const layers: JobLayer[] = j.record.layers.map((l, i) => {
      if (i < j.layerIdx) return { i, result: worst(l.checks), done: true };
      if (i === j.layerIdx && j.status === 'running') {
        const emittedChecks = j.log.filter((x) => x.kind === 'check' && x.layer === i && x.result);
        const res = emittedChecks.some((x) => x.result === 'stop') ? 'stop' : emittedChecks.some((x) => x.result === 'warn') ? 'warn' : emittedChecks.length ? 'pass' : null;
        return { i, result: res, done: false };
      }
      return { i, result: null, done: false };
    });
    return {
      id: j.id,
      runId: j.record.id,
      name: j.name,
      task: j.form.task,
      taskName: task?.name ?? j.form.task,
      tools: j.record.tools.map((t) => t.name),
      seeds: j.form.seeds,
      status: j.status,
      layerIdx: j.layerIdx,
      progress: j.progress,
      elapsedMs: Math.round(j.elapsedMs),
      createdAt: new Date(j.createdAt).toISOString(),
      layers,
      verdict: j.status === 'done' ? j.record.verdict.outcome : null,
    };
  }

  /** The record as the live adapter would build it at this point of the run. */
  recordSnapshot(j: SimJob): UiRunRecord {
    if (j.status === 'done') return j.record;
    const layers = j.record.layers.map((l, i) => {
      if (i < j.layerIdx) return l;
      const running = i === j.layerIdx && j.status === 'running';
      const seen = running ? j.log.filter((x) => x.kind === 'check' && x.layer === i).length : 0;
      const checks = l.checks.map((c, k) => (k < seen ? c : { id: c.id, name: c.name, tool: c.tool, gate: c.gate, result: 'pending' as const }));
      const { durationMs: _omit, ...rest } = l;
      void _omit;
      return { ...rest, status: running ? ('running' as const) : ('pending' as const), checks, counts: countResults(checks.filter((c) => c.result !== 'pending')) };
    });
    const doneLayers = layers.filter((l) => l.status === 'done');
    const stops = doneLayers.flatMap((l) => l.checks.filter((c) => c.result === 'stop').map((c) => c.id));
    const warnings = doneLayers.flatMap((l) => l.checks.filter((c) => c.result === 'warn').map((c) => c.id));
    return {
      ...j.record,
      status: j.status,
      layers,
      verdict: { claim: j.record.claim, outcome: null, statement: '', stops, warnings, incomplete: layers.filter((l) => l.status !== 'done').map((l) => String(l.key)) },
      narrative: [],
    };
  }

  agentSnapshot(t: SimAgentTask): AgentTask {
    return {
      id: t.id,
      goal: t.goal,
      status: t.status,
      createdAt: new Date(t.startedAt).toISOString(),
      progress: t.total ? Math.min(1, t.elapsedMs / t.total) : t.status === 'done' ? 1 : 0,
      steps: this.revealedSteps(t),
      outcome: t.status === 'done' ? { ...t.outcome } : null,
      stepsTotal: t.steps.length,
      elapsedMs: Math.round(t.elapsedMs),
    };
  }

  /** Steps whose time has elapsed (prototype `prog()`), with seq and ts. */
  revealedSteps(t: SimAgentTask): AgentStep[] {
    const out: AgentStep[] = [];
    let acc = 0;
    for (let i = 0; i < t.steps.length; i++) {
      const s = t.steps[i];
      const t0 = acc;
      acc += s.ms;
      if (t.elapsedMs >= acc) out.push({ seq: i + 1, ts: new Date(t.startedAt + t0).toISOString(), kind: s.kind, text: s.text, ms: s.ms });
      else break;
    }
    return out;
  }
}
