'use client';

// Placeholder used by the route stubs until the screens are built: shows loading, error and the
// hook data as JSON. Screen agents replace the page bodies; keep this for debugging if useful.

import { ErrorState, Spinner } from '@/components/ui';
import type { ApiError } from '@/lib/api-client';

export interface DataPreviewProps {
  label: string;
  data: unknown;
  error?: ApiError | null;
  loading?: boolean;
  onRetry?: () => void;
  /** Characters of JSON to show (the full record is large). */
  max?: number;
}

export function DataPreview({ label, data, error, loading, onRetry, max = 6000 }: DataPreviewProps) {
  const json = data === undefined ? '' : JSON.stringify(data, null, 2);
  return (
    <section className="flex flex-col gap-2" data-testid={`preview-${label}`}>
      <div className="flex items-center gap-2">
        <span className="eyebrow">{label}</span>
        {loading && <Spinner size={9} />}
      </div>
      <ErrorState error={error} onRetry={onRetry} />
      {json && (
        <pre className="max-h-[420px] overflow-auto rounded-card border border-line bg-surface p-3 font-mono text-[11px] leading-[1.5] text-ink2">
          {json.length > max ? `${json.slice(0, max)}\n… ${json.length - max} more characters` : json}
        </pre>
      )}
    </section>
  );
}
