// Shared figure props and caption.

import clsx from 'clsx';
import type { ReactNode } from 'react';
import type { ReportBlockProps } from '../types';

export interface FigureProps extends ReportBlockProps {
  /** Show the caption (default true). */
  caption?: boolean;
  /** Figure number in the caption (report numbering by default). */
  figNo?: number | string;
}

export function FigureCaption({ no, children, print }: { no?: number | string; children: ReactNode; print?: boolean }) {
  return (
    <div className={clsx('text-muted', print ? 'mt-1 text-[8pt]' : 'mt-2.5 text-[11px]')} data-testid="figure-caption">
      {no !== undefined && no !== '' ? `Fig. ${no} · ` : ''}
      {children}
    </div>
  );
}

/** SVG text defaults of the prototype figures. */
export const SVG_TEXT = { fontSize: 8.5, fill: 'var(--color-muted)', fontFamily: 'var(--font-mono)' } as const;
