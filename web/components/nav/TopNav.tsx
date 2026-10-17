'use client';

// Port of the prototype nav (Harness v2.dc.html, <nav>): 44px bar, logo mark, tabs with count
// badges and a 1.5px active underline, cluster status on the right. Tabs and badges follow the
// prototype's `tabs` list in logic-v2.js. The right side also shows the API mode: "mock", or the
// live connection state from /health polling.

import clsx from 'clsx';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAgentTasks, useHealth, useJobs } from '@/lib/hooks';

interface TabDef {
  id: string;
  label: string;
  href: string;
  active: boolean;
  badge?: number;
}

/** runId in /reports/<id>... or /documents/<id>, so Reports, Ensemble and Documents stay on one run. */
function currentRunId(pathname: string): string {
  const m = pathname.match(/^\/(?:reports|documents)\/([^/]+)/);
  return m ? decodeURIComponent(m[1]) : 'latest';
}

export function TopNav() {
  const pathname = usePathname() || '/';
  const jobs = useJobs();
  const agent = useAgentTasks();
  const health = useHealth();

  const list = jobs.data ?? [];
  const running = list.filter((j) => j.status === 'running').length;
  const queued = list.filter((j) => j.status === 'queued').length;
  const done = list.filter((j) => j.status === 'done').length;
  const agentRunning = (agent.data ?? []).filter((t) => t.status === 'running').length;
  const rid = encodeURIComponent(currentRunId(pathname));
  const isReport = /^\/reports\/[^/]+\/?$/.test(pathname);
  const isEnsemble = /^\/reports\/[^/]+\/ensemble/.test(pathname);

  const tabs: TabDef[] = [
    { id: 'new', label: 'New run', href: '/runs/new', active: pathname.startsWith('/runs') },
    { id: 'jobs', label: 'Jobs', href: '/jobs', active: pathname.startsWith('/jobs'), badge: running + queued },
    { id: 'report', label: 'Reports', href: `/reports/${rid}`, active: isReport, badge: done },
    { id: 'ensemble', label: 'Ensemble', href: `/reports/${rid}/ensemble`, active: isEnsemble },
    { id: 'agent', label: 'Agent', href: '/agent', active: pathname.startsWith('/agent'), badge: agentRunning },
    { id: 'docs', label: 'Documents', href: `/documents/${rid}`, active: pathname.startsWith('/documents'), badge: done },
  ];

  const connection = health.connection;
  const disconnected = connection === 'disconnected';
  // connection first (Live, Mock data, API unreachable), then runs in progress; never "idle"
  const connLabel = connection === 'mock' ? 'Mock data' : connection === 'connected' ? 'Live' : connection === 'checking' ? 'Connecting' : 'API unreachable';
  const connColor = connection === 'connected' ? 'var(--color-pass)' : disconnected ? 'var(--color-stop)' : 'var(--color-faint)';
  const connTitle =
    connection === 'connected'
      ? `Connected to the harness API${health.data?.version ? ` · ${health.data.version}` : ''}`
      : connection === 'mock'
        ? 'Mock data: the in-browser simulator, no harness API'
        : disconnected
          ? `Harness API unreachable${health.error ? `: ${health.error.message}` : ''}`
          : 'Checking the harness API';
  const runsLabel = running ? `${running} running${queued ? ` · ${queued} queued` : ''}` : queued ? `${queued} queued` : '';

  return (
    <nav
      data-print="hide"
      data-testid="top-nav"
      className="sticky top-0 z-20 flex h-11 items-center gap-4 border-b border-line bg-canvas px-4 sm:gap-8 sm:px-6"
    >
      <Link href="/runs/new" className="flex items-center gap-[9px] text-ink hover:text-ink" aria-label="Dock Harness">
        <span className="relative h-3.5 w-3.5 rounded-[3px] border-[1.5px] border-ink">
          <span className="absolute inset-[3px] rounded-[1px] bg-accent" />
        </span>
        <span className="text-[13px] font-semibold max-md:sr-only">Dock Harness</span>
      </Link>
      <div className="flex min-w-0 flex-1 gap-0.5 overflow-x-auto [scrollbar-width:none]">
        {tabs.map((t) => (
          <Link
            key={t.id}
            href={t.href}
            data-testid={`nav-tab-${t.id}`}
            data-state={t.active ? 'active' : 'inactive'}
            aria-current={t.active ? 'page' : undefined}
            className={clsx(
              'flex flex-none items-center gap-[7px] whitespace-nowrap border-b-[1.5px] px-2.5 pt-3 pb-[11px] text-[13px] leading-[normal] font-medium transition-colors duration-150 hover:text-ink',
              t.active ? 'border-ink text-ink' : 'border-transparent text-muted',
            )}
          >
            <span>{t.label}</span>
            {!!t.badge && (
              <span className="font-mono text-[11px] text-muted" data-testid={`nav-badge-${t.id}`}>
                {t.badge}
              </span>
            )}
          </Link>
        ))}
      </div>
      <div className="flex flex-none items-center gap-3 text-[12px] text-ink2" data-testid="cluster-status">
        {runsLabel && !disconnected && (
          <span className="flex items-center gap-1.5 font-mono text-[11px] whitespace-nowrap" data-testid="runs-status">
            <span aria-hidden className="h-1.5 w-1.5 animate-pulse-slow rounded-full bg-accent" />
            {runsLabel}
          </span>
        )}
        <span
          data-testid="api-status"
          data-state={connection}
          title={connTitle}
          className={clsx('flex items-center gap-1.5 text-[11.5px] whitespace-nowrap', disconnected ? 'text-stop' : connection === 'connected' ? 'text-ink2' : 'text-muted')}
        >
          <span aria-hidden className="h-1.5 w-1.5 rounded-full" style={{ background: connColor }} />
          {connLabel}
        </span>
      </div>
    </nav>
  );
}
