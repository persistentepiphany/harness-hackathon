'use client';

// PyMOL render of the run's structure (record.renders[]), with its caption: the static structure
// figure for printed reports. "not computed" when the run has no renders.

import clsx from 'clsx';
import { RenderImage } from '@/components/viewer/RenderImage';
import { NotComputed } from './parts';
import type { ReportBlockProps } from './types';

export interface StructureImageProps extends ReportBlockProps {
  /** Render view to show first (`overview`, `pocket`); default the first render. */
  view?: string;
  /** Structure id (renders[].structure); default the first structure with renders. */
  structure?: string;
  /** Box height in px (default 300). */
  height?: number;
  /** Show the render caption under the image (default true). */
  caption?: boolean;
}

export function StructureImage({ record, view, structure, height = 300, caption = true, variant, className }: StructureImageProps) {
  const print = variant === 'print';
  const all = record.renders ?? [];
  const sid = structure ?? all[0]?.structure;
  const renders = all.filter((r) => r.structure === sid);
  const first = view ? renders.findIndex((r) => r.view === view) : 0;
  const ordered = first > 0 ? [renders[first], ...renders.filter((_, i) => i !== first)] : renders;
  if (!ordered.length) return <NotComputed what="renders" print={print} className={className} />;
  return (
    <figure className={clsx('m-0', className)} data-testid="structure-image">
      <div className="relative overflow-hidden rounded-[4px] border border-line bg-surface" style={{ height }}>
        <RenderImage renders={ordered} bare={print} />
      </div>
      {caption && ordered[0].caption && <figcaption className={clsx('mt-1.5 text-muted', print ? 'text-[8pt]' : 'text-[11px]')}>{ordered[0].caption}</figcaption>}
    </figure>
  );
}
