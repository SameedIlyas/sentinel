import React, { useEffect, useState } from 'react';
import {
  Box, Typography, Stack, Card, CardContent, Chip, LinearProgress,
  Alert as MuiAlert, Paper,
} from '@mui/material';

import apiClient from '@/api/client';
import { useT } from '@/i18n';

interface ClinicAlert {
  id: string;
  timestamp: string;
  severity: string;
  severity_label: string;
  title: string;
  description: string;
  next_step: string | null;
  is_translated: boolean;
  acknowledged: boolean;
}

const SEV_COLOR: Record<string, 'default' | 'info' | 'warning' | 'error'> = {
  low: 'default',
  medium: 'info',
  high: 'warning',
  critical: 'error',
};

const AlertCenter: React.FC = () => {
  const t = useT();
  const [alerts, setAlerts] = useState<ClinicAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const data = await apiClient.get<ClinicAlert[]>('/v1/clinic/alerts');
        setAlerts(data);
      } catch (e: any) {
        setError(e?.response?.data?.detail || 'Could not load notifications');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <LinearProgress />;

  return (
    <Box>
      <Typography variant="h1" sx={{ fontWeight: 700, mb: 0.5 }}>
        {t('clinic.alerts.title')}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Recent things our system thinks you should look at.
      </Typography>

      {error && <MuiAlert severity="error" sx={{ mb: 2 }}>{error}</MuiAlert>}

      {alerts.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography color="text.secondary">{t('clinic.alerts.empty')}</Typography>
        </Paper>
      ) : (
        <Stack spacing={2}>
          {alerts.map((a) => (
            <Card key={a.id} sx={{ borderLeft: 4, borderColor: `${SEV_COLOR[a.severity] ?? 'default'}.main` }}>
              <CardContent>
                <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                  <Chip
                    label={a.severity_label}
                    size="small"
                    color={SEV_COLOR[a.severity] ?? 'default'}
                    variant="outlined"
                  />
                  <Typography variant="caption" color="text.secondary">
                    {new Date(a.timestamp).toLocaleString()}
                  </Typography>
                  {a.acknowledged && (
                    <Chip label={t('common.acknowledged')} size="small" variant="outlined" />
                  )}
                </Stack>
                <Typography variant="h4" sx={{ fontWeight: 600, mb: 0.5 }}>{a.title}</Typography>
                <Typography variant="body2" sx={{ mb: a.next_step ? 1.5 : 0 }}>{a.description}</Typography>
                {a.next_step && (
                  <Box
                    sx={{
                      mt: 1, p: 1.25, borderRadius: 1, bgcolor: 'action.hover',
                      borderLeft: 3, borderColor: 'primary.main',
                    }}
                  >
                    <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: 0.6 }}>
                      {t('clinic.alerts.next_step')}
                    </Typography>
                    <Typography variant="body2">{a.next_step}</Typography>
                  </Box>
                )}
              </CardContent>
            </Card>
          ))}
        </Stack>
      )}
    </Box>
  );
};

export default AlertCenter;
