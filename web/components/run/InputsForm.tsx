'use client';

// Inputs grid (prototype manual setup): target, partner, reference, seeds, pH, ligand SMILES.

import type { InputHTMLAttributes } from 'react';
import type { InputVisibility, RunForm } from '@/lib/selectors/run';

export type InputKey = 'target' | 'partner' | 'reference' | 'seeds' | 'ph' | 'ligand';

export interface InputsFormProps {
  form: RunForm;
  show: InputVisibility;
  onChange: (key: InputKey, value: string) => void;
}

const FIELD = 'w-full rounded border border-line bg-surface px-[11px] py-[9px] font-mono leading-[normal] text-ink placeholder:text-[#757575]';

export function InputsForm({ form, show, onChange }: InputsFormProps) {
  const field = (key: InputKey, placeholder: string, extra: InputHTMLAttributes<HTMLInputElement> = {}) => (
    <input
      value={form[key]}
      onChange={(e) => onChange(key, e.target.value)}
      placeholder={placeholder}
      aria-label={placeholder}
      data-testid={`input-${key}`}
      className={`${FIELD} text-[13px]`}
      {...extra}
    />
  );
  return (
    <div data-testid="inputs-form">
      <div className="eyebrow mb-2.5">Inputs</div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-2.5">
        {field('target', 'Target · UniProt')}
        {show.partner && field('partner', 'Partner · UniProt')}
        {show.reference && field('reference', 'Reference · PDB')}
        {field('seeds', 'Seeds', { type: 'number', min: 1, max: 20 })}
        {show.ph && field('ph', 'pH', { type: 'number', step: 0.1 })}
      </div>
      {show.ligand && (
        <input
          value={form.ligand}
          onChange={(e) => onChange('ligand', e.target.value)}
          placeholder="Ligand · SMILES"
          aria-label="Ligand · SMILES"
          data-testid="input-ligand"
          className={`${FIELD} mt-2.5 text-[12.5px]`}
        />
      )}
    </div>
  );
}
