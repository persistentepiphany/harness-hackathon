import { describe, expect, it } from 'vitest';
import { AGENT_TASKS, PRESET_JOBS, SAMPLE_PROMPTS, interpretRun, lookupEntities, makeRunRecord } from '@/lib/mock/data';
import { createMockHarnessApi } from '@/lib/mock/mock-api';
import { Simulator } from '@/lib/mock/simulator';
import type { AgentStep, LogLine } from '@/lib/types';

describe('mock data port', () => {
  it('interprets the sample prompts like the prototype', () => {
    expect(SAMPLE_PROMPTS.map((p) => interpretRun(p).task)).toEqual([
      'ligand_pose',
      // prototype rule order: "decoy" selects virtual_screening before the interaction rule
      'virtual_screening',
      'affinity_ranking',
      'virtual_screening',
      'protein_protein_docking',
    ]);
    const r = interpretRun(SAMPLE_PROMPTS[0]);
    expect(r.tools).toEqual(['boltz2', 'gnina']);
    expect(r.target).toBe('P00519');
    expect(r.reference).toBe('1IEP');
    expect(r.steps.map((s) => s.field)).toEqual(['task', 'tools', 'target', 'ligand', 'seeds', 'ph', 'reference', 'claim']);
  });

  it('resolves entities by name', () => {
    const groups = lookupEntities('dock imatinib into abl1');
    expect(groups.map((g) => g.source)).toEqual(['UniProt', 'RCSB PDB', 'AlphaFold DB', 'PDBe-KB', 'PubChem', 'PDB CCD', 'ChEMBL']);
  });

  it('makes records with the prototype verdicts and UI additions', () => {
    const t = Date.UTC(2026, 9, 17, 12);
    const pose = makeRunRecord(PRESET_JOBS[0].form, t);
    const disc = makeRunRecord(PRESET_JOBS[1].form, t);
    expect(pose.verdict.outcome).toBe('narrowed');
    expect(disc.verdict.outcome).toBe('refused');
    expect(pose.source).toBe('mock');
    expect(pose.layers).toHaveLength(6);
    expect(pose.layers.every((l) => l.status === 'done')).toBe(true);
    expect(pose.layers[0].counts.pass).toBe(pose.layers[0].checks.filter((c) => c.result === 'pass').length);
    expect(pose.id).toMatch(/^run_20261017_[0-9a-f]{6}$/);
    expect(pose.tools[0].outputs?.length).toBeGreaterThan(0);
    expect(pose.docking?.toolId).toBe('gnina');
    expect(pose.stats.ensemble?.find((e) => e.kind === 'docking')?.values).toHaveProperty('CNNscore');
  });
});

describe('Simulator', () => {
  it('is deterministic with a seed', () => {
    const a = new Simulator({ seed: 7 });
    const b = new Simulator({ seed: 7 });
    expect(a.jobs.map((j) => j.id)).toEqual(b.jobs.map((j) => j.id));
    a.advance(5000);
    b.advance(5000);
    expect(a.jobs.map((j) => j.log.length)).toEqual(b.jobs.map((j) => j.log.length));
    expect(a.jobs[1].log.map((l) => l.text)).toEqual(b.jobs[1].log.map((l) => l.text));
  });

  it('starts with the preset job states and runs jobs to a verdict', () => {
    const sim = new Simulator({ seed: 1, simSpeed: 4 });
    expect(sim.jobs.map((j) => j.status)).toEqual(['done', 'running', 'queued']);
    expect(sim.jobs[1].layerIdx).toBe(3);
    sim.advance(1000);
    expect(sim.jobs[2].status).toBe('running');
    sim.advance(60000);
    expect(sim.jobs.every((j) => j.status === 'done')).toBe(true);
    const last = sim.jobs[1].log[sim.jobs[1].log.length - 1];
    expect(last.text).toMatch(/^verdict · refused/);
    const seqs = sim.jobs[1].log.map((l) => l.seq);
    expect(seqs).toEqual(seqs.map((_, i) => i + 1));
  });

  it('respects maxConcurrent', () => {
    const sim = new Simulator({ seed: 2, maxConcurrent: 1 });
    sim.advance(500);
    expect(sim.jobs.filter((j) => j.status === 'running')).toHaveLength(1);
  });

  it('snapshots jobs in the wire shape', () => {
    const sim = new Simulator({ seed: 3 });
    const job = sim.jobSnapshot(sim.jobs[1]);
    expect(job.layers).toHaveLength(6);
    expect(job.layers.slice(0, 3).every((l) => l.done)).toBe(true);
    expect(job.verdict).toBeNull();
    const rec = sim.recordSnapshot(sim.jobs[1]);
    expect(rec.layers[3].status).toBe('running');
    expect(rec.layers[5].status).toBe('pending');
    expect(rec.layers[5].checks.every((c) => c.result === 'pending')).toBe(true);
    expect(rec.verdict.outcome).toBeNull();
  });

  it('plays agent steps one task at a time', () => {
    const sim = new Simulator({ seed: 4 });
    expect(sim.agentTasks.map((t) => t.status)).toEqual(['done', 'running', 'queued']);
    const before = sim.revealedSteps(sim.agentTasks[1]).length;
    sim.advance(3000);
    expect(sim.revealedSteps(sim.agentTasks[1]).length).toBeGreaterThan(before);
    sim.advance(40000);
    expect(sim.agentTasks[1].status).toBe('done');
    expect(sim.agentTasks[2].status).not.toBe('queued');
    expect(sim.agentSnapshot(sim.agentTasks[0]).steps).toHaveLength(AGENT_TASKS[0].steps.length);
  });
});

