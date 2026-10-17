import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { CATALOG, TASKS, TOOLS } from '@/lib/mock/data';
import { Simulator } from '@/lib/mock/simulator';
import type { Catalog, EntityGroup, Job, LogLine, Task, Tool, UiRunRecord } from '@/lib/types';
import { checkTotals, layerCells } from './jobs';
import {
  applyStep,
  currentStep,
  defaultForm,
  dockingParams,
  executorGroups,
  executorRows,
  fmtStep,
  formText,
  groupEntities,
  inputLines,
  inputVisibility,
  ligandFromInput,
  ligandRows,
  logLineView,
  logStats,
  planTools,
  requestSummary,
  runHeaderModel,
  runStatus,
  selectTask,
  settingsFromForm,
  shortPrompt,
  suggestName,
  targetFromInput,
  targetRows,
  taskGroups,
  taskHint,
  taskKind,
  toggleTool,
  verdictCounts,
} from './run';

const dir = path.join(__dirname, '..', '..', 'tests', 'fixtures', 'live');
const load = <T,>(name: string): T | null => {
  const p = path.join(dir, name);
  return existsSync(p) ? (JSON.parse(readFileSync(p, 'utf8')) as T) : null;
};
const liveTools = load<Tool[]>('tools.json');
const liveTasks = load<Task[]>('tasks.json');
const liveLog = load<LogLine[]>('log-3ptb.json');
const liveJobs = load<Job[]>('jobs.json') ?? [];
const rec3ptb = load<UiRunRecord>('ui-record-3ptb.json');

