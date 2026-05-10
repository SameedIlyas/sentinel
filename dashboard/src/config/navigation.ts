import { UserRole, TierKey, isClinicTier } from '@/types';

export interface NavItem {
  label: string;
  path: string;
  iconName: string;
  allowedRoles?: UserRole[];   // undefined = all authenticated roles
  /** If set, this item is shown only when the user's tier is in the list.
   *  Undefined = visible on every tier. */
  requiredTiers?: TierKey[];
}

export interface NavSection {
  section: string;
  items: NavItem[];
  allowedRoles?: UserRole[];   // section hidden if user lacks any allowed role
  /** If set, the section is shown only when the user's tier is in the list. */
  requiredTiers?: TierKey[];
}

export const ENTERPRISE_TIERS: TierKey[] = ['enterprise'];
export const CLINIC_ALL_TIERS: TierKey[] = [
  'clinic_basic',
  'clinic_standard',
  'clinic_multi_site',
];
export const CLINIC_STANDARD_AND_UP: TierKey[] = [
  'clinic_standard',
  'clinic_multi_site',
];


export const NAV_SECTIONS: NavSection[] = [
  // ── Clinic-tier sections ───────────────────────────────────────────
  {
    section: 'Practice',
    requiredTiers: CLINIC_ALL_TIERS,
    items: [
      { label: 'Dashboard',     path: '/clinic',           iconName: 'Dashboard' },
      { label: 'AI tools',      path: '/clinic/tools',     iconName: 'SmartToy' },
      { label: 'Practice rules', path: '/clinic/policies', iconName: 'Policy' },
      { label: 'Notifications', path: '/clinic/alerts',    iconName: 'Notifications' },
      {
        label: 'Shadow AI watcher',
        path: '/clinic/shadow-ai',
        iconName: 'VisibilityOff',
        requiredTiers: CLINIC_STANDARD_AND_UP,
      },
      {
        label: 'Reports',
        path: '/clinic/reports',
        iconName: 'Description',
        requiredTiers: CLINIC_STANDARD_AND_UP,
      },
    ],
  },
  {
    section: 'Practice Settings',
    requiredTiers: CLINIC_ALL_TIERS,
    allowedRoles: [UserRole.SYSTEM_ADMIN, UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER],
    items: [
      { label: 'Practice info', path: '/clinic/settings/practice',    iconName: 'Business' },
      { label: 'Compliance',    path: '/clinic/settings/compliance',  iconName: 'HealthAndSafety' },
      { label: 'Plan & billing', path: '/clinic/settings/billing',    iconName: 'AttachMoney' },
    ],
  },

  // ── Enterprise / hospital-tier sections (preserved) ────────────────
  {
    section: 'Core',
    requiredTiers: ENTERPRISE_TIERS,
    items: [
      { label: 'Dashboard',   path: '/',        iconName: 'Dashboard' },
      { label: 'Agents',      path: '/agents',  iconName: 'SmartToy' },
      { label: 'Policies',    path: '/policies', iconName: 'Policy' },
      { label: 'Audit Logs',  path: '/audit',   iconName: 'Assignment' },
      { label: 'Alerts',      path: '/alerts',  iconName: 'Notifications' },
      {
        label: 'Users',
        path: '/users',
        iconName: 'People',
        allowedRoles: [UserRole.SYSTEM_ADMIN, UserRole.ADMIN],
      },
    ],
  },
  {
    section: 'Clinical Governance',
    requiredTiers: ENTERPRISE_TIERS,
    allowedRoles: [
      UserRole.SYSTEM_ADMIN, UserRole.ADMIN, UserRole.CMIO,
      UserRole.DATA_SCIENTIST, UserRole.CLINICAL_USER,
    ],
    items: [
      {
        label: 'Model Cards',
        path: '/clinical/model-cards',
        iconName: 'Article',
        allowedRoles: [UserRole.SYSTEM_ADMIN, UserRole.ADMIN, UserRole.CMIO, UserRole.DATA_SCIENTIST],
      },
      {
        label: 'Bias Audits',
        path: '/clinical/bias-audits',
        iconName: 'BalanceOutlined',
        allowedRoles: [UserRole.SYSTEM_ADMIN, UserRole.ADMIN, UserRole.DATA_SCIENTIST],
      },
      {
        label: 'Drift Monitor',
        path: '/clinical/drift',
        iconName: 'ShowChart',
        allowedRoles: [UserRole.SYSTEM_ADMIN, UserRole.ADMIN, UserRole.DATA_SCIENTIST],
      },
      {
        label: 'HITL Queue',
        path: '/clinical/hitl',
        iconName: 'HowToReg',
        allowedRoles: [UserRole.SYSTEM_ADMIN, UserRole.ADMIN, UserRole.CMIO, UserRole.CLINICAL_USER],
      },
    ],
  },
  {
    section: 'Admin Governance',
    requiredTiers: ENTERPRISE_TIERS,
    allowedRoles: [UserRole.SYSTEM_ADMIN, UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER],
    items: [
      {
        label: 'Shadow AI',
        path: '/admin/shadow-ai',
        iconName: 'VisibilityOff',
      },
      {
        label: 'Scribe Audits',
        path: '/admin/scribe-audits',
        iconName: 'RecordVoiceOver',
      },
      {
        label: 'Transparency',
        path: '/transparency',
        iconName: 'Public',
      },
    ],
  },
  {
    section: 'Financial',
    requiredTiers: ENTERPRISE_TIERS,
    allowedRoles: [UserRole.SYSTEM_ADMIN, UserRole.ADMIN, UserRole.COMPLIANCE_OFFICER],
    items: [
      {
        label: 'Prior Auth Trail',
        path: '/finance/prior-auth',
        iconName: 'AccountTree',
      },
      {
        label: 'Revenue Cycle',
        path: '/finance/revenue-cycle',
        iconName: 'AttachMoney',
      },
    ],
  },
  {
    section: 'Regulatory',
    requiredTiers: ENTERPRISE_TIERS,
    allowedRoles: [
      UserRole.SYSTEM_ADMIN, UserRole.ADMIN, UserRole.DATA_SCIENTIST,
      UserRole.COMPLIANCE_OFFICER,
    ],
    items: [
      {
        label: 'Technical Files',
        path: '/regulatory/technical-files',
        iconName: 'Description',
      },
      {
        label: 'Adverse Events',
        path: '/regulatory/adverse-events',
        iconName: 'ReportProblem',
      },
      {
        label: 'Post-Market',
        path: '/regulatory/pms-reports',
        iconName: 'MonitorHeart',
      },
    ],
  },
  {
    section: 'Risk',
    requiredTiers: ENTERPRISE_TIERS,
    allowedRoles: [
      UserRole.SYSTEM_ADMIN, UserRole.ADMIN, UserRole.CMIO,
      UserRole.DATA_SCIENTIST, UserRole.COMPLIANCE_OFFICER,
    ],
    items: [
      { label: 'Risk Portfolio', path: '/risk/portfolio', iconName: 'Speed' },
    ],
  },
  {
    section: 'Settings',
    requiredTiers: ENTERPRISE_TIERS,
    allowedRoles: [UserRole.SYSTEM_ADMIN, UserRole.ADMIN],
    items: [
      { label: 'Organization',       path: '/settings/organization', iconName: 'Business' },
      { label: 'Risk Config',        path: '/settings/risk',         iconName: 'Tune' },
      { label: 'HIPAA Config',       path: '/settings/hipaa',        iconName: 'HealthAndSafety' },
    ],
  },
];

