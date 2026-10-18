'use client';

// /ensemble?runs=a,b,c: several runs side by side. One tile per run: the assessed structure (Mol*
// while viewer slots last, else the PyMOL render), an overlay with the verdict badge, target and
// tools, and the run's median scores with units. The header row holds the medians across the
// selected runs; every run shows only the scores it has.

import clsx from 'clsx';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { memo, useCallback, useEffect, useMemo, useState } from 'react';
import { Num } from '@/components/report/parts';
import { StructureViewer } from '@/components/viewer/StructureViewer';
import { useViewerConfig } from '@/components/viewer/config';
import { fmtQuantityParts, shortRunId } from '@/lib/format';
import { getHarnessApi } from '@/lib/harness-api';
import { useJobs, useRunRecord, useTools } from '@/lib/hooks';
import { defaultStructureId, ensembleMembers, overallMedians, runSummary, structureTargets, type RunSummary, type SummaryScore } from '@/lib/selectors/report';
import type { Tool } from '@/lib/types';

const BADGE: Record<string, string> = {
  supported: 'bg-pass-tint text-pass',
  narrowed: 'bg-accent-tint text-accent-deep',
  refused: 'bg-stop-tint text-stop',
  incomplete: 'bg-line2 text-ink2',
  not_assessed: 'bg-line2 text-ink2',
  pending: 'bg-line2 text-muted',
};

function ScoreLine({ s, dark }: { s: SummaryScore; dark?: boolean }) {
  const p = fmtQuantityParts(s.value, s.quantity, s.unit);
  return (
    <div className={clsx('flex items-baseline justify-between gap-3 font-mono text-[11px]', dark ? 'text-ink2' : 'text-ink2')} data-testid="compare-score" data-score={s.id}>
      <span className={clsx('truncate font-sans text-[11px]', s.rankingOnly ? 'text-accent-deep' : 'text-muted')} title={`${s.label} over ${s.n} ${s.id === 'pb' ? 'poses' : 'values'}`}>
        {s.label}
      </span>
      <Num value={p.value} unit={p.unit} className="text-ink" />
    </div>
  );
}

const Tile = memo(function Tile({ runId, tools, slot, onSummary, onRemove }: { runId: string; tools: Tool[] | null | undefined; slot: boolean; onSummary: (id: string, s: RunSummary | null) => void; onRemove: (id: string) => void }) {
  const rec = useRunRecord(runId);
  const cfg = useViewerConfig();
  const record = rec.data;
  const targets = useMemo(() => (record ? structureTargets(record, { assetUrl: (p) => getHarnessApi().assetUrl(p), register: tools }) : []), [record, tools]);
  const members = useMemo(() => (record ? ensembleMembers(record, targets, tools) : []), [record, targets, tools]);
  const summary = useMemo(() => (record ? runSummary(record, members, tools) : null), [record, members, tools]);
  useEffect(() => {
    onSummary(runId, summary);
  }, [runId, summary, onSummary]);
  const chips = targets.filter((t) => t.kind !== 'overlay');
  const target = chips.find((t) => t.id === defaultStructureId(chips));
  return (
    <div className="group relative overflow-hidden rounded-card border border-line bg-surface transition-[border-color] duration-200 hover:border-faint" data-testid="compare-tile" data-run={runId} data-state={summary?.verdict.state ?? 'loading'}>
      <StructureViewer
        target={target}
        mode={cfg.mode}
        slot={slot}
        compact
        placeholder={rec.error ? `cannot load ${runId}` : !record ? 'loading run record' : !targets.length ? 'no structures in the record' : undefined}
        className="h-[300px]"
        data-testid="compare-viewer"
      />
      {summary && (
        <div className="pointer-events-none absolute inset-x-0 top-0 flex items-start justify-between gap-2 p-2.5">
          <div className="pointer-events-auto max-w-[75%] rounded-[6px] bg-white/90 px-2 py-1.5 shadow-[0_1px_4px_rgba(0,0,0,.06)] backdrop-blur-[2px]">
            <div className="flex items-center gap-1.5">
              <span className={clsx('rounded-[4px] px-1.5 py-px text-[10.5px] font-semibold tracking-[.04em] uppercase', BADGE[summary.verdict.state] ?? BADGE.pending)} data-testid="compare-badge">
                {summary.verdict.label}
              </span>
              <Link href={`/reports/${encodeURIComponent(runId)}`} className="truncate font-mono text-[11px] text-ink2 hover:text-ink" title={runId}>
                {shortRunId(runId)}
              </Link>
            </div>
            <div className="mt-1 truncate text-[12px] font-medium text-ink" title={summary.target}>
              {summary.target}
            </div>
            <div className="truncate text-[11px] text-muted">
              {summary.tools.join(', ') || 'no tool'}
              {summary.verdict.preRun ? ' · nothing predicted' : ''}
            </div>
          </div>
          <button type="button" onClick={() => onRemove(runId)} className="pointer-events-auto rounded-[4px] border-0 bg-white/80 px-1.5 text-[12px] leading-[18px] text-muted opacity-0 transition-opacity duration-200 group-hover:opacity-100 hover:text-ink" aria-label={`Remove ${runId}`} data-testid="compare-remove">
            ×
          </button>
        </div>
      )}
      <div className="border-t border-line2 px-3 py-2" data-testid="compare-scores">
        {summary?.scores.length ? summary.scores.map((s) => <ScoreLine key={s.id} s={s} />) : <div className="font-mono text-[11px] text-faint">{summary ? (summary.verdict.preRun ? 'no predicted structures' : 'no scores in the record') : 'loading'}</div>}
      </div>
    </div>
  );
});

