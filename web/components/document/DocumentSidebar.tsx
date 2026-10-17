'use client';

// Left column of the documents page (hidden in print): finished runs, then PDF (browser print),
// the run record as JSON and the report files the run wrote (live) or the notebook (mock record).

import clsx from 'clsx';
import Link from 'next/link';
import { downloadRecord } from '@/components/report';
import { getHarnessApi } from '@/lib/harness-api';
import { reportFiles, type DocListItem } from '@/lib/selectors/document';
import type { UiRunRecord } from '@/lib/types';

const BTN_PRIMARY = 'rounded border-0 bg-ink px-3.5 py-2 text-center text-[12.5px] leading-[normal] font-medium text-white hover:text-white';
const BTN = 'rounded border border-line bg-transparent px-3.5 py-[7px] text-center text-[12.5px] leading-[normal] font-medium text-ink hover:border-ink hover:text-ink';

/** The prototype's notebook skeleton for a mock record (record.record.notebook is set only there). */
function downloadNotebook(r: UiRunRecord) {
  const name = r.record.notebook;
  if (!name) return;
  const cell = (src: string) => ({ cell_type: 'code', metadata: {}, outputs: [], execution_count: null, source: src });
  const nb = {
    nbformat: 4,
    nbformat_minor: 5,
    metadata: { kernelspec: { name: 'python3', display_name: 'Python 3' }, papermill: { parameters: { run_record: `${r.id}.json` } } },
    cells: [
      { cell_type: 'markdown', metadata: {}, source: `# ${r.id}\nReruns every query and check from the run record.` },
      cell(`import json\nrecord = json.load(open('${r.id}.json'))`),
      cell(`for s in record['sources']:\n    assert fetch(s['source'], s['accession'], s['release']).sha256 == s['sha256'], s`),
      ...r.layers.slice(1).map((l) => cell(`# ${l.name}\nfor c in record['layers'][${l.i}]['checks']:\n    assert run_check(c['id'], record['inputs']).result == c['result'], c['id']`)),
    ],
  };
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(nb, null, 2)], { type: 'application/json' }));
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

export interface DocumentSidebarProps {
  items: DocListItem[];
  selected: string | null;
  record: UiRunRecord | undefined;
}

export function DocumentSidebar({ items, selected, record }: DocumentSidebarProps) {
  const files = record ? reportFiles(record) : [];
  return (
    <div data-print="hide" className="sticky top-[68px] flex flex-col gap-3.5" data-testid="doc-sidebar">
      <h1 className="m-0 text-[18px] font-semibold tracking-[-0.01em]">Documents</h1>
      {/* the column is sticky: a long run list scrolls on its own so the buttons stay in view */}
      <div className="-ml-0.5 flex max-h-[calc(100vh-380px)] flex-col gap-3.5 overflow-y-auto pl-0.5" data-testid="doc-list">
        {items.map((d) => {
          const on = d.runId === selected;
          return (
            <Link
              key={d.runId}
              href={`/documents/${encodeURIComponent(d.runId)}`}
              className={clsx('flex flex-col gap-0.5 border-l-2 py-1.5 pl-3 text-ink hover:border-faint hover:text-ink', on ? 'border-ink' : 'border-line')}
              data-testid="doc-list-item"
              data-run={d.runId}
              data-state={d.outcome ?? 'pending'}
              data-selected={on ? 'true' : undefined}
              aria-current={on ? 'page' : undefined}
            >
              <span className={clsx('text-[13px] leading-[normal]', on ? 'font-semibold' : 'font-medium')}>{d.name}</span>
              <span className="font-mono text-[11px] leading-[normal]" style={{ color: d.verdictColor }}>
                {d.verdictLabel} · {d.date}
              </span>
            </Link>
          );
        })}
      </div>
      {record && (
        <div className="mt-2.5 flex flex-col gap-1.5">
          <button type="button" className={BTN_PRIMARY} onClick={() => window.print()} data-testid="doc-print">
            PDF
          </button>
          <button type="button" className={BTN} onClick={() => downloadRecord(record)} data-testid="doc-download-record">
            Run record · JSON
          </button>
          {record.record.notebook && (
            <button type="button" className={BTN} onClick={() => downloadNotebook(record)} data-testid="doc-download-notebook">
              Notebook · ipynb
            </button>
          )}
          {files.map((f) => (
            <a key={f.id} href={getHarnessApi().assetUrl(f.url)} target="_blank" rel="noreferrer" className={BTN} data-testid={`doc-file-${f.id}`}>
              {f.label}
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
