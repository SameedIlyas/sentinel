/**
 * Tests for ApiClient.getCurrentUser — covers two regressions:
 *
 * HIGH-025: ApiClient.getUser() must not throw on corrupt localStorage
 * payloads (quota-truncated writes, manual edits, extension tampering).
 *
 * CRIT-011: cached values must go through a strict Zod schema. An
 * attacker who writes a forged ``{role: 'system_admin'}`` object to
 * localStorage cannot pass any client-side role check — getUser() now
 * returns null on schema failure and clears the corrupt entry.
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { apiClient } from './client';

const VALID_USER = {
  id: 'u1',
  username: 'jane',
  email: 'jane@example.com',
  role: 'viewer',
  is_active: true,
  organization_id: 'org-1',
  tier: 'enterprise',
  created_at: '2026-01-01T00:00:00Z',
};

describe('ApiClient.getCurrentUser', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  // ── HIGH-025 ────────────────────────────────────────────────────────

  it('returns null when no user key is present', () => {
    expect(apiClient.getCurrentUser()).toBeNull();
  });

  it('returns the parsed user when localStorage is valid', () => {
    localStorage.setItem('user', JSON.stringify(VALID_USER));
    expect(apiClient.getCurrentUser()).toMatchObject(VALID_USER);
  });

  it('does NOT throw when the stored user JSON is corrupt', () => {
    localStorage.setItem('user', '{not-valid-json');
    expect(() => apiClient.getCurrentUser()).not.toThrow();
    expect(apiClient.getCurrentUser()).toBeNull();
  });

  it('clears the corrupt entry so subsequent calls also return null', () => {
    localStorage.setItem('user', '{"role":');
    apiClient.getCurrentUser();
    expect(localStorage.getItem('user')).toBeNull();
  });

  // ── CRIT-011 — Zod schema validation ────────────────────────────────

  it('rejects a forged role value not in the enum', () => {
    localStorage.setItem(
      'user',
      JSON.stringify({ ...VALID_USER, role: 'super_root' })
    );
    expect(apiClient.getCurrentUser()).toBeNull();
    expect(localStorage.getItem('user')).toBeNull();
  });

  it('rejects a forged minimal {role: system_admin} payload', () => {
    // Classic client-side privilege-escalation attempt.
    localStorage.setItem('user', JSON.stringify({ role: 'system_admin' }));
    expect(apiClient.getCurrentUser()).toBeNull();
    expect(localStorage.getItem('user')).toBeNull();
  });

  it('rejects a payload missing the required username field', () => {
    const { username: _omit, ...incomplete } = VALID_USER;
    void _omit;
    localStorage.setItem('user', JSON.stringify(incomplete));
    expect(apiClient.getCurrentUser()).toBeNull();
  });

  it('rejects a payload where role is the wrong type', () => {
    localStorage.setItem(
      'user',
      JSON.stringify({ ...VALID_USER, role: 42 })
    );
    expect(apiClient.getCurrentUser()).toBeNull();
  });

  it('rejects an invalid tier value', () => {
    localStorage.setItem(
      'user',
      JSON.stringify({ ...VALID_USER, tier: 'platinum' })
    );
    expect(apiClient.getCurrentUser()).toBeNull();
  });

  it('accepts each canonical role', () => {
    for (const role of [
      'system_admin',
      'admin',
      'cmio',
      'data_scientist',
      'compliance_officer',
      'clinical_user',
      'analyst',
      'viewer',
    ]) {
      localStorage.setItem('user', JSON.stringify({ ...VALID_USER, role }));
      expect(apiClient.getCurrentUser()?.role).toBe(role);
    }
  });
});
