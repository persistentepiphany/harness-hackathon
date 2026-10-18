// Small A4 building blocks of the report document (prototype DOCUMENTS view, pt sizes).

import clsx from 'clsx';
import type { ReactNode } from 'react';
import type { KeyNumber, Tone } from '@/lib/selectors/document';

const TONE: Record<Tone, string> = {
  ink: 'text-ink',
  warn: 'text-warn',
  stop: 'text-stop',
  muted: 'text-faint',
};

/** Uppercase 8.5pt section label. */
export function DocLabel({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={clsx('mb-1.5 text-[8.5pt] tracking-[.08em] text-muted uppercase', className)}>{children}</div>;
}

/** 8pt muted caption under a figure or table: `Fig. 2 · ...`. */
export function DocCaption({ children, className, 'data-testid': testId }: { children: ReactNode; className?: string; 'data-testid'?: string }) {
  return (
    <div className={clsx('mt-1 text-[8pt] text-muted', className)} data-testid={testId ?? 'doc-caption'}>
      {children}
    </div>
  );
}

/** A figure or table slot whose block the harness did not compute: one muted line, slot kept. */
export function DocNotComputed({ label, block }: { label: ReactNode; block: string }) {
  return (
    <div className="break-inside-avoid border-t border-line pt-1 text-[8pt] text-muted" data-testid="not-computed" data-block={block}>
      {label} · not computed
    </div>
  );
}

export function KeyNumbers({ items }: { items: KeyNumber[] }) {
  return (
    <div className="grid grid-cols-6 gap-2.5 break-inside-avoid" data-testid="doc-key-numbers">
      {items.map((k) => (
        <div key={k.id} className="border-t border-ink pt-1.5" data-testid="doc-key-number" data-key={k.id} title={k.title}>
          <div className={clsx('font-mono text-[14pt] font-medium', TONE[k.tone])}>{k.value}</div>
          <div className="mt-0.5 text-[8pt] leading-[1.3] text-muted">{k.label}</div>
        </div>
      ))}
    </div>
  );
}
