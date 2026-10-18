import type { VerdictTone } from '@/lib/selectors/jobs';

/** Text colour class of a verdict tone (prototype vmeta colours; incomplete in ink2). */
export const VERDICT_TEXT: Record<VerdictTone, string> = {
  pass: 'text-pass',
  narrowed: 'text-accent-deep',
  stop: 'text-stop',
  muted: 'text-ink2',
};
