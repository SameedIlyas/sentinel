import React from 'react';
import {
  Box, Typography, Paper, Grid, Chip, LinearProgress, Alert,
  Skeleton, Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
} from '@mui/material';
import SpeedIcon from '@mui/icons-material/Speed';
import { useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { getRiskScore, getRiskHistory } from '@/api/healthcare';
import { RiskLevel, RiskTrend } from '@/types/index';

const RISK_COLORS: Record<RiskLevel, string> = {
  critical: '#df1b41',
  high: '#e87f17',
  medium: '#f59e0b',
  low: '#0ea371',
};

function riskColor(level: RiskLevel): string {
  return RISK_COLORS[level] ?? '#888';
}

function trendDisplay(trend: RiskTrend): { label: string; color: string } {
  if (trend === 'up') return { label: '↑', color: '#df1b41' };
  if (trend === 'down') return { label: '↓', color: '#0ea371' };
  return { label: '→', color: '#888' };
}

const RiskScoreDetail: React.FC = () => {
  const { modelId = '' } = useParams<{ modelId: string }>();

  const { data: score, isLoading: scoreLoading, isError: scoreError } = useQuery({
    queryKey: ['riskScore', modelId],
    queryFn: () => getRiskScore(modelId),
    enabled: !!modelId,
  });

  const { data: history, isLoading: historyLoading, isError: historyError } = useQuery({
    queryKey: ['riskHistory', modelId],
    queryFn: () => getRiskHistory(modelId),
    enabled: !!modelId,
  });

  const isLoading = scoreLoading || historyLoading;
  const isError = scoreError || historyError;

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 3 }}>
        <SpeedIcon sx={{ color: 'primary.main', fontSize: 28 }} />
        <Box>
          <Typography variant="h4">Risk Score Detail</Typography>
          <Typography variant="body2" color="text.secondary">
            Model: <code>{modelId}</code>
          </Typography>
        </Box>
      </Box>

      {isError && (
        <Alert severity="error" sx={{ mb: 3 }}>
          Failed to load risk score data. Please try again.
        </Alert>
      )}

      {isLoading ? (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Skeleton variant="text" width="30%" height={60} />
          <Skeleton variant="text" width="20%" />
          <Skeleton variant="rectangular" height={10} sx={{ mt: 2, borderRadius: 4 }} />
        </Paper>
      ) : score ? (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
            <Typography variant="h2" sx={{ fontWeight: 800, color: riskColor(score.risk_level) }}>
              {score.total_risk.toFixed(1)}
            </Typography>
            <Box>
              <Chip
                label={score.risk_level}
                sx={{
                  backgroundColor: riskColor(score.risk_level),
                  color: '#fff',
                  fontWeight: 700,
                  textTransform: 'capitalize',
                  mb: 0.5,
                  display: 'block',
                }}
              />
              <Typography variant="caption" color="text.secondary">
                {new Date(score.computed_at).toLocaleString()}
              </Typography>
            </Box>
          </Box>
          <LinearProgress
            variant="determinate"
            value={Math.min(score.total_risk, 100)}
            sx={{
              height: 12, borderRadius: 6,
              '& .MuiLinearProgress-bar': { backgroundColor: riskColor(score.risk_level) },
            }}
          />
        </Paper>
      ) : null}

      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2.5 }}>
            <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 2 }}>
              Severity Factors
            </Typography>
            {isLoading ? (
              [0, 1, 2].map((i) => <Skeleton key={i} variant="text" sx={{ mb: 1 }} />)
            ) : score ? (
              Object.entries(score.severity_factors).map(([key, val]) => (
                <Box key={key} sx={{ mb: 1.5 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                    <Typography variant="body2">{key.replace(/_/g, ' ')}</Typography>
                    <Typography variant="body2" fontWeight={600}>{val}</Typography>
                  </Box>
                  <LinearProgress
                    variant="determinate"
                    value={Math.min((val / 10) * 100, 100)}
                    sx={{ height: 6, borderRadius: 3 }}
                  />
                </Box>
              ))
            ) : null}
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2.5 }}>
            <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 2 }}>
              Exposure Factors
            </Typography>
            {isLoading ? (
              [0, 1].map((i) => <Skeleton key={i} variant="text" sx={{ mb: 1 }} />)
            ) : score ? (
              Object.entries(score.exposure_factors).map(([key, val]) => (
                <Box key={key} sx={{ mb: 1.5 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                    <Typography variant="body2">{key.replace(/_/g, ' ')}</Typography>
                    <Typography variant="body2" fontWeight={600}>{val}</Typography>
                  </Box>
                  <LinearProgress
                    variant="determinate"
                    value={Math.min((val / 10) * 100, 100)}
                    sx={{ height: 6, borderRadius: 3 }}
                  />
                </Box>
              ))
            ) : null}
          </Paper>
        </Grid>
      </Grid>

      <Paper sx={{ p: 2.5, mb: 3 }}>
        <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 2 }}>
          Regulatory Flags
        </Typography>
        {isLoading ? (
          <Skeleton variant="rectangular" height={36} width={200} />
        ) : score ? (
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {Object.entries(score.regulatory_flags).map(([flag, active]) => (
              <Chip
                key={flag}
                label={flag.toUpperCase()}
                size="small"
                sx={{
                  backgroundColor: active ? '#df1b41' : '#e0e0e0',
                  color: active ? '#fff' : '#555',
                  fontWeight: 600,
                }}
              />
            ))}
          </Box>
        ) : null}
      </Paper>

      <Paper>
        <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
          <Typography variant="subtitle1" fontWeight={700}>Risk History</Typography>
        </Box>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Date</TableCell>
                <TableCell>Total Risk</TableCell>
                <TableCell>Risk Level</TableCell>
                <TableCell>Delta</TableCell>
                <TableCell>Trend</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {historyLoading ? (
                [0, 1, 2].map((i) => (
                  <TableRow key={i}>
                    {[0, 1, 2, 3, 4].map((j) => (
                      <TableCell key={j}><Skeleton variant="text" /></TableCell>
                    ))}
                  </TableRow>
                ))
              ) : !history || history.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} align="center" sx={{ py: 3 }}>
                    <Typography color="text.secondary">No history available</Typography>
                  </TableCell>
                </TableRow>
              ) : (
                history.map((entry) => {
                  const trend = trendDisplay(entry.trend);
                  return (
                    <TableRow key={entry.id} hover>
                      <TableCell>{new Date(entry.computed_at).toLocaleDateString()}</TableCell>
                      <TableCell>{entry.total_risk.toFixed(1)}</TableCell>
                      <TableCell>
                        <Chip
                          label={entry.risk_level}
                          size="small"
                          sx={{
                            backgroundColor: riskColor(entry.risk_level),
                            color: '#fff',
                            textTransform: 'capitalize',
                            fontWeight: 600,
                          }}
                        />
                      </TableCell>
                      <TableCell>
                        {entry.delta !== undefined ? (
                          <Typography
                            variant="body2"
                            sx={{ color: entry.delta > 0 ? '#df1b41' : entry.delta < 0 ? '#0ea371' : '#888' }}
                          >
                            {entry.delta > 0 ? '+' : ''}{entry.delta.toFixed(1)}
                          </Typography>
                        ) : '—'}
                      </TableCell>
                      <TableCell>
                        <Typography sx={{ color: trend.color, fontWeight: 700, fontSize: 16 }}>
                          {trend.label}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>
    </Box>
  );
};

export default RiskScoreDetail;
