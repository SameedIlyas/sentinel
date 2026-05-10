/**
 * Clinic Multi-Site dictionary — extends ``clinic_standard``.  Multi-site
 * vocabulary tends to involve "location" rather than "practice".
 */

import type { TierDict } from './types';
import { clinic_standard } from './clinic_standard';

export const clinic_multi_site: TierDict = {
  ...clinic_standard,
  'noun.organization': 'Practice group',
  'noun.organizations': 'Practice groups',
  'role.admin': 'Group administrator',
  'role.cmio': 'Medical director',
};
