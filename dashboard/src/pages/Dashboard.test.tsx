/**
 * Regression test for HIGH-029 — Dashboard polling must be gated on
 * !isConnected so the 60s REST poll does not race the WebSocket stream
 * and overwrite fresh push data with an older REST snapshot.
 *
 * Rendering the full Dashboard under jsdom is fragile (recharts + MUI +
 * theme + every metric field). We assert the contract at the source
 * level instead — matches the pattern used for migration 005 and the
 * extension options validator. Vite's `?raw` query loads the source
 * without needing @types/node.
 */
import SOURCE from './Dashboard.tsx?raw';
import { describe, expect, it } from 'vitest';

const source = SOURCE as string;

describe('Dashboard polling × WebSocket (HIGH-029)', () => {
  it('reads isConnected from useDashboardWebSocket', () => {
    expect(source).toMatch(/isConnected\s*}\s*=\s*useDashboardWebSocket|isConnected\s*}\s*=\s*useWebSocket/);
  });

  it('guards the polling effect dep array on isConnected', () => {
    // Find a useEffect that registers setInterval(fetchMetrics, ...).
    const match = source.match(
      /useEffect\(\(\)\s*=>\s*\{[\s\S]*?setInterval\(\s*fetchMetrics[\s\S]*?\},\s*\[([^\]]*)\]\)/,
    );
    expect(match, 'polling useEffect not found').not.toBeNull();
    expect(match![1]).toContain('isConnected');
  });

  it('short-circuits when the WebSocket is connected', () => {
    // Body of the polling effect must early-return when connected, so
    // setInterval is never scheduled.
    const match = source.match(
      /useEffect\(\(\)\s*=>\s*\{([\s\S]*?setInterval\(\s*fetchMetrics[\s\S]*?)\},\s*\[[^\]]*isConnected/,
    );
    expect(match, 'gated polling effect not found').not.toBeNull();
    const body = match![1];
    expect(body).toMatch(/if\s*\(\s*isConnected\s*\)\s*return/);
  });

  it('still performs an initial fetch on mount', () => {
    // Initial fetchMetrics() must run unconditionally so the dashboard
    // is not blank while the WS handshake is in flight.
    expect(source).toContain('fetchMetrics();');
  });
});
