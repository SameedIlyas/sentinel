import React, { useEffect, useState } from 'react';
import {
  Box, Typography, Button, Stack, Card, CardContent, Chip, LinearProgress,
  Alert as MuiAlert, Snackbar,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';

import apiClient from '@/api/client';
import { useT } from '@/i18n';

interface Template {
  template_id: string;
  name: string;
  description: string;
  why_it_matters: string;
  policy_type: string;
  priority: number;
  recommended_for_tiers: string[];
}

const PolicyLibrary: React.FC = () => {
  const t = useT();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [applied, setApplied] = useState<Set<string>>(new Set());
  const [applyingId, setApplyingId] = useState<string | null>(null);
  const [snack, setSnack] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const data = await apiClient.get<Template[]>('/v1/clinic/policy-templates');
        setTemplates(data);
      } catch (e: any) {
        setError(e?.response?.data?.detail || 'Could not load templates');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const apply = async (id: string) => {
    setApplyingId(id);
    try {
      await apiClient.post('/v1/clinic/policy-templates/apply', { template_id: id });
      setApplied((prev) => new Set(prev).add(id));
      setSnack('Practice rule applied');
    } catch (e: any) {
      setSnack(e?.response?.data?.detail || 'Could not apply rule');
    } finally {
      setApplyingId(null);
    }
  };

  if (loading) return <LinearProgress />;

  return (
    <Box>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h1" sx={{ fontWeight: 700 }}>{t('clinic.policies.title')}</Typography>
        <Typography variant="body2" color="text.secondary">
          {t('clinic.policies.subtitle')}
        </Typography>
      </Box>

      {error && <MuiAlert severity="error" sx={{ mb: 2 }}>{error}</MuiAlert>}

      <Stack spacing={2}>
        {templates.map((tpl) => {
          const isApplied = applied.has(tpl.template_id);
          const applying = applyingId === tpl.template_id;
          return (
            <Card key={tpl.template_id}>
              <CardContent>
                <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} alignItems="flex-start">
                  <Box sx={{ flex: 1 }}>
                    <Stack direction="row" spacing={1} sx={{ mb: 0.5 }}>
                      <Typography variant="h4" sx={{ fontWeight: 600 }}>{tpl.name}</Typography>
                      {isApplied && (
                        <Chip
                          label={t('clinic.policies.applied')}
                          size="small"
                          color="success"
                          icon={<CheckCircleIcon />}
                        />
                      )}
                    </Stack>
                    <Typography variant="body2" sx={{ mb: 1.5 }}>{tpl.description}</Typography>
                    <Box
                      sx={{
                        bgcolor: 'action.hover',
                        borderRadius: 1,
                        p: 1.5,
                        borderLeft: 3,
                        borderColor: 'primary.main',
                      }}
                    >
                      <Typography variant="caption" sx={{ color: 'text.secondary', textTransform: 'uppercase', letterSpacing: 0.6 }}>
                        {t('clinic.policies.why_it_matters')}
                      </Typography>
                      <Typography variant="body2">{tpl.why_it_matters}</Typography>
                    </Box>
                  </Box>
                  <Box>
                    <Button
                      variant={isApplied ? 'outlined' : 'contained'}
                      onClick={() => apply(tpl.template_id)}
                      disabled={applying || isApplied}
                    >
                      {isApplied ? 'Applied' : applying ? 'Applying…' : t('clinic.policies.apply')}
                    </Button>
                  </Box>
                </Stack>
              </CardContent>
            </Card>
          );
        })}
      </Stack>

      <Snackbar
        open={!!snack}
        autoHideDuration={3500}
        onClose={() => setSnack(null)}
        message={snack ?? ''}
      />
    </Box>
  );
};

export default PolicyLibrary;
