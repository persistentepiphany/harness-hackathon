'use client';

import type { ReactNode } from 'react';
import { EmptyState, ErrorState, Spinner } from '@/components/ui';
import type { RunRoute } from '@/lib/use-run-route';

/** Loading / empty / error states while a [runId] route (including `latest`) resolves. */
export function RunRouteGate({ route, children }: { route: RunRoute; children: (runId: string) => ReactNode }) {
  if (route.state === 'ready' && route.runId) return <>{children(route.runId)}</>;
  if (route.state === 'error') return <ErrorState error={route.error} onRetry={route.reload} title="Cannot list runs" />;
  if (route.state === 'none') return <EmptyState data-testid="no-runs">No finished run yet.</EmptyState>;
  return (
    <div className="flex items-center gap-2 text-muted" data-testid="run-route-loading">
      <Spinner /> resolving run
    </div>
  );
}
