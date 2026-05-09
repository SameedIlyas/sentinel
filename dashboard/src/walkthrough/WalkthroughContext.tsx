/**
 * Walkthrough provider — owns the tour state and persists "completed" to
 * localStorage so the auto-trigger only fires once per user-agent.
 *
 * Auto-start logic:
 *   - On first authenticated render where `localStorage[STORAGE_KEY]` is unset
 *     and the user is not on /login, show the tour.
 *   - The user can dismiss with Skip (which marks completed) or Finish.
 *   - "Restart tour" in the user menu calls `restart()` which resets the
 *     in-memory state and re-shows step 0 without touching localStorage.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '@/contexts/AuthContext';
import { STEPS, TOUR_VERSION } from './steps';
import type { WalkthroughContextValue, WalkthroughStep } from './types';

const STORAGE_KEY = `sentinel.walkthrough.${TOUR_VERSION}.completed`;

const WalkthroughContext = createContext<WalkthroughContextValue | undefined>(undefined);

export function useWalkthrough(): WalkthroughContextValue {
  const ctx = useContext(WalkthroughContext);
  if (!ctx) {
    throw new Error('useWalkthrough must be used inside a WalkthroughProvider');
  }
  return ctx;
}

function readCompletedFlag(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === 'true';
  } catch {
    return false;
  }
}

function writeCompletedFlag(value: boolean): void {
  try {
    if (value) {
      window.localStorage.setItem(STORAGE_KEY, 'true');
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // localStorage unavailable (private browsing / SSR) — fine, the
    // walkthrough degrades to "auto-runs every session"
  }
}

interface WalkthroughProviderProps {
  children: ReactNode;
  steps?: WalkthroughStep[];
}

export function WalkthroughProvider({
  children,
  steps = STEPS,
}: WalkthroughProviderProps) {
  const { isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [hasCompleted, setHasCompleted] = useState<boolean>(() => readCompletedFlag());
  const [currentIndex, setCurrentIndex] = useState<number>(-1);
  const autoStartedRef = useRef<boolean>(false);

  // Auto-start once per user-agent on the first authenticated mount.
  useEffect(() => {
    if (isLoading || !isAuthenticated) return;
    if (autoStartedRef.current) return;
    if (hasCompleted) return;
    if (location.pathname === '/login') return;

    autoStartedRef.current = true;
    // Slight delay so the layout finishes mounting + nav items render
    const timer = window.setTimeout(() => {
      setCurrentIndex(0);
    }, 600);
    return () => window.clearTimeout(timer);
  }, [isAuthenticated, isLoading, hasCompleted, location.pathname]);

  // When the active step has a `path`, navigate there before showing the step.
  useEffect(() => {
    if (currentIndex < 0) return;
    const step = steps[currentIndex];
    if (step?.path && location.pathname !== step.path) {
      navigate(step.path);
    }
  }, [currentIndex, steps, navigate, location.pathname]);

  const start = useCallback(() => {
    setCurrentIndex(0);
  }, []);

  const next = useCallback(() => {
    setCurrentIndex((idx) => {
      if (idx < 0) return idx;
      if (idx >= steps.length - 1) {
        setHasCompleted(true);
        writeCompletedFlag(true);
        return -1;
      }
      return idx + 1;
    });
  }, [steps.length]);

  const back = useCallback(() => {
    setCurrentIndex((idx) => Math.max(0, idx - 1));
  }, []);

  const skip = useCallback(() => {
    setHasCompleted(true);
    writeCompletedFlag(true);
    setCurrentIndex(-1);
  }, []);

  const finish = useCallback(() => {
    setHasCompleted(true);
    writeCompletedFlag(true);
    setCurrentIndex(-1);
  }, []);

  const restart = useCallback(() => {
    // Clear the persisted flag so a future fresh mount will also auto-run.
    writeCompletedFlag(false);
    setHasCompleted(false);
    setCurrentIndex(0);
  }, []);

  const value = useMemo<WalkthroughContextValue>(
    () => ({
      isActive: currentIndex >= 0,
      hasCompleted,
      currentIndex,
      steps,
      start,
      next,
      back,
      skip,
      finish,
      restart,
    }),
    [currentIndex, hasCompleted, steps, start, next, back, skip, finish, restart],
  );

  return (
    <WalkthroughContext.Provider value={value}>
      {children}
    </WalkthroughContext.Provider>
  );
}
