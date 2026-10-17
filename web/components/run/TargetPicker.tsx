'use client';

// Targets: catalog chips, "+ accession or name" input, detail card of the picked target.

import { Chip } from '@/components/ui';
import { DASH } from '@/lib/format';
import { targetRows, type TargetOption } from '@/lib/selectors/run';
import { DetailCard } from './DetailCard';
import { AddInput, SectionHead } from './parts';

export interface TargetPickerProps {
  options: TargetOption[];
  selected: string;
  detail: TargetOption | null;
  onSelect: (p: TargetOption) => void;
  addValue: string;
  onAddValue: (v: string) => void;
  onAdd: (v: string) => void;
}

export function TargetPicker({ options, selected, detail, onSelect, addValue, onAddValue, onAdd }: TargetPickerProps) {
  return (
    <div data-testid="target-picker">
      <SectionHead label="Targets" hint="examples · any UniProt accession or name works" />
      <div className="flex flex-wrap items-center gap-1.5">
        {options.map((p) => (
          <Chip
            key={p.accession}
            selected={selected === p.accession}
            sub={p.accession}
            onClick={() => onSelect(p)}
            data-testid="target-chip"
            data-accession={p.accession}
            data-state={selected === p.accession ? 'selected' : 'idle'}
          >
            {p.label}
          </Chip>
        ))}
        <AddInput value={addValue} onChange={onAddValue} onSubmit={onAdd} placeholder="+ accession or name" width={170} data-testid="add-target" />
      </div>
      {detail && (
        <DetailCard
          data-testid="target-detail"
          title={detail.label}
          sub={`${detail.entry || DASH} · ${detail.accession}`}
          rows={targetRows(detail)}
        />
      )}
    </div>
  );
}
