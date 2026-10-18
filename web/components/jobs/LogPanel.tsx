'use client';

// Live log of a job (prototype log panel): Plain (default) or Terminal, streamed through
// useJobLog (SSE in live mode). Sticks to the bottom while new lines arrive unless the reader has
// scrolled up; "Latest" brings it back.

import clsx from 'clsx';
import { useCallback, useLayoutEffect, useRef, useState } from 'react';
import type { ApiError } from '@/lib/api-client';
import { logLineView, logStats, type LogMode } from '@/lib/selectors/run';
import { DASH } from '@/lib/format';
import type { LogLine, RecordSource } from '@/lib/types';

export interface LogPanelProps {
  lines: LogLine[];
  header: string;
  /** Text shown while there are no lines (queued: waiting for a slot). */
  emptyText: string;
  status: string;
  error?: ApiError | null;
  /** record.sources: the fetched count when the log has no fetch/cache lines. */
  sources?: Pick<RecordSource, 'cached'>[] | null;
}

const STICK_PX = 24;

export function LogPanel({ lines, header, emptyText, status, error, sources }: LogPanelProps) {
  const [mode, setMode] = useState<LogMode>('plain');
  const [stuck, setStuck] = useState(true);
  const body = useRef<HTMLDivElement>(null);
  const term = mode === 'terminal';
  const stats = logStats(lines, sources);

  const toBottom = useCallback(() => {
    const el = body.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, []);

  useLayoutEffect(() => {
    if (stuck) toBottom();
  }, [lines.length, mode, stuck, toBottom]);

  const onScroll = () => {
    const el = body.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < STICK_PX;
    if (atBottom !== stuck) setStuck(atBottom);
  };

  return (
    <div
      data-testid="log-panel"
      data-mode={mode}
      data-state={status}
      className={clsx(
        'relative flex h-[min(620px,calc(100vh-300px))] min-h-[320px] flex-col overflow-hidden rounded-card border transition-colors duration-200',
        term ? 'border-terminal-bg bg-terminal-bg text-terminal-fg' : 'border-line bg-surface text-ink',
      )}
    >
      <div className={clsx('flex items-center justify-between gap-3 border-b py-2.5 pr-3 pl-3.5', term ? 'border-white/[.08]' : 'border-line2')}>
        <span className={clsx('min-w-0 truncate font-mono text-[12px]', term ? 'text-[#6B6B66]' : 'text-faint')} data-testid="log-current">
          {header}
        </span>
        <div className={clsx('flex flex-none gap-0.5 rounded-[5px] p-0.5', term ? 'bg-white/[.08]' : 'bg-[#F1F1ED]')} role="tablist" aria-label="Log view">
          {(['plain', 'terminal'] as const).map((m) => (
            <button
              key={m}
              type="button"
              role="tab"
              aria-selected={mode === m}
              data-testid={`log-mode-${m}`}
              onClick={() => setMode(m)}
              className={clsx(
                'rounded-[4px] border-0 px-[9px] py-[3px] text-[11px] leading-[normal] font-medium',
                mode === m ? 'bg-surface text-ink' : 'bg-transparent text-muted',
              )}
            >
              {m === 'plain' ? 'Plain' : 'Terminal'}
            </button>
          ))}
        </div>
      </div>
      <div
        ref={body}
        onScroll={onScroll}
        data-testid="log-body"
        className={clsx('flex-1 overflow-auto px-3.5 py-2.5 leading-[1.6]', term ? 'font-mono text-[11px]' : 'font-sans text-[12.5px]')}
      >
        {lines.map((l) => {
          const v = logLineView(l, mode);
          return (
            <div
              key={l.seq}
              data-testid="log-line"
              data-state={l.result ?? l.kind}
              data-kind={l.kind}
              data-seq={l.seq}
              className={clsx('grid animate-fade-in grid-cols-[44px_14px_minmax(0,1fr)] gap-2.5', term ? 'py-px' : 'py-1')}
            >
              <span className={term ? 'text-[#6B6B66]' : 'text-faint'}>{l.t}</span>
              <span className="relative top-1.5 h-1.5 w-1.5 rounded-full" style={{ background: v.dot ?? 'transparent' }} />
              <span className="[overflow-wrap:anywhere]" style={{ color: v.color, fontWeight: v.weight }}>
                {v.text}
              </span>
            </div>
          );
        })}
        {lines.length === 0 && !error && (
          <div className={term ? 'text-[#6B6B66]' : 'text-faint'} data-testid="log-empty">
            {emptyText}
          </div>
        )}
        {error && (
          <div className="text-stop" role="alert" data-testid="log-error">
            Log stream: {error.message} ({error.code})
          </div>
        )}
      </div>
      {!stuck && lines.length > 0 && (
        <button
          type="button"
          onClick={() => {
            setStuck(true);
            toBottom();
          }}
          data-testid="log-latest"
          className={clsx(
            'absolute right-3 bottom-12 rounded-full border px-2.5 py-1 text-[11px] font-medium shadow-sm',
            term ? 'border-white/10 bg-[#2A2A27] text-terminal-fg' : 'border-line bg-surface text-ink2 hover:text-ink',
          )}
        >
          Latest ↓
        </button>
      )}
      <div className={clsx('flex gap-3.5 border-t px-3.5 py-[9px] font-mono text-[11px]', term ? 'border-white/[.08] text-[#6B6B66]' : 'border-line2 text-faint')} data-testid="log-footer">
        <span className="text-terminal-pass">{stats.pass} pass</span>
        <span className="text-terminal-warn">{stats.warn} warn</span>
        <span className="text-terminal-stop">{stats.stop} stop</span>
        {stats.skip > 0 && <span>{stats.skip} skip</span>}
        <span className="ml-auto">
          {stats.fetched ?? DASH} fetched{stats.cached !== null ? ` · ${stats.cached} cached` : ''} · {stats.checks} checks
        </span>
      </div>
    </div>
  );
}
