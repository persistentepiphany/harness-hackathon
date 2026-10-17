import { describe, expect, it } from 'vitest';
import { THIN } from '@/lib/format';
import type { AgentStep, AgentTask } from '@/lib/types';
import {
  INITIAL_FOLLOW,
  agentSummary,
  defaultTaskId,
  fmtSteps,
  nextFollow,
  pendingLabel,
  runLinks,
  runRefs,
  runsOf,
  stepCount,
  stepCounts,
  stepViews,
  taskCard,
  taskElapsedMs,
} from './agent';

const T0 = '2026-10-17T15:46:07.000Z';

/** Live wire shape: `steps` is a count, `data` and `ms` may be null. */
function liveTask(over: Partial<Record<keyof AgentTask, unknown>> = {}): AgentTask {
  return {
    id: '20261017154607-a18ccf',
    goal: 'Decide whether the 3PTB inputs support a pose claim',
    status: 'running',
    createdAt: T0,
    progress: 0,
    steps: 3,
    outcome: null,
    elapsedMs: 2000,
    ...over,
  } as unknown as AgentTask;
}

const step = (seq: number, kind: AgentStep['kind'], text: string, offsetMs: number, extra: Partial<AgentStep> = {}): AgentStep => ({
  seq,
  ts: new Date(Date.parse(T0) + offsetMs).toISOString(),
  kind,
  text,
  ...extra,
});

describe('stepCount', () => {
  it('reads the live count and the mock step list', () => {
    expect(stepCount(liveTask({ steps: 4 }))).toBe(4);
    expect(stepCount(liveTask({ steps: [step(1, 'thought', 'a', 0), step(2, 'tool', 'b', 10)] }))).toBe(2);
    expect(stepCount(liveTask({ steps: undefined }))).toBe(0);
  });
});

describe('agentSummary and defaultTaskId', () => {
  it('counts running and completed, failed only when present', () => {
    const tasks = [liveTask({ status: 'running' }), liveTask({ status: 'done' }), liveTask({ status: 'done' })];
    expect(agentSummary(tasks)).toBe('1 running · 2 completed');
    expect(agentSummary([...tasks, liveTask({ status: 'failed' })])).toBe('1 running · 2 completed · 1 failed');
  });
  it('picks the first running task, else the first', () => {
    expect(defaultTaskId([liveTask({ id: 'a', status: 'done' }), liveTask({ id: 'b', status: 'running' })])).toBe('b');
    expect(defaultTaskId([liveTask({ id: 'a', status: 'done' }), liveTask({ id: 'b', status: 'done' })])).toBe('a');
    expect(defaultTaskId([])).toBeNull();
  });
});

describe('nextFollow', () => {
  it('keeps the first selection and follows tasks that start later', () => {
    const first = [liveTask({ id: 'a', status: 'done' }), liveTask({ id: 'b', status: 'running' }), liveTask({ id: 'c', status: 'queued' })];
    let f = nextFollow(INITIAL_FOLLOW, first);
    expect(f.auto).toBe('b');
    // b finishes, c (known since the first load) starts: the selection stays on b
    const later = [liveTask({ id: 'a', status: 'done' }), liveTask({ id: 'b', status: 'done' }), liveTask({ id: 'c', status: 'running' })];
    expect(nextFollow(f, later)).toBe(f);
    // a new task appears running: it is followed
    f = nextFollow(f, [liveTask({ id: 'd', status: 'running' }), ...later]);
    expect(f.auto).toBe('d');
    expect(f.seen).toEqual(['a', 'b', 'c', 'd']);
    // a new finished task does not take the selection
    expect(nextFollow(f, [liveTask({ id: 'e', status: 'done' }), ...later]).auto).toBe('d');
  });
});

describe('taskCard', () => {
  it('shows a live running task without a planned total', () => {
    const c = taskCard(liveTask({ progress: 0.5, elapsedMs: 1500 }), { live: true, nowMs: Date.parse(T0) + 4200 });
    expect(c.statusLabel).toBe('running');
    expect(c.pct).toBe(50);
    expect(c.stepsTotal).toBeNull();
    expect(c.stepLabel).toBe('3 steps');
    expect(c.elapsedMs).toBe(4200);
  });
  it('uses streamed steps when they are ahead of the polled count, and counts referenced runs', () => {
    const steps = [step(1, 'thought', 'plan', 0), step(2, 'tool', 'harness.submit', 900, { data: { runId: 'ui-3ptb' } }), step(3, 'result', 'queued', 1000), step(4, 'tool', 'harness.wait ui-3ptb', 2000, { data: { runId: 'ui-3ptb' } })];
    const c = taskCard(liveTask({ steps: 2 }), { live: true, nowMs: Date.parse(T0) + 3000, steps });
    expect(c.stepsDone).toBe(4);
    expect(c.runs).toBe(1);
    expect(c.stepLabel).toBe('4 steps · 1 runs');
  });
  it('shows a finished task with its outcome label and final count', () => {
    const c = taskCard(liveTask({ status: 'done', progress: 1, steps: 5, outcome: { label: 'Completed', detail: '1 run', runs: 1 }, elapsedMs: 9100 }), {
      live: true,
      nowMs: Date.parse(T0) + 60000,
    });
    expect(c.statusLabel).toBe('completed');
    expect(c.stepLabel).toBe('5/5 steps · 1 runs');
    expect(c.elapsedMs).toBe(9100);
    expect(c.pct).toBe(100);
  });
  it('uses the planned total and the simulated elapsed time in mock mode', () => {
    const mock = { ...liveTask({ steps: [step(1, 'thought', 'a', 0)], stepsTotal: 13, progress: 0.2, elapsedMs: 4100 }) };
    const c = taskCard(mock, { live: false, nowMs: 0 });
    expect(c.stepLabel).toBe('1/13 steps');
    expect(c.elapsedMs).toBe(4100);
  });
  it('labels a failed task', () => {
    expect(taskCard(liveTask({ status: 'failed', outcome: { label: 'Stopped' } }), { live: true, nowMs: 0 }).statusLabel).toBe('failed');
  });
});

