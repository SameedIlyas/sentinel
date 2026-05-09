/**
 * Smoke tests for the walkthrough state machine.
 *
 * These don't render the full overlay (DOM measurement gets messy in jsdom).
 * They cover the behaviours the user actually depends on:
 *   - Auto-start fires once when the user is authenticated and has not
 *     completed before.
 *   - skip / finish persist a "completed" flag so the next render is silent.
 *   - restart clears the persisted flag and re-starts the tour.
 */
import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';

import { WalkthroughProvider, useWalkthrough } from '../WalkthroughContext';
import { TOUR_VERSION } from '../steps';

const STORAGE_KEY = `sentinel.walkthrough.${TOUR_VERSION}.completed`;

// Mock the auth context so we can flip auth state without a real session.
let mockAuth = { isAuthenticated: false, isLoading: false };
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => mockAuth,
}));

function wrapper({ children }: { children: ReactNode }) {
  return (
    <MemoryRouter initialEntries={['/']}>
      <WalkthroughProvider>{children}</WalkthroughProvider>
    </MemoryRouter>
  );
}

describe('useWalkthrough', () => {
  beforeEach(() => {
    window.localStorage.clear();
    mockAuth = { isAuthenticated: false, isLoading: false };
  });

  it('does not auto-start when the user is not authenticated', async () => {
    const { result } = renderHook(() => useWalkthrough(), { wrapper });
    // Wait the auto-start delay window
    await new Promise((r) => setTimeout(r, 700));
    expect(result.current.isActive).toBe(false);
  });

  it('auto-starts the tour for an authenticated user with no completion flag', async () => {
    mockAuth = { isAuthenticated: true, isLoading: false };
    const { result } = renderHook(() => useWalkthrough(), { wrapper });
    await waitFor(() => expect(result.current.isActive).toBe(true), { timeout: 1500 });
    expect(result.current.currentIndex).toBe(0);
  });

  it('does not auto-start when the user has already completed', async () => {
    window.localStorage.setItem(STORAGE_KEY, 'true');
    mockAuth = { isAuthenticated: true, isLoading: false };
    const { result } = renderHook(() => useWalkthrough(), { wrapper });
    await new Promise((r) => setTimeout(r, 700));
    expect(result.current.isActive).toBe(false);
    expect(result.current.hasCompleted).toBe(true);
  });

  it('next advances the index, back retreats, with index clamped at 0', async () => {
    mockAuth = { isAuthenticated: true, isLoading: false };
    const { result } = renderHook(() => useWalkthrough(), { wrapper });
    await waitFor(() => expect(result.current.isActive).toBe(true));

    act(() => result.current.next());
    expect(result.current.currentIndex).toBe(1);
    act(() => result.current.next());
    expect(result.current.currentIndex).toBe(2);
    act(() => result.current.back());
    expect(result.current.currentIndex).toBe(1);
    act(() => result.current.back());
    act(() => result.current.back()); // clamped
    expect(result.current.currentIndex).toBe(0);
  });

  it('skip ends the tour and persists completion', async () => {
    mockAuth = { isAuthenticated: true, isLoading: false };
    const { result } = renderHook(() => useWalkthrough(), { wrapper });
    await waitFor(() => expect(result.current.isActive).toBe(true));

    act(() => result.current.skip());
    expect(result.current.isActive).toBe(false);
    expect(result.current.hasCompleted).toBe(true);
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('true');
  });

  it('restart clears persisted completion and re-shows step 0', async () => {
    window.localStorage.setItem(STORAGE_KEY, 'true');
    mockAuth = { isAuthenticated: true, isLoading: false };
    const { result } = renderHook(() => useWalkthrough(), { wrapper });
    await new Promise((r) => setTimeout(r, 100));

    act(() => result.current.restart());
    expect(result.current.isActive).toBe(true);
    expect(result.current.currentIndex).toBe(0);
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it('next on the last step finishes the tour and persists completion', async () => {
    mockAuth = { isAuthenticated: true, isLoading: false };
    const { result } = renderHook(() => useWalkthrough(), { wrapper });
    await waitFor(() => expect(result.current.isActive).toBe(true));
    const lastIndex = result.current.steps.length - 1;

    // Jump to last step
    for (let i = 0; i < lastIndex; i++) {
      act(() => result.current.next());
    }
    expect(result.current.currentIndex).toBe(lastIndex);

    act(() => result.current.next());
    expect(result.current.isActive).toBe(false);
    expect(result.current.hasCompleted).toBe(true);
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('true');
  });
});
