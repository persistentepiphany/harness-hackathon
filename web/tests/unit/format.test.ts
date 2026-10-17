import { describe, expect, it } from 'vitest';
import {
  DASH,
  THIN,
  countSegments,
  fmtBytes,
  fmtCounts,
  fmtFraction,
  fmtMs,
  fmtNum,
  fmtPct,
  fmtSeconds,
  fmtSha,
  measuredVsThreshold,
  pairMeasurement,
  thresholdText,
  tallyResults,
} from '@/lib/format';

describe('fmtNum', () => {
  it('puts the unit after a thin space', () => {
    expect(fmtNum(2.1, 'Å')).toBe(`2.1${THIN}Å`);
    expect(fmtNum(412, 'ms')).toBe(`412${THIN}ms`);
  });
  it('keeps requested decimals and uses a true minus sign', () => {
    expect(fmtNum(0.5, null, 2)).toBe('0.50');
    expect(fmtNum(-10.2, 'kcal/mol')).toBe(`−10.2${THIN}kcal/mol`);
  });
  it('removes float noise', () => {
    expect(fmtNum(0.1 + 0.2)).toBe('0.3');
  });
  it('renders missing values as an en dash, never 0', () => {
    expect(fmtNum(null)).toBe(DASH);
    expect(fmtNum(undefined, 'Å')).toBe(DASH);
    expect(fmtNum(Number.NaN)).toBe(DASH);
    expect(fmtNum(0)).toBe('0');
  });
});

describe('durations', () => {
  it('shows ms below 1 s and seconds to one decimal above', () => {
    expect(fmtMs(412)).toBe(`412${THIN}ms`);
    expect(fmtMs(999.6)).toBe(`1000${THIN}ms`);
    expect(fmtMs(1000)).toBe(`1.0${THIN}s`);
    expect(fmtMs(12440)).toBe(`12.4${THIN}s`);
    expect(fmtMs(undefined)).toBe(DASH);
  });
  it('elapsed clock is always seconds', () => {
    expect(fmtSeconds(400)).toBe(`0.4${THIN}s`);
  });
});

describe('fmtSha', () => {
  const sha = '2daae107e8c8e06022040be8b9f5c2d50c4b0249c452e612de8dbcabc333b12a';
  it('shows the first 12 hex characters', () => {
    expect(fmtSha(sha)).toBe('2daae107e8c8');
    expect(fmtSha(sha, { ellipsis: true })).toBe('2daae107e8c8…');
    expect(fmtSha(null)).toBe(DASH);
  });
});

describe('counts and fractions', () => {
  it('formats counts with zeros kept', () => {
    expect(fmtCounts({ pass: 12, warn: 1, skip: 8 })).toBe('pass 12 · warn 1 · stop 0 · skip 8');
  });
  it('marks zero segments muted', () => {
    const segs = countSegments({ pass: 3 });
    expect(segs.map((s) => s.muted)).toEqual([false, true, true, true]);
  });
  it('tallies results', () => {
    expect(tallyResults([{ result: 'pass' }, { result: 'pass' }, { result: 'stop' }])).toEqual({ pass: 2, stop: 1 });
  });
  it('keeps the denominator', () => {
    expect(fmtFraction(13, 41)).toBe('13/41');
    expect(fmtFraction(13, null)).toBe(DASH);
  });
  it('formats percentages and bytes', () => {
    expect(fmtPct(0.42)).toBe('42%');
    expect(fmtBytes(176072)).toBe(`176${THIN}kB`);
    expect(fmtBytes(512)).toBe(`512${THIN}B`);
  });
});

describe('measuredVsThreshold', () => {
  it('pairs with the measurement the threshold names (undefined_stereo -> undefined)', () => {
    const check = {
      measurements: [
        { name: 'stereo_elements', value: 1, unit: null },
        { name: 'undefined', value: 1, unit: null },
      ],
      thresholds: [{ name: 'undefined_stereo', value: 0, comparator: '==', origin: 'spec', evidenceLevel: 'reproduced', measurement: 'undefined' }],
    };
    expect(measuredVsThreshold(check)).toBe('undefined 1 · must be 0');
  });
  it('never pairs by substring (pocket_residues is not missing_pocket_residues)', () => {
    const check = {
      measurements: [
        { name: 'pocket_residues', value: 22 },
        { name: 'ph', value: 7.4 },
      ],
      thresholds: [
        { name: 'missing_pocket_residues', value: 0, comparator: '==', origin: 'spec', evidenceLevel: 'published' },
        { name: 'ph_window', value: 1, comparator: '==', origin: 'spec', evidenceLevel: 'published' },
      ],
    };
    expect(pairMeasurement(check)).toBeNull();
  });
  it('prefers an exact name', () => {
    const check = {
      measurements: [
        { name: 'segments', value: 1 },
        { name: 'mismatches', value: 0 },
      ],
      thresholds: [{ name: 'mismatches', value: 0, comparator: '==', origin: 'spec', evidenceLevel: 'reproduced' }],
    };
    expect(measuredVsThreshold(check)).toBe('mismatches 0 · must be 0');
  });
  it('does not guess a pairing', () => {
    const check = {
      measurements: [{ name: 'proteins', value: 1 }],
      thresholds: [{ name: 'identical', value: true, comparator: '==', origin: 'spec', evidenceLevel: 'reproduced' }],
    };
    expect(pairMeasurement(check)).toBeNull();
    expect(measuredVsThreshold(check)).toBeNull();
    expect(measuredVsThreshold({})).toBeNull();
  });
  it('appends the unit to both sides', () => {
    const check = {
      measurements: [{ name: 'drift', value: 0.6, unit: 'Å' }],
      thresholds: [{ name: 'drift', value: 2, comparator: '<=', origin: 'spec', evidenceLevel: 'suspected' }],
    };
    expect(measuredVsThreshold(check)).toBe(`drift 0.6${THIN}Å · at most 2${THIN}Å`);
  });
});

describe('thresholdText', () => {
  it('names the threshold and formats its value like the Thresholds list', () => {
    const t = { name: 'pocket_distance', value: 8.0, comparator: '<=', origin: 'spec', evidenceLevel: 'published' };
    expect(thresholdText({ thresholds: [t], threshold: { value: '<= 8.0', origin: 'spec', evidenceLevel: 'published' } })).toBe('pocket_distance <= 8');
    expect(thresholdText({ thresholds: [{ ...t, name: 'relative_sasa', value: 0.1, comparator: '<' }] })).toBe('relative_sasa < 0.1');
    expect(thresholdText({ threshold: { value: '> 1.0', origin: 'spec', evidenceLevel: 'x' } })).toBe('threshold > 1.0');
    expect(thresholdText({})).toBeNull();
  });
});

describe('run labels', () => {
  it('shortens <task>-<hex> run ids and keeps other ids', async () => {
    const { shortRunId } = await import('@/lib/format');
    expect(shortRunId('ligand_pose-04e7e402bf85')).toBe('04e7e4');
    expect(shortRunId('ui-3ptb')).toBe('ui-3ptb');
  });
  it('finds labels used more than once', async () => {
    const { duplicateLabels } = await import('@/lib/format');
    expect([...duplicateLabels(['a', 'b', 'a'], (x) => x)]).toEqual(['a']);
    expect(duplicateLabels([], (x: string) => x).size).toBe(0);
  });
});
