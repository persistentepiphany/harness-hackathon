// Mock mode only: the prototype's synthetic PAE pattern (logic-v2.js drawPae), drawn for mock
// records so the PAE figure has prototype data. Live records draw stats.pae or show "not computed".

import type { UiRunRecord } from '@/lib/types';
import type { PaeData } from './pae';

export function mockPae(record: UiRunRecord): PaeData {
  const n = 48;
  const disc = record.task === 'interaction_discovery';
  const split = disc ? 28 : 38;
  let s = 7;
  const r = () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
  const matrix: number[][] = Array.from({ length: n }, () => new Array<number>(n).fill(0));
  // the prototype fills column-major (i = x, j = y); keep its draw order so the noise matches
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      const same = i < split === j < split;
      const d = Math.abs(i - j);
      matrix[j][i] = same ? Math.min(30, 1 + d * 0.25 + r() * 2.5) : disc ? 9 + r() * 12 : 2.5 + r() * 2;
    }
  }
  const lig = record.inputs.ligand !== null && record.inputs.ligand !== undefined && record.inputs.ligand !== '';
  const paeMetric = record.stats.metrics?.find((m) => /PAE/.test(m.name));
  return {
    matrix,
    block: { rows: [0, split], cols: [split, n] },
    lines: [
      `${lig ? 'pocket' : 'interface'} block ${paeMetric?.value ?? '–'} mean`,
      'intra-chain 1.4 Å · diagonal',
      lig ? '38 pocket residues × ligand tokens' : `${record.inputs.target ?? ''} × ${record.inputs.partner ?? ''}`,
    ],
    max: 30,
  };
}
