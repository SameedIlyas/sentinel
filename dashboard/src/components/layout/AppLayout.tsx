import React, { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  AppBar,
  Toolbar,
  Typography,
  IconButton,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Divider,
  Avatar,
  Menu,
  MenuItem,
  Chip,
  useTheme,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import DashboardIcon from '@mui/icons-material/Dashboard';
import PolicyIcon from '@mui/icons-material/Policy';
import AgentIcon from '@mui/icons-material/SmartToy';
import AuditIcon from '@mui/icons-material/Assignment';
import AlertIcon from '@mui/icons-material/Notifications';
import PeopleIcon from '@mui/icons-material/People';
import LogoutIcon from '@mui/icons-material/Logout';
import AccountCircle from '@mui/icons-material/AccountCircle';
import ChevronLeft from '@mui/icons-material/ChevronLeft';
import KeyboardArrowDown from '@mui/icons-material/KeyboardArrowDown';
import LightModeOutlined from '@mui/icons-material/LightModeOutlined';
import DarkModeOutlined from '@mui/icons-material/DarkModeOutlined';
import { useAuth } from '@/contexts/AuthContext';
import { useThemeMode } from '@/contexts/ThemeContext';
import { UserRole } from '@/types';

const DRAWER_WIDTH = 236;
const DRAWER_COLLAPSED = 66;

interface NavItem {
  label: string;
  path: string;
  icon: React.ReactNode;
  requiredRoles?: UserRole[];
}

const navItems: NavItem[] = [
  { label: 'Dashboard', path: '/', icon: <DashboardIcon sx={{ fontSize: 19 }} /> },
  { label: 'Agents', path: '/agents', icon: <AgentIcon sx={{ fontSize: 19 }} /> },
  { label: 'Policies', path: '/policies', icon: <PolicyIcon sx={{ fontSize: 19 }} /> },
  { label: 'Audit Logs', path: '/audit', icon: <AuditIcon sx={{ fontSize: 19 }} /> },
  { label: 'Alerts', path: '/alerts', icon: <AlertIcon sx={{ fontSize: 19 }} /> },
  { label: 'Users', path: '/users', icon: <PeopleIcon sx={{ fontSize: 19 }} />, requiredRoles: [UserRole.ADMIN] },
];

const AppLayout: React.FC = () => {
  const theme = useTheme();
  const { mode, toggleTheme } = useThemeMode();
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout, hasRole } = useAuth();
  const [drawerOpen, setDrawerOpen] = useState(true);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  const dark = mode === 'dark';

  const handleLogout = async () => {
    setAnchorEl(null);
    await logout();
    navigate('/login');
  };

  const getRoleColor = (role: string) => {
    switch (role) {
      case 'admin': return theme.palette.error.main;
      case 'analyst': return theme.palette.warning.main;
      case 'viewer': return theme.palette.info.main;
      default: return theme.palette.text.secondary;
    }
  };

  const filteredNavItems = navItems.filter((item) => {
    if (!item.requiredRoles) return true;
    return hasRole(item.requiredRoles);
  });

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  const currentWidth = drawerOpen ? DRAWER_WIDTH : DRAWER_COLLAPSED;

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: 'background.default' }}>
      <AppBar
        position="fixed"
        sx={{
          zIndex: (t) => t.zIndex.drawer + 1,
          ml: `${currentWidth}px`,
          width: `calc(100% - ${currentWidth}px)`,
          transition: 'all 0.2s cubic-bezier(0.4,0,0.2,1)',
        }}
      >
        <Toolbar sx={{ minHeight: '52px !important', px: { xs: 2, sm: 3 } }}>
          <IconButton
            edge="start"
            onClick={() => setDrawerOpen(!drawerOpen)}
            sx={{ mr: 1, color: 'text.secondary' }}
            size="small"
          >
            {drawerOpen ? <ChevronLeft fontSize="small" /> : <MenuIcon fontSize="small" />}
          </IconButton>

          <Box sx={{ flexGrow: 1 }} />

          <IconButton
            onClick={toggleTheme}
            size="small"
            sx={{
              mr: 1.5,
              color: 'text.secondary',
              border: `1px solid ${theme.palette.divider}`,
              width: 32,
              height: 32,
            }}
          >
            {dark ? <LightModeOutlined sx={{ fontSize: 16 }} /> : <DarkModeOutlined sx={{ fontSize: 16 }} />}
          </IconButton>

          <Box
            onClick={(e) => setAnchorEl(e.currentTarget)}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              cursor: 'pointer',
              py: 0.5,
              px: 1,
              borderRadius: 1.5,
              border: `1px solid transparent`,
              '&:hover': { bgcolor: dark ? 'rgba(255,255,255,0.035)' : 'rgba(0,0,0,0.03)' },
            }}
          >
            <Avatar
              sx={{
                width: 28,
                height: 28,
                bgcolor: theme.palette.primary.main,
                color: '#fff',
                fontSize: '0.7rem',
                fontWeight: 700,
              }}
            >
              {user?.username?.charAt(0).toUpperCase()}
            </Avatar>
            <Box sx={{ display: { xs: 'none', sm: 'block' } }}>
              <Typography sx={{ fontWeight: 600, lineHeight: 1.2, fontSize: '0.775rem', color: 'text.primary' }}>
                {user?.full_name || user?.username}
              </Typography>
              <Typography sx={{ color: 'text.secondary', fontSize: '0.65rem' }}>
                {user?.role}
              </Typography>
            </Box>
            <KeyboardArrowDown sx={{ fontSize: 15, color: 'text.secondary' }} />
          </Box>

          <Menu
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={() => setAnchorEl(null)}
            transformOrigin={{ horizontal: 'right', vertical: 'top' }}
            anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
          >
            <MenuItem disabled sx={{ opacity: '0.7 !important' }}>
              <ListItemIcon><AccountCircle fontSize="small" /></ListItemIcon>
              <Box>
                <Typography sx={{ fontWeight: 600, fontSize: '0.8125rem' }}>{user?.username}</Typography>
                <Typography sx={{ color: 'text.secondary', fontSize: '0.6875rem' }}>{user?.email}</Typography>
              </Box>
            </MenuItem>
            <Divider sx={{ my: 0.5 }} />
            <MenuItem onClick={handleLogout}>
              <ListItemIcon><LogoutIcon fontSize="small" sx={{ color: 'error.main' }} /></ListItemIcon>
              <Typography sx={{ color: 'error.main', fontSize: '0.8125rem', fontWeight: 500 }}>Sign out</Typography>
            </MenuItem>
          </Menu>
        </Toolbar>
      </AppBar>

      <Drawer
        variant="permanent"
        sx={{
          width: currentWidth,
          flexShrink: 0,
          transition: 'width 0.2s cubic-bezier(0.4,0,0.2,1)',
          '& .MuiDrawer-paper': {
            width: currentWidth,
            boxSizing: 'border-box',
            overflowX: 'hidden',
            transition: 'width 0.2s cubic-bezier(0.4,0,0.2,1)',
          },
        }}
      >
        <Box sx={{ pt: 1.75, pb: 0.75, px: drawerOpen ? 2.25 : 1.25, display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 52 }}>
          <Box
            component="img"
            src="/sentinel.png"
            alt="Sentinel Governance AI"
            sx={{
              height: drawerOpen ? 44 : 30,
              width: 'auto',
              objectFit: 'contain',
              flexShrink: 0,
            }}
          />
        </Box>

        <Divider sx={{ mx: 1.75, my: 0.75 }} />

        <Box sx={{ flex: 1, py: 0.5 }}>
          <List sx={{ px: 1 }}>
            {filteredNavItems.map((item) => {
              const active = isActive(item.path);
              return (
                <ListItem key={item.path} disablePadding sx={{ mb: 0.25 }}>
                  <ListItemButton
                    onClick={() => navigate(item.path)}
                    sx={{
                      borderRadius: '6px',
                      minHeight: 36,
                      px: drawerOpen ? 1.25 : 1.25,
                      justifyContent: drawerOpen ? 'initial' : 'center',
                      position: 'relative',
                      bgcolor: active
                        ? (dark ? 'rgba(99,91,255,0.1)' : 'rgba(99,91,255,0.06)')
                        : 'transparent',
                      '&:hover': {
                        bgcolor: active
                          ? (dark ? 'rgba(99,91,255,0.14)' : 'rgba(99,91,255,0.09)')
                          : (dark ? 'rgba(255,255,255,0.035)' : 'rgba(0,0,0,0.03)'),
                      },
                      '&::before': active ? {
                        content: '""',
                        position: 'absolute',
                        left: 0,
                        top: '50%',
                        transform: 'translateY(-50%)',
                        width: 3,
                        height: 18,
                        borderRadius: '0 3px 3px 0',
                        bgcolor: 'primary.main',
                      } : {},
                    }}
                  >
                    <ListItemIcon
                      sx={{
                        color: active ? 'primary.main' : 'text.secondary',
                        minWidth: drawerOpen ? 34 : 'auto',
                        justifyContent: 'center',
                      }}
                    >
                      {item.icon}
                    </ListItemIcon>
                    {drawerOpen && (
                      <ListItemText
                        primary={item.label}
                        primaryTypographyProps={{
                          fontSize: '0.8125rem',
                          fontWeight: active ? 600 : 450,
                          color: active ? 'text.primary' : 'text.secondary',
                        }}
                      />
                    )}
                  </ListItemButton>
                </ListItem>
              );
            })}
          </List>
        </Box>

        {drawerOpen && (
          <Box sx={{ p: 1.5 }}>
            <Box
              sx={{
                p: 1.25,
                borderRadius: '8px',
                bgcolor: dark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.015)',
                border: `1px solid ${theme.palette.divider}`,
                display: 'flex',
                alignItems: 'center',
                gap: 1.25,
              }}
            >
              <Avatar
                sx={{
                  width: 30,
                  height: 30,
                  bgcolor: theme.palette.primary.main,
                  color: '#fff',
                  fontSize: '0.7rem',
                  fontWeight: 700,
                }}
              >
                {user?.username?.charAt(0).toUpperCase()}
              </Avatar>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography sx={{ fontWeight: 600, fontSize: '0.75rem', lineHeight: 1.2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'text.primary' }}>
                  {user?.full_name || user?.username}
                </Typography>
                <Chip
                  label={user?.role}
                  size="small"
                  sx={{
                    height: 17,
                    fontSize: '0.55rem',
                    fontWeight: 600,
                    bgcolor: `${getRoleColor(user?.role || '')}18`,
                    color: getRoleColor(user?.role || ''),
                    border: `1px solid ${getRoleColor(user?.role || '')}30`,
                    mt: 0.25,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    '& .MuiChip-label': { px: 0.75 },
                  }}
                />
              </Box>
            </Box>
          </Box>
        )}
      </Drawer>

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          px: { xs: 2, sm: 3 },
          py: 2.5,
          transition: 'all 0.2s cubic-bezier(0.4,0,0.2,1)',
          minHeight: '100vh',
        }}
      >
        <Toolbar sx={{ minHeight: '52px !important' }} />
        <Outlet />
      </Box>
    </Box>
  );
};

export default AppLayout;
