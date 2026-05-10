import React, { useEffect, useState } from 'react';
import {
  Box, Typography, Stack, Paper, TextField, Button, Alert as MuiAlert,
  LinearProgress,
} from '@mui/material';

import apiClient from '@/api/client';
import { useT } from '@/i18n';

interface PracticeInfo {
  name: string;
  address: string | null;
  phone: string | null;
  primary_specialty: string | null;
  locations_count: number;
}

const PracticeSettings: React.FC = () => {
  const t = useT();
  const [data, setData] = useState<PracticeInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [snack, setSnack] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const d = await apiClient.get<PracticeInfo>('/v1/clinic/settings/practice');
        setData(d);
      } catch (e: any) {
        setError(e?.response?.data?.detail || 'Could not load');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const save = async () => {
    if (!data) return;
    setSaving(true);
    setError(null);
    try {
      await apiClient.put('/v1/clinic/settings/practice', {
        name: data.name,
        address: data.address ?? '',
        phone: data.phone ?? '',
        primary_specialty: data.primary_specialty ?? '',
      });
      setSnack(true);
      setTimeout(() => setSnack(false), 2000);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LinearProgress />;
  if (!data) return null;

  const set = <K extends keyof PracticeInfo>(k: K, v: PracticeInfo[K]) =>
    setData((prev) => (prev ? { ...prev, [k]: v } : prev));

  return (
    <Box sx={{ maxWidth: 720 }}>
      <Typography variant="h1" sx={{ fontWeight: 700, mb: 1 }}>
        {t('clinic.settings.practice')}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Practice details that show up in your reports and BAA.
      </Typography>

      {error && <MuiAlert severity="error" sx={{ mb: 2 }}>{error}</MuiAlert>}
      {snack && <MuiAlert severity="success" sx={{ mb: 2 }}>Saved.</MuiAlert>}

      <Paper sx={{ p: 3 }}>
        <Stack spacing={2.5}>
          <TextField
            label="Practice name"
            value={data.name}
            onChange={(e) => set('name', e.target.value)}
            fullWidth
          />
          <TextField
            label="Address"
            value={data.address ?? ''}
            onChange={(e) => set('address', e.target.value)}
            fullWidth
          />
          <TextField
            label="Phone"
            value={data.phone ?? ''}
            onChange={(e) => set('phone', e.target.value)}
            fullWidth
          />
          <TextField
            label="Primary specialty"
            value={data.primary_specialty ?? ''}
            onChange={(e) => set('primary_specialty', e.target.value)}
            fullWidth
            placeholder="Family medicine, pediatrics, …"
          />
          <Stack direction="row" justifyContent="flex-end">
            <Button variant="contained" onClick={save} disabled={saving}>
              {saving ? 'Saving…' : t('common.save')}
            </Button>
          </Stack>
        </Stack>
      </Paper>
    </Box>
  );
};

export default PracticeSettings;
