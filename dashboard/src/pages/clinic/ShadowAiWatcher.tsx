import React, { useEffect, useState } from 'react';
import {
  Box, Typography, Stack, Button, Card, Table, TableHead, TableRow, TableCell,
  TableBody, Chip, IconButton, Paper, LinearProgress, Alert as MuiAlert,
  TextField, Tooltip,
} from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import RefreshIcon from '@mui/icons-material/Refresh';
import CheckIcon from '@mui/icons-material/Check';

import apiClient from '@/api/client';
import { useT } from '@/i18n';

interface Observation {
  id: string;
  host: string;
  tool_fingerprint: string | null;
  severity: string;
  observed_at: string;
  extension_version: string | null;
  acknowledged: boolean;
}

interface TokenStatus {
  has_active_token: boolean;
  issued_at: string | null;
  last_used_at: string | null;
}

interface IssuedToken {
  token: string;
  issued_at: string;
  warning: string;
}

const ShadowAiWatcher: React.FC = () => {
  const t = useT();
  const [obs, setObs] = useState<Observation[]>([]);
  const [tokenStatus, setTokenStatus] = useState<TokenStatus | null>(null);
  const [issued, setIssued] = useState<IssuedToken | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [confirmRotate, setConfirmRotate] = useState(false);

  const refresh = async () => {
    setLoading(true);
    try {
      const [rows, status] = await Promise.all([
        apiClient.get<Observation[]>('/v1/clinic/shadow-ai/observations'),
        apiClient.get<TokenStatus>('/v1/clinic/shadow-ai/extension-token/status'),
      ]);
      setObs(rows);
      setTokenStatus(status);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Could not load observations');
    } finally {
      setLoading(false);
    }
  };

  const issueToken = async () => {
    setError(null);
    try {
      const resp = await apiClient.post<IssuedToken>('/v1/clinic/shadow-ai/extension-token');
      setIssued(resp);
      setTokenStatus({
        has_active_token: true,
        issued_at: resp.issued_at,
        last_used_at: null,
      });
      setConfirmRotate(false);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Could not issue token');
    }
  };

  const acknowledge = async (id: string) => {
    try {
      await apiClient.post(`/v1/clinic/shadow-ai/observations/${id}/acknowledge`);
      setObs((prev) => prev.map((o) => (o.id === id ? { ...o, acknowledged: true } : o)));
    } catch {
      // soft fail
    }
  };

  useEffect(() => { refresh(); }, []);

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 3 }}>
        <Box>
          <Typography variant="h1" sx={{ fontWeight: 700 }}>{t('clinic.shadow_ai.title')}</Typography>
          <Typography variant="body2" color="text.secondary">
            {t('clinic.shadow_ai.subtitle')}
          </Typography>
        </Box>
        <Stack direction="row" spacing={1}>
          <IconButton onClick={refresh} disabled={loading}>
            <RefreshIcon />
          </IconButton>
        </Stack>
      </Stack>

      {error && <MuiAlert severity="error" sx={{ mb: 2 }}>{error}</MuiAlert>}

      <Paper sx={{ p: 2.5, mb: 3 }}>
        <Typography variant="h4" sx={{ fontWeight: 600, mb: 1 }}>Browser extension</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Install the Sentinel browser extension on each clinic device. It watches
          for AI tools without sending any patient information — only domain names
          and tool fingerprints come back.
        </Typography>

        {/* Just-issued: show plaintext once, with one-time-only warning. */}
        {issued ? (
          <Box>
            <MuiAlert severity="warning" sx={{ mb: 1.5 }}>{issued.warning}</MuiAlert>
            <Typography variant="caption" sx={{ textTransform: 'uppercase', letterSpacing: 0.6 }}>
              {t('clinic.shadow_ai.token_label')}
            </Typography>
            <Stack direction="row" spacing={1} alignItems="center">
              <TextField value={issued.token} fullWidth InputProps={{ readOnly: true }} sx={{ fontFamily: 'monospace' }} />
              <Tooltip title="Copy">
                <IconButton onClick={() => navigator.clipboard.writeText(issued.token)}>
                  <ContentCopyIcon />
                </IconButton>
              </Tooltip>
            </Stack>
            <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
              <Button variant="outlined" onClick={() => setIssued(null)}>I've saved it</Button>
            </Stack>
          </Box>
        ) : tokenStatus?.has_active_token ? (
          <Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
              An active extension token is on file
              {tokenStatus.issued_at
                ? ` (issued ${new Date(tokenStatus.issued_at).toLocaleDateString()})`
                : ''}
              {tokenStatus.last_used_at
                ? ` — last used ${new Date(tokenStatus.last_used_at).toLocaleDateString()}`
                : ' — no observations yet'}
              . For security we only show the token once at issuance.
            </Typography>
            {confirmRotate ? (
              <Stack direction="row" spacing={1}>
                <Button variant="contained" color="error" onClick={issueToken}>
                  Yes, rotate token
                </Button>
                <Button onClick={() => setConfirmRotate(false)}>Cancel</Button>
              </Stack>
            ) : (
              <Button variant="outlined" onClick={() => setConfirmRotate(true)}>
                Rotate token
              </Button>
            )}
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
              Rotating immediately revokes the previous token. Update each
              installed extension with the new value.
            </Typography>
          </Box>
        ) : (
          <Button variant="contained" onClick={issueToken}>
            Get extension token
          </Button>
        )}
      </Paper>

      {loading ? (
        <LinearProgress />
      ) : obs.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography color="text.secondary">{t('clinic.shadow_ai.empty')}</Typography>
        </Paper>
      ) : (
        <Card>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Host</TableCell>
                <TableCell>Detected as</TableCell>
                <TableCell>Severity</TableCell>
                <TableCell>Observed</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {obs.map((o) => (
                <TableRow key={o.id} hover>
                  <TableCell sx={{ fontFamily: 'monospace' }}>{o.host}</TableCell>
                  <TableCell>{o.tool_fingerprint ?? '—'}</TableCell>
                  <TableCell>
                    <Chip
                      label={o.severity}
                      size="small"
                      color={o.severity === 'critical' ? 'error' : o.severity === 'high' ? 'warning' : 'default'}
                    />
                  </TableCell>
                  <TableCell>{new Date(o.observed_at).toLocaleString()}</TableCell>
                  <TableCell align="right">
                    {o.acknowledged ? (
                      <Chip icon={<CheckIcon />} label={t('common.acknowledged')} size="small" variant="outlined" />
                    ) : (
                      <Button size="small" onClick={() => acknowledge(o.id)}>
                        {t('common.acknowledge')}
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </Box>
  );
};

export default ShadowAiWatcher;
