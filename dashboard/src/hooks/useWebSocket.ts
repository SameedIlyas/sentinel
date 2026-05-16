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
 * Custom hook for WebSocket connection
 * Automatically handles reconnection and connection management
 */
export const useWebSocket = (url: string, options: UseWebSocketOptions = {}) => {
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

  const connect = useCallback(() => {
    try {
      // Close existing connection if any
      if (wsRef.current) {
        wsRef.current.close();
      }

      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = (event) => {
        console.log('WebSocket connected:', url);
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

        // Attempt to reconnect
        if (reconnectCountRef.current < reconnectAttempts) {
          reconnectCountRef.current += 1;
          console.log(
            `Reconnecting... (${reconnectCountRef.current}/${reconnectAttempts})`
          );
          reconnectTimeoutRef.current = window.setTimeout(() => {
            connect();
          }, reconnectInterval) as unknown as number;
        } else {
          console.error('Max reconnection attempts reached');
        }
      };
    } catch (error) {
      console.error('Error creating WebSocket connection:', error);
    }
  }, [url, reconnectInterval, reconnectAttempts]);

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
    connect();

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
 * Build a WebSocket URL relative to the configured API base, appending the
 * JWT from localStorage as a query string parameter so the backend
 * `_authenticate_ws_token` check can validate the connection. Falls back
 * to localhost:8000 when VITE_API_BASE_URL is unset (dev default).
 */
function buildWsUrl(path: string): string {
  const apiBase = (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000';
  const wsBase = apiBase.replace(/^http/i, 'ws').replace(/\/$/, '');
  const token = localStorage.getItem('access_token') || '';
  const qs = token ? `?token=${encodeURIComponent(token)}` : '';
  return `${wsBase}${path}${qs}`;
}

/**
 * Hook specifically for dashboard metrics WebSocket
 */
export const useDashboardWebSocket = (
  onMetricsUpdate: (metrics: any) => void,
  enabled = true
) => {
  const wsUrl = buildWsUrl('/ws/dashboard');

  const handleMessage = useCallback(
    (message: WebSocketMessage) => {
      if (message.type === 'metrics_update' && message.data) {
        onMetricsUpdate(message.data);
      } else if (message.type === 'refresh_request') {
        // Server is requesting a refresh
        console.log('Server requested metrics refresh');
      }
    },
    [onMetricsUpdate]
  );

  const { isConnected, lastMessage } = useWebSocket(wsUrl, {
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
  const wsUrl = buildWsUrl('/ws/events');

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

  const { isConnected, lastMessage } = useWebSocket(wsUrl, {
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