function tierAllowed(allowed: TierKey[] | undefined, tier: TierKey): boolean {
  if (!allowed) return true;
  return allowed.includes(tier);
}

/**
 * Tier + role-aware navigation filter.  Use this from `AppLayout`.
 *
 * The legacy `getNavForRole` is preserved below for callers that have
 * not yet migrated; it implicitly treats the user as enterprise.
 */
export function getNavForUserAndTier(role: UserRole, tier: TierKey): NavSection[] {
  return NAV_SECTIONS
    .filter((sec) => tierAllowed(sec.requiredTiers, tier))
    .filter((sec) => !sec.allowedRoles || sec.allowedRoles.includes(role))
    .map((sec) => ({
      ...sec,
      items: sec.items
        .filter((item) => tierAllowed(item.requiredTiers, tier))
        .filter((item) => !item.allowedRoles || item.allowedRoles.includes(role)),
    }))
    .filter((sec) => sec.items.length > 0);
}

/** Legacy role-only filter — assumes enterprise tier. */
export function getNavForRole(role: UserRole): NavSection[] {
  return getNavForUserAndTier(role, 'enterprise');
}

/** Helper exported for components that need to know whether a path is
 *  visible to a given user / tier combination (e.g., direct-link guards). */
export function navItemVisible(role: UserRole, tier: TierKey, path: string): boolean {
  for (const section of getNavForUserAndTier(role, tier)) {
    if (section.items.some((it) => it.path === path)) return true;
  }
  return false;
}

// Re-export for callers that may want to introspect tier groups.
export { isClinicTier };
