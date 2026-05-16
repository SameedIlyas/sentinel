/**
 * Regression test for HIGH-025 — ApiClient.getUser() must not throw on corrupt
 * localStorage payloads.
 *
 * Before the fix, `JSON.parse(userStr)` in `getUser()` propagated a SyntaxError
 * up through `AuthContext.initAuth` whenever the `user` key in localStorage
 * was malformed (truncated write due to quota, manual edit, browser-extension
 * interference). The user saw a silent logout with no error state and the
 * corrupt entry remained in localStorage, so every subsequent load also blew
 * up. The fix wraps the parse in try/catch, clears the corrupt entry, and
 * returns `null` so the caller routes to the login flow cleanly.
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { apiClient } from './client';

describe('ApiClient.getCurrentUser (HIGH-025)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('returns null when no user key is present', () => {
    expect(apiClient.getCurrentUser()).toBeNull();
  });

  it('returns the parsed user when localStorage is valid', () => {
    const user = { id: 'u1', email: 'u@x.com', role: 'viewer', tier: 'enterprise' };
    localStorage.setItem('user', JSON.stringify(user));
    expect(apiClient.getCurrentUser()).toMatchObject(user);
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
});
