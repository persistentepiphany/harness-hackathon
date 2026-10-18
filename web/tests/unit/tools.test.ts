import { describe, expect, it } from 'vitest';
import { TOOLS, makeRunRecord, PRESET_JOBS } from '@/lib/mock/data';
import { familyOf, groupByFamily, labelFor, metricsFor, recordTools, toolById, unitFor } from '@/lib/tools';
import type { UiRunRecord } from '@/lib/types';

const record = makeRunRecord(PRESET_JOBS[0].form, Date.UTC(2026, 9, 17, 12));

describe('toolById', () => {
  it('returns the record tool with its outputs', () => {
    const t = toolById(record, 'boltz2');
    expect(t.name).toBe('Boltz-2');
    expect(t.outputs.some((o) => o.key === 'iptm')).toBe(true);
  });
  it('falls back to the register when the record entry has no outputs', () => {
    const rec = { tools: [{ id: 'gnina', name: 'Gnina', version: '1.3', outputs: [] }] } as Pick<UiRunRecord, 'tools'>;
    expect(toolById(rec, 'gnina', TOOLS).outputs.map((o) => o.key)).toContain('CNNscore');
  });
  it('renders an unknown tool with its id as name and no outputs', () => {
    expect(toolById(record, 'newdock')).toEqual({ id: 'newdock', name: 'newdock', version: null, outputs: [] });
    expect(toolById(null, 'x').name).toBe('x');
  });
});

describe('familyOf', () => {
  it('accepts both spellings', () => {
    expect(familyOf({ family: 'co-folding' })).toBe('co-folding');
    expect(familyOf({ family: 'cofolding' })).toBe('co-folding');
    expect(familyOf({ family: 'docking' })).toBe('docking');
    expect(familyOf({})).toBeNull();
  });
  it('groups the register by family', () => {
    const groups = groupByFamily(TOOLS);
    expect(groups.map((g) => g.family)).toEqual(['co-folding', 'docking']);
  });
});

describe('labelFor / unitFor', () => {
  it('reads labels and units from outputs', () => {
    const gnina = TOOLS.find((t) => t.id === 'gnina');
    expect(labelFor(gnina, 'CNNscore')).toBe('CNN pose score');
    expect(unitFor(gnina, 'minimizedAffinity')).toBe('kcal/mol');
    expect(labelFor(gnina, 'unknown_key')).toBe('unknown_key');
  });
});

describe('metricsFor', () => {
  it('builds columns from the record tools and separates ranking-only outputs', () => {
    const m = metricsFor(record);
    expect(m.columns.length).toBeGreaterThan(0);
    expect(m.columns.every((c) => !c.rankingOnly)).toBe(true);
    expect(m.rankingOnly.map((c) => c.id)).toEqual(
      expect.arrayContaining(['boltz2:affinity_pred_value', 'gnina:CNNaffinity', 'gnina:minimizedAffinity']),
    );
  });
  it('attaches the reported value when stats.metrics references the key', () => {
    const m = metricsFor(record);
    const iptm = m.columns.find((c) => c.id === 'boltz2:iptm');
    expect(iptm?.metric?.value).toBe('0.88');
  });
  it('gives no columns for tools without outputs', () => {
    const rec = { tools: [{ id: 'x', name: 'X', version: null, outputs: [] }], stats: {} } as unknown as UiRunRecord;
    expect(metricsFor(rec)).toEqual({ columns: [], rankingOnly: [] });
    expect(recordTools(rec)[0].name).toBe('X');
  });
});

describe('outputs missing from the record entry', () => {
  it('labels keys the record does not declare from the register', () => {
    const rec = { tools: [{ id: 'vina', name: 'AutoDock Vina', version: '1.2.5', outputs: [{ key: 'vina_affinity', label: 'Vina score', kind: 'score', scope: 'pose' }] }] } as Pick<UiRunRecord, 'tools'>;
    const register = [{ id: 'vina', name: 'AutoDock Vina', family: 'docking', version: '1.2.5', role: 'Executor', available: true, outputs: [{ key: 'rmsd_lb', label: 'RMSD lower bound', unit: 'Å', kind: 'rmsd', scope: 'pose' }] }] as typeof TOOLS;
    const t = toolById(rec, 'vina', register);
    expect(labelFor(t, 'vina_affinity')).toBe('Vina score');
    expect(labelFor(t, 'rmsd_lb')).toBe('RMSD lower bound');
    expect(unitFor(t, 'rmsd_lb')).toBe('Å');
  });
  it('resolves `<key>.<name>` map outputs to the declared key', () => {
    const t = { outputs: [{ key: 'pdockq', label: 'pDockQ', kind: 'interface', scope: 'interface' }] } as Parameters<typeof labelFor>[0];
    expect(labelFor(t, 'pdockq.A-B')).toBe('pDockQ');
    expect(labelFor(t, 'other.A-B')).toBe('other.A-B');
  });
});
