import React, { useEffect, useState } from 'react';
import {
  Box, Typography, Stack, Paper, Button, Chip, Alert as MuiAlert,
  Grid, LinearProgress, Card, CardContent,
} from '@mui/material';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';

import apiClient from '@/api/client';
import { useT } from '@/i18n';

interface PlanInfo {
  tier: string;
  display_name: string;
  monthly_price_usd: number;
  tool_cap: number;
  seat_cap: number;
  audit_retention_days: number;
  locations_cap: number;
  baa_mode: string;
  description: string;
  payment_link_url: string | null;
  upgrade_options: string[];
}

interface PlanSummary {
  tier: string;
  display_name: string;
  monthly_price_usd: number;
  description: string;
  payment_link_url: string | null;
}

interface DashboardSummary {
  billing: {
    subscription_status: string | null;
    cancel_at: string | null;
    current_period_end: string | null;
    has_payment_method: boolean;
  };
}

const STATUS_LABEL: Record<string, { label: string; severity: 'success' | 'warning' | 'error' | 'info' }> = {
  active:   { label: 'Active',                 severity: 'success' },
  trialing: { label: 'Trial',                  severity: 'info' },
  past_due: { label: 'Payment failed',         severity: 'error' },
  canceled: { label: 'Canceled (grace period)', severity: 'warning' },
};

const Billing: React.FC = () => {
  const t = useT();
  const [plan, setPlan] = useState<PlanInfo | null>(null);
  const [allPlans, setAllPlans] = useState<PlanSummary[]>([]);
  const [billing, setBilling] = useState<DashboardSummary['billing'] | null>(null);
  const [loading, setLoading] = useState(true);
  const [portalLoading, setPortalLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [p, a, summary] = await Promise.all([
          apiClient.get<PlanInfo>('/v1/clinic/settings/plan'),
          apiClient.get<PlanSummary[]>('/v1/billing/clinic/plans'),
          apiClient.get<DashboardSummary>('/v1/clinic/dashboard/summary'),
        ]);
        setPlan(p);
        setAllPlans(a);
        setBilling(summary.billing);
      } catch (e: any) {
        setError(e?.response?.data?.detail || 'Could not load plan');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const openPortal = async () => {
    setPortalLoading(true);
    setError(null);
    try {
      const resp = await apiClient.post<{ url: string }>('/v1/billing/clinic/portal');
      window.open(resp.url, '_blank', 'noopener,noreferrer');
    } catch (e: any) {
      setError(
        e?.response?.data?.detail
          || 'Could not open Stripe Customer Portal — make sure STRIPE_SECRET_KEY is configured.'
      );
    } finally {
      setPortalLoading(false);
    }
  };

  if (loading) return <LinearProgress />;
  if (!plan) return null;

  return (
    <Box sx={{ maxWidth: 960 }}>
      <Typography variant="h1" sx={{ fontWeight: 700, mb: 1 }}>
        {t('clinic.settings.billing')}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Your plan, what's included, and how to upgrade.
      </Typography>

      {error && <MuiAlert severity="error" sx={{ mb: 2 }}>{error}</MuiAlert>}

      {billing?.subscription_status === 'past_due' && (
        <MuiAlert
          severity="error"
          sx={{ mb: 2 }}
          action={
            <Button
              color="inherit"
              size="small"
              onClick={openPortal}
              disabled={portalLoading}
            >
              {portalLoading ? 'Opening…' : 'Update payment method'}
            </Button>
          }
        >
          Your last payment failed. Update your payment method to keep service running.
        </MuiAlert>
      )}

      {billing?.subscription_status === 'canceled' && (
        <MuiAlert severity="warning" sx={{ mb: 2 }}>
          Your subscription is canceled. You'll keep read access
          {billing.current_period_end
            ? ` until ${new Date(billing.current_period_end).toLocaleDateString()}`
            : ' until the end of your paid period'}
          , then your account moves to read-only.
        </MuiAlert>
      )}

      <Paper sx={{ p: 3, mb: 3 }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems={{ sm: 'center' }}>
          <Box sx={{ flex: 1 }}>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
              <Typography variant="h2" sx={{ fontWeight: 700 }}>{plan.display_name}</Typography>
              <Chip label="Current plan" size="small" color="primary" variant="outlined" />
              {billing?.subscription_status && STATUS_LABEL[billing.subscription_status] && (
                <Chip
                  label={STATUS_LABEL[billing.subscription_status].label}
                  size="small"
                  color={STATUS_LABEL[billing.subscription_status].severity}
                  variant="outlined"
                />
              )}
            </Stack>
            <Typography variant="body2" color="text.secondary">{plan.description}</Typography>
          </Box>
          <Box sx={{ textAlign: { sm: 'right' } }}>
            <Typography variant="h2" sx={{ fontWeight: 700 }}>
              ${plan.monthly_price_usd}<Typography component="span" variant="body2" color="text.secondary">/mo</Typography>
            </Typography>
            {billing?.has_payment_method && (
              <Button
                variant="outlined"
                size="small"
                startIcon={<OpenInNewIcon />}
                onClick={openPortal}
                disabled={portalLoading}
                sx={{ mt: 1 }}
              >
                {portalLoading ? 'Opening…' : 'Manage subscription'}
              </Button>
            )}
          </Box>
        </Stack>
        <Grid container spacing={2} sx={{ mt: 2 }}>
          <Grid item xs={6} sm={3}>
            <Typography variant="caption" color="text.secondary">Tools</Typography>
            <Typography variant="h4" sx={{ fontWeight: 600 }}>{plan.tool_cap}</Typography>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Typography variant="caption" color="text.secondary">Seats</Typography>
            <Typography variant="h4" sx={{ fontWeight: 600 }}>{plan.seat_cap}</Typography>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Typography variant="caption" color="text.secondary">Audit retention</Typography>
            <Typography variant="h4" sx={{ fontWeight: 600 }}>
              {Math.round(plan.audit_retention_days / 365)} yr
            </Typography>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Typography variant="caption" color="text.secondary">BAA</Typography>
            <Typography variant="h4" sx={{ fontWeight: 600 }}>
              {plan.baa_mode === 'click_through' ? 'Click-through' : 'Executed'}
            </Typography>
          </Grid>
        </Grid>
      </Paper>

      {plan.upgrade_options.length > 0 && (
        <Box>
          <Typography variant="h3" sx={{ fontWeight: 600, mb: 2 }}>
            {t('common.upgrade_plan')}
          </Typography>
          <Grid container spacing={2}>
            {allPlans
              .filter((p) => plan.upgrade_options.includes(p.tier))
              .map((p) => (
                <Grid item xs={12} md={6} key={p.tier}>
                  <Card>
                    <CardContent>
                      <Typography variant="h3" sx={{ fontWeight: 700 }}>{p.display_name}</Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>{p.description}</Typography>
                      <Typography variant="h2" sx={{ fontWeight: 700, mb: 2 }}>
                        ${p.monthly_price_usd}<Typography component="span" variant="body2" color="text.secondary">/mo</Typography>
                      </Typography>
                      <Button
                        variant="contained"
                        fullWidth
                        disabled={!p.payment_link_url}
                        onClick={() => p.payment_link_url && window.open(p.payment_link_url, '_blank')}
                      >
                        {p.payment_link_url ? `Upgrade to ${p.display_name}` : 'Contact sales'}
                      </Button>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
          </Grid>
        </Box>
      )}
    </Box>
  );
};

export default Billing;
