'use client';

// Key numbers of an ensemble member (cell footer and detail table). Labels come from the tools'
// outputs; rankingOnly scores sit on their own muted line, never styled as pose quality.

import clsx from 'clsx';
import { ResultDot } from '@/components/report/parts';
import { DASH, fmtNum, fmtSha, THIN } from '@/lib/format';
import type { EnsembleMember, MemberColumn, MemberValue } from '@/lib/selectors/report';

const val = (v: MemberValue) => fmtNum(v.value, v.unit);

export function GateDot({ m, size = 6 }: { m: EnsembleMember; size?: number }) {
  return (
    <span title={m.gate ? `worst gate on this structure: ${m.gate}` : 'no per-structure gate in the record'} data-testid="member-gate" data-state={m.gate ?? 'none'} className="inline-flex">
      <ResultDot result={m.gate} size={size} hollow={!m.gate} className="top-0" />
    </span>
  );
}

/** Cell footer (prototype cell stats): the member columns present in the ensemble, up to four, then the ranking line. */
export function MemberFooter({ m, columns, showRanking }: { m: EnsembleMember; columns: MemberColumn[]; showRanking: boolean }) {
  const cells = columns.filter((c) => !c.ranking).slice(0, 4);
  return (
    <div className="border-t border-line2 px-3 py-2 font-mono text-[11px]">
      <div className="grid gap-1.5" style={{ gridTemplateColumns: `repeat(${Math.max(cells.length, 1)},minmax(0,1fr))` }}>
        {cells.map((c) => {
          const t = c.text(m);
          return (
            <div key={c.id} className="min-w-0" data-testid={`member-${c.id}`}>
              <div className="truncate text-[10px] text-muted" title={c.title}>
                {c.header}
              </div>
              <div className={clsx('truncate', t === DASH ? 'text-faint' : c.warn?.(m) ? 'text-warn' : 'text-ink')}>
                {c.id === 'rmsd' && t !== DASH ? `${t}${THIN}Å${m.cluster !== null ? ` · c${m.cluster}` : ''}` : t}
              </div>
            </div>
          );
        })}
        {!cells.length && <div className="text-[10.5px] text-faint">not computed</div>}
      </div>
      {showRanking && (
        <div className="mt-1 truncate text-[10.5px] text-muted" data-testid="member-ranking" title="ranking scores, read within this run only">
          {m.ranking.length ? m.ranking.map((r) => `${r.label} ${val(r)}`).join(' · ') : DASH}
        </div>
      )}
    </div>
  );
}

/** Full numbers of one member: provenance, harness statistics, every tool output with units. */
export function MemberTable({ m }: { m: EnsembleMember }) {
  const rows: [string, string, string?][] = [
    ['kind', m.kind],
    ['tool', m.toolName ?? (m.kind === 'crystal' ? 'experimental' : DASH)],
    ['source', m.structure?.path ?? m.source],
    ['sha256', m.structure?.sha256 ? fmtSha(m.structure.sha256) : DASH, m.structure?.sha256],
    ['RMSD to medoid', m.rmsd === null ? DASH : fmtNum(m.rmsd, 'Å', 2)],
    ...(m.rmsdToReference !== null ? ([['RMSD to reference', fmtNum(m.rmsdToReference, 'Å', 2)]] as [string, string][]) : []),
    ['cluster', m.cluster === null ? DASH : String(m.cluster)],
    ['pocket pLDDT', m.plddt === null ? DASH : fmtNum(m.plddt)],
    ['PoseBusters', m.pb ? (m.pb.total ? `${m.pb.passed}/${m.pb.total}` : String(m.pb.passed)) : DASH],
    ['gate', m.gate ?? DASH],
  ];
  const quality = m.outputs.filter((o) => !o.rankingOnly);
  return (
    <div className="overflow-auto rounded-card border border-line bg-surface font-mono text-[11.5px]" data-testid="member-table">
      {rows.map(([k, v, title]) => (
        <div key={k} className="grid grid-cols-[120px_minmax(0,1fr)] gap-3 border-b border-line3 px-3 py-1.5">
          <span className="text-muted">{k}</span>
          <span className={clsx('truncate text-right', v === DASH ? 'text-faint' : 'text-ink')} title={title ?? v}>
            {v}
          </span>
        </div>
      ))}
      <div className="px-3 pt-2.5 pb-1 text-[10.5px] text-muted">{m.toolName ? `${m.toolName} outputs` : 'tool outputs'}</div>
      {quality.map((o) => (
        <div key={o.key} className="grid grid-cols-[minmax(0,1fr)_auto] gap-3 border-b border-line3 px-3 py-1.5" data-testid="member-output">
          <span className="truncate text-ink2" title={o.key}>
            {o.label}
          </span>
          <span className="text-right text-ink">{val(o)}</span>
        </div>
      ))}
      {m.ranking.length > 0 && <div className="h-0 border-t border-accent" />}
      {m.ranking.map((o) => (
        <div key={o.key} className="grid grid-cols-[minmax(0,1fr)_auto] gap-3 border-b border-accent px-3 py-1.5" data-testid="member-output" data-ranking="true">
          <span className="truncate text-ink2" title={o.key}>
            {o.label}
          </span>
          <span className="text-right text-accent-deep">{val(o)}</span>
        </div>
      ))}
      {!m.outputs.length && <div className="px-3 py-2 font-sans text-[12px] text-muted">not computed</div>}
    </div>
  );
}
