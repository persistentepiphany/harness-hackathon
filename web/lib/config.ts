// Runtime configuration read from NEXT_PUBLIC_* variables (inlined at build time) and, for the
// mock simulator only, from the page URL (?seed=, ?simSpeed=, ?maxConcurrent=).

import type { HarnessMode } from './types';

/** `live` unless NEXT_PUBLIC_HARNESS_MODE=mock. Live mode never switches to mock by itself. */
export function harnessMode(): HarnessMode {
  return process.env.NEXT_PUBLIC_HARNESS_MODE === 'mock' ? 'mock' : 'live';
}

/** Browser-side base path of the proxy to `pah serve` (app/api/harness/[...path]/route.ts). */
export const API_BASE = '/api/harness';

export interface MockOptions {
  /** Fixed seed: virtual clock and fixed 110 ms ticks, so ids and timings repeat across loads. */
  seed?: number;
  /** Simulation speed factor (prototype tweak `simSpeed`). */
  simSpeed: number;
  /** Concurrent running jobs (prototype tweak `maxConcurrent`). */
  maxConcurrent: number;
  /** Simulated latency of mock API calls in ms. */
  latencyMs: number;
}

function num(v: string | null | undefined): number | undefined {
  if (v === null || v === undefined || v === '') return undefined;
  const n = Number(v);
  return Number.isFinite(n) ? n : undefined;
}

export function mockOptions(search?: string): MockOptions {
  let params: URLSearchParams | null = null;
  try {
    params = new URLSearchParams(search ?? (typeof window !== 'undefined' ? window.location.search : ''));
  } catch {
    params = null;
  }
  const seed = num(params?.get('seed')) ?? num(process.env.NEXT_PUBLIC_MOCK_SEED);
  return {
    seed,
    simSpeed: num(params?.get('simSpeed')) ?? num(process.env.NEXT_PUBLIC_MOCK_SIM_SPEED) ?? 1,
    maxConcurrent: num(params?.get('maxConcurrent')) ?? num(process.env.NEXT_PUBLIC_MOCK_MAX_CONCURRENT) ?? 3,
    latencyMs: num(params?.get('latency')) ?? num(process.env.NEXT_PUBLIC_MOCK_LATENCY_MS) ?? 120,
  };
}