describe('taskElapsedMs', () => {
  it('never goes below the reported value and handles a missing createdAt', () => {
    expect(taskElapsedMs({ status: 'running', createdAt: T0, elapsedMs: 9000 }, { live: true, nowMs: Date.parse(T0) + 1000 })).toBe(9000);
    expect(taskElapsedMs({ status: 'running', createdAt: 'not a date', elapsedMs: 300 }, { live: true, nowMs: 0 })).toBe(300);
    expect(taskElapsedMs({ status: 'done', createdAt: T0 }, { live: true, nowMs: 0 })).toBeNull();
  });
});

describe('runRefs', () => {
  it('reads data.runId, data.jobId, id arrays and run_ tokens in the text, deduplicated', () => {
    const refs = runRefs({
      text: 'harness.wait · run_20261017_e1d265 and run_20261017_e1d265 again',
      data: { runId: 'ui-3ptb', jobIds: ['job_1', 'ui-3ptb'], progress: 0.4 },
    });
    expect(refs).toEqual([
      { id: 'ui-3ptb', from: 'run' },
      { id: 'job_1', from: 'job' },
      { id: 'run_20261017_e1d265', from: 'text' },
    ]);
  });
  it('links harness run ids in the text and not words that start with run_', () => {
    expect(runRefs({ text: 'pah_get_report run_id=ligand_pose-04e7e402bf85', data: {} })).toEqual([{ id: 'ligand_pose-04e7e402bf85', from: 'text' }]);
    expect(runRefs({ text: 'run_id and run_dir', data: {} })).toEqual([]);
  });
  it('drops ids that are not path-safe and tolerates null data', () => {
    expect(runRefs({ text: 'no ids here', data: { runId: '../etc/passwd', jobId: 42 } })).toEqual([]);
    expect(runRefs({ text: 'x', data: null as unknown as undefined })).toEqual([]);
  });
  it('builds job and report links', () => {
    expect(runLinks({ text: '', data: { runId: 'ligand_pose-ccdd088be87b' } })).toEqual([
      { id: 'ligand_pose-ccdd088be87b', jobHref: '/jobs/ligand_pose-ccdd088be87b', reportHref: '/reports/ligand_pose-ccdd088be87b' },
    ]);
  });
});

describe('stepViews', () => {
  it('offsets steps from the task start and formats durations', () => {
    const views = stepViews([step(1, 'thought', 'a', 0, { ms: 1400 }), step(2, 'tool', 'b', 1500, { ms: 900 }), step(3, 'report', 'c', 12345, { ms: null as unknown as undefined })], T0);
    expect(views.map((v) => v.offsetLabel)).toEqual(['0.0s', '1.5s', '12.3s']);
    expect(views.map((v) => v.msLabel)).toEqual([`1.4${THIN}s`, `900${THIN}ms`, null]);
  });
  it('maps an unknown kind to thought and a bad timestamp to a dash', () => {
    const [v] = stepViews([{ seq: 1, ts: 'bad', kind: 'other' as AgentStep['kind'], text: 'x' }], T0);
    expect(v.kind).toBe('thought');
    expect(v.offsetLabel).toBe('–');
  });
});

describe('counts and labels', () => {
  it('counts tool calls and reports', () => {
    expect(stepCounts([{ kind: 'tool' }, { kind: 'result' }, { kind: 'tool' }, { kind: 'report' }])).toEqual({ toolCalls: 2, reports: 1 });
  });
  it('formats step counts', () => {
    expect(fmtSteps(1, null)).toBe('1 step');
    expect(fmtSteps(4, null)).toBe('4 steps');
    expect(fmtSteps(4, 13)).toBe('4/13 steps');
  });
  it('derives the pending label from the last step', () => {
    expect(pendingLabel({ kind: 'tool' }, 'running')).toBe('waiting for result');
    expect(pendingLabel({ kind: 'thought' }, 'running')).toBe('thinking');
    expect(pendingLabel(undefined, 'running')).toBe('thinking');
    expect(pendingLabel(undefined, 'queued')).toBe('queued');
  });
  it('prefers outcome.runs over referenced runs', () => {
    expect(runsOf({ label: 'Completed', runs: 12 }, [])).toBe(12);
    expect(runsOf(null, [step(1, 'tool', 'x', 0)])).toBeNull();
    expect(runsOf(null, undefined)).toBeNull();
  });
});