describe('mock HarnessApi', () => {
  it('streams a job log to its end without duplicates', async () => {
    const api = createMockHarnessApi({ seed: 5, latencyMs: 0, autoStart: false, simSpeed: 8 });
    const jobs = await api.listJobs();
    const running = jobs.find((j) => j.status === 'running')!;
    const lines: LogLine[] = [];
    let ended = false;
    const stop = api.streamJobLog(running.id, { onLine: (l) => lines.push(l), onEnd: () => (ended = true) });
    await new Promise((r) => setTimeout(r, 5));
    api.mock.advance(30000);
    stop();
    expect(ended).toBe(true);
    expect(new Set(lines.map((l) => l.seq)).size).toBe(lines.length);
    expect(lines[lines.length - 1].text).toMatch(/^verdict/);
  });

  it('starts a run from settings and lists it first', async () => {
    const api = createMockHarnessApi({ seed: 6, latencyMs: 0, autoStart: false });
    const res = await api.startRun({ task: 'ligand_pose', tools: ['boltz2', 'gnina'], target: 'P00519', reference: '1IEP', ph: 7.4, seeds: 3, name: 'test run' });
    const jobs = await api.listJobs();
    expect(jobs[0]).toMatchObject({ id: res.jobId, name: 'test run', status: 'queued', seeds: 3 });
    const rec = await api.getRunRecord(res.runId);
    expect(rec.source).toBe('mock');
    expect(rec.verdict.outcome).toBeNull();
  });

  it('rejects unknown ids with a 404 ApiError', async () => {
    const api = createMockHarnessApi({ seed: 6, latencyMs: 0, autoStart: false });
    await expect(api.getJob('nope')).rejects.toMatchObject({ status: 404, code: 'not_found' });
  });

  it('streams agent steps', async () => {
    const api = createMockHarnessApi({ seed: 8, latencyMs: 0, autoStart: false });
    const steps: AgentStep[] = [];
    const stop = api.streamAgentSteps('agent_01', { onStep: (s) => steps.push(s) });
    await new Promise((r) => setTimeout(r, 5));
    stop();
    expect(steps.map((s) => s.seq)).toEqual(AGENT_TASKS[0].steps.map((_, i) => i + 1));
  });

  it('interprets text into settings and steps', async () => {
    const api = createMockHarnessApi({ latencyMs: 0, autoStart: false });
    const r = await api.interpret('Does KRAS interact with RAF1? Run Boltz-2 and Protenix');
    expect(r.settings).toMatchObject({ task: 'interaction_discovery', target: 'P01116', partner: 'P04049' });
    expect(r.steps.length).toBeGreaterThan(5);
  });
});

describe('mock addTool', () => {
  it('adds a custom executor to the session register once', async () => {
    const api = createMockHarnessApi({ seed: 3, latencyMs: 0, autoStart: false });
    const t = await api.addTool({ name: 'MyDock', version: '1.0', image: 'MyDock:1.0' });
    expect(t).toMatchObject({ id: 'mydock', name: 'MyDock', family: 'docking', version: '1.0', custom: true });
    await api.addTool({ name: 'MyDock' });
    const tools = await api.listTools();
    expect(tools.filter((x) => x.id === 'mydock')).toHaveLength(1);
    await expect(api.addTool({ name: '  ' })).rejects.toMatchObject({ status: 422 });
  });
});
