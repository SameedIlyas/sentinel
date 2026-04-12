import React from 'react';
import {
  Box, Typography, Paper, Chip, Skeleton, Alert, Button,
  LinearProgress, Divider,
} from '@mui/material';
import BalanceIcon from '@mui/icons-material/Balance';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { getBiasAudit, runBiasAudit } from '@/api/healthcare';
import type { BiasAuditStatus } from '@/types';

const statusColor = (s: BiasAuditStatus): 'default' | 'warning' | 'success' | 'error' => {
  if (s === 'completed') return 'success';
  if (s === 'running') return 'warning';
  if (s === 'failed') return 'error';
  return 'default';
};

const dirColor = (ratio: number): string => {
  if (ratio > 0.8) return 'success.main';
  if (ratio >= 0.6) return 'warning.main';
  return 'error.main';
};

const BiasAuditDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();

  const { data: audit, isLoading, isError } = useQuery({
    queryKey: ['biasAudit', id],
    queryFn: () => getBiasAudit(id!),
    enabled: !!id,
  });

  const mutation = useMutation({
    mutationFn: () => runBiasAudit(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['biasAudit', id] });
    },
  });

  const canRunAudit = audit?.status === 'pending' || audit?.status === 'failed';

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 3 }}>
        <BalanceIcon sx={{ color: 'primary.main', fontSize: 28 }} />
        <Typography variant="h4">Bias Audit</Typography>
      </Box>

      {isError && <Alert severity="error" sx={{ mb: 2 }}>Failed to load bias audit.</Alert>}

      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>Audit Details</Typography>
        <Divider sx={{ mb: 2 }} />
        {isLoading ? (
          Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} variant="text" sx={{ mb: 1 }} />)
        ) : audit ? (
          <>
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 2 }}>
              <Box>
                <Typography variant="caption" color="text.secondary">Model Card ID</Typography>
                <Typography>{audit.model_card_id}</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">Status</Typography>
                <Box>
                  <Chip label={audit.status} color={statusColor(audit.status)} size="small" />
                </Box>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">Created</Typography>
                <Typography>{new Date(audit.created_at).toLocaleDateString()}</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">Completed</Typography>
                <Typography>
                  {audit.completed_at ? new Date(audit.completed_at).toLocaleDateString() : '—'}
                </Typography>
              </Box>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">Subgroups</Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.5 }}>
                {audit.subgroups.map((sg) => (
                  <Chip key={sg} label={sg} size="small" variant="outlined" />
                ))}
              </Box>
            </Box>
          </>
        ) : null}
      </Paper>

      {audit?.status === 'completed' && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>Metrics</Typography>
          <Divider sx={{ mb: 2 }} />

          {audit.overall_score != null && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" gutterBottom>
                Overall Score: {audit.overall_score.toFixed(1)}
              </Typography>
              <LinearProgress
                variant="determinate"
                value={Math.min(audit.overall_score, 100)}
                sx={{ height: 10, borderRadius: 1 }}
              />
            </Box>
          )}

          {audit.disparate_impact_ratio != null && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="caption" color="text.secondary">Disparate Impact Ratio</Typography>
              <Typography
                variant="h5"
                sx={{ color: dirColor(audit.disparate_impact_ratio), fontWeight: 700 }}
              >
                {audit.disparate_impact_ratio.toFixed(3)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {'(>0.8 = acceptable, 0.6–0.8 = marginal, <0.6 = concerning)'}
              </Typography>
            </Box>
          )}

          {audit.findings_summary && (
            <Box>
              <Typography variant="caption" color="text.secondary">Findings Summary</Typography>
              <Typography variant="body2" sx={{ mt: 0.5, whiteSpace: 'pre-wrap' }}>
                {audit.findings_summary}
              </Typography>
            </Box>
          )}
        </Paper>
      )}

      {audit && canRunAudit && (
        <Box>
          {mutation.isError && (
            <Alert severity="error" sx={{ mb: 2 }}>Failed to start audit. Please try again.</Alert>
          )}
          {mutation.isSuccess && (
            <Alert severity="success" sx={{ mb: 2 }}>Audit started successfully.</Alert>
          )}
          <Button
            variant="contained"
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
          >
            {mutation.isPending ? 'Starting…' : 'Run Audit'}
          </Button>
        </Box>
      )}
    </Box>
  );
};

export default BiasAuditDetail;
