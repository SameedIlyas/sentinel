import React from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  Box, AppBar, Toolbar, Typography, IconButton, Drawer, List, ListItem,
  ListItemButton, ListItemIcon, ListItemText, Divider, Avatar, Menu,
  MenuItem, Chip, useTheme, Tooltip, useMediaQuery,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import ChevronLeft from '@mui/icons-material/ChevronLeft';
import LogoutIcon from '@mui/icons-material/Logout';
import AccountCircle from '@mui/icons-material/AccountCircle';
import KeyboardArrowDown from '@mui/icons-material/KeyboardArrowDown';
import LightModeOutlined from '@mui/icons-material/LightModeOutlined';
import DarkModeOutlined from '@mui/icons-material/DarkModeOutlined';
// Core icons
import DashboardIcon from '@mui/icons-material/Dashboard';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import PolicyIcon from '@mui/icons-material/Policy';
import AssignmentIcon from '@mui/icons-material/Assignment';
import NotificationsIcon from '@mui/icons-material/Notifications';
import PeopleIcon from '@mui/icons-material/People';
// Clinical icons
import ArticleIcon from '@mui/icons-material/Article';
import BalanceIcon from '@mui/icons-material/Balance';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import HowToRegIcon from '@mui/icons-material/HowToReg';
// Admin icons
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import RecordVoiceOverIcon from '@mui/icons-material/RecordVoiceOver';
import PublicIcon from '@mui/icons-material/Public';
// Finance icons
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import AttachMoneyIcon from '@mui/icons-material/AttachMoney';
// Regulatory icons
import DescriptionIcon from '@mui/icons-material/Description';
import ReportProblemIcon from '@mui/icons-material/ReportProblem';
import MonitorHeartIcon from '@mui/icons-material/MonitorHeart';
// Risk icons
import SpeedIcon from '@mui/icons-material/Speed';
// Settings icons
import BusinessIcon from '@mui/icons-material/Business';
import TuneIcon from '@mui/icons-material/Tune';
import HealthAndSafetyIcon from '@mui/icons-material/HealthAndSafety';

import { useAuth } from '@/contexts/AuthContext';
import { useThemeMode } from '@/contexts/ThemeContext';
import { useUIStore } from '@/stores/uiStore';
import { getNavForRole } from '@/config/navigation';
import { UserRole } from '@/types';
import { WalkthroughOverlay, useWalkthrough } from '@/walkthrough';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import PageErrorBoundary from '@/components/common/PageErrorBoundary';

const DRAWER_WIDTH = 236;
const DRAWER_COLLAPSED = 66;

const ICON_MAP: Record<string, React.ReactNode> = {
  Dashboard: <DashboardIcon sx={{ fontSize: 19 }} />,
  SmartToy: <SmartToyIcon sx={{ fontSize: 19 }} />,
  Policy: <PolicyIcon sx={{ fontSize: 19 }} />,
  Assignment: <AssignmentIcon sx={{ fontSize: 19 }} />,
  Notifications: <NotificationsIcon sx={{ fontSize: 19 }} />,
  People: <PeopleIcon sx={{ fontSize: 19 }} />,
  Article: <ArticleIcon sx={{ fontSize: 19 }} />,
  BalanceOutlined: <BalanceIcon sx={{ fontSize: 19 }} />,
  ShowChart: <ShowChartIcon sx={{ fontSize: 19 }} />,
  HowToReg: <HowToRegIcon sx={{ fontSize: 19 }} />,
  VisibilityOff: <VisibilityOffIcon sx={{ fontSize: 19 }} />,
  RecordVoiceOver: <RecordVoiceOverIcon sx={{ fontSize: 19 }} />,
  Public: <PublicIcon sx={{ fontSize: 19 }} />,
  AccountTree: <AccountTreeIcon sx={{ fontSize: 19 }} />,
  AttachMoney: <AttachMoneyIcon sx={{ fontSize: 19 }} />,
  Description: <DescriptionIcon sx={{ fontSize: 19 }} />,
  ReportProblem: <ReportProblemIcon sx={{ fontSize: 19 }} />,
  MonitorHeart: <MonitorHeartIcon sx={{ fontSize: 19 }} />,
  Speed: <SpeedIcon sx={{ fontSize: 19 }} />,
  Business: <BusinessIcon sx={{ fontSize: 19 }} />,
  Tune: <TuneIcon sx={{ fontSize: 19 }} />,
  HealthAndSafety: <HealthAndSafetyIcon sx={{ fontSize: 19 }} />,
};

