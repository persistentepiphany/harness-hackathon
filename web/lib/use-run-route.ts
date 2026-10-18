'use client';

// Resolves the [runId] route segment. `latest` is an alias for the newest finished run; once it
// resolves, the URL is replaced with the concrete id so the page can be shared.

import { useParams, useRouter } from 'next/navigation';
import { useEffect } from 'react';
import type { ApiError } from './api-client';
import { useResolvedRunId } from './hooks';

export type RunRouteState = 'loading' | 'ready' | 'none' | 'error';

export interface RunRoute {
  /** Route value as written (`latest` or an id). */
  param: string | null;
  /** Concrete run id, once known. */
  runId: string | null;
  state: RunRouteState;
  error: ApiError | null;
  reload: () => void;
}

/** `toPath(id)` builds the canonical URL for the resolved id, e.g. (id) => `/reports/${id}`. */
export function useRunRoute(toPath: (runId: string) => string): RunRoute {
  const params = useParams<{ runId?: string }>();
  const router = useRouter();
  const param = params?.runId ? decodeURIComponent(params.runId) : null;
  const resolved = useResolvedRunId(param);
  const runId = resolved.data ?? null;
  const target = resolved.isAlias && runId ? toPath(runId) : null;

  useEffect(() => {
    // keep ?seed= and other query parameters on the canonical URL
    if (target) router.replace(`${target}${window.location.search}`);
  }, [router, target]);

  const state: RunRouteState = runId ? 'ready' : resolved.error ? 'error' : resolved.loading || resolved.data === undefined ? 'loading' : 'none';
  return { param, runId, state, error: resolved.error, reload: resolved.reload };
}
