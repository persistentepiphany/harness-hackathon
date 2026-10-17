// Report and ensemble selectors on a mock record (prototype data) and on the live fixtures
// (real `pah` records: L2-L5 not implemented, stats empty, structures and renders present).
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { makeRunRecord, PRESET_JOBS, TOOLS } from '@/lib/mock/data';
import { paeFromStats } from '@/components/report/figures/pae';
import { toolById } from '@/lib/tools';
import type { UiRunRecord } from '@/lib/types';
import {
  agreementCellStyle,
  blockSource,
  ensembleMembers,
  flaggedResidues,
  overlayLoads,
  pbFailed,
  seedAxis,
  seedAxisLabel,
  seedSpreadPoints,
  sortMembers,
  sourceLabel,
  defaultLayerIndex,
  defaultStructureId,
  describe as describeValues,
  ensembleScore,
  ensembleScoreColumn,
  fmtPoseBusters,
  isNotImplemented,
  layerNav,
  medoidClusterPopulation,
  memberColumns,
  memberValueText,
  metricRows,
  physicsTable,
  poseLabel,
  rmsdCell,
  runDurationMs,
  seedConfidenceLabel,
  statCards,
  stripPositions,
  structureCaption,
  structureTargets,
  summaryRows,
  thresholdRows,
  verdictMeta,
  worstResult,
} from './report';

const dir = path.join(__dirname, '..', '..', 'tests', 'fixtures', 'live');
const load = (name: string): UiRunRecord | null => {
  const p = path.join(dir, name);
  return existsSync(p) ? (JSON.parse(readFileSync(p, 'utf8')) as UiRunRecord) : null;
};
const live3ptb = load('ui-record-3ptb.json');
const liveFaulty = load('ui-record-faulty.json');
const liveVina = load('ui-record-vina.json');
const evaluated = (r: UiRunRecord, i: number) => r.layers[i].checks.some((c) => c.result !== 'skip' && c.result !== 'pending');
const mock = makeRunRecord(PRESET_JOBS[0].form, Date.UTC(2026, 9, 17, 12, 0, 0));
const mockDisc = makeRunRecord(PRESET_JOBS[1].form, Date.UTC(2026, 9, 17, 12, 0, 0));
const assetUrl = (p: string) => (p.startsWith('/') ? `/api/harness${p}` : p);

describe('verdict and layers', () => {
  it('maps every outcome to a label and state', () => {
    expect(verdictMeta('narrowed')).toMatchObject({ label: 'Narrowed', state: 'narrowed' });
    expect(verdictMeta('refused').label).toBe('Refused');
    expect(verdictMeta('supported').label).toBe('Supported');
    expect(verdictMeta('incomplete')).toMatchObject({ label: 'Incomplete', state: 'incomplete' });
    expect(verdictMeta(null).state).toBe('pending');
  });

  it('orders results stop > warn > pass > reported > pending > skip', () => {
    expect(worstResult([{ result: 'pass' }, { result: 'warn' }])).toBe('warn');
    expect(worstResult([{ result: 'skip' }, { result: 'pass' }])).toBe('pass');
    expect(worstResult([{ result: 'skip' }])).toBe('skip');
    expect(worstResult([])).toBeNull();
  });

  it('opens the mock report on output validity, as the prototype', () => {
    expect(defaultLayerIndex(mock)).toBe(4);
    expect(layerNav(mock)[4].summary).toContain('PoseBusters');
  });

  it.runIf(!!live3ptb)('opens a live run on layer 4 when it ran checks, else on the last layer that did', () => {
    const r = live3ptb as UiRunRecord;
    const i = defaultLayerIndex(r);
    if (r.verdict.outcome !== 'refused') {
      expect(evaluated(r, i)).toBe(true);
      if (!evaluated(r, 4)) for (let k = i + 1; k < r.layers.length; k++) expect(evaluated(r, k)).toBe(false);
    }
    const nav = layerNav(r);
    nav.forEach((n, k) => {
      expect(n.total).toBe(r.layers[k].checks.length);
      expect(n.notImplemented).toBe(r.layers[k].checks.filter(isNotImplemented).length);
    });
  });

  it.runIf(!!liveFaulty)('opens a refused run on the first layer with a stop', () => {
    const r = liveFaulty as UiRunRecord;
    expect(r.verdict.outcome).toBe('refused');
    const first = r.layers.findIndex((l) => l.checks.some((c) => c.result === 'stop'));
    expect(defaultLayerIndex(r)).toBe(first);
    expect(layerNav(r)[first].dot).toBe('stop');
  });
});