describe('New run form (mock catalog)', () => {
  const form = defaultForm(CATALOG, TASKS);

  it('starts from the prototype defaults', () => {
    expect(form).toMatchObject({ task: 'ligand_pose', tools: ['boltz2', 'gnina'], target: 'P00519', reference: '1IEP', ph: '7.4', seeds: '5', partner: '' });
    expect(form.ligand).toBe(CATALOG.ligands[0].smiles);
    expect(suggestName(form, CATALOG, TASKS)).toBe('ABL1 kinase · ligand pose');
    expect(formText(form, CATALOG, 'with gnina')).toBe('P00519 imatinib with gnina');
  });

  it('builds settings with only the inputs the task takes', () => {
    expect(settingsFromForm({ ...form, partner: 'P04049', seeds: '', ph: 'x' }, CATALOG, TASKS)).toEqual({
      task: 'ligand_pose', tools: ['boltz2', 'gnina'], target: 'P00519', reference: '1IEP', ph: 7.4, seeds: 5, name: 'ABL1 kinase · ligand pose', ligand: form.ligand,
    });
    const disc = selectTask(form, TASKS.find((t) => t.id === 'interaction_discovery') as Task, CATALOG);
    expect(disc).toMatchObject({ task: 'interaction_discovery', tools: ['boltz2', 'protenix'], partner: 'P04049' });
    const s = settingsFromForm({ ...disc, name: ' mine ' }, CATALOG, TASKS);
    expect(s.partner).toBe('P04049');
    expect(s.ligand).toBeUndefined();
    expect(s.name).toBe('mine');
  });

  it('knows each task kind and its inputs', () => {
    expect(taskKind(TASKS.find((t) => t.id === 'known_complex'))).toBe('complex');
    expect(inputVisibility(TASKS.find((t) => t.id === 'known_complex'))).toMatchObject({ partner: true, ligand: false, ph: false });
    expect(taskKind(TASKS.find((t) => t.id === 'monomer'))).toBe('monomer');
    expect(taskKind({ ...TASKS[0], kind: undefined as never, inputs: ['target', 'partner'] })).toBe('complex');
    expect(taskKind({ ...TASKS[0], kind: undefined as never, inputs: [] })).toBe('ligand');
    const g = taskGroups(TASKS);
    expect(g.cofolding).toHaveLength(8);
    expect(g.docking).toHaveLength(6);
    expect(taskHint(TASKS[3])).toBe('permitted claim: Pose within stated uncertainty');
  });

  it('applies and formats interpreter steps', () => {
    const f = applyStep(applyStep(form, { field: 'tools', value: ['vina'], because: '' }), { field: 'seeds', value: 8, because: '' });
    expect(f.tools).toEqual(['vina']);
    expect(f.seeds).toBe('8');
    expect(applyStep(form, { field: 'claim', value: 'x', because: '' })).toBe(form);
    expect(fmtStep({ field: 'tools', value: ['boltz2', 'gnina', 'nope'], because: '' }, TASKS, TOOLS)).toBe('Boltz-2 · Gnina · nope');
    expect(fmtStep({ field: 'task', value: 'ligand_pose', because: '' }, TASKS, TOOLS)).toBe('Ligand pose in a known pocket');
    expect(fmtStep({ field: 'ligand', value: 'C'.repeat(50), because: '' }, TASKS, TOOLS)).toBe(`${'C'.repeat(38)}…`);
    expect(requestSummary(' dock  imatinib ', [{ field: 'task', value: 'x', because: '' }])).toBe('2 tokens · 1 decisions');
    expect(shortPrompt('Does KRAS interact with RAF1? Run Boltz-2')).toBe('Does KRAS interact with RAF1?');
    expect(shortPrompt('Dock imatinib, 5 seeds')).toBe('Dock imatinib');
  });

  it('turns typed entries into catalog hits or custom chips', () => {
    expect(targetFromInput('kras', CATALOG)?.accession).toBe('P01116');
    expect(targetFromInput('q9xyz1', CATALOG)).toMatchObject({ accession: 'Q9XYZ1', custom: true });
    expect(targetFromInput('  ', CATALOG)).toBeNull();
    expect(ligandFromInput('AQ4', CATALOG)?.names[0]).toBe('erlotinib');
    expect(ligandFromInput('ABC', CATALOG)).toMatchObject({ ccd: 'ABC', custom: true });
    expect(ligandFromInput('CC(=O)Oc1ccccc1C(=O)O', CATALOG)).toMatchObject({ names: ['custom ligand'], ccd: 'NEW' });
  });

  it('shows an en dash for fields the catalog does not carry', () => {
    const rows = targetRows({ names: ['trypsin'], accession: 'P00760', label: 'Trypsin', pdb: '3PTB', resolution: '1.70 Å', length: 246 });
    expect(rows.find((r) => r.k === 'Length')?.v).toBe('246 aa');
    expect(rows.find((r) => r.k === 'Reference')?.v).toBe('3PTB · 1.70 Å');
    expect(rows.find((r) => r.k === 'Holo entries')).toEqual({ k: 'Holo entries', v: '–', missing: true });
    expect(rows.find((r) => r.k === 'Release')?.missing).toBe(true);
    const lig = ligandRows({ names: ['benzamidine'], smiles: 'NC(=N)c1ccccc1', ccd: 'BEN', cid: '2332', chembl: 'CHEMBL20936' });
    expect(lig.find((r) => r.k === 'ChEMBL')?.v).toBe('CHEMBL20936');
    expect(lig.find((r) => r.k === 'pKa')?.missing).toBe(true);
    expect(ligandRows({ names: ['x'], smiles: 'x', ccd: 'NEW', cid: '—' }).slice(0, 2).every((r) => r.missing)).toBe(true);
  });

  it('groups entity lookups by entity and keeps error rows', () => {
    const groups: EntityGroup[] = [
      { key: 'uniprot:P1', kind: 'protein', title: 'T', source: 'UniProt', query: 'P1', ms: 212, rows: [['Length', '10 aa']] },
      { key: 'rcsb:P1', kind: 'protein', title: 'T', source: 'RCSB PDB', query: '1ABC', ms: 30, rows: [], ...({ status: 'error', message: 'http_404: not found' } as object) },
      { key: 'pubchem:1', kind: 'ligand', title: 'L', source: 'PubChem', query: 'CID 1', ms: Number.NaN, rows: [] },
    ];
    const g = groupEntities(groups);
    expect(g.map((x) => [x.title, x.items.length])).toEqual([
      ['T', 2],
      ['L', 1],
    ]);
    expect(g[0].items[1]).toMatchObject({ status: 'error', message: 'http_404: not found', ms: 30 });
    expect(g[1].items[0].ms).toBeNull();
  });
});

