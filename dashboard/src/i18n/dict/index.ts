/**
 * Tier-keyed dictionary registry.  Lookups go through ``resolveDict`` so
 * the rest of the app does not need to know which tiers exist.
 *
 * R2 + HEALTH-2 — `resolveDictLocale(tier, locale)` returns a Spanish
 * overlay merged on top of the English tier dict when `locale` starts
 * with 'es'. Enterprise has no Spanish overlay (yet), so it passes
 * through unchanged.
 */

import type { TierDict } from './types';
import { enterprise } from './enterprise';
import { clinic_basic } from './clinic_basic';
import { clinic_standard } from './clinic_standard';
import { clinic_multi_site } from './clinic_multi_site';
import { clinic_basic_es } from './clinic_basic.es';
import { clinic_standard_es } from './clinic_standard.es';
import { clinic_multi_site_es } from './clinic_multi_site.es';
import type { TierKey } from '@/types';

export const DICTS: Record<TierKey, TierDict> = {
  enterprise,
  clinic_basic,
  clinic_standard,
  clinic_multi_site,
};

const ES_OVERLAYS: Partial<Record<TierKey, TierDict>> = {
  clinic_basic: clinic_basic_es,
  clinic_standard: clinic_standard_es,
  clinic_multi_site: clinic_multi_site_es,
};

/** Resolve a dictionary for a tier, falling back to enterprise. */
export function resolveDict(tier: TierKey | null | undefined): TierDict {
  if (!tier) return enterprise;
  return DICTS[tier] ?? enterprise;
}

/**
 * R2 + HEALTH-2 — Locale-aware dictionary resolver.
 *
 * When `locale` starts with `'es'` (case-insensitive) and a Spanish
 * overlay exists for the tier, the overlay is merged on top of the
 * English dictionary. All other locales return the English tier dict.
 *
 * `locale` is typically `navigator.language` (e.g. 'en-US', 'es-MX').
 * Pass `undefined` for the fallback (English).
 */
export function resolveDictLocale(
  tier: TierKey | null | undefined,
  locale: string | null | undefined,
): TierDict {
  const base = resolveDict(tier);
  if (!tier) return base;
  if (typeof locale !== 'string') return base;
  if (!locale.toLowerCase().startsWith('es')) return base;
  const overlay = ES_OVERLAYS[tier];
  if (!overlay) return base;
  return { ...base, ...overlay };
}

export { enterprise };
