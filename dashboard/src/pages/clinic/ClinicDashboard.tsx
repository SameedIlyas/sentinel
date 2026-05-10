import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Card, CardContent, Typography, Grid, Button, Chip, LinearProgress, Stack,
  Alert as MuiAlert,
} from '@mui/material';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import NotificationsIcon from '@mui/icons-material/Notifications';
import BlockIcon from '@mui/icons-material/Block';
import DescriptionIcon from '@mui/icons-material/Description';
import HealthAndSafetyIcon from '@mui/icons-material/HealthAndSafety';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';

import apiClient from '@/api/client';
import { useAuth } from '@/contexts/AuthContext';
import { useT } from '@/i18n';

interface DashboardSummary {
  org_name: string;
  tier: string;
  tier_display_name: string;
  baa_signed: boolean;
  counts: {
    tools_total: number;
    tools_high_risk: number;
    alerts_open: number;
    alerts_critical: number;
    blocked_today: number;
    shadow_observations_open: number;
  };
  latest_report: { id: string; period_end: string; download_url: string } | null;
  onboarding: { step: number; completed: boolean };
  billing: {
    subscription_status: string | null;
    cancel_at: string | null;
    current_period_end: string | null;
    has_payment_method: boolean;
  };
}

interface TileProps {
  label: string;
  sublabel: string;
  value: number | string;
  icon: React.ReactNode;
  warn?: boolean;
  bad?: boolean;
  onClick?: () => void;
  cta?: string;
}

const Tile: React.FC<TileProps> = ({ label, sublabel, value, icon, warn, bad, onClick, cta }) => (
  <Card
    onClick={onClick}
    sx={{
      cursor: onClick ? 'pointer' : 'default',
      transition: 'border-color 0.15s',
      borderColor: bad ? 'error.main' : warn ? 'warning.main' : undefined,
      '&:hover': onClick ? { borderColor: 'primary.main' } : {},
    }}
  >
    <CardContent>
      <Stack direction="row" spacing={2} alignItems="center">
        <Box
          sx={{
            width: 40, height: 40, borderRadius: 2,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            bgcolor: bad ? 'error.light' : warn ? 'warning.light' : 'primary.light',
            color: bad ? 'error.dark' : warn ? 'warning.dark' : 'primary.dark',
            opacity: 0.85,
          }}
        >
          {icon}
        </Box>
        <Box sx={{ flex: 1 }}>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>{label}</Typography>
          <Typography variant="h3" sx={{ fontWeight: 700 }}>{value}</Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>{sublabel}</Typography>
        </Box>
      </Stack>
      {cta && (
        <Button size="small" sx={{ mt: 1.5 }} variant="outlined" onClick={(e) => { e.stopPropagation(); onClick?.(); }}>
          {cta}
        </Button>
      )}
    </CardContent>
  </Card>
);

