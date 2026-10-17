// EventSource stream with reconnection and seq dedupe, for GET /jobs/{id}/log and
// GET /agent/tasks/{id}/steps (docs/UI.md: `event: line|step`, `event: end`, `id: <seq>`).
//
// While the connection drops, EventSource reconnects by itself and sends Last-Event-ID, so the
// server resumes after the last seq. When the browser gives up (HTTP error, proxy error), the
// stream is reopened here with exponential backoff; the server then replays from the start and
// items with seq <= the last delivered one are dropped.

import { ApiError } from './api-client';

export type Unsubscribe = () => void;

export type StreamStatus = 'connecting' | 'open' | 'reconnecting' | 'ended' | 'failed';

/** Why the server ended a stream (`event: end` data); absent when it does not say. */
export interface StreamEnd {
  reason?: string;
  lastSeq?: number;
}

export interface StreamCallbacks {
  onEnd?: (end?: StreamEnd) => void;
  onError?: (err: ApiError) => void;
  onStatus?: (status: StreamStatus) => void;
}

export interface SseOptions {
  /** Reopen attempts after the browser closed the stream. */
  maxRetries?: number;
  baseDelayMs?: number;
  maxDelayMs?: number;
  EventSourceImpl?: typeof EventSource;
}

interface Seq {
  seq: number;
}

export function openSseStream<T extends Seq>(
  url: string,
  eventName: string,
  onItem: (item: T) => void,
  cb: StreamCallbacks = {},
  opts: SseOptions = {},
): Unsubscribe {
  const ES = opts.EventSourceImpl ?? (typeof EventSource !== 'undefined' ? EventSource : undefined);
  const maxRetries = opts.maxRetries ?? 8;
  const baseDelay = opts.baseDelayMs ?? 1000;
  const maxDelay = opts.maxDelayMs ?? 15000;

  let es: EventSource | null = null;
  let lastSeq = -Infinity;
  let attempts = 0;
  let disposed = false;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let status: StreamStatus | null = null;

  const setStatus = (s: StreamStatus) => {
    if (s === status) return;
    status = s;
    cb.onStatus?.(s);
  };

  const close = () => {
    if (es) {
      es.close();
      es = null;
    }
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
  };

  if (!ES) {
    queueMicrotask(() => {
      if (disposed) return;
      setStatus('failed');
      cb.onError?.(new ApiError({ status: 0, code: 'unsupported', message: 'EventSource is not available in this environment', url }));
    });
    return () => {
      disposed = true;
    };
  }

  const handleItem = (ev: MessageEvent) => {
    let item: T;
    try {
      item = JSON.parse(String(ev.data)) as T;
    } catch {
      return;
    }
    const seq = typeof item.seq === 'number' ? item.seq : Number(ev.lastEventId);
    if (Number.isFinite(seq)) {
      if (seq <= lastSeq) return;
      lastSeq = seq;
    }
    onItem(item);
  };

  const connect = () => {
    if (disposed) return;
    setStatus(attempts === 0 ? 'connecting' : 'reconnecting');
    const source = new ES(url);
    es = source;
    source.addEventListener('open', () => {
      attempts = 0;
      setStatus('open');
    });
    source.addEventListener(eventName, handleItem as EventListener);
    source.addEventListener('end', (ev: Event) => {
      // `{"reason": "run_end" | "stale" | "missing", "lastSeq": n}` (GET /ui/jobs/{id}/log)
      let end: StreamEnd = {};
      try {
        const data = (ev as MessageEvent).data;
        const p = typeof data === 'string' && data ? (JSON.parse(data) as StreamEnd) : {};
        end = { reason: typeof p.reason === 'string' ? p.reason : undefined, lastSeq: typeof p.lastSeq === 'number' ? p.lastSeq : undefined };
      } catch {
        /* no reason given */
      }
      close();
      setStatus('ended');
      cb.onEnd?.(end);
    });
    source.addEventListener('error', (ev: Event) => {
      if (disposed || es !== source) return;
      const data = (ev as MessageEvent).data;
      if (typeof data === 'string' && data) {
        // a server-sent `event: error` frame: {"error": {code, message}}
        let code = 'stream_error';
        let message = data;
        try {
          const p = JSON.parse(data) as { error?: { code?: string; message?: string } };
          code = p.error?.code ?? code;
          message = p.error?.message ?? message;
        } catch {
          /* plain text */
        }
        close();
        setStatus('failed');
        cb.onError?.(new ApiError({ status: 0, code, message, url, payload: data }));
        return;
      }
      if (source.readyState === 2 /* CLOSED */) {
        close();
        if (attempts >= maxRetries) {
          setStatus('failed');
          cb.onError?.(new ApiError({ status: 0, code: 'stream_failed', message: `The stream closed and ${maxRetries} reconnection attempts failed`, url }));
          return;
        }
        const delay = Math.min(maxDelay, baseDelay * 2 ** attempts);
        attempts += 1;
        setStatus('reconnecting');
        timer = setTimeout(connect, delay);
      } else {
        // CONNECTING: the browser retries by itself and sends Last-Event-ID
        attempts += 1;
        if (attempts > maxRetries) {
          close();
          setStatus('failed');
          cb.onError?.(new ApiError({ status: 0, code: 'stream_failed', message: `The stream dropped and ${maxRetries} reconnection attempts failed`, url }));
          return;
        }
        setStatus('reconnecting');
      }
    });
  };

  connect();
  return () => {
    disposed = true;
    close();
  };
}
