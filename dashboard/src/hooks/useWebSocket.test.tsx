/**
 * Regression test for HIGH-027 — useWebSocket must not reconnect on every
 * parent re-render.
 *
 * connect() lists onMessage/onError/onOpen/onClose in its useCallback deps.
 * Parent components frequently pass plain (non-memoised) handlers
 * (Dashboard.tsx:66-72 historically did). Each parent render therefore
 * produced a new handler identity, which changed connect's identity,
 * triggered the binding useEffect, and opened a fresh socket before the
 * previous one finished closing — duplicate connections, duplicate
 * message delivery, and (eventually) the 5-attempt reconnect cap.
 *
 * The fix stores callbacks in refs and removes them from connect's deps so
 * connect identity depends only on [url, reconnectInterval, reconnectAttempts].
 */
import { act, render } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useWebSocket } from './useWebSocket';

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  static OPEN = 1;
  static CONNECTING = 0;
  static CLOSING = 2;
  static CLOSED = 3;

  readyState: number = FakeWebSocket.CONNECTING;
  onopen: ((e: Event) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  onclose: ((e: CloseEvent) => void) | null = null;
  url: string;
  closed = false;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  close(): void {
    this.closed = true;
    this.readyState = FakeWebSocket.CLOSED;
    // Don't fire onclose synchronously — the historical bug was the new
    // socket racing the old one, so we keep timing intentional.
  }

  send(_payload: string): void {
    /* not exercised */
  }
}

describe('useWebSocket reconnect race (HIGH-027)', () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    // @ts-expect-error monkey-patch global WebSocket for the test
    global.WebSocket = FakeWebSocket;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('opens exactly one socket across many parent re-renders', () => {
    function Parent() {
      const [tick, setTick] = useState(0);
      // Pass a brand-new function identity on every render — exactly the
      // anti-pattern Dashboard.tsx exhibits without useCallback.
      const onMessage = (_m: unknown) => {
        void _m;
      };
      useWebSocket('ws://test/dashboard', { onMessage });
      return (
        <button data-testid="bump" onClick={() => setTick(tick + 1)}>
          {tick}
        </button>
      );
    }

    const { getByTestId } = render(<Parent />);

    // Trigger ten re-renders with a fresh onMessage identity each time.
    for (let i = 0; i < 10; i++) {
      act(() => {
        getByTestId('bump').click();
      });
    }

    // Before the fix this was 11 (one per render). After the fix exactly 1.
    expect(FakeWebSocket.instances.length).toBe(1);
  });

  it('still routes incoming messages to the latest onMessage callback', () => {
    function Parent({ sink }: { sink: (s: string) => void }) {
      const onMessage = (m: { type: string }) => sink(m.type);
      useWebSocket('ws://test/route', { onMessage });
      return null;
    }

    const calls: string[] = [];
    const sink = (s: string) => calls.push(s);
    render(<Parent sink={sink} />);

    const ws = FakeWebSocket.instances[0];
    expect(ws).toBeDefined();
    act(() => {
      ws.onmessage?.(new MessageEvent('message', { data: JSON.stringify({ type: 'ping' }) }));
    });

    expect(calls).toEqual(['ping']);
  });
});
