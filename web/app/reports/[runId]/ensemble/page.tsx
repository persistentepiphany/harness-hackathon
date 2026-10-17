'use client';

// /reports/[runId]/ensemble (prototype view `ensemble`). `latest` resolves to the newest finished run.
import { RunRouteGate } from '@/components/dev/RunRouteGate';
import { EnsembleView } from '@/components/ensemble/EnsembleView';
import { useRunRoute } from '@/lib/use-run-route';

export default function EnsemblePage() {
  const route = useRunRoute((id) => `/reports/${encodeURIComponent(id)}/ensemble`);
  return (
    <main className="mx-auto flex w-full max-w-[1280px] animate-fade-up flex-col gap-7 px-6 pt-11 pb-20" data-testid="page-ensemble">
      <RunRouteGate route={route}>{(runId) => <EnsembleView runId={runId} />}</RunRouteGate>
    </main>
  );
}
