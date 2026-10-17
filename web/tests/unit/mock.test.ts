import { describe, expect, it } from 'vitest';
import { AGENT_TASKS, PRESET_JOBS, SAMPLE_PROMPTS, TASKS, interpretRun, lookupEntities, makeRunRecord, toPreRun } from '@/lib/mock/data';
import { createMockHarnessApi } from '@/lib/mock/mock-api';
import { Simulator } from '@/lib/mock/simulator';
import type { AgentStep, LogLine } from '@/lib/types';

describe('mock data port', () => {
  it('interprets the sample prompts onto Quick setup tasks', () => {
    expect(SAMPLE_PROMPTS.map((p) => interpretRun(p).task)).toEqual(['ligand_pose', 'known_complex', 'pose_known_pocket', 'redocking', 'series_scoring', 'protein_protein_docking']);
    const r = interpretRun(SAMPLE_PROMPTS[0]);
    expect(r.tools).toEqual(['boltz2', 'protenix']);
    expect(r.target).toBe('P00519');
    // a PDB entry named in the request wins over the target's default holo entry
    expect(r.reference).toBe('2HYY');
    expect(r.steps.map((s) => s.field)).toEqual(['task', 'tools', 'target', 'ligand', 'seeds', 'ph', 'reference', 'claim']);
    // the redocking prompt names only the PDB entry: the target comes from it
    expect(interpretRun(SAMPLE_PROMPTS[3])).toMatchObject({ target: 'P00760', reference: '3PTB' });
    expect(interpretRun(SAMPLE_PROMPTS[1])).toMatchObject({ target: 'P01116', partner: 'P04049', ligand: '' });
  });

  it('suggests only runs whose outputs are possible', () => {
    for (const p of SAMPLE_PROMPTS) {
      const r = interpretRun(p);
      const task = TASKS.find((t) => t.id === r.task);
      expect(task?.quickSetup, p).toBe(true);
      expect(r.warnings, p).toEqual([]);
      for (const id of r.tools) expect(task?.compatibleTools, `${p}: ${id}`).toContain(id);
      expect(r.target, p).toBeTruthy();
      if (task?.kind === 'complex') expect(r.partner, p).toBeTruthy();
      if (task?.kind === 'ligand') expect(r.ligand, p).toBeTruthy();
    }
    // every task's defaults report its endpoint
    for (const t of TASKS) for (const id of t.defaultTools) expect(t.compatibleTools, `${t.id}: ${id}`).toContain(id);
    // a named tool that cannot report the endpoint is kept, with a warning
    const r = interpretRun('Rank the imatinib congeneric series against ABL1 by Boltz-2 affinity, corroborate with Gnina');
    expect(r.task).toBe('affinity_ranking');
    expect(r.warnings).toEqual(['Gnina cannot produce affinity series for affinity ranking']);
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

  it('keeps an added executor in the run that is started with it', async () => {
    const api = createMockHarnessApi({ seed: 4, latencyMs: 0, autoStart: false });
    await api.addTool({ name: 'rosettafold', version: '1.0', image: 'rosettafold:1.0' });
    const res = await api.startRun({ task: 'redocking', tools: ['vina', 'gnina', 'rosettafold'], target: 'P00519', reference: '1IEP', ph: 7.4, seeds: 3, name: 'custom tool run' });
    const rec = await api.getRunRecord(res.runId);
    expect(rec.tools.map((t) => t.id)).toContain('rosettafold');
    expect(rec.tools.find((t) => t.id === 'rosettafold')).toMatchObject({ name: 'rosettafold', version: '1.0' });
    const job = await api.getJob(res.jobId);
    expect(job.tools).toContain('rosettafold');
  });
});

describe('mock entity lookups for names outside the catalog', () => {
  it('returns error rows for a custom accession and custom ligands, with no values', () => {
    const groups = lookupEntities('Q9Y6K9 ccd ATP cid 2244 CC(=O)Oc1ccccc1C(=O)O');
    const byKey = Object.fromEntries(groups.map((g) => [g.key, g]));
    expect(byKey['uniprot:Q9Y6K9']).toMatchObject({ kind: 'protein', source: 'UniProt', status: 'error', message: 'not in the mock catalog', rows: [] });
    expect(byKey['ccd:ATP']).toMatchObject({ kind: 'ligand', source: 'PDB CCD', status: 'error' });
    expect(byKey['pubchem:2244']).toMatchObject({ kind: 'ligand', query: 'CID 2244', status: 'error' });
    expect(byKey['smiles:CC(=O)Oc1ccccc1C(=O)O']).toMatchObject({ kind: 'ligand', title: 'custom ligand', status: 'error' });
  });

  it('adds no error rows for catalog entries', () => {
    const groups = lookupEntities('P00519 imatinib');
    expect(groups.length).toBeGreaterThan(0);
    expect(groups.every((g) => g.status !== 'error')).toBe(true);
  });
});

describe('execution stage and pre-run checks', () => {
  it('runs a GPU executor through queued, building, running and done, with seeds, renders and log lines', () => {
    const sim = new Simulator({ seed: 2 });
    const job = sim.submit({ task: 'ligand_pose', tools: ['boltz2', 'gnina'], target: 'P00519', ligand: 'Cc1ccc', reference: '1IEP', ph: 7.4, seeds: 3, execute: true });
    const phases = new Set<string>();
    let sawStage = false;
    for (let i = 0; i < 600 && job.status !== 'done'; i++) {
      sim.advance(110);
      const snap = sim.jobSnapshot(job);
      (snap.execution ?? []).forEach((e) => phases.add(`${e.executor}:${e.phase}`));
      if (job.stage === 'execute') {
        sawStage = true;
        expect(snap.layerIdx).toBe(4);
      }
    }
    expect(job.status).toBe('done');
    expect(sawStage).toBe(true);
    for (const p of ['queued', 'building', 'running', 'done']) expect(phases).toContain(`boltz2:${p}`);
    const rec = sim.recordSnapshot(job);
    expect(rec.assessment).toBe('full');
    const boltz = rec.execution?.find((e) => e.executor === 'boltz2');
    expect(boltz).toMatchObject({ phase: 'done', gpu: 'A100', route: 'stock' });
    expect(boltz?.seeds.map((s) => s.phase)).toEqual(['done', 'done', 'done']);
    expect(boltz?.seeds.every((s) => typeof s.ms === 'number' && s.ms > 0)).toBe(true);
    // one render per finished seed and executor, with seed, rank, score and per-pose checks
    expect(rec.renders?.filter((r) => r.executor === 'boltz2')).toHaveLength(3);
    expect(rec.renders?.[0]).toMatchObject({ seed: 0, rank: 1 });
    expect(rec.renders?.[0].checks?.length).toBeGreaterThan(0);
    expect(job.log.some((l) => l.kind === 'exec' && /boltz2 · running/.test(l.text))).toBe(true);
    expect(job.log.some((l) => l.kind === 'artifact')).toBe(true);
    expect(rec.verdict.outcome).toBe('narrowed');
  });

  it('keeps polling-relevant state while executing: job.execution active, report stage reported', () => {
    const sim = new Simulator({ seed: 3 });
    const job = sim.submit({ task: 'redocking', tools: ['vina', 'gnina'], target: 'P00519', ligand: 'C', reference: '1IEP', ph: 7.4, seeds: 2, execute: true });
    let sawReport = false;
    for (let i = 0; i < 600 && job.status !== 'done'; i++) {
      sim.advance(110);
      if (sim.jobSnapshot(job).reportStatus === 'running') sawReport = true;
    }
    expect(sawReport).toBe(true);
    expect(sim.jobSnapshot(job).reportStatus).toBe('done');
  });

  it('a run with execute off is a pre-run check: layers 4–5 pending, verdict not assessed', () => {
    const sim = new Simulator({ seed: 5 });
    const job = sim.submit({ task: 'pose_known_pocket', tools: ['vina', 'gnina'], target: 'P00760', ligand: 'NC(=N)c1ccccc1', reference: '3PTB', ph: 7.4, seeds: 3, execute: false });
    for (let i = 0; i < 400 && job.status !== 'done'; i++) sim.advance(110);
    const rec = sim.recordSnapshot(job);
    expect(rec.assessment).toBe('pre-run');
    expect(rec.verdict.outcome).toBe('not_assessed');
    expect(rec.verdict.assessedClaim).toBe('Inputs fit to run');
    expect(rec.verdict.pending?.length).toBe(rec.layers.filter((l) => l.i >= 4).flatMap((l) => l.checks).length);
    expect(rec.layers.filter((l) => l.i >= 4).every((l) => l.status === 'not_run' && l.checks.every((c) => c.skipReason === 'pending_input'))).toBe(true);
    expect(rec.evaluatedLayers).toEqual([0, 1, 2, 3]);
    expect(rec.execution).toEqual([]);
    expect(rec.stats.ensemble?.every((e) => e.kind === 'crystal')).toBe(true);
    expect(sim.jobSnapshot(job).layers.slice(4).map((l) => l.result)).toEqual(['skip', 'skip']);
    // a refused input check stays refused, never supported without predictions
    const disc = toPreRun(makeRunRecord(PRESET_JOBS[1].form, Date.UTC(2026, 9, 17, 12)));
    expect(disc.verdict.outcome).toBe('refused');
    expect(disc.dimensions?.map((d) => d.id)).toEqual(['inputs', 'exposure', 'physical_validity', 'chemical_plausibility', 'stability', 'corroboration']);
  });

  it('serves the glossary and passes execute through startRun', async () => {
    const api = createMockHarnessApi({ seed: 6, latencyMs: 0, autoStart: false });
    const g = await api.getGlossary();
    expect(g.scores.find((s) => s.key === 'vina_score')).toMatchObject({ unit: 'kcal/mol', producedBy: ['vina'], higherIsBetter: false });
    const off = await api.startRun({ task: 'redocking', tools: ['vina'], target: 'P00760', reference: '3PTB', ligand: 'NC(=N)c1ccccc1', ph: 7.4, seeds: 2, execute: false });
    expect((await api.getJob(off.jobId)).assessment).toBe('pre-run');
    const on = await api.startRun({ task: 'redocking', tools: ['vina'], target: 'P00760', reference: '3PTB', ligand: 'NC(=N)c1ccccc1', ph: 7.4, seeds: 2, execute: true });
    expect((await api.getJob(on.jobId)).assessment).toBe('full');
  });
});
