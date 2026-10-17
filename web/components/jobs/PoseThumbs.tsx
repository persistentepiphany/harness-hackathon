"use client";

import clsx from "clsx";
import { getHarnessApi } from "@/lib/harness-api";
import type { PoseThumbView } from "@/lib/selectors/jobs";
import type { UiRenderProgress } from "@/lib/types";

const BADGE: Record<PoseThumbView["badge"]["tone"], string> = {
  pass: "text-pass",
  warn: "text-accent-deep",
  stop: "text-stop",
  muted: "text-muted",
};

/** PyMOL render thumbnails of predicted poses, each with seed/rank, main score and a validity badge.
 *  The main structure renders first; the others show `rendering…` until their PNG exists. */
export function PoseThumbs({
  thumbs,
  progress,
}: {
  thumbs: PoseThumbView[];
  progress?: UiRenderProgress;
}) {
  if (!thumbs.length) return null;
  const api = getHarnessApi();
  return (
    <>
      {progress && progress.done < progress.total && (
        <div
          className="mt-2 text-[11.5px] text-muted tabular-nums"
          data-testid="render-progress"
        >
          renders {progress.done} of {progress.total}
          {progress.failed > 0 && (
            <span className="text-stop"> · {progress.failed} failed</span>
          )}
        </div>
      )}
      <div
        className="mt-2.5 grid grid-cols-[repeat(auto-fill,minmax(150px,1fr))] gap-2"
        data-testid="pose-thumbs"
      >
        {thumbs.map((t) => (
          <figure
            key={t.key}
            className="relative m-0 aspect-[5/3] animate-fade-up overflow-hidden rounded border border-line bg-canvas"
            data-testid="pose-thumb"
            data-state={t.badge.tone}
            data-render={t.status}
            data-main={t.main ? "true" : undefined}
            title={t.caption}
          >
            {t.status === "rendered" && t.png ? (
              // eslint-disable-next-line @next/next/no-img-element -- run files come through the API proxy
              <img
                src={api.assetUrl(t.png)}
                alt={t.alt}
                className="block h-full w-full object-cover"
                loading="lazy"
              />
            ) : (
              <div
                className={clsx(
                  "flex h-full w-full items-center justify-center text-[11px]",
                  t.status === "failed"
                    ? "text-stop"
                    : "animate-pulse text-muted",
                )}
                data-testid="pose-thumb-pending"
              >
                {t.status === "failed" ? "render failed" : "rendering…"}
              </div>
            )}
            <figcaption className="pointer-events-none absolute inset-0 flex flex-col justify-between p-1.5 font-mono text-[10px] leading-[1.25]">
              <span className="flex items-start justify-between gap-1">
                <span className="rounded-[3px] bg-surface/90 px-1 py-[1px] text-ink">
                  {t.label}
                </span>
                <span
                  className={clsx(
                    "rounded-[3px] bg-surface/90 px-1 py-[1px] text-right",
                    BADGE[t.badge.tone],
                  )}
                  data-testid="pose-badge"
                >
                  {t.badge.text}
                </span>
              </span>
              {t.score && (
                <span className="self-start rounded-[3px] bg-surface/90 px-1 py-[1px] text-ink2">
                  {t.score}
                </span>
              )}
            </figcaption>
          </figure>
        ))}
      </div>
    </>
  );
}
