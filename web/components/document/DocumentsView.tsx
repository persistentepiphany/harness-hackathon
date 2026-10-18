'use client';

// /documents/[runId]: finished runs on the left, the A4 report of the selected run on the right.
// Print hides the nav and the sidebar (data-print="hide") and lays the page out on A4 sheets.

import { RunRouteGate } from '@/components/dev/RunRouteGate';
import { RecordGate } from '@/components/report';
import { useJobs, useRunRecord, useTools } from '@/lib/hooks';
import { docList, documentName } from '@/lib/selectors/document';
import { useRunRoute } from '@/lib/use-run-route';
import { DocumentSidebar } from './DocumentSidebar';
import { ReportDocument } from './ReportDocument';

/** A4 sheets with 16 mm margins and a white sheet; the page element drops its own padding in print. */
const PRINT_CSS = '@page { size: A4; margin: 16mm; } @media print { html, body { background: #fff !important; } }';

export function DocumentsView() {
  const route = useRunRoute((id) => `/documents/${encodeURIComponent(id)}`);
  const jobs = useJobs();
  const tools = useTools().data;
  const record = useRunRecord(route.runId);
  const items = docList(jobs.data);

  return (
    <main
      className="mx-auto grid w-full max-w-[1200px] animate-fade-up grid-cols-[220px_minmax(0,1fr)] items-start gap-10 px-6 pt-11 pb-20 print:block print:max-w-none print:animate-none print:p-0"
      data-testid="page-documents"
    >
      <style>{PRINT_CSS}</style>
      <DocumentSidebar items={items} selected={route.runId} record={record.data} />
      <div className="min-w-0 overflow-x-auto print:overflow-visible">
        <RunRouteGate route={route}>
          {(runId) => (
            <RecordGate runId={runId}>
              {(r) => <ReportDocument record={r} tools={tools} name={documentName(r, jobs.data)} />}
            </RecordGate>
          )}
        </RunRouteGate>
      </div>
    </main>
  );
}