describe.skipIf(!liveTools || !liveTasks)('New run with the live register and tasks', () => {
  const tools = liveTools as Tool[];
  const tasks = liveTasks as Task[];

  it('groups executors by family; unavailable tools are disabled unless selected', () => {
    const groups = executorGroups(tools, ['boltz2']);
    expect(groups.map((g) => g.family)).toEqual(['co-folding', 'docking']);
    const boltz = groups[0].chips.find((c) => c.id === 'boltz2');
    expect(boltz).toMatchObject({ selected: true, available: false, disabled: false });
    expect(boltz?.note).toMatch(/not installed/);
    expect(groups[0].chips.find((c) => c.id === 'protenix')?.disabled).toBe(true);
    const af3 = groups[0].chips.find((c) => c.id === 'alphafold3');
    expect(af3?.version).toHaveLength(12);
    expect(af3?.versionTitle).toHaveLength(40);
    expect(toggleTool(['boltz2', 'gnina'], 'gnina')).toEqual(['boltz2']);
    expect(planTools(['boltz2', 'afdb'], tools)).toBe('Boltz-2 · afdb');
    expect(planTools([], tools)).toBe('none');
  });

  it('reads catalog defaults and reports implemented checks', () => {
    const catalog = {
      proteins: [{ names: ['trypsin'], accession: 'P00760', label: 'Trypsin', pdb: '3PTB' }],
      ligands: [{ names: ['imatinib'], smiles: 'CCC' }, { names: ['benzamidine'], smiles: 'NC(=N)c1ccccc1', ccd: 'BEN' }],
      defaults: { target: 'P00760', partner: 'P04049', ligand: 'benzamidine', reference: '3PTB' },
    } as unknown as Catalog;
    const form = defaultForm(catalog, tasks);
    expect(form).toMatchObject({ task: 'ligand_pose', target: 'P00760', reference: '3PTB', ligand: 'NC(=N)c1ccccc1', tools: ['boltz2', 'gnina'] });
    expect(taskHint(tasks.find((t) => t.id === 'ligand_pose'))).toMatch(/^permitted claim: .+ · checks implemented \d+\/\d+$/);
    // the live task list carries no kind or inputs: ligand inputs are shown
    expect(inputVisibility(tasks.find((t) => t.id === 'ligand_pose'))).toMatchObject({ ligand: true, partner: false });
    const settings = settingsFromForm({ ...form, tools: ['boltz2'] }, catalog, tasks);
    expect(settings).toMatchObject({ task: 'ligand_pose', tools: ['boltz2'], target: 'P00760', reference: '3PTB', ligand: 'NC(=N)c1ccccc1', name: 'Trypsin · ligand pose' });
  });
});

describe('single job view (mock simulator)', () => {
  const sim = new Simulator({ seed: 3 });
  const running = sim.jobs[1];
  const job = sim.jobSnapshot(running);
  const record = sim.recordSnapshot(running);

  it('builds header, status and log text', () => {
    const h = runHeaderModel(job, record, TOOLS, TASKS);
    expect(h).toMatchObject({ name: 'KRAS · RAF1 discovery', taskName: 'Interaction discovery', models: 'Boltz-2 2.1.1 · Protenix 0.5.0', sampling: '5 seeds × 5 samples' });
    const cells = layerCells(job, record);
    expect(runStatus(job, cells, checkTotals(record))).toMatchObject({ tone: 'ink2', dot: 'running' });
    expect(runStatus(job, cells, checkTotals(record)).label).toMatch(/^applicability · \d+%$/);
    expect(currentStep(job, running.log)).toBe(running.log[running.log.length - 1].text.slice(0, 60));
    expect(currentStep({ ...job, status: 'queued' }, [])).toBe('queued');
    expect(currentStep({ ...job, status: 'done', elapsedMs: 18000 }, [])).toBe('finished · 18.0 s');
  });

  it('lists executors from the execution lines', () => {
    const rows = executorRows(job, record, TOOLS);
    expect(rows.map((r) => r.tool)).toEqual(['Boltz-2', 'Protenix']);
    expect(rows.every((r) => r.state === 'ok')).toBe(true);
    expect(executorRows({ ...job, status: 'queued' }, record, TOOLS)[0].state).toBe('loading');
    expect(inputLines(record, job)).toEqual(['P01116 + P04049 · 6VJJ · pH 7.4', '5 seeds × 5 samples · A1:B1']);
  });

  it('lists docking parameters from the register with reported values', () => {
    const done = sim.jobs[0];
    const rec = done.record;
    const params = dockingParams(rec, 'gnina', TOOLS);
    expect(params.find((p) => p.key === 'exhaustiveness')).toMatchObject({ value: '16', isDefault: false });
    expect(params.find((p) => p.key === 'cnn_scoring')).toMatchObject({ value: 'rescore', isDefault: true });
    expect(params.find((p) => p.key === 'autobox_add')).toMatchObject({ value: '4', unit: 'Å' });
    const rows = executorRows(sim.jobSnapshot(done), rec, TOOLS);
    expect(rows.find((r) => r.tool === 'Gnina')?.params?.length).toBe(4);
    expect(rows.find((r) => r.tool === 'Boltz-2')?.params).toBeUndefined();
  });
});

