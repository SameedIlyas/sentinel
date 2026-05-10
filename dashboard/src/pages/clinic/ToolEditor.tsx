import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Box, Typography, Button, TextField, MenuItem, Stack, FormControlLabel,
  Switch, Alert as MuiAlert, Paper, LinearProgress, Divider,
} from '@mui/material';

import apiClient from '@/api/client';
import { useT } from '@/i18n';

interface ToolForm {
  name: string;
  vendor: string;
  category: string;
  purpose: string;
  handles_phi: boolean;
  risk_level: string;
  notes: string;
}

const CATEGORIES = [
  { value: 'ambient_scribe', label: 'Ambient scribe' },
  { value: 'documentation', label: 'Documentation help' },
  { value: 'decision_support', label: 'Clinical decision support' },
  { value: 'imaging', label: 'Imaging / radiology' },
  { value: 'patient_communication', label: 'Patient communication' },
  { value: 'revenue_cycle', label: 'Billing / revenue cycle' },
  { value: 'other', label: 'Other' },
];

const RISKS = [
  { value: 'low', label: 'Low — informational' },
  { value: 'medium', label: 'Medium — affects workflow' },
  { value: 'high', label: 'High — affects clinical or financial decisions' },
];

const empty: ToolForm = {
  name: '',
  vendor: '',
  category: 'other',
  purpose: '',
  handles_phi: false,
  risk_level: 'low',
  notes: '',
};

const ToolEditor: React.FC = () => {
  const t = useT();
  const navigate = useNavigate();
  const { id } = useParams();
  const isEdit = Boolean(id);

  const [form, setForm] = useState<ToolForm>(empty);
  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isEdit) return;
    (async () => {
      try {
        const data = await apiClient.get<ToolForm>(`/v1/clinic/tools/${id}`);
        setForm({
          name: data.name ?? '',
          vendor: data.vendor ?? '',
          category: data.category ?? 'other',
          purpose: data.purpose ?? '',
          handles_phi: !!data.handles_phi,
          risk_level: data.risk_level ?? 'low',
          notes: data.notes ?? '',
        });
      } catch (e: any) {
        setError(e?.response?.data?.detail || 'Could not load tool');
      } finally {
        setLoading(false);
      }
    })();
  }, [id, isEdit]);

  const set = <K extends keyof ToolForm>(key: K, value: ToolForm[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const submit = async () => {
    setSaving(true);
    setError(null);
    try {
      if (isEdit) {
        await apiClient.put(`/v1/clinic/tools/${id}`, form);
      } else {
        await apiClient.post('/v1/clinic/tools', form);
      }
      navigate('/clinic/tools');
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      // Surface the PHI-rejection message in plain English instead of the
      // raw 422 envelope.
      if (detail && typeof detail === 'object' && detail.error === 'phi_in_freetext') {
        setError(
          detail.message
            || `Please remove patient information from the "${detail.field}" field.`
        );
      } else if (detail && typeof detail === 'object' && detail.error === 'baa_required') {
        setError(
          'Your Business Associate Agreement is not on file yet — sign your BAA in Practice Settings → Compliance before adding tools.'
        );
      } else {
        setError(typeof detail === 'string' ? detail : 'Save failed');
      }
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LinearProgress />;

  return (
    <Box sx={{ maxWidth: 720 }}>
      <Typography variant="h1" sx={{ fontWeight: 700, mb: 1 }}>
        {isEdit ? 'Edit AI tool' : t('clinic.tools.add')}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Tell us about an AI tool your practice uses. The more honest you are
        about whether it sees patient information and how risky it feels, the
        better the platform protects you.
      </Typography>

      <MuiAlert severity="info" sx={{ mb: 3 }}>
        <strong>Don't paste patient information here.</strong> These fields
        describe the tool — not the people who use it. Names, dates of
        birth, MRNs, SSNs, and phone numbers will be rejected.
      </MuiAlert>

      {error && <MuiAlert severity="error" sx={{ mb: 2 }}>{error}</MuiAlert>}

      <Paper sx={{ p: 3 }}>
        <Stack spacing={2.5}>
          <TextField
            label={t('clinic.tools.field.name')}
            value={form.name}
            onChange={(e) => set('name', e.target.value)}
            required
            fullWidth
            placeholder="e.g., Nuance DAX, Doximity Ambient"
          />
          <TextField
            label={t('clinic.tools.field.vendor')}
            value={form.vendor}
            onChange={(e) => set('vendor', e.target.value)}
            fullWidth
            placeholder="The company that makes it"
          />
          <TextField
            select
            label={t('clinic.tools.field.category')}
            value={form.category}
            onChange={(e) => set('category', e.target.value)}
            fullWidth
          >
            {CATEGORIES.map((c) => (
              <MenuItem key={c.value} value={c.value}>{c.label}</MenuItem>
            ))}
          </TextField>
          <TextField
            label={t('clinic.tools.field.purpose')}
            value={form.purpose}
            onChange={(e) => set('purpose', e.target.value)}
            fullWidth
            multiline
            rows={2}
            placeholder="What do you use it for?"
          />
          <Divider />
          <FormControlLabel
            control={
              <Switch
                checked={form.handles_phi}
                onChange={(e) => set('handles_phi', e.target.checked)}
              />
            }
            label={t('clinic.tools.field.handles_phi')}
          />
          <TextField
            select
            label={t('clinic.tools.field.risk_level')}
            value={form.risk_level}
            onChange={(e) => set('risk_level', e.target.value)}
            fullWidth
          >
            {RISKS.map((r) => (
              <MenuItem key={r.value} value={r.value}>{r.label}</MenuItem>
            ))}
          </TextField>
          <TextField
            label={t('clinic.tools.field.notes')}
            value={form.notes}
            onChange={(e) => set('notes', e.target.value)}
            fullWidth
            multiline
            rows={3}
          />
          <Stack direction="row" spacing={1} justifyContent="flex-end">
            <Button onClick={() => navigate('/clinic/tools')} disabled={saving}>
              {t('common.cancel')}
            </Button>
            <Button variant="contained" onClick={submit} disabled={saving || !form.name}>
              {saving ? 'Saving…' : t('common.save')}
            </Button>
          </Stack>
        </Stack>
      </Paper>
    </Box>
  );
};

export default ToolEditor;
