'use client';

// /reports/[runId] (prototype view `report`). `latest` resolves to the newest finished run.
import { RunRouteGate } from '@/components/dev/RunRouteGate';
import { ReportView } from '@/components/report/ReportView';
import { useRunRoute } from '@/lib/use-run-route';

export default function ReportPage() {
  const route = useRunRoute((id) => `/reports/${encodeURIComponent(id)}`);
  return (
    <main className="mx-auto flex w-full max-w-[1280px] animate-fade-up flex-col gap-7 px-6 pt-11 pb-20" data-testid="page-report">
      <RunRouteGate route={route}>{(runId) => <ReportView runId={runId} />}</RunRouteGate>
    </main>
  );
}