const ROLE_COLORS: Record<string, string> = {
  system_admin: '#df1b41',
  admin: '#e87f17',
  cmio: '#635bff',
  data_scientist: '#3b82f6',
  compliance_officer: '#0ea371',
  clinical_user: '#a78bfa',
  analyst: '#f59e0b',
  viewer: '#8b8fa3',
};

const AppLayout: React.FC = () => {
  const theme = useTheme();
  const { mode, toggleTheme } = useThemeMode();
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const { sidebarOpen, toggleSidebar } = useUIStore();
  const { restart: restartWalkthrough } = useWalkthrough();
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);

  const handleRestartTour = () => {
    setAnchorEl(null);
    restartWalkthrough();
  };

  // Mobile uses a temporary (overlay) drawer that closes on navigation.
  // Below the `md` breakpoint (<900px) we treat the layout as mobile.
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [mobileOpen, setMobileOpen] = React.useState(false);

  const dark = mode === 'dark';
  const desktopWidth = sidebarOpen ? DRAWER_WIDTH : DRAWER_COLLAPSED;
  // On mobile the sidebar overlays content, so the main column reserves no width for it.
  const currentWidth = isMobile ? 0 : desktopWidth;
  const roleColor = ROLE_COLORS[user?.role ?? ''] ?? theme.palette.text.secondary;

  const navSections = user ? getNavForRole(user.role as UserRole) : [];

  const isActive = (path: string) =>
    path === '/' ? location.pathname === '/' : location.pathname.startsWith(path);

  const handleLogout = async () => {
    setAnchorEl(null);
    setMobileOpen(false);
    await logout();
    navigate('/login');
  };

  const handleNav = (path: string) => {
    navigate(path);
    if (isMobile) setMobileOpen(false);
  };

  const handleToolbarMenuClick = () => {
    if (isMobile) {
      setMobileOpen((open) => !open);
    } else {
      toggleSidebar();
    }
  };

  // On mobile the drawer always shows the expanded layout; on desktop it follows sidebarOpen.
  const drawerExpanded = isMobile ? true : sidebarOpen;

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: 'background.default' }}>
      {/* ── Top bar ── */}
      <AppBar
        position="fixed"
        sx={{
          zIndex: (t) => t.zIndex.drawer + 1,
          ml: `${currentWidth}px`,
          width: `calc(100% - ${currentWidth}px)`,
          transition: 'all 0.2s cubic-bezier(0.4,0,0.2,1)',
        }}
      >
        <Toolbar sx={{ minHeight: '52px !important', px: { xs: 1.5, sm: 3 } }}>
          <IconButton
            edge="start"
            onClick={handleToolbarMenuClick}
            size="small"
            sx={{ mr: 1, color: 'text.secondary' }}
            aria-label={
              isMobile
                ? mobileOpen ? 'Close menu' : 'Open menu'
                : sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'
            }
          >
            {isMobile
              ? <MenuIcon fontSize="small" />
              : sidebarOpen
                ? <ChevronLeft fontSize="small" />
                : <MenuIcon fontSize="small" />}
          </IconButton>
          <Box sx={{ flexGrow: 1 }} />
          <Tooltip title={dark ? 'Light mode' : 'Dark mode'}>
            <IconButton
              onClick={toggleTheme}
              size="small"
              aria-label="Toggle theme"
              data-walkthrough="theme-toggle"
              sx={{ mr: 1.5, color: 'text.secondary', border: `1px solid ${theme.palette.divider}`, width: 32, height: 32 }}
            >
              {dark ? <LightModeOutlined sx={{ fontSize: 16 }} /> : <DarkModeOutlined sx={{ fontSize: 16 }} />}
            </IconButton>
          </Tooltip>
          <Box
            onClick={(e) => setAnchorEl(e.currentTarget)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && setAnchorEl(e.currentTarget as HTMLElement)}
            aria-label="User menu"
            data-walkthrough="user-menu"
            sx={{
              display: 'flex', alignItems: 'center', gap: 1, cursor: 'pointer',
              py: 0.5, px: 1, borderRadius: 1.5, border: '1px solid transparent',
              '&:hover': { bgcolor: dark ? 'rgba(255,255,255,0.035)' : 'rgba(0,0,0,0.03)' },
            }}
          >
            <Avatar sx={{ width: 28, height: 28, bgcolor: 'primary.main', color: '#fff', fontSize: '0.7rem', fontWeight: 700 }}>
              {user?.username?.charAt(0).toUpperCase()}
            </Avatar>
            <Box sx={{ display: { xs: 'none', sm: 'block' } }}>
              <Typography sx={{ fontWeight: 600, lineHeight: 1.2, fontSize: '0.775rem', color: 'text.primary' }}>
                {user?.full_name || user?.username}
              </Typography>
              <Typography sx={{ color: 'text.secondary', fontSize: '0.65rem' }}>{user?.role}</Typography>
            </Box>
            <KeyboardArrowDown sx={{ fontSize: 15, color: 'text.secondary' }} />
          </Box>
          <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={() => setAnchorEl(null)}
            transformOrigin={{ horizontal: 'right', vertical: 'top' }}
            anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}>
            <MenuItem disabled sx={{ opacity: '0.7 !important' }}>
              <ListItemIcon><AccountCircle fontSize="small" /></ListItemIcon>
              <Box>
                <Typography sx={{ fontWeight: 600, fontSize: '0.8125rem' }}>{user?.username}</Typography>
                <Typography sx={{ color: 'text.secondary', fontSize: '0.6875rem' }}>{user?.email}</Typography>
              </Box>
            </MenuItem>
            <Divider sx={{ my: 0.5 }} />
            <MenuItem onClick={handleRestartTour}>
              <ListItemIcon><HelpOutlineIcon fontSize="small" sx={{ color: 'primary.main' }} /></ListItemIcon>
              <Typography sx={{ color: 'text.primary', fontSize: '0.8125rem', fontWeight: 500 }}>Restart tour</Typography>
            </MenuItem>
            <Divider sx={{ my: 0.5 }} />
            <MenuItem onClick={handleLogout}>
              <ListItemIcon><LogoutIcon fontSize="small" sx={{ color: 'error.main' }} /></ListItemIcon>
              <Typography sx={{ color: 'error.main', fontSize: '0.8125rem', fontWeight: 500 }}>Sign out</Typography>
            </MenuItem>
          </Menu>
        </Toolbar>
      </AppBar>

      {/* ── Sidebar ── */}
      <Drawer
        variant={isMobile ? 'temporary' : 'permanent'}
        open={isMobile ? mobileOpen : true}
        onClose={() => setMobileOpen(false)}
        ModalProps={{ keepMounted: true }}
        PaperProps={{ 'data-walkthrough': 'sidebar' } as React.HTMLAttributes<HTMLDivElement>}
        sx={{
          width: isMobile ? 0 : desktopWidth, flexShrink: 0,
          transition: 'width 0.2s cubic-bezier(0.4,0,0.2,1)',
          '& .MuiDrawer-paper': {
            width: isMobile ? Math.min(DRAWER_WIDTH + 24, 280) : desktopWidth,
            boxSizing: 'border-box',
            overflowX: 'hidden',
            transition: 'width 0.2s cubic-bezier(0.4,0,0.2,1)',
          },
        }}
      >
        {/* Logo */}
        <Box sx={{ pt: 1.75, pb: 0.75, px: drawerExpanded ? 2.25 : 1.25, display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 52 }}>
          <Box component="img" src="/sentinel.png" alt="Sentinel Governance AI"
            sx={{ height: drawerExpanded ? 44 : 30, width: 'auto', objectFit: 'contain', flexShrink: 0 }} />
        </Box>
        <Divider sx={{ mx: 1.75, my: 0.75 }} />

        {/* Nav sections */}
        <Box sx={{ flex: 1, py: 0.5, overflowY: 'auto', overflowX: 'hidden' }}>
          {navSections.map((section, si) => (
            <Box key={section.section}>
              {si > 0 && <Divider sx={{ mx: 1.75, my: 0.5 }} />}
              {drawerExpanded && (
                <Typography sx={{ px: 2.25, pt: si > 0 ? 1 : 0.5, pb: 0.25, fontSize: '0.6rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'text.secondary' }}>
                  {section.section}
                </Typography>
              )}
              <List sx={{ px: 1, py: 0.25 }}>
                {section.items.map((item) => {
                  const active = isActive(item.path);
                  const icon = ICON_MAP[item.iconName] ?? <DashboardIcon sx={{ fontSize: 19 }} />;
                  return (
                    <ListItem key={item.path} disablePadding sx={{ mb: 0.25 }}>
                      <Tooltip title={drawerExpanded ? '' : item.label} placement="right">
                        <ListItemButton
                          onClick={() => handleNav(item.path)}
                          aria-label={item.label}
                          aria-current={active ? 'page' : undefined}
                          data-walkthrough={`nav-${item.label}`}
                          sx={{
                            borderRadius: '6px', minHeight: 36,
                            px: 1.25, justifyContent: drawerExpanded ? 'initial' : 'center',
                            position: 'relative',
                            bgcolor: active ? (dark ? 'rgba(99,91,255,0.1)' : 'rgba(99,91,255,0.06)') : 'transparent',
                            '&:hover': { bgcolor: active ? (dark ? 'rgba(99,91,255,0.14)' : 'rgba(99,91,255,0.09)') : (dark ? 'rgba(255,255,255,0.035)' : 'rgba(0,0,0,0.03)') },
                            '&::before': active ? { content: '""', position: 'absolute', left: 0, top: '50%', transform: 'translateY(-50%)', width: 3, height: 18, borderRadius: '0 3px 3px 0', bgcolor: 'primary.main' } : {},
                          }}
                        >
                          <ListItemIcon sx={{ color: active ? 'primary.main' : 'text.secondary', minWidth: drawerExpanded ? 34 : 'auto', justifyContent: 'center' }}>
                            {icon}
                          </ListItemIcon>
                          {drawerExpanded && (
                            <ListItemText primary={item.label} primaryTypographyProps={{ fontSize: '0.8125rem', fontWeight: active ? 600 : 450, color: active ? 'text.primary' : 'text.secondary' }} />
                          )}
                        </ListItemButton>
                      </Tooltip>
                    </ListItem>
                  );
                })}
              </List>
            </Box>
          ))}
        </Box>

        {/* User card at bottom */}
        {drawerExpanded && (
          <Box sx={{ p: 1.5 }}>
            <Box sx={{ p: 1.25, borderRadius: '8px', bgcolor: dark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.015)', border: `1px solid ${theme.palette.divider}`, display: 'flex', alignItems: 'center', gap: 1.25 }}>
              <Avatar sx={{ width: 30, height: 30, bgcolor: 'primary.main', color: '#fff', fontSize: '0.7rem', fontWeight: 700 }}>
                {user?.username?.charAt(0).toUpperCase()}
              </Avatar>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography sx={{ fontWeight: 600, fontSize: '0.75rem', lineHeight: 1.2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'text.primary' }}>
                  {user?.full_name || user?.username}
                </Typography>
                <Chip label={user?.role} size="small" sx={{ height: 17, fontSize: '0.55rem', fontWeight: 600, bgcolor: `${roleColor}18`, color: roleColor, border: `1px solid ${roleColor}30`, mt: 0.25, textTransform: 'uppercase', letterSpacing: '0.05em', '& .MuiChip-label': { px: 0.75 } }} />
              </Box>
            </Box>
          </Box>
        )}
      </Drawer>

      {/* ── Main content ── */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          width: { xs: '100%', md: `calc(100% - ${currentWidth}px)` },
          px: { xs: 1.5, sm: 2.5, md: 3 },
          py: { xs: 2, sm: 2.5 },
          transition: 'all 0.2s cubic-bezier(0.4,0,0.2,1)',
          minHeight: '100vh',
          overflowX: 'hidden',
        }}
      >
        <Toolbar sx={{ minHeight: '52px !important' }} />
        <PageErrorBoundary resetKey={location.pathname}>
          <Outlet />
        </PageErrorBoundary>
      </Box>

      {/* First-run walkthrough — auto-shows on first authenticated mount */}
      <WalkthroughOverlay />
    </Box>
  );
};

export default AppLayout;