const ClinicDashboard: React.FC = () => {
  const t = useT();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const summary = await apiClient.get<DashboardSummary>('/v1/clinic/dashboard/summary');
        if (mounted) setData(summary);
      } catch (e: any) {
        if (mounted) setError(e?.response?.data?.detail || 'Could not load dashboard');
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, []);

  const openPortal = async () => {
    try {
      const resp = await apiClient.post<{ url: string }>('/v1/billing/clinic/portal');
      window.open(resp.url, '_blank', 'noopener,noreferrer');
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Could not open Customer Portal');
    }
  };

  if (loading) return <LinearProgress />;
  if (error) return <MuiAlert severity="error">{error}</MuiAlert>;
  if (!data) return null;

  const showOnboarding = !data.onboarding.completed;
  const subStatus = data.billing.subscription_status;
  const showPastDue = subStatus === 'past_due';
  const showCanceled = subStatus === 'canceled';

  return (
    <Box>
      <Stack direction={{ xs: 'column', sm: 'row' }} alignItems={{ sm: 'center' }} justifyContent="space-between" spacing={2} sx={{ mb: 3 }}>
        <Box>
          <Typography variant="h1" sx={{ fontWeight: 700, mb: 0.5 }}>{data.org_name}</Typography>
          <Typography variant="body2" color="text.secondary">
            {t('clinic.dashboard.welcome')}
            {user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''}
            {' · '}
            <Chip label={data.tier_display_name} size="small" sx={{ ml: 0.5 }} />
            {data.baa_signed && (
              <Chip label="BAA on file" size="small" color="success" variant="outlined" sx={{ ml: 1 }} />
            )}
          </Typography>
        </Box>
        <Stack direction="row" spacing={1}>
          <Button variant="outlined" onClick={() => navigate('/clinic/tools/new')}>{t('clinic.tools.add')}</Button>
        </Stack>
      </Stack>

      {showPastDue && (
        <MuiAlert
          severity="error"
          sx={{ mb: 2 }}
          action={
            <Button color="inherit" size="small" onClick={openPortal}>
              Update payment
            </Button>
          }
        >
          Your last payment failed. Update your card to keep service running.
        </MuiAlert>
      )}

      {showCanceled && (
        <MuiAlert
          severity="warning"
          sx={{ mb: 2 }}
          action={
            data.billing.has_payment_method ? (
              <Button color="inherit" size="small" onClick={openPortal}>
                Reactivate
              </Button>
            ) : null
          }
        >
          Your subscription is canceled
          {data.billing.current_period_end
            ? `. You keep access until ${new Date(data.billing.current_period_end).toLocaleDateString()}.`
            : '.'}
        </MuiAlert>
      )}

      {showOnboarding && (
        <MuiAlert
          severity="info"
          sx={{ mb: 3 }}
          action={
            <Button color="inherit" size="small" onClick={() => navigate('/clinic/onboarding')}>
              Continue setup
            </Button>
          }
        >
          You're {data.onboarding.step} of 3 steps through setup. Let's finish so we can start watching your AI tools.
        </MuiAlert>
      )}

      <Grid container spacing={2}>
        <Grid item xs={12} sm={6} md={3}>
          <Tile
            label={t('clinic.dashboard.tools_tile')}
            sublabel={t('clinic.dashboard.tools_subtitle')}
            value={data.counts.tools_total}
            icon={<SmartToyIcon />}
            warn={data.counts.tools_high_risk > 0}
            onClick={() => navigate('/clinic/tools')}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Tile
            label={t('clinic.dashboard.alerts_tile')}
            sublabel={data.counts.alerts_critical > 0
              ? `${data.counts.alerts_critical} critical`
              : t('clinic.dashboard.alerts_subtitle')}
            value={data.counts.alerts_open}
            icon={<NotificationsIcon />}
            bad={data.counts.alerts_critical > 0}
            warn={data.counts.alerts_open > 0 && data.counts.alerts_critical === 0}
            onClick={() => navigate('/clinic/alerts')}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Tile
            label={t('clinic.dashboard.blocked_tile')}
            sublabel={t('clinic.dashboard.blocked_subtitle')}
            value={data.counts.blocked_today}
            icon={<BlockIcon />}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Tile
            label={t('clinic.dashboard.report_tile')}
            sublabel={data.latest_report
              ? `Period ending ${new Date(data.latest_report.period_end).toLocaleDateString()}`
              : 'Generates monthly'}
            value={data.latest_report ? '✓' : '—'}
            icon={<DescriptionIcon />}
            onClick={() => navigate('/clinic/reports')}
            cta={data.latest_report ? 'Download' : 'View reports'}
          />
        </Grid>

        {/* Secondary row */}
        <Grid item xs={12} sm={6}>
          <Tile
            label={t('noun.shadow_ai')}
            sublabel={t('clinic.shadow_ai.subtitle')}
            value={data.counts.shadow_observations_open}
            icon={<VisibilityOffIcon />}
            warn={data.counts.shadow_observations_open > 5}
            onClick={() => navigate('/clinic/shadow-ai')}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <Tile
            label="Compliance posture"
            sublabel={data.baa_signed ? 'BAA on file' : 'Action needed'}
            value={data.baa_signed ? 'OK' : 'Sign BAA'}
            icon={<HealthAndSafetyIcon />}
            bad={!data.baa_signed}
            onClick={() => navigate('/clinic/settings/compliance')}
          />
        </Grid>
      </Grid>
    </Box>
  );
};

export default ClinicDashboard;
