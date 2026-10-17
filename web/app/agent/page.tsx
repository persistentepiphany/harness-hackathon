import type { Metadata } from 'next';
import { Suspense } from 'react';
import { AgentMonitor } from '@/components/agent';

export const metadata: Metadata = { title: 'Agent · Harness' };

export default function AgentPage() {
  // AgentMonitor reads ?task= (useSearchParams), which needs a Suspense boundary
  return (
    <Suspense fallback={null}>
      <AgentMonitor />
    </Suspense>
  );
}
