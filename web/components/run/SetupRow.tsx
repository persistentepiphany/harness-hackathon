'use client';

// Setup under the request box: tools, target, ligand and seeds as menus on one aligned grid, the
// run line (where the tools run, estimated wall time) and Start run.

import type { ReactNode } from 'react';
import { Button, ErrorState } from '@/components/ui';
import { Menu, type MenuItem } from '@/components/ui/Menu';
import type { ApiError } from '@/lib/api-client';
import { TOOL_GROUP_LABELS, toolGroup, toolRunLabel, type LigandOption, type TargetOption } from '@/lib/selectors/run';
import type { Tool } from '@/lib/types';

export const SEED_CHOICES = [1, 3, 5] as const;

export interface SetupRowProps {
  register: Tool[];
  tools: string[];
  onToggleTool: (id: string) => void;
  targets: TargetOption[];
  target: string;
  onTarget: (p: TargetOption) => void;
  onAddTarget: (v: string) => void;
  ligands: LigandOption[] | null;
  ligand: string;
  onLigand: (l: LigandOption) => void;
  onAddLigand: (v: string) => void;
  seeds: number;
  onSeeds: (n: number) => void;
  onStart: () => void;
  starting?: boolean;
  error?: ApiError | null;
  /** Quick setup shows its own Start run; the setup row then shows the run line only. */
  hideStart?: boolean;
}

/** Wall time of the slowest selected tool (executors run in parallel, seeds in sequence). */
export function etaSeconds(register: Tool[], ids: string[], seeds: number): number | null {
  const times = ids
    .map((id) => register.find((t) => t.id === id)?.eta)
    .filter((e): e is NonNullable<Tool['eta']> => !!e)
    .map((e) => e.coldStartS + e.firstSeedExtraS + e.perSeedS * seeds);
  return times.length ? Math.max(...times) : null;
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <span className="pt-2 text-[12.5px] text-muted">{label}</span>
      <div className="min-w-0">{children}</div>
    </>
  );
}

export function SetupRow(p: SetupRowProps) {
  const toolItems: MenuItem[] = p.register.map((t) => {
    const runs = t.dispatchable !== false && t.available !== false;
    return {
      id: t.id,
      label: t.name,
      sub: runs ? (toolRunLabel(t) ?? undefined) : 'not available',
      group: TOOL_GROUP_LABELS[toolGroup(t)],
      disabled: !runs && !p.tools.includes(t.id),
      title: runs ? t.note : t.dispatchReason || t.note,
    };
  });
  const targetItems: MenuItem[] = p.targets.map((t) => ({ id: t.accession, label: t.label, sub: t.accession }));
  const ligandItems: MenuItem[] = (p.ligands ?? []).map((l) => ({ id: l.smiles, label: l.names[0] ?? l.smiles, sub: l.ccd || undefined }));
  const chosen = p.register.filter((t) => p.tools.includes(t.id));
  const remote = chosen.some((t) => t.route === 'modal');
  const local = chosen.some((t) => t.route === 'local');
  const eta = etaSeconds(p.register, p.tools, p.seeds);
  const where = [remote ? 'Modal A100' : null, local ? 'CPU' : null].filter(Boolean).join(' + ');
  const line = chosen.length
    ? [`${chosen.length} tool${chosen.length > 1 ? 's' : ''}`, `${p.seeds} seed${p.seeds > 1 ? 's' : ''}`, where || null, eta ? `about ${Math.max(1, Math.round(eta / 60))} min` : null].filter(Boolean).join(' · ')
    : 'no tool selected: inputs are checked, no model runs';

  return (
    <div className="flex flex-col gap-4" data-testid="setup-row">
      <div className="grid grid-cols-[72px_minmax(0,1fr)] items-start gap-x-4 gap-y-2.5">
        <Row label="Tools">
          <Menu label="Tools" items={toolItems} selected={p.tools} onSelect={p.onToggleTool} multiple placeholder="choose tools" data-testid="menu-tools" />
        </Row>
        <Row label="Target">
          <Menu
            label="Target"
            items={targetItems}
            selected={p.target ? [p.target] : []}
            onSelect={(id) => {
              const t = p.targets.find((x) => x.accession === id);
              if (t) p.onTarget(t);
            }}
            placeholder="choose a target"
            entry={{ placeholder: 'other: UniProt accession or name', onSubmit: p.onAddTarget }}
            data-testid="menu-target"
          />
        </Row>
        {p.ligands && (
          <Row label="Ligand">
            <Menu
              label="Ligand"
              items={ligandItems}
              selected={p.ligand ? [p.ligand] : []}
              onSelect={(id) => {
                const l = p.ligands?.find((x) => x.smiles === id);
                if (l) p.onLigand(l);
              }}
              placeholder="choose a ligand"
              entry={{ placeholder: 'other: SMILES, CCD code or name', onSubmit: p.onAddLigand }}
              data-testid="menu-ligand"
            />
          </Row>
        )}
        <Row label="Seeds">
          <div className="inline-flex h-9 overflow-hidden rounded border border-line" role="radiogroup" aria-label="Seeds" data-testid="seed-choice">
            {SEED_CHOICES.map((n) => (
              <button
                key={n}
                type="button"
                role="radio"
                aria-checked={p.seeds === n}
                onClick={() => p.onSeeds(n)}
                className={`w-12 border-l border-line text-[13px] tabular-nums first:border-l-0 ${p.seeds === n ? 'bg-ink text-white' : 'bg-surface text-ink hover:bg-line2'}`}
              >
                {n}
              </button>
            ))}
          </div>
        </Row>
      </div>
      <div className="flex items-center justify-between gap-4 border-t border-line pt-4">
        <span className="min-w-0 text-[12.5px] text-muted" data-testid="run-line">
          {line}
        </span>
        {!p.hideStart && (
          <Button onClick={p.onStart} disabled={p.starting} data-testid="start-run">
            {p.starting ? 'Starting' : chosen.length ? 'Start run' : 'Check inputs'}
          </Button>
        )}
      </div>
      {p.error && <ErrorState error={p.error} title="Run not started" />}
    </div>
  );
}