function parseRuns(v: string | null): string[] {
  return (v ?? '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
    .filter((s, i, a) => a.indexOf(s) === i);
}

export function CompareView() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const jobs = useJobs().data ?? [];
  const tools = useTools().data;
  const cfg = useViewerConfig();
  const done = jobs.filter((j) => j.status === 'done');
  const fromUrl = parseRuns(params.get('runs'));
  const runs = fromUrl.length ? fromUrl : done.slice(0, 4).map((j) => j.runId);
  const setRuns = (next: string[]) => router.replace(`${pathname}?runs=${next.map(encodeURIComponent).join(',')}`, { scroll: false });
  const [summaries, setSummaries] = useState<Record<string, RunSummary | null>>({});
  const onSummary = useCallback((id: string, s: RunSummary | null) => setSummaries((m) => (m[id] === s ? m : { ...m, [id]: s })), []);
  const shown = runs.map((r) => summaries[r]).filter((s): s is RunSummary => !!s);
  const overall = overallMedians(shown);
  const toggle = (id: string) => setRuns(runs.includes(id) ? runs.filter((r) => r !== id) : [...runs, id]);

  return (
    <div className="flex flex-col gap-6" data-testid="compare-view">
      <div>
        <div className="flex items-baseline justify-between gap-4">
          <h1 className="m-0 text-[22px] font-semibold tracking-[-0.015em]">Compare runs</h1>
          <span className="font-mono text-[11px] text-muted">{runs.length} selected</span>
        </div>
        <div className="mt-3 flex flex-wrap gap-1.5" data-testid="compare-picker">
          {done.map((j) => {
            const on = runs.includes(j.runId);
            return (
              <button
                key={j.id}
                type="button"
                onClick={() => toggle(j.runId)}
                aria-pressed={on}
                data-testid="compare-pick"
                data-run={j.runId}
                title={j.runId}
                className={clsx('rounded-[5px] border px-2 py-[3px] text-[12px] transition-colors duration-150', on ? 'border-ink bg-ink text-white' : 'border-line text-ink2 hover:border-ink')}
              >
                {j.name}
                <span className={clsx('ml-1 font-mono text-[10.5px]', on ? 'text-white/60' : 'text-faint')}>{shortRunId(j.runId)}</span>
              </button>
            );
          })}
          {!done.length && <span className="text-[12px] text-muted">no finished runs</span>}
        </div>
      </div>

      <div className="grid gap-x-8 gap-y-1 border-y border-line py-3" style={{ gridTemplateColumns: 'repeat(auto-fill,minmax(230px,1fr))' }} data-testid="compare-overall">
        <div className="eyebrow col-span-full mb-1">Across {shown.length} runs · median of run medians</div>
        {overall.map((s) => (
          <div key={s.id} className="flex items-baseline justify-between gap-3 text-[12px]" data-testid="compare-overall-score" data-score={s.id}>
            <span className={s.rankingOnly ? 'text-accent-deep' : 'text-ink2'}>
              {s.label}
              <span className="ml-1 font-mono text-[10.5px] text-faint">{s.runs} {s.runs === 1 ? 'run' : 'runs'}</span>
            </span>
            {(() => {
              const p = fmtQuantityParts(s.value, s.quantity, s.unit);
              return <Num value={p.value} unit={p.unit} className="font-mono text-[12px] text-ink" />;
            })()}
          </div>
        ))}
        {!overall.length && <div className="text-[12px] text-muted">no scores in the selected runs</div>}
      </div>

      <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fill,minmax(320px,1fr))' }} data-testid="compare-grid">
        {runs.map((r, i) => (
          <Tile key={r} runId={r} tools={tools} slot={i < cfg.gridViewers} onSummary={onSummary} onRemove={(id) => setRuns(runs.filter((x) => x !== id))} />
        ))}
      </div>
      {!runs.length && <div className="text-[12px] text-muted">Pick runs above.</div>}
    </div>
  );
}