describe.skipIf(!liveLog || !rec3ptb)('single job view (live fixtures)', () => {
  const log = liveLog as LogLine[];
  const rec = rec3ptb as UiRunRecord;
  const job = liveJobs.find((j) => j.id === 'ui-3ptb') as Job;

  it('counts log lines and colours them per mode', () => {
    const s = logStats(log);
    expect(s.checks).toBe(log.filter((l) => l.kind === 'check').length);
    expect(s.pass + s.warn + s.stop + s.skip).toBeLessThanOrEqual(s.checks);
    const warn = log.find((l) => l.result === 'warn') as LogLine;
    expect(logLineView(warn, 'plain')).toMatchObject({ color: 'var(--color-accent-deep)', dot: 'var(--color-warn)', text: warn.plain });
    expect(logLineView(warn, 'terminal')).toMatchObject({ color: 'var(--color-terminal-warn)', text: warn.text });
    const layer = log.find((l) => l.kind === 'layer') as LogLine;
    expect(logLineView(layer, 'plain').weight).toBe(500);
    const plainLog = log.find((l) => l.kind === 'log' && !l.result) as LogLine;
    expect(logLineView(plainLog, 'plain').dot).toBe('#D7D7D2');
    const skip: LogLine = { seq: 0, ts: '', t: '0.0s', layer: 2, kind: 'check', result: 'skip', text: 'x', plain: '' };
    expect(logLineView(skip, 'plain')).toMatchObject({ dot: 'var(--color-faint)', text: 'x' });
  });

  it('shows executors that did not run, with their checkpoint', () => {
    const rows = executorRows(job, rec, liveTools);
    expect(rows.map((r) => r.key)).toEqual(rec.tools.map((t) => t.id));
    rec.tools.forEach((t, i) => {
      if (t.ran === false) expect(rows[i]).toMatchObject({ state: 'not_run', text: expect.stringMatching(/^not run \(checks only\)/) });
      if (t.checkpoint) expect(rows[i].text).toContain(`checkpoint ${t.checkpoint}`);
    });
    const lines = inputLines(rec, job);
    expect(lines[0]).toBe(`${rec.inputs.target} · ${rec.inputs.reference} · pH ${rec.inputs.ph}`);
    if (rec.inputs.ligand) expect(lines.at(-1)).toBe(rec.inputs.ligand);
    expect(runHeaderModel(job, rec, liveTools).sampling).toBe(`${rec.inputs.seeds} seeds`);
    const t = checkTotals(rec);
    expect(verdictCounts(t)).toEqual({ text: `${t.pass} pass · ${t.warn} warn · ${t.stop} stop`, skip: t.skip ? ` · ${t.skip} skip` : undefined });
    expect(runStatus(job, layerCells(job, rec), t)).toEqual({ label: `complete · ${t.total} checks`, tone: 'pass', dot: 'done' });
  });

  it('lists register defaults for a docking tool the record does not describe', () => {
    const params = dockingParams(rec, 'gnina', liveTools);
    expect(params.find((p) => p.key === 'exhaustiveness')).toMatchObject({ value: '8', isDefault: true });
    expect(params.find((p) => p.key === 'size')).toMatchObject({ value: '–', isDefault: false });
  });
});
