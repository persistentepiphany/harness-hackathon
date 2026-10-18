'use client';

import clsx from 'clsx';
import { ApiError } from '@/lib/api-client';

export interface ErrorStateProps {
  error: ApiError | Error | null | undefined;
  onRetry?: () => void;
  title?: string;
  className?: string;
}

/** Error with the API's message, its code and status, and an optional retry. */
export function ErrorState({ error, onRetry, title = 'Request failed', className }: ErrorStateProps) {
  if (!error) return null;
  const api = error instanceof ApiError ? error : null;
  return (
    <div
      role="alert"
      data-testid="error-state"
      data-state={api?.code ?? 'error'}
      className={clsx('flex items-start gap-3 rounded-card border border-stop-tint bg-surface px-4 py-3 text-[12.5px]', className)}
    >
      <span className="mt-[5px] inline-block h-[7px] w-[7px] flex-none rounded-full bg-stop" aria-hidden />
      <div className="min-w-0 flex-1">
        <div className="font-medium text-ink">{title}</div>
        <div className="mt-0.5 break-words text-ink2">{error.message}</div>
        {api && (
          <div className="mt-1 font-mono text-[11px] text-muted">
            {api.code}
            {api.status ? ` · HTTP ${api.status}` : ''}
          </div>
        )}
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="flex-none rounded border border-line px-3 py-[5px] text-[12px] font-medium text-ink2 hover:border-ink hover:text-ink"
        >
          Retry
        </button>
      )}
    </div>
  );
}
