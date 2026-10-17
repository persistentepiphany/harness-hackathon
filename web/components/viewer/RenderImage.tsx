'use client';

// PyMOL renders (record.renders[]): the fallback when WebGL is unavailable (headless browsers,
// placeholder mode) and the structure figure on printed reports. Several views of one structure
// switch with small tabs; the .pse session is linked.

import clsx from 'clsx';
import { useState } from 'react';
import { getHarnessApi } from '@/lib/harness-api';
import type { RecordRender } from '@/lib/types';

export interface RenderImageProps {
  renders: RecordRender[];
  /** Fit inside the parent box (absolute fill) or flow with intrinsic height. */
  fill?: boolean;
  /** Hide the view tabs and .pse link (print). */
  bare?: boolean;
  className?: string;
}

export function RenderImage({ renders, fill = true, bare = false, className }: RenderImageProps) {
  const [view, setView] = useState(0);
  if (!renders.length) return null;
  const r = renders[Math.min(view, renders.length - 1)];
  const api = getHarnessApi();
  return (
    <div className={clsx(fill ? 'absolute inset-0' : 'relative', 'bg-surface', className)} data-testid="render-image" data-view={r.view}>
      {/* eslint-disable-next-line @next/next/no-img-element -- run files are served by the API proxy, not next/image */}
      <img
        src={api.assetUrl(r.png)}
        alt={r.alt ?? r.caption ?? `PyMOL render, ${r.view}`}
        title={r.caption}
        className={clsx('block h-full w-full object-contain', !fill && 'h-auto')}
      />
      {!bare && (
        <div className="absolute top-2 right-2 flex items-center gap-1 font-mono text-[10.5px]">
          {renders.length > 1 &&
            renders.map((x, i) => (
              <button
                key={`${x.png}-${i}`}
                type="button"
                onClick={() => setView(i)}
                aria-pressed={i === view}
                className={clsx(
                  'rounded-[4px] border px-1.5 py-[1px]',
                  i === view ? 'border-ink bg-ink text-white' : 'border-line bg-surface/90 text-ink2 hover:border-ink',
                )}
              >
                {x.view}
              </button>
            ))}
          {r.pse && (
            <a href={api.assetUrl(r.pse)} download className="rounded-[4px] border border-line bg-surface/90 px-1.5 py-[1px] text-ink2 hover:border-ink hover:text-ink">
              .pse
            </a>
          )}
        </div>
      )}
    </div>
  );
}
