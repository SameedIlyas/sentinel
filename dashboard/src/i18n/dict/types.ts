/**
 * Tier dictionary type — partial maps that override the canonical
 * (enterprise) dictionary.  Keys are dot-paths owned by the calling site.
 */

export type TierDictKey = string;

export type TierDict = Record<TierDictKey, string>;
