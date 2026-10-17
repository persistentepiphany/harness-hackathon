'use client';

import { useEffect, useState } from 'react';
import type { Job } from '@/lib/types';

/**
 * Elapsed ms of a job, ticking every 100 ms while it runs. Between polls the time is extrapolated
 * from the last reported value; it never goes backwards. Not running: the reported value.
 */
export function useElapsed(job: Pick<Job, 'id' | 'status' | 'elapsedMs'> | null | undefined): number | undefined {
  const [tick, setTick] = useState<{ id: string; ms: number } | null>(null);
  const id = job?.id;
  const running = job?.status === 'running';
  const base = job?.elapsedMs;
  useEffect(() => {
    if (!running || id === undefined || base === undefined) return;
    const at = Date.now();
    const timer = setInterval(() => {
      const ms = base + (Date.now() - at);
      setTick((prev) => ({ id, ms: prev && prev.id === id ? Math.max(prev.ms, ms) : ms }));
    }, 100);
    return () => clearInterval(timer);
  }, [id, running, base]);
  if (!job) return undefined;
  if (!running || !tick || tick.id !== job.id) return job.elapsedMs;
  return Math.max(tick.ms, job.elapsedMs);
}
