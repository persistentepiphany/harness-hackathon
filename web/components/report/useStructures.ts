'use client';

// Structure targets, ensemble members and report chips of a record (memoised per record/register).

import { useMemo } from 'react';
import { getHarnessApi } from '@/lib/harness-api';
import { ensembleMembers, reportChipMembers, structureTargets, type EnsembleMember, type StructureTarget } from '@/lib/selectors/report';
import type { Tool, UiRunRecord } from '@/lib/types';

export interface StructureModel {
  targets: StructureTarget[];
  members: EnsembleMember[];
  /** Members shown as chips (REPORT_CHIP_LIMIT), then the overlay. */
  chips: EnsembleMember[];
  shown: StructureTarget[];
  hiddenCount: number;
}

export function useStructures(record: UiRunRecord, tools?: Tool[] | null): StructureModel {
  return useMemo(() => {
    const targets = structureTargets(record, { assetUrl: (p) => getHarnessApi().assetUrl(p), register: tools });
    const members = ensembleMembers(record, targets, tools);
    const overlay = targets.find((t) => t.kind === 'overlay');
    const chips = reportChipMembers(members);
    return { targets, members, chips, shown: [...chips, ...(overlay ? [overlay] : [])], hiddenCount: members.length - chips.length };
  }, [record, tools]);
}

/** Chip id of the structure a pose id (or label) names. */
export function chipForPose(model: StructureModel, pose: string | null): string | null {
  if (!pose) return null;
  const m = model.members.find((x) => x.entry?.pose === pose || x.label === pose || x.entry?.label === pose);
  if (!m) return null;
  return model.shown.some((t) => t.id === m.id) ? m.id : null;
}
