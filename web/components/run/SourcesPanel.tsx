'use client';

// Sources side panel: entity lookups (GET /ui/entities?q=, debounced) grouped by entity; each row
// is source · query → rows; the resolver's latency is in the source label's tooltip.

import { ErrorState, Spinner } from '@/components/ui';
import type { ApiError } from '@/lib/api-client';
import { fmtMs } from '@/lib/format';
import type { EntityGroupView } from '@/lib/selectors/run';
import { RingDot, SectionHead } from './parts';

export interface SourcesPanelProps {
  groups: EntityGroupView[];
  busy: boolean;
  error: ApiError | null;
}

export function SourcesPanel({ groups, busy, error }: SourcesPanelProps) {
  return (
    <div data-testid="sources-panel" data-state={busy ? 'loading' : error ? 'error' : groups.length ? 'ready' : 'empty'}>
      <SectionHead label="Sources" hint={busy ? <Spinner size={9} label="resolving" /> : undefined} />
      {groups.length === 0 && !error && <div className="text-[12.5px] text-faint">Records load here as targets and ligands are named.</div>}
      {error && <ErrorState error={error} title="Lookup failed" className="mb-3" />}
      <div className="flex flex-col gap-3.5">
        {groups.map((g) => (
          <div key={g.title} className="animate-fade-up" data-testid="entity-group" data-kind={g.kind}>
            <div className="mb-1.5 flex items-center gap-2 text-[13px] font-semibold">
              <span className={g.kind === 'protein' ? 'h-[7px] w-[7px] rounded-[2px] bg-accent' : 'h-[7px] w-[7px] rounded-[2px] bg-docking'} />
              {g.title}
            </div>
            <div className="flex flex-col gap-px">
              {g.items.map((e) => (
                <div
                  key={e.key}
                  data-testid="entity-row"
                  data-source={e.source}
                  data-state={e.status}
                  className="grid animate-fade-in grid-cols-[12px_84px_minmax(0,1fr)] items-start gap-2 border-t border-line2 py-[5px]"
                >
                  <RingDot state={e.status === 'error' ? 'error' : 'ok'} size={8} className="relative top-1" />
                  <span className="pt-px text-[11.5px] text-muted" title={e.ms !== null ? `resolved in ${fmtMs(e.ms)}` : undefined}>
                    {e.source}
                  </span>
                  <div className="min-w-0 text-[12px]">
                    {e.status === 'error' ? (
                      <div className="flex min-w-0 gap-2">
                        <span className="flex-none font-mono text-[11.5px] text-faint">{e.query}</span>
                        <span className="min-w-0 break-words text-stop">{e.message || 'lookup failed'}</span>
                      </div>
                    ) : (
                      e.rows.map((r, i) => (
                        <div key={`${r.k}-${i}`} className="flex min-w-0 gap-2">
                          <span className="flex-none text-muted">{r.k}</span>
                          <span className="overflow-hidden font-mono text-[11.5px] text-ellipsis whitespace-nowrap" title={r.v}>
                            {r.v}
                          </span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
