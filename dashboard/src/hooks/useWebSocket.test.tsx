/**
 * useWebSocket tests
 *
 * Covers two regressions on the same hook:
 *
 * 1. HIGH-027 — useWebSocket must not reconnect on every parent re-render.
 *    connect() listed onMessage/onError/onOpen/onClose in its useCallback
 *    deps. Parent components frequently pass plain (non-memoised) handlers,
 *    each render produced a new handler identity, which changed connect's
 *    identity, triggered the binding useEffect, and opened a fresh socket
 *    before the previous one finished closing — duplicate connections,
 *    duplicate message delivery, and eventually the 5-attempt cap.
 *    Fix: callbacks stored in refs; connect identity depends only on
 *    [path, reconnectInterval, reconnectAttempts].
 *
 * 2. CRIT-013 — JWT must not appear in the WebSocket URL. The hook now
 *    POSTs to /v1/ws/ticket with the Authorization header, gets an opaque
 *    single-use ticket, and opens the socket with ?ticket=<id>. The JWT
 *    only ever rides in HTTP headers.
 */
import { act, render, waitFor } from '@testing-library/react';
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
  }

  send(_payload: string): void {
    /* not exercised */
  }
}

const TICKETS = (() => {
  let n = 0;
  return () => `ticket-${++n}`;
})();

function installFetchMock(): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn(async (_input: any, _init?: any) => ({
    ok: true,
    json: async () => ({ ticket: TICKETS(), expires_in: 30 }),
  }));
  // @ts-expect-error monkey-patch global fetch
  global.fetch = fetchMock;
  return fetchMock;
}

describe('useWebSocket', () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    // @ts-expect-error monkey-patch global WebSocket for the test
    global.WebSocket = FakeWebSocket;
    // Provide an access_token so fetchWsTicket attempts the POST.
    window.localStorage.setItem('access_token', 'jwt-here');
    installFetchMock();
  });

  afterEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it('opens exactly one socket across many parent re-renders (HIGH-027)', async () => {
    function Parent() {
      const [tick, setTick] = useState(0);
      // Pass a brand-new function identity on every render.
      const onMessage = (_m: unknown) => {
        void _m;
      };
      useWebSocket('/ws/dashboard', { onMessage });
      return (
        <button data-testid="bump" onClick={() => setTick(tick + 1)}>
          {tick}
        </button>
      );
    }

    const { getByTestId } = render(<Parent />);
    // The first ticket fetch is async — wait for the socket to be opened.
    await waitFor(() => expect(FakeWebSocket.instances.length).toBe(1));

    for (let i = 0; i < 10; i++) {
      act(() => {
        getByTestId('bump').click();
      });
    }

    expect(FakeWebSocket.instances.length).toBe(1);
  });

  it('routes incoming messages to the latest onMessage callback', async () => {
    function Parent({ sink }: { sink: (s: string) => void }) {
      const onMessage = (m: { type: string }) => sink(m.type);
      useWebSocket('/ws/route', { onMessage });
      return null;
    }

    const calls: string[] = [];
    const sink = (s: string) => calls.push(s);
    render(<Parent sink={sink} />);

    await waitFor(() => expect(FakeWebSocket.instances.length).toBe(1));
    const ws = FakeWebSocket.instances[0];
    act(() => {
      ws.onmessage?.(
        new MessageEvent('message', { data: JSON.stringify({ type: 'ping' }) })
      );
    });

    expect(calls).toEqual(['ping']);
  });

  it('fetches a fresh ticket and omits the JWT from the URL (CRIT-013)', async () => {
    const fetchMock = installFetchMock();

    function Parent() {
      useWebSocket('/ws/dashboard');
      return null;
    }
    render(<Parent />);

    // Wait for the ticket POST to land and the socket to be opened.
    await waitFor(() => expect(FakeWebSocket.instances.length).toBe(1));

    // /v1/ws/ticket was called with the bearer token in the header.
    expect(fetchMock).toHaveBeenCalled();
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/v1\/ws\/ticket$/);
    expect(init?.method).toBe('POST');
    expect(init?.headers?.Authorization).toBe('Bearer jwt-here');

    // The opened WebSocket URL contains a ticket and NOT the JWT.
    const wsUrl = FakeWebSocket.instances[0].url;
    expect(wsUrl).toMatch(/[?&]ticket=ticket-\d+/);
    expect(wsUrl).not.toContain('jwt-here');
    expect(wsUrl).not.toMatch(/[?&]token=/);
  });

  it('skips reconnect on a 4401 close (auth unrecoverable)', async () => {
    function Parent() {
      useWebSocket('/ws/dashboard', { reconnectInterval: 1, reconnectAttempts: 5 });
      return null;
    }
    render(<Parent />);

    await waitFor(() => expect(FakeWebSocket.instances.length).toBe(1));
    const ws = FakeWebSocket.instances[0];

    // Server signals an unrecoverable auth problem.
    act(() => {
      ws.onclose?.(
        new CloseEvent('close', { code: 4401, reason: 'bad ticket', wasClean: false })
      );
    });

    // Wait a tick and assert no new socket appeared.
    await new Promise((r) => setTimeout(r, 30));
    expect(FakeWebSocket.instances.length).toBe(1);
  });
});