describe('structures', () => {
  it('builds prototype chips for a mock record: crystal from RCSB, medoid, seeds, docking, overlay', () => {
    const t = structureTargets(mock, { assetUrl });
    expect(t[0]).toMatchObject({ kind: 'crystal', label: '1IEP' });
    expect(t[0].load[0]).toMatchObject({ url: 'https://files.rcsb.org/download/1IEP.cif', format: 'mmcif' });
    expect(t[1]).toMatchObject({ id: 'medoid', kind: 'medoid' });
    expect(t.filter((x) => x.kind === 'seed')).toHaveLength(4);
    expect(t.filter((x) => x.kind === 'docking')).toHaveLength(3);
    expect(t[t.length - 1]).toMatchObject({ id: 'overlay', kind: 'overlay' });
    expect(t.filter((x) => x.kind === 'seed').every((x) => x.load.length === 0)).toBe(true);
    expect(defaultStructureId(t)).toBe('medoid');
    expect(structureCaption(mock, t[1], t)).toMatch(/s1000 · RMSD to medoid 0\.0/);
    // overlay caption counts predicted members, and only those with coordinates as drawn
    expect(structureCaption(mock, t[t.length - 1], t)).toBe('1IEP + predicted · 0 of 8 structures with coordinates');
    // docking labels already start with the tool name
    const pose = t.find((x) => x.kind === 'docking');
    expect(structureCaption(mock, pose, t)).toMatch(/^Gnina 1 · RMSD to medoid/);
  });

  it.runIf(!!live3ptb && !!liveVina)('keeps the declared reference and drops exposure comparators', () => {
    const t = structureTargets(live3ptb as UiRunRecord, { assetUrl });
    expect(t.map((x) => x.label)).toEqual(['3PTB']);
    const v = structureTargets(liveVina as UiRunRecord, { assetUrl });
    expect(v.filter((x) => x.kind === 'crystal').map((x) => x.label)).toEqual(['3PTB']);
    expect(v[v.length - 1].kind).toBe('overlay');
    const cap = structureCaption(liveVina as UiRunRecord, v[v.length - 1], v);
    expect(cap).toBe(`3PTB + predicted · ${v.filter((x) => x.kind !== 'overlay' && x.kind !== 'crystal').length} structures`);
  });

  it.runIf(!!live3ptb)('loads the live crystal structure from the files route, never from the network', () => {
    const r = live3ptb as UiRunRecord;
    const t = structureTargets(r, { assetUrl });
    expect(t[0]).toMatchObject({ kind: 'crystal', label: '3PTB' });
    expect(t[0].load).toEqual([{ url: '/api/harness/runs/ui-3ptb/files/artifacts/sources/3PTB.cif', format: 'mmcif', label: '3PTB mmCIF' }]);
    expect(t[0].renders.map((x) => x.view)).toEqual(['overview', 'pocket']);
    for (const x of t) for (const l of x.load) expect(l.url.startsWith('/api/harness/runs/ui-3ptb/files/')).toBe(true);
    // intermediate work files and check-derived files are not ensemble members
    expect(t.some((x) => x.structure?.artifactKind === 'file' || /(^|\/)derived\//.test(x.structure?.path ?? ''))).toBe(false);
    const withDerived = { ...r, structures: [...(r.structures ?? []), { id: 'derived/l4/pose', label: 'pose', kind: 'model' as const, url: '/runs/ui-3ptb/files/derived/l4/pose.pdb', format: 'pdb' as const, path: 'derived/l4/pose.pdb' }] };
    expect(structureTargets(withDerived, { assetUrl }).some((x) => x.id === 'derived/l4/pose')).toBe(false);
    const crystal = r.structures?.find((x) => x.kind === 'crystal');
    expect(structureCaption(r, t[0], t)).toBe(`3PTB mmCIF · crystal · sha256 ${crystal?.sha256?.slice(0, 12)}`);
  });
});

describe('ensemble', () => {
  it('takes the score column from the tools whose outputs appear in the ensemble', () => {
    const col = ensembleScoreColumn(mock, TOOLS);
    expect(col?.keys.map((k) => `${k.toolId}:${k.key}`)).toEqual(['boltz2:iptm', 'gnina:CNNscore']);
    expect(col?.header).toBe('ipTM/CNN');
    const medoid = mock.stats.ensemble?.find((e) => e.kind === 'medoid');
    const pose = mock.stats.ensemble?.find((e) => e.kind === 'docking');
    expect(ensembleScore(medoid!, col)).toBe(medoid!.iptm);
    expect(ensembleScore(pose!, col)).toBe(pose!.cnn);
    expect(rmsdCell(medoid!).text).toBe('–');
    expect(medoidClusterPopulation(mock)).toBe('4/5 seeds');
  });

  it('formats PoseBusters with the number of tests in the record', () => {
    expect(fmtPoseBusters(18, 20)).toBe('18/20');
    expect(fmtPoseBusters(18, null)).toBe('18');
    expect(fmtPoseBusters(null, 20)).toBe('–');
  });

  it('describes values with the sample sd', () => {
    const d = describeValues([4, 1, 3, 2, null]);
    expect(d).toMatchObject({ n: 4, median: 2.5, mean: 2.5, min: 1, max: 4 });
    expect(d?.sd).toBeCloseTo(1.291, 3);
    expect(describeValues([])).toBeNull();
    const s = stripPositions([1, null, 4], ['a', 'b', 'c'], d!);
    expect(s.points).toEqual([{ x: 4, fill: 'a' }, { x: 196, fill: 'c' }]);
    expect(s.medianX).toBe(100);
  });

  it('builds summary rows from stats and tool outputs, co-folding first', () => {
    expect(summaryRows(mock, TOOLS).map((r) => r.id)).toEqual(['rmsd', 'plddt', 'boltz2:iptm', 'posebusters', 'gnina:CNNscore', 'drift', 'strain', 'clashscore']);
    expect(summaryRows(mockDisc, TOOLS).map((r) => r.id)).not.toContain('posebusters');
  });

  it.runIf(!!live3ptb)('returns nothing for stats blocks a live record lacks', () => {
    const r = live3ptb as UiRunRecord;
    if (!r.stats.ensemble) {
      expect(ensembleScoreColumn(r)).toBeNull();
      expect(medoidClusterPopulation(r)).toBeNull();
    }
    if (!r.stats.physics) expect(physicsTable(r)).toBeNull();
    if (!r.stats.ensemble && !r.stats.physics) expect(summaryRows(r)).toEqual([]);
    expect(seedConfidenceLabel(r)).toBe('ipTM');
  });
});

describe('tables and cards', () => {
  it('flags the seed with fewer PoseBusters passes and adds a median row', () => {
    const t = physicsTable(mock)!;
    expect(t.columns.map((c) => c.label)).toEqual(['drift Å', 'torsions', 'clashes', 'strain', 'unsat.', 'PB', 'clashscore']);
    expect(t.rows).toHaveLength(5);
    expect(t.rows.filter((r) => r.flagged)).toHaveLength(1);
    expect(t.median).toHaveLength(7);
  });

  it('moves ranking-only metrics below the rule using the tool outputs', () => {
    const m = metricRows(mock, TOOLS);
    expect(m.computed).toBe(true);
    expect(m.ranking.map((r) => r.name)).toEqual(['Gnina affinity score', 'Boltz-2 affinity']);
    expect(m.rows.some((r) => r.name === 'Gnina pose score')).toBe(true);
  });

  it.runIf(!!live3ptb)('lists the tool outputs with no values when metrics were not computed', () => {
    const m = metricRows(live3ptb as UiRunRecord);
    expect(m.computed).toBe(false);
    expect(m.rows.every((r) => r.value === null)).toBe(true);
    expect(m.rows.map((r) => r.id)).toContain('boltz2:iptm');
    expect(m.ranking.map((r) => r.id)).toContain('boltz2:affinity_pred_value');
    expect(m.rows.map((r) => r.id)).not.toContain('boltz2:pae');
  });

  it('builds site, pose and docking cards for the mock record', () => {
    const c = statCards(mock, TOOLS);
    expect(c.map((x) => x.title)).toEqual(['Binding site', 'Pose', 'Docking · Gnina']);
    expect(c.every((x) => x.computed)).toBe(true);
    expect(statCards(mockDisc, TOOLS).map((x) => x.title)).toEqual(['Interface', 'Complex', 'Sampling']);
  });

  it.runIf(!!live3ptb)('marks card slots computed only for stats blocks the record has', () => {
    const r = live3ptb as UiRunRecord;
    const c = statCards(r);
    expect(c[0]).toMatchObject({ id: 'site', computed: !!r.stats.site });
    expect(c[1]).toMatchObject({ id: 'pose', computed: !!r.stats.pose });
    if (!r.stats.pose) expect(c[1].rows).toEqual([]);
  });

  it.runIf(!!live3ptb)('takes live thresholds from the checks, with origin and evidence level', () => {
    const rows = thresholdRows(live3ptb as UiRunRecord);
    const row = rows.find((r) => r.check === 'l0.cross.uniprot_seqres');
    expect(row).toMatchObject({ value: '== 0', origin: 'Specification, Layer 0 (cross-source checks)', level: 'published' });
  });

  it('colours agreement cells by value, neutral on the diagonal', () => {
    expect(agreementCellStyle(0).text).toBe('–');
    expect(agreementCellStyle(1.1).color).toBe('var(--color-pass)');
    expect(agreementCellStyle(3.8).color).toBe('var(--color-accent-deep)');
    expect(agreementCellStyle(7.2).color).toBe('var(--color-stop)');
  });
});

describe.runIf(!!liveVina)('live Vina run (per-pose ensemble)', () => {
  const r = liveVina as UiRunRecord;
  const targets = structureTargets(r, { assetUrl });
  const members = ensembleMembers(r, targets);

  it('has one member per ensemble row, crystal first, medoid accent, crystal ink', () => {
    expect(members).toHaveLength(r.stats.ensemble?.length ?? 0);
    expect(members[0].kind).toBe('crystal');
    expect(members[0].color).toBe('#1A1A18');
    const medoid = members.find((m) => m.kind === 'medoid');
    expect(medoid?.color).toBe('#B07E2C');
    expect(medoid?.pb?.total).toBeGreaterThan(0);
    expect(members.filter((m) => m.kind === 'docking').length).toBeGreaterThan(0);
    expect(members.every((m) => m.load.every((l) => l.url.startsWith('/api/harness/runs/ui-vina/files/')))).toBe(true);
    expect(members.every((m) => !m.perResidueConfidence)).toBe(true);
  });

  it('keeps ranking-only scores off the quality column', () => {
    const col = ensembleScoreColumn(r);
    for (const k of col?.keys ?? []) expect(r.stats.metrics?.find((m) => m.key === k.key)?.separate ?? false).toBe(false);
    const withValues = members.filter((m) => m.outputs.length);
    expect(withValues.length).toBeGreaterThan(0);
    for (const m of withValues) for (const o of m.ranking) expect(o.rankingOnly).toBe(true);
  });

  it('overlays docking poses as ligands on the crystal receptor', () => {
    const loads = overlayLoads(members);
    const crystal = loads.find((l) => l.id === members[0].id);
    expect(crystal?.polymer).toBe(true);
    const poses = loads.filter((l) => l.polymer === false);
    expect(poses.length).toBe(members.filter((m) => m.kind !== 'crystal' && (m.kind === 'docking' || m.family === 'docking') && m.load.length).length);
    expect(poses.every((l) => !l.align)).toBe(true);
  });

  it('plots seeds against their score when they carry no confidence, IQR band without a CI', () => {
    const axis = seedAxis(r);
    if (r.stats.seeds?.some((s) => typeof s.confidence === 'number')) expect(axis?.field).toBe('confidence');
    else expect(axis?.field).toBe('score');
    const seeds = (r.stats.seeds ?? []) as { scoreKey?: string; confidenceKey?: string; toolId?: string }[];
    const key = axis?.field === 'score' ? seeds.find((x) => x.scoreKey)?.scoreKey : seeds.find((x) => x.confidenceKey)?.confidenceKey;
    if (key) expect(seedAxisLabel(r)).toContain(toolById(r, seeds.find((x) => x.toolId)?.toolId ?? '', null).outputs.find((o) => o.key === key)?.label ?? key);
    const sp = seedSpreadPoints(r);
    expect(sp.points.every((p) => Number.isFinite(p.cx) && Number.isFinite(p.cy))).toBe(true);
    if (!r.stats.pairwise?.ci95 && r.stats.pairwise?.iqr) expect(sp.band?.kind).toBe('iqr');
  });

  it('shows only the per-seed columns the rows carry and names each block source', () => {
    const t = physicsTable(r);
    for (const c of t?.columns ?? []) expect(r.stats.physics?.some((p) => typeof p[c.key] === 'number')).toBe(true);
    expect(blockSource(r, 'posebusters')?.check).toBe('l4.posebusters');
    expect(sourceLabel(blockSource(r, 'posebusters'))).toMatch(/^source: l4\.posebusters · posebusters/);
    expect(summaryRows(r).map((x) => x.id)).toContain('rmsd');
  });

  it('sorts by RMSD with the crystal first and filters PoseBusters failures', () => {
    const sorted = sortMembers(members, 'rmsd');
    expect(sorted[0].kind).toBe('crystal');
    const rs = sorted.slice(1).map((m) => m.rmsd).filter((x): x is number => x !== null);
    expect(rs).toEqual([...rs].sort((a, b) => a - b));
    expect(members.filter(pbFailed).every((m) => m.pb !== null && m.pb.total !== null && m.pb.passed < m.pb.total)).toBe(true);
  });

  it('finds residues named in warned findings', () => {
    const f = flaggedResidues(r);
    const warned = r.layers.flatMap((l) => l.checks).filter((c) => c.result === 'warn' || c.result === 'stop');
    for (const x of f) expect(warned.some((c) => (c.evidence ?? '').toUpperCase().includes(`${x.name}${x.num}`))).toBe(true);
  });
});

describe('flagged residues', () => {
  it('parses three-letter residues with numbers and chains, ignoring other words', () => {
    const rec = { layers: [{ checks: [{ id: 'a', result: 'warn', evidence: 'pKa within 1.0 of pH 7.4: HIS57A pKa 7.46, ASP189A pKa 6.49 · seed0 mode1' }, { id: 'b', result: 'pass', evidence: 'GLU12' }, { id: 'c', result: 'stop', evidence: 'amide NH, 4.1 Å from Glu286' }] }] } as unknown as UiRunRecord;
    expect(flaggedResidues(rec).map((x) => `${x.name}${x.num}${x.chain ?? ''}`)).toEqual(['HIS57A', 'ASP189A', 'GLU286']);
  });
});

describe('run duration', () => {
  it('uses the record timestamps, as the job page, and falls back to the layer sum', () => {
    const layers = [{ durationMs: 1000 }, { durationMs: 2000 }] as UiRunRecord['layers'];
    const rec = { layers, record: { startedAt: '2026-10-17T17:12:30.294383Z', finishedAt: '2026-10-17T17:12:37.572924Z' } } as unknown as UiRunRecord;
    expect(runDurationMs(rec)).toBe(7278);
    expect(runDurationMs({ layers, record: {} } as unknown as UiRunRecord)).toBe(3000);
  });
});

describe.runIf(!!liveVina)('ensemble summary and columns (live Vina record)', () => {
  const r = liveVina as UiRunRecord;
  it('leaves the crystal out of the RMSD-to-medoid distribution and keeps counts as integers', () => {
    const rows = summaryRows(r);
    const rmsd = rows.find((x) => x.id === 'rmsd');
    const crystal = r.stats.ensemble?.find((e) => e.kind === 'crystal');
    const preds = (r.stats.ensemble ?? []).filter((e) => e.kind !== 'medoid' && e.kind !== 'crystal' && typeof e.rmsdToMedoid === 'number');
    expect(rmsd?.stats.n).toBe(preds.length);
    if (crystal && typeof crystal.rmsdToMedoid === 'number') expect(rmsd?.stats.max).toBeLessThan(crystal.rmsdToMedoid);
    expect(rows.find((x) => x.id === 'posebusters')?.integer).toBe(true);
    // the medoid is matched by pose id, so live physics rows get the medoid ring
    expect(rows.find((x) => x.id === 'strain')?.medoidValue).toBeTypeOf('number');
  });
  it('shows RMSD to the reference for redocking members and units on other outputs', () => {
    const m = ensembleMembers(r, structureTargets(r, { assetUrl }));
    const cols = memberColumns(m);
    const ref = cols.find((c) => c.id === 'ref');
    expect(ref?.title).toBe('RMSD to the crystal reference (Å)');
    const red = m.find((x) => x.label.startsWith('redocking'));
    if (red && red.rmsdToReference !== null) expect(ref?.text(red)).toBe(red.rmsdToReference.toFixed(1));
    const other = cols.find((c) => c.id.startsWith('out:rmsd'));
    const medoid = m.find((x) => x.kind === 'medoid');
    if (other && medoid) expect(other.text(medoid)).toMatch(/\u2009Å$/);
  });
});

describe('overlay legend values', () => {
  it('names the metric of each value', () => {
    const conf = { key: 'iptm', label: 'ipTM', value: 0.9, kind: 'interface' } as unknown as Parameters<typeof memberValueText>[0]['confidence'];
    expect(memberValueText({ confidence: conf, rmsd: 0.9, kind: 'seed' })).toBe('ipTM 0.9');
    expect(memberValueText({ confidence: null, rmsd: 0.94, kind: 'crystal' })).toBe('RMSD 0.9\u2009Å');
    expect(memberValueText({ confidence: null, rmsd: 0, kind: 'medoid' })).toBe('–');
  });
});

describe('PAE block (live API shape)', () => {
  it('reads the matrix pae_block embeds next to the file, and nothing from a file reference alone', () => {
    const base = mock;
    const withMatrix = { ...base, stats: { ...base.stats, pae: { path: 'predictions/pae.npy', url: '/runs/x/files/predictions/pae.npy', format: 'npy', matrix: [[0.5, 4], [4, 0.5]], tokens: 2 } } } as UiRunRecord;
    expect(paeFromStats(withMatrix)?.matrix).toEqual([[0.5, 4], [4, 0.5]]);
    const fileOnly = { ...base, stats: { ...base.stats, pae: { path: 'predictions/pae.npy', url: '/x', format: 'npy' } } } as UiRunRecord;
    expect(paeFromStats(fileOnly)).toBeNull();
  });
});

describe('seed spread labels and per-pose keys', () => {
  it('labels per pose, keys by pose and keeps only the first of overlapping labels', () => {
    expect(poseLabel({ seed: 3 })).toBe('s3');
    expect(poseLabel({ seed: 3, sample: 2 })).toBe('s3.2');
    expect(poseLabel({ pose: 'vina/seed9/mode0' })).toBe('vina/seed9/mode0');
    const seeds = [
      { seed: 1, sample: 0, pose: 'a', rmsdToMedoid: 1.0, cluster: 1, confidence: 0.8 },
      { seed: 1, sample: 1, pose: 'b', rmsdToMedoid: 1.05, cluster: 1, confidence: 0.8 },
      { seed: 2, sample: 0, pose: 'c', rmsdToMedoid: 6.0, cluster: 2, confidence: 0.6 },
    ];
    const rec = { ...mock, stats: { ...mock.stats, seeds } } as UiRunRecord;
    const { points } = seedSpreadPoints(rec);
    expect(points.map((p) => p.key)).toEqual(['a', 'b', 'c']);
    expect(points.map((p) => p.label)).toEqual(['s1', 's1.1', 's2']);
    expect(points.map((p) => p.showLabel)).toEqual([true, false, true]);
  });
  it('keys physics rows by pose so repeated seeds stay distinct', () => {
    const phys = [
      { seed: 0, sample: 0, pose: 'p0', drift: 1 },
      { seed: 0, sample: 1, pose: 'p1', drift: 2 },
      { pose: 'p2', drift: 3 },
    ];
    const rec = { ...mock, stats: { ...mock.stats, physics: phys } } as UiRunRecord;
    const t = physicsTable(rec);
    expect(t?.rows.map((r) => [r.key, r.seed])).toEqual([
      ['p0', 's0'],
      ['p1', 's0.1'],
      ['p2', 'p2'],
    ]);
  });
});
