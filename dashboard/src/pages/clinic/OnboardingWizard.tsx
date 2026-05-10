import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Typography, Stepper, Step, StepLabel, Button, Stack, Paper,
  TextField, FormControlLabel, Checkbox, Alert as MuiAlert, LinearProgress,
} from '@mui/material';

import apiClient from '@/api/client';
import { useT } from '@/i18n';

interface OnboardingState {
  step: number;
  baa_accepted_at: string | null;
  first_tool_registered: boolean;
  extension_enabled: boolean;
  completed_at: string | null;
}

interface BaaStatus {
  signed: boolean;
  mode: string;
  plan_display_name: string;
  can_self_accept: boolean;
}

const OnboardingWizard: React.FC = () => {
  const t = useT();
  const navigate = useNavigate();
  const [state, setState] = useState<OnboardingState | null>(null);
  const [baaStatus, setBaaStatus] = useState<BaaStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // BAA form
  const [orgLegalName, setOrgLegalName] = useState('');
  const [accepterName, setAccepterName] = useState('');
  const [accepterTitle, setAccepterTitle] = useState('');
  const [agreed, setAgreed] = useState(false);
  const [signing, setSigning] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [s, b] = await Promise.all([
          apiClient.get<OnboardingState>('/v1/clinic/onboarding'),
          apiClient.get<BaaStatus>('/v1/clinic/baa/status'),
        ]);
        setState(s);
        setBaaStatus(b);
      } catch (e: any) {
        setError(e?.response?.data?.detail || 'Could not load onboarding');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const advance = async (next: number) => {
    const s = await apiClient.post<OnboardingState>('/v1/clinic/onboarding/advance', { step: next });
    setState(s);
  };

  const signBaa = async () => {
    setSigning(true);
    setError(null);
    try {
      await apiClient.post<BaaStatus>('/v1/clinic/baa/accept', {
        organization_legal_name: orgLegalName,
        accepter_full_name: accepterName,
        accepter_title: accepterTitle,
      });
      const fresh = await apiClient.get<BaaStatus>('/v1/clinic/baa/status');
      setBaaStatus(fresh);
      await advance(1);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'BAA acceptance failed');
    } finally {
      setSigning(false);
    }
  };

  const enableExtension = async () => {
    await apiClient.post('/v1/clinic/onboarding/extension-enabled');
    await advance(3);
  };

  if (loading) return <LinearProgress />;
  if (!state) return null;

  const steps = [t('clinic.onboarding.step.baa'), t('clinic.onboarding.step.tool'), t('clinic.onboarding.step.extension')];

  if (state.completed_at) {
    return (
      <Paper sx={{ p: 4, textAlign: 'center', maxWidth: 640, mx: 'auto' }}>
        <Typography variant="h2" sx={{ fontWeight: 700, mb: 1 }}>
          {t('clinic.onboarding.complete')}
        </Typography>
        <Button variant="contained" onClick={() => navigate('/clinic')}>
          Go to dashboard
        </Button>
      </Paper>
    );
  }

  return (
    <Box sx={{ maxWidth: 760, mx: 'auto' }}>
      <Typography variant="h1" sx={{ fontWeight: 700, mb: 1 }}>
        {t('clinic.onboarding.title')}
      </Typography>

      <Stepper activeStep={state.step} sx={{ mb: 4 }}>
        {steps.map((label) => (
          <Step key={label}><StepLabel>{label}</StepLabel></Step>
        ))}
      </Stepper>

      {error && <MuiAlert severity="error" sx={{ mb: 2 }}>{error}</MuiAlert>}

      {/* Step 0 — BAA */}
      {state.step === 0 && baaStatus && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h3" sx={{ fontWeight: 600, mb: 1 }}>
            {t('clinic.settings.baa.title')}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {baaStatus.can_self_accept
              ? t('clinic.settings.baa.click_through_intro')
              : t('clinic.settings.baa.executed_intro')}
          </Typography>
          {baaStatus.can_self_accept ? (
            <Stack spacing={2}>
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
                placeholder="Practice owner / Office manager"
              />
              <FormControlLabel
                control={<Checkbox checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />}
                label="I'm authorized to sign this BAA on behalf of the practice."
              />
              <Stack direction="row" spacing={1} justifyContent="flex-end">
                <Button onClick={() => navigate('/clinic')}>{t('clinic.onboarding.skip')}</Button>
                <Button
                  variant="contained"
                  disabled={!agreed || !orgLegalName || !accepterName || !accepterTitle || signing}
                  onClick={signBaa}
                >
                  {signing ? 'Signing…' : t('clinic.settings.baa.accept_button')}
                </Button>
              </Stack>
            </Stack>
          ) : (
            <Stack direction="row" spacing={1} justifyContent="flex-end">
              <Button variant="contained" onClick={() => advance(1)}>{t('clinic.onboarding.next')}</Button>
            </Stack>
          )}
        </Paper>
      )}

      {/* Step 1 — first tool */}
      {state.step === 1 && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h3" sx={{ fontWeight: 600, mb: 1 }}>
            Register your first AI tool
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Even one tool is plenty to start. You can always add more later.
          </Typography>
          <Stack direction="row" spacing={1} justifyContent="flex-end">
            <Button onClick={() => advance(0)}>{t('clinic.onboarding.back')}</Button>
            <Button onClick={() => advance(2)}>{t('clinic.onboarding.skip')}</Button>
            <Button variant="contained" onClick={() => navigate('/clinic/tools/new')}>
              Register a tool
            </Button>
          </Stack>
        </Paper>
      )}

      {/* Step 2 — extension */}
      {state.step === 2 && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h3" sx={{ fontWeight: 600, mb: 1 }}>
            Install the Shadow-AI watcher
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            A small browser extension that flags when staff use AI tools you didn't
            register. It never sends patient information — only domain names and
            tool fingerprints come back.
          </Typography>
          <Stack direction="row" spacing={1} justifyContent="flex-end">
            <Button onClick={() => advance(1)}>{t('clinic.onboarding.back')}</Button>
            <Button onClick={() => advance(3)}>{t('clinic.onboarding.skip')}</Button>
            <Button variant="outlined" onClick={() => navigate('/clinic/shadow-ai')}>
              Get install token
            </Button>
            <Button variant="contained" onClick={enableExtension}>
              {t('clinic.onboarding.finish')}
            </Button>
          </Stack>
        </Paper>
      )}
    </Box>
  );
};

export default OnboardingWizard;
