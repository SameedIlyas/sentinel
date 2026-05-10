import React, { useEffect, useState } from 'react';
import {
  Box, Typography, Paper, Stack, TextField, Button, Alert as MuiAlert,
  Chip, Checkbox, FormControlLabel, LinearProgress, Divider,
} from '@mui/material';
import HealthAndSafetyIcon from '@mui/icons-material/HealthAndSafety';

import apiClient from '@/api/client';
import { useT } from '@/i18n';

interface BaaStatus {
  signed: boolean;
  signed_at: string | null;
  mode: string;
  plan: string;
  plan_display_name: string;
  can_self_accept: boolean;
}

const Compliance: React.FC = () => {
  const t = useT();
  const [status, setStatus] = useState<BaaStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Click-through form
  const [orgLegalName, setOrgLegalName] = useState('');
  const [accepterName, setAccepterName] = useState('');
  const [accepterTitle, setAccepterTitle] = useState('');
  const [agreed, setAgreed] = useState(false);
  const [signing, setSigning] = useState(false);

  const refresh = async () => {
    try {
      const s = await apiClient.get<BaaStatus>('/v1/clinic/baa/status');
      setStatus(s);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Could not load BAA status');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refresh(); }, []);

  const sign = async () => {
    setSigning(true);
    setError(null);
    try {
      await apiClient.post('/v1/clinic/baa/accept', {
        organization_legal_name: orgLegalName,
        accepter_full_name: accepterName,
        accepter_title: accepterTitle,
      });
      await refresh();
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'BAA acceptance failed');
    } finally {
      setSigning(false);
    }
  };

  if (loading) return <LinearProgress />;
  if (!status) return null;

  return (
    <Box sx={{ maxWidth: 720 }}>
      <Typography variant="h1" sx={{ fontWeight: 700, mb: 1 }}>
        {t('clinic.settings.compliance')}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        HIPAA Business Associate Agreement and audit posture.
      </Typography>

      {error && <MuiAlert severity="error" sx={{ mb: 2 }}>{error}</MuiAlert>}

      <Paper sx={{ p: 3 }}>
        <Stack direction="row" alignItems="center" spacing={2} sx={{ mb: 1.5 }}>
          <HealthAndSafetyIcon color="primary" />
          <Typography variant="h3" sx={{ fontWeight: 600 }}>
            {t('clinic.settings.baa.title')}
          </Typography>
          {status.signed && (
            <Chip label="On file" size="small" color="success" variant="outlined" />
          )}
        </Stack>

        {status.signed ? (
          <Box>
            <Typography variant="body2" color="text.secondary">
              {t('clinic.settings.baa.signed_on')}{' '}
              {status.signed_at && new Date(status.signed_at).toLocaleDateString()}
              {' · '}
              <Chip label={status.plan_display_name} size="small" sx={{ ml: 1 }} />
            </Typography>
          </Box>
        ) : status.can_self_accept ? (
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Typography variant="body2">
              {t('clinic.settings.baa.click_through_intro')}
            </Typography>
            <Divider />
            <TextField
              label="Practice legal name"
              value={orgLegalName}
              onChange={(e) => setOrgLegalName(e.target.value)}
              fullWidth
            />
            <TextField
              label="Your full name"
              value={accepterName}
              onChange={(e) => setAccepterName(e.target.value)}
              fullWidth
            />
            <TextField
              label="Your title"
              value={accepterTitle}
              onChange={(e) => setAccepterTitle(e.target.value)}
              fullWidth
            />
            <FormControlLabel
              control={<Checkbox checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />}
              label="I'm authorized to sign this BAA for the practice."
            />
            <Stack direction="row" justifyContent="flex-end">
              <Button
                variant="contained"
                disabled={!agreed || !orgLegalName || !accepterName || !accepterTitle || signing}
                onClick={sign}
              >
                {signing ? 'Signing…' : t('clinic.settings.baa.accept_button')}
              </Button>
            </Stack>
          </Stack>
        ) : (
          <Typography variant="body2" color="text.secondary">
            {t('clinic.settings.baa.executed_intro')}
          </Typography>
        )}
      </Paper>
    </Box>
  );
};

export default Compliance;
