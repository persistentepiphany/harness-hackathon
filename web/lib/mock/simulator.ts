// Port of the job and agent simulator in web/design/prototype/logic-v2.js (makeJob, startLines,
// suggestName, linesFor, emitLayer, tick, agent step playback). Same timing model: a 110 ms
// interval advances running jobs by dt * simSpeed through each layer's durationMs, emitting the
// layer's log lines proportionally; at most `maxConcurrent` jobs run at once; agent tasks reveal a
// step once its `ms` has elapsed, one task running at a time.
//
// With a seed, the clock is virtual (fixed base time + simulated ms) and each tick advances exactly
// 110 ms, so record ids, timings and logs repeat across page loads (tests, video recording).

import type { AgentStep, AgentTask, ExecutionPhase, Job, JobLayer, LogKind, LogLine, RecordRender, Result, UiCheck, UiExecution, UiRunRecord } from '../types';
import {
  AGENT_TASKS,
  CATALOG,
  MOCK_RUNTIME,
  PRESET_JOBS,
  TASKS,
  countResults,
  dimensionsFor,
  executionPlan,
  makeRunRecord,
  mockRenderSvg,
  resetMockCounters,
  toolVersionsFor,
  type MockAgentTask,
  type MockExecPlan,
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

/** Report stage (renders, figures, provenance graph) in simulated ms. */
export const REPORT_MS = 900;

/** Stage of a running job: pre-run layers 0–3, execute, output layers 4–5, report. */
export type SimStage = 'pre' | 'execute' | 'output' | 'report' | 'done';

export interface SimJob {
  id: string;
  name: string;
  form: MockForm;
  record: UiRunRecord;
  status: 'queued' | 'running' | 'done';
  /** RunSettings.execute and at least one dispatchable executor. */
  execute: boolean;
  stage: SimStage;
  plan: MockExecPlan[];
  /** Simulated ms into the execute stage, and the job's elapsed ms when it began. */
  execT: number;
  execAt: number | null;
  reportT: number;
  /** Execution state last logged per executor (`phase:seed`), to log transitions once. */
  execLogged: Record<string, string>;
  /** The execute stage was simulated in this session (renders are written). */
  live: boolean;
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
  checks.some((c) => c.result === 'stop') ? 'stop' : checks.some((c) => c.result === 'warn') ? 'warn' : checks.length && checks.every((c) => c.result === 'skip') ? 'skip' : 'pass';

const TERMINAL: ExecutionPhase[] = ['done', 'failed', 'skipped'];

/** State of one executor `t` ms into the execute stage (queue, build, seeds one after another). */
export function execAt(p: MockExecPlan, t: number, stageStartIso: string | null): UiExecution {
  const base = { executor: p.executor, name: p.name, gpu: p.gpu, route: p.dispatchable ? p.route : null, routeNote: p.routeNote };
  if (!p.dispatchable) return { ...base, phase: 'skipped', startedAt: null, elapsedMs: null, seeds: [], message: `not dispatched: ${p.note || 'no runtime'}` };
  const started = stageStartIso ? new Date(new Date(stageStartIso).getTime() + p.queueMs).toISOString() : null;
  if (t < p.queueMs) return { ...base, phase: 'queued', startedAt: null, elapsedMs: null, seeds: p.seeds.map((x) => ({ seed: x.seed, phase: 'queued', ms: null })), message: `waiting for a ${p.gpu ?? 'CPU'} slot` };
  const since = t - p.queueMs;
  if (since < p.buildMs) {
    return { ...base, phase: 'building', startedAt: started, elapsedMs: Math.round(since), seeds: p.seeds.map((x) => ({ seed: x.seed, phase: 'queued', ms: null })), message: p.route === 'kit' ? 'loading the accelerated kit image' : p.route === 'local' ? 'preparing local inputs' : 'pulling the stock image' };
  }
  let r = since - p.buildMs;
  const seeds = p.seeds.map((x) => {
    if (r >= x.ms) {
      r -= x.ms;
      return { seed: x.seed, phase: 'done', ms: x.ms };
    }
    if (r >= 0) {
      const ms = Math.round(r);
      r = -1;
      return { seed: x.seed, phase: 'running', ms };
    }
    return { seed: x.seed, phase: 'queued', ms: null };
  });
  const done = seeds.every((x) => x.phase === 'done');
  const cur = seeds.find((x) => x.phase === 'running');
  const total = p.buildMs + p.seeds.reduce((a, x) => a + x.ms, 0);
  return {
    ...base,
    phase: done ? 'done' : 'running',
    startedAt: started,
    elapsedMs: Math.round(done ? total : since),
    seeds,
    message: done ? `${seeds.length} seeds done` : `seed ${cur ? cur.seed + 1 : seeds.filter((x) => x.phase === 'done').length}/${seeds.length}`,
  };
}

const planTotal = (p: MockExecPlan) => (p.dispatchable ? p.queueMs + p.buildMs + p.seeds.reduce((a, x) => a + x.ms, 0) : 0);

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

  makeJob(form0: MockForm, name: string | undefined, createdAt: number, status: SimJob['status'] = 'queued', layerIdx = 0): SimJob {
    // execute only when asked and some selected executor can be dispatched (else a pre-run check)
    const execute = form0.execute !== false && form0.tools.some((id) => MOCK_RUNTIME[id]?.dispatchable);
    const form = { ...form0, execute };
    const record = makeRunRecord(form, createdAt);
    const plan = execute ? executionPlan(record.tools, form.seeds, createdAt) : [];
    const job: SimJob = {
      id: record.id,
      name: name || this.suggestName(form),
      form,
      record,
      status,
      execute,
      stage: status === 'done' ? 'done' : layerIdx >= 4 ? 'output' : 'pre',
      plan,
      execT: 0,
      execAt: null,
      reportT: 0,
      execLogged: {},
      live: false,
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
        if (i === 4 && execute) {
          job.execAt = job.elapsedMs;
          job.execT = Math.max(0, ...plan.map(planTotal));
          job.elapsedMs += job.execT;
          this.logExecution(job);
        }
        job.elapsedMs += record.layers[i].durationMs ?? 0;
        if (i >= 4 && !execute) this.emitPending(job, i);
        else this.emitLayer(job, i, 1);
      }
      if (status === 'done') {
        job.elapsedMs += REPORT_MS;
        job.reportT = REPORT_MS;
        job.record = this.finalRecord(job);
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
    const names = job.record.tools.map((t) => t.name).join(' and ');
    const run = job.plan.filter((p) => p.dispatchable);
    this.push(job, {
      layer: 0,
      kind: 'exec',
      t: '0.0s',
      text: `slot acquired · ${job.record.tools.map((t) => t.container).join(' ')} · execute=${job.execute ? 'yes' : 'no'}`,
      plain: job.execute
        ? `Started. Layers 0–3 check the inputs, then ${run.map((p) => `${p.name} (${p.gpu ?? 'CPU'}, ${p.route})`).join(' and ')} run, then layers 4–5 check their outputs.`
        : `Started a pre-run check. ${names} are not run; layers 0–3 check the inputs and the output checks wait for predictions.`,
    });
  }

  /** Log the execution transitions not logged yet (phase changes, each seed finished, renders). */
  private logExecution(job: SimJob): void {
    const iso = job.execAt === null ? null : new Date(job.createdAt + job.execAt).toISOString();
    for (const p of job.plan) {
      const e = execAt(p, job.execT, iso);
      const doneSeeds = e.seeds.filter((x) => x.phase === 'done');
      const key = `${e.phase}:${doneSeeds.length}`;
      const prev = job.execLogged[p.executor];
      if (prev === key) continue;
      const [prevPhase, prevSeeds] = prev ? prev.split(':') : ['', '0'];
      const where = `${p.gpu ?? 'CPU'} · ${p.route} route`;
      if (e.phase !== prevPhase) {
        const text =
          e.phase === 'queued' ? `execute ${p.executor} · queued · ${where}`
          : e.phase === 'building' ? `execute ${p.executor} · building · ${p.routeNote}`
          : e.phase === 'running' ? `execute ${p.executor} · running · ${p.seeds.length} seeds · ${where}`
          : e.phase === 'done' ? `execute ${p.executor} · done · ${((e.elapsedMs ?? 0) / 1000).toFixed(1)} s`
          : `execute ${p.executor} · ${e.phase} · ${e.message ?? ''}`;
        const plain =
          e.phase === 'queued' ? `${p.name} queued for ${p.gpu ? `an ${p.gpu} GPU on Modal` : 'a local CPU slot'}.`
          : e.phase === 'building' ? `${p.name}: ${p.routeNote}.`
          : e.phase === 'running' ? `${p.name} engaged on ${p.gpu ?? 'CPU'} (${p.route} route): ${p.seeds.length} seeds.`
          : e.phase === 'done' ? `${p.name} finished ${p.seeds.length} seeds in ${((e.elapsedMs ?? 0) / 1000).toFixed(1)} s.`
          : `${p.name} not run: ${e.message ?? 'no runtime'}.`;
        if (e.phase === 'done') {
          this.pushSeeds(job, p, doneSeeds, +prevSeeds);
          this.push(job, { layer: null, kind: 'exec', text, plain });
        } else {
          this.push(job, { layer: null, kind: 'exec', text, plain });
          this.pushSeeds(job, p, doneSeeds, +prevSeeds);
        }
      } else this.pushSeeds(job, p, doneSeeds, +prevSeeds);
      job.execLogged[p.executor] = key;
    }
  }

  private pushSeeds(job: SimJob, p: MockExecPlan, done: { seed: number; ms?: number | null }[], from: number): void {
    for (const x of done.slice(from)) {
      this.push(job, { layer: null, kind: 'exec', text: `execute ${p.executor} · seed ${x.seed} done · ${x.ms} ms`, plain: `${p.name} seed ${x.seed} done in ${((x.ms ?? 0) / 1000).toFixed(1)} s.` });
      this.push(job, { layer: null, kind: 'artifact', text: `artifact render ${p.executor}_seed${x.seed}.png · pse`, plain: `PyMOL render of ${p.name} seed ${x.seed} written.` });
    }
  }

  /** Pre-run: an output layer whose checks wait for predictions. */
  private emitPending(job: SimJob, i: number): void {
    const L = job.record.layers[i];
    job.emitted[i] = this.linesFor(job, i).length;
    if (job.log.some((l) => l.kind === 'layer' && l.layer === i)) return;
    this.push(job, {
      layer: i,
      kind: 'layer',
      result: 'skip',
      text: `── ${L.name.toLowerCase()} · ${L.checks.length} checks · pending_input · pre-run`,
      plain: `${L.name}: ${L.checks.length} checks wait for predictions (pre-run check, no executor ran).`,
    });
  }

  /** Executions of the job at this point (none for a pre-run check). */
  execution(job: SimJob): UiExecution[] {
    if (!job.execute) return [];
    const iso = job.execAt === null ? null : new Date(job.createdAt + job.execAt).toISOString();
    return job.plan.map((p) => execAt(p, job.execAt === null ? 0 : job.execT, iso));
  }

  /** Renders written so far: one per finished seed of each executor (mock thumbnails). */
  renders(job: SimJob): (RecordRender & Record<string, unknown>)[] {
    const out: (RecordRender & Record<string, unknown>)[] = [];
    const ex = this.execution(job);
    const l4 = job.record.layers[4];
    const l4done = job.layerIdx > 4 || job.status === 'done';
    const pb = l4?.checks.filter((c) => /posebusters|clash/.test(c.id)) ?? [];
    for (const e of ex) {
      const tool = job.record.tools.find((t) => t.id === e.executor);
      const key = tool?.outputs?.find((o) => o.kind === 'confidence' || o.kind === 'score' || o.kind === 'affinity');
      e.seeds.forEach((x, rank) => {
        if (x.phase !== 'done') return;
        const value = key ? Math.round((key.kind === 'affinity' && key.higherIsBetter === false ? -9.6 + ((x.seed * 7) % 10) / 10 : 0.62 + ((x.seed * 13 + rank * 3) % 30) / 100) * 100) / 100 : null;
        const checks = l4done ? pb.map((c) => ({ id: c.id, name: c.name, result: x.seed === 3 && c.id === 'posebusters.clash' ? ('warn' as const) : c.result })) : [];
        out.push({
          structure: `${e.executor}_seed${x.seed}`,
          png: mockRenderSvg(e.executor, x.seed),
          pse: '',
          view: 'overview',
          caption: `${e.name} seed ${x.seed} (mock render)`,
          alt: `Schematic placeholder for the ${e.name} seed ${x.seed} pose (mock mode, no PyMOL)`,
          executor: e.executor,
          seed: x.seed,
          rank: rank + 1,
          score: key && value !== null ? { key: key.key, label: key.label, value, unit: key.unit ?? null } : null,
          checks,
        });
      });
    }
    return out;
  }

  /** The record once the job is done: final execution, renders when executors ran. */
  private finalRecord(job: SimJob): UiRunRecord {
    if (!job.execute) return job.record;
    // renders only for executions simulated in this session (the presets' reports stay as they were)
    const renders = job.live ? this.renders(job) : [];
    return { ...job.record, execution: this.execution(job), ...(renders.length ? { renders } : {}) };
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
      const d = dt * speed;
      j.elapsedMs += d;
      if (j.stage === 'execute') {
        j.execT += d;
        this.logExecution(j);
        if (this.execution(j).every((e) => TERMINAL.includes(e.phase))) {
          j.stage = 'output';
          j.progress = 0;
          this.push(j, { layer: 4, kind: 'exec', text: `execute done · ${(j.execT / 1000).toFixed(1)} s · outputs → layer 4`, plain: `Executors finished in ${(j.execT / 1000).toFixed(1)} s. Output checks start.` });
        }
        continue;
      }
      if (j.stage === 'report') {
        j.reportT += d;
        if (j.reportT >= REPORT_MS) this.finish(j);
        continue;
      }
      j.progress += d / (j.record.layers[j.layerIdx].durationMs || 1);
      if (j.progress >= 1) {
        this.emitLayer(j, j.layerIdx, 1);
        j.layerIdx += 1;
        j.progress = 0;
        if (j.layerIdx === 4 && j.execute) {
          j.stage = 'execute';
          j.live = true;
          j.execAt = j.elapsedMs;
          j.execT = 0;
          this.logExecution(j);
        } else if (j.layerIdx === 4 && !j.execute) {
          this.emitPending(j, 4);
          this.emitPending(j, 5);
          j.layerIdx = 6;
          this.startReport(j);
        } else if (j.layerIdx >= 6) {
          j.layerIdx = 6;
          this.startReport(j);
        } else if (j.layerIdx >= 4) j.stage = 'output';
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

  private startReport(j: SimJob): void {
    j.stage = 'report';
    j.reportT = 0;
    j.progress = 1;
    this.push(j, { layer: null, kind: 'artifact', text: `report · renders, figures, provenance graph`, plain: 'Writing the report: renders, figures and the provenance graph.' });
  }

  private finish(j: SimJob): void {
    j.status = 'done';
    j.stage = 'done';
    j.layerIdx = 6;
    j.record = this.finalRecord(j);
    const o = j.record.verdict.outcome;
    this.push(j, {
      layer: 5,
      kind: 'layer',
      result: o === 'refused' ? 'stop' : o === 'narrowed' ? 'warn' : o === 'not_assessed' ? 'skip' : 'pass',
      text: `verdict · ${o} · ${(j.elapsedMs / 1000).toFixed(1)} s total · report generated`,
      plain: o === 'not_assessed' ? `Pre-run check done after ${(j.elapsedMs / 1000).toFixed(1)} s: inputs checked, claim not assessed. The report is ready.` : `Verdict: ${o} after ${(j.elapsedMs / 1000).toFixed(1)} s. The report is ready.`,
    });
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
      assessment: j.execute ? 'full' : 'pre-run',
      execution: this.execution(j),
      reportStatus: j.stage === 'report' ? 'running' : j.status === 'done' ? 'done' : undefined,
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
    const renders = j.live ? this.renders(j) : [];
    return {
      ...j.record,
      status: j.status,
      layers,
      verdict: { claim: j.record.claim, outcome: null, statement: '', stops, warnings, incomplete: layers.filter((l) => l.status !== 'done').map((l) => String(l.key)) },
      narrative: [],
      assessment: j.execute ? 'full' : 'pre-run',
      evaluatedLayers: layers.filter((l) => l.status === 'done' && l.checks.some((c) => c.result !== 'skip' && c.result !== 'pending')).map((l) => l.i),
      dimensions: dimensionsFor(layers),
      toolVersions: toolVersionsFor(j.record.tools, layers, j.execute && j.stage !== 'pre' && j.stage !== 'execute'),
      execution: this.execution(j),
      tools: j.record.tools.map((t) => ({ ...t, ran: false, ranBy: null })),
      ...(renders.length ? { renders } : { renders: undefined }),
      ...(j.stage === 'report' ? { report: { status: 'running' } } : {}),
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
