/**
 * Tier-keyed dictionary registry.  Lookups go through ``resolveDict`` so
 * the rest of the app does not need to know which tiers exist.
 */

import type { TierDict } from './types';
import { enterprise } from './enterprise';
import { clinic_basic } from './clinic_basic';
import { clinic_standard } from './clinic_standard';
import { clinic_multi_site } from './clinic_multi_site';
import type { TierKey } from '@/types';

export const DICTS: Record<TierKey, TierDict> = {
  enterprise,
  clinic_basic,
  clinic_standard,
  clinic_multi_site,
};

/** Resolve a dictionary for a tier, falling back to enterprise. */
export function resolveDict(tier: TierKey | null | undefined): TierDict {
  if (!tier) return enterprise;
  return DICTS[tier] ?? enterprise;
}

export { enterprise };
