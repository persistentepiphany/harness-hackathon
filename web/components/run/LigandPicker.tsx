'use client';

// Ligands: catalog chips, "+ SMILES, CCD or name" input, detail card of the picked ligand.

import { Chip } from '@/components/ui';
import { ligandFormula, ligandRows, type LigandOption } from '@/lib/selectors/run';
import { DetailCard } from './DetailCard';
import { AddInput, SectionHead } from './parts';

export interface LigandPickerProps {
  options: LigandOption[];
  /** SMILES of the selected ligand. */
  selected: string;
  detail: LigandOption | null;
  onSelect: (l: LigandOption) => void;
  addValue: string;
  onAddValue: (v: string) => void;
  onAdd: (v: string) => void;
}

export function LigandPicker({ options, selected, detail, onSelect, addValue, onAddValue, onAdd }: LigandPickerProps) {
  return (
    <div data-testid="ligand-picker">
      <SectionHead label="Ligands" hint="examples · paste any SMILES, CCD code or name" />
      <div className="flex flex-wrap items-center gap-1.5">
        {options.map((l) => {
          const on = selected === l.smiles;
          return (
            <Chip
              key={l.smiles}
              selected={on}
              sub={l.ccd || undefined}
              onClick={() => onSelect(l)}
              data-testid="ligand-chip"
              data-ligand={l.names[0]}
              data-state={on ? 'selected' : 'idle'}
            >
              {l.names[0]}
            </Chip>
          );
        })}
        <AddInput value={addValue} onChange={onAddValue} onSubmit={onAdd} placeholder="+ SMILES, CCD or name" width={190} data-testid="add-ligand" />
      </div>
      {detail && <DetailCard data-testid="ligand-detail" title={detail.names[0]} sub={ligandFormula(detail)} rows={ligandRows(detail)} ellipsis />}
    </div>
  );
}
