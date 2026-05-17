import React, { createContext, ReactNode, useContext, useMemo } from 'react';
import type { TierKey } from '@/types';
import { resolveDict, resolveDictLocale, enterprise } from './dict';
import type { TierDict } from './dict/types';

interface I18nContextValue {
  tier: TierKey;
  /** Resolve a key to its tier-aware label, falling through to the
   *  enterprise dictionary when the tier doesn't override it. */
  t: (key: string, fallback?: string) => string;
}

const I18nContext = createContext<I18nContextValue | undefined>(undefined);

function makeT(dict: TierDict): I18nContextValue['t'] {
  return (key, fallback) => {
    const value = dict[key] ?? enterprise[key];
    if (value !== undefined) return value;
    if (fallback !== undefined) return fallback;
    // In dev, surface the missing key so we can add it; in prod, render the
    // key itself rather than blowing up the page.
    if (import.meta.env?.MODE !== 'production') {
      // eslint-disable-next-line no-console
      console.warn(`[i18n] missing key: ${key}`);
    }
    return key;
  };
}

/** Detect the browser locale once at module load. SSR-safe: returns
 *  undefined when `navigator` is unavailable so callers fall back to en. */
function detectBrowserLocale(): string | undefined {
  if (typeof navigator === 'undefined') return undefined;
  return navigator.language || undefined;
}

interface ProviderProps {
  tier: TierKey | null | undefined;
  /** Optional override for tests / locale switchers. Defaults to
   *  `navigator.language` at render time. */
  locale?: string;
  children: ReactNode;
}

export const I18nProvider: React.FC<ProviderProps> = ({ tier, locale, children }) => {
  const resolvedTier: TierKey = tier ?? 'enterprise';
  const effectiveLocale = locale ?? detectBrowserLocale();
  const value = useMemo<I18nContextValue>(() => {
    // R2 + HEALTH-2 — locale-aware resolver merges the Spanish overlay
    // on top of the English tier dict when the browser locale starts
    // with 'es'. On enterprise tier (no overlay yet) this collapses to
    // `resolveDict`.
    const tierDict = effectiveLocale
      ? resolveDictLocale(resolvedTier, effectiveLocale)
      : resolveDict(resolvedTier);
    const dict = { ...enterprise, ...tierDict };
    return { tier: resolvedTier, t: makeT(dict) };
  }, [resolvedTier, effectiveLocale]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
};

export function useT(): I18nContextValue['t'] {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    // Render-without-provider safety: return enterprise.
    return makeT(enterprise);
  }
  return ctx.t;
}

export function useTier(): TierKey {
  const ctx = useContext(I18nContext);
  return ctx?.tier ?? 'enterprise';
}
