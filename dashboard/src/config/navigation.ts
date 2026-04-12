import { UserRole } from '@/types';

export interface NavItem {
  label: string;
  path: string;
  iconName: string;
  allowedRoles?: UserRole[];   // undefined = all authenticated roles
}

export interface NavSection {
  section: string;
  items: NavItem[];
  allowedRoles?: UserRole[];   // section hidden if user lacks any allowed role
}


export const NAV_SECTIONS: NavSection[] = [
  {
    section: 'Core',
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
    allowedRoles: [UserRole.SYSTEM_ADMIN, UserRole.ADMIN],
    items: [
      { label: 'Organization',       path: '/settings/organization', iconName: 'Business' },
      { label: 'Risk Config',        path: '/settings/risk',         iconName: 'Tune' },
      { label: 'HIPAA Config',       path: '/settings/hipaa',        iconName: 'HealthAndSafety' },
    ],
  },
];

/** Returns only sections/items the given role may see. */
export function getNavForRole(role: UserRole): NavSection[] {
  return NAV_SECTIONS
    .filter((sec) => !sec.allowedRoles || sec.allowedRoles.includes(role))
    .map((sec) => ({
      ...sec,
      items: sec.items.filter((item) => !item.allowedRoles || item.allowedRoles.includes(role)),
    }))
    .filter((sec) => sec.items.length > 0);
}
