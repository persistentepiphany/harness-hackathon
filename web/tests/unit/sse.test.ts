import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { openSseStream, type StreamStatus } from '@/lib/sse';

type Listener = (ev: MessageEvent | Event) => void;

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  readyState = 0;
  url: string;
  listeners: Record<string, Listener[]> = {};
  closed = false;
  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }
  addEventListener(type: string, fn: Listener) {
    (this.listeners[type] ||= []).push(fn);
  }
  close() {
    this.closed = true;
    this.readyState = 2;
  }
  emit(type: string, data?: unknown, id?: string) {
    const ev = data === undefined ? new Event(type) : new MessageEvent(type, { data: typeof data === 'string' ? data : JSON.stringify(data), lastEventId: id });
    (this.listeners[type] || []).forEach((fn) => fn(ev));
  }
  open() {
    this.readyState = 1;
    this.emit('open');
  }
  fail(state: 0 | 2) {
    this.readyState = state;
    this.emit('error');
  }
}

const ES = FakeEventSource as unknown as typeof EventSource;

describe('openSseStream', () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('delivers items once by seq and ends on `end`', () => {
    const items: number[] = [];
    const statuses: StreamStatus[] = [];
    const onEnd = vi.fn();
    openSseStream<{ seq: number }>('/api/harness/ui/jobs/a/log', 'line', (x) => items.push(x.seq), { onEnd, onStatus: (s) => statuses.push(s) }, { EventSourceImpl: ES });
    const es = FakeEventSource.instances[0];
    es.open();
    es.emit('line', { seq: 1 }, '1');
    es.emit('line', { seq: 2 }, '2');
    es.emit('line', { seq: 2 }, '2');
    es.emit('end', '{}');
    expect(items).toEqual([1, 2]);
    expect(onEnd).toHaveBeenCalledOnce();
    expect(es.closed).toBe(true);
    expect(statuses).toEqual(['connecting', 'open', 'ended']);
  });

  it('passes the server end reason to onEnd', () => {
    const onEnd = vi.fn();
    openSseStream<{ seq: number }>('/s', 'line', () => undefined, { onEnd }, { EventSourceImpl: ES });
    const es = FakeEventSource.instances[0];
    es.open();
    es.emit('end', { reason: 'stale', lastSeq: 4 });
    expect(onEnd).toHaveBeenCalledWith({ reason: 'stale', lastSeq: 4 });
  });

  it('reopens after the browser closed the stream and drops replayed items', () => {
    const items: number[] = [];
    openSseStream<{ seq: number }>('/s', 'line', (x) => items.push(x.seq), {}, { EventSourceImpl: ES, baseDelayMs: 100 });
    const first = FakeEventSource.instances[0];
    first.open();
    first.emit('line', { seq: 1 });
    first.emit('line', { seq: 2 });
    first.fail(2);
    expect(FakeEventSource.instances).toHaveLength(1);
    vi.advanceTimersByTime(100);
    const second = FakeEventSource.instances[1];
    second.open();
    second.emit('line', { seq: 1 });
    second.emit('line', { seq: 2 });
    second.emit('line', { seq: 3 });
    expect(items).toEqual([1, 2, 3]);
  });

  it('fails with an ApiError after the retry budget', () => {
    const onError = vi.fn();
    openSseStream('/s', 'line', () => undefined, { onError }, { EventSourceImpl: ES, maxRetries: 1, baseDelayMs: 10 });
    FakeEventSource.instances[0].fail(2);
    vi.advanceTimersByTime(10);
    FakeEventSource.instances[1].fail(2);
    expect(onError).toHaveBeenCalledOnce();
    expect(onError.mock.calls[0][0]).toMatchObject({ code: 'stream_failed', status: 0 });
  });

  it('surfaces a server-sent error frame', () => {
    const onError = vi.fn();
    openSseStream('/s', 'line', () => undefined, { onError }, { EventSourceImpl: ES });
    const es = FakeEventSource.instances[0];
    es.emit('error', { error: { code: 'not_found', message: 'no such job' } });
    expect(onError.mock.calls[0][0]).toMatchObject({ code: 'not_found', message: 'no such job' });
    expect(es.closed).toBe(true);
  });

  it('unsubscribe closes the source and stops reconnecting', () => {
    const stop = openSseStream('/s', 'line', () => undefined, {}, { EventSourceImpl: ES, baseDelayMs: 10 });
    const es = FakeEventSource.instances[0];
    es.fail(2);
    stop();
    vi.advanceTimersByTime(1000);
    expect(FakeEventSource.instances).toHaveLength(1);
  });
});
