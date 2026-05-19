import { useEffect, useRef, useState, useCallback } from 'react';

export interface WebSocketMessage {
  type: string;
  timestamp: string;
  data?: any;
  event_type?: string;
}

export interface UseWebSocketOptions {
  onMessage?: (message: WebSocketMessage) => void;
  onError?: (error: Event) => void;
  onOpen?: (event: Event) => void;
  onClose?: (event: CloseEvent) => void;
  reconnectInterval?: number;
  reconnectAttempts?: number;
}

/**
 * Build a fresh single-use WebSocket ticket by calling /v1/ws/ticket.
 *
 * CRIT-013 — the JWT must never appear in the WebSocket URL.
 * CRIT-011 — the JWT lives in an HttpOnly cookie now, so this request
 * uses ``credentials: 'include'`` to send the cookie automatically;
 * there is no localStorage access token to read. The ticket itself is
 * short-lived (~30s) and consumed on first use by the server.
 *
 * The mutating POST also needs the CSRF double-submit header. The
 * cookie is JS-readable; we lift it into ``X-CSRF-Token`` here.
 */
function readCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const target = name + '=';
  for (const part of document.cookie.split(';')) {
    const trimmed = part.trim();
    if (trimmed.startsWith(target)) {
      return decodeURIComponent(trimmed.slice(target.length));
    }
  }
  return null;
}

async function fetchWsTicket(): Promise<string | null> {
  const apiBase =
    (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000';
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  const csrf = readCookie('csrf_token');
  if (csrf) headers['X-CSRF-Token'] = csrf;
  try {
    const r = await fetch(`${apiBase.replace(/\/$/, '')}/v1/ws/ticket`, {
      method: 'POST',
      credentials: 'include',
      headers,
    });
    if (!r.ok) return null;
    const body = (await r.json()) as { ticket?: string };
    return body.ticket ?? null;
  } catch (_e) {
    return null;
  }
}

function wsBaseUrl(): string {
  const apiBase =
    (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000';
  return apiBase.replace(/^http/i, 'ws').replace(/\/$/, '');
}

/**
 * Custom hook for WebSocket connection.
 *
 * Each (re)connection fetches a fresh single-use ticket from the server
 * and opens the socket with ``?ticket=<id>``. The JWT in localStorage is
 * still the underlying credential but it's only ever sent in an
 * Authorization HEADER, never the URL (CRIT-013).
 */
export const useWebSocket = (
  path: string,
  options: UseWebSocketOptions = {}
) => {
  const {
    onMessage,
    onError,
    onOpen,
    onClose,
    reconnectInterval = 3000,
    reconnectAttempts = 5,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const reconnectTimeoutRef = useRef<number | null>(null);

  // HIGH-027 — store callbacks in refs and read from them inside the static
  // handler closures so connect()'s identity does NOT depend on caller
  // callback identity. Parent re-renders that hand us a new onMessage no
  // longer tear down and re-open the socket.
  const onMessageRef = useRef(onMessage);
  const onErrorRef = useRef(onError);
  const onOpenRef = useRef(onOpen);
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onMessageRef.current = onMessage;
    onErrorRef.current = onError;
    onOpenRef.current = onOpen;
    onCloseRef.current = onClose;
  }, [onMessage, onError, onOpen, onClose]);

  const connect = useCallback(async () => {
    try {
      if (wsRef.current) {
        wsRef.current.close();
      }

      const ticket = await fetchWsTicket();
      if (!ticket) {
        // No authenticated session — refuse to open the socket so the
        // server never sees a malformed handshake.
        setIsConnected(false);
        return;
      }

      const url = `${wsBaseUrl()}${path}?ticket=${encodeURIComponent(ticket)}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = (event) => {
        console.log('WebSocket connected:', path);
        setIsConnected(true);
        reconnectCountRef.current = 0;
        if (onOpenRef.current) onOpenRef.current(event);
      };

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          setLastMessage(message);
          if (onMessageRef.current) onMessageRef.current(message);
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      ws.onerror = (event) => {
        console.error('WebSocket error:', event);
        if (onErrorRef.current) onErrorRef.current(event);
      };

      ws.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason);
        setIsConnected(false);
        wsRef.current = null;
        if (onCloseRef.current) onCloseRef.current(event);

        // Server signals an unrecoverable auth problem with 4401 — don't
        // burn reconnects trying again until the user re-authenticates.
        if (event.code === 4401) {
          return;
        }

        if (reconnectCountRef.current < reconnectAttempts) {
          reconnectCountRef.current += 1;
          console.log(
            `Reconnecting... (${reconnectCountRef.current}/${reconnectAttempts})`
          );
          reconnectTimeoutRef.current = window.setTimeout(() => {
            void connect();
          }, reconnectInterval) as unknown as number;
        } else {
          console.error('Max reconnection attempts reached');
        }
      };
    } catch (error) {
      console.error('Error creating WebSocket connection:', error);
    }
  }, [path, reconnectInterval, reconnectAttempts]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const sendMessage = useCallback((message: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    } else {
      console.error('WebSocket is not connected');
    }
  }, []);

  useEffect(() => {
    void connect();

    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    isConnected,
    lastMessage,
    sendMessage,
    disconnect,
    reconnect: connect,
  };
};

/**
 * Hook specifically for dashboard metrics WebSocket
 */
export const useDashboardWebSocket = (
  onMetricsUpdate: (metrics: any) => void,
  enabled = true
) => {
  const handleMessage = useCallback(
    (message: WebSocketMessage) => {
      if (message.type === 'metrics_update' && message.data) {
        onMetricsUpdate(message.data);
      } else if (message.type === 'refresh_request') {
        console.log('Server requested metrics refresh');
      }
    },
    [onMetricsUpdate]
  );

  const { isConnected, lastMessage } = useWebSocket('/ws/dashboard', {
    onMessage: enabled ? handleMessage : undefined,
    onError: (error) => {
      console.error('Dashboard WebSocket error:', error);
    },
    onOpen: () => {
      console.log('Connected to dashboard updates');
    },
    onClose: (_event) => {
      console.log('Disconnected from dashboard updates');
    },
  });

  return {
    isConnected,
    lastMessage,
  };
};

/**
 * Hook for events WebSocket (alerts, notifications, etc.)
 */
export const useEventsWebSocket = (
  onEvent: (eventType: string, data: any) => void,
  enabled = true
) => {
  const handleMessage = useCallback(
    (message: WebSocketMessage) => {
      if (message.type === 'event' && message.event_type && message.data) {
        onEvent(message.event_type, message.data);
      } else if (message.type === 'heartbeat') {
        // Just a heartbeat, ignore
      }
    },
    [onEvent]
  );

  const { isConnected, lastMessage } = useWebSocket('/ws/events', {
    onMessage: enabled ? handleMessage : undefined,
    onError: (error) => {
      console.error('Events WebSocket error:', error);
    },
  });

  return {
    isConnected,
    lastMessage,
  };
};
