import React from 'react';
import {
  Box, Typography, Grid, Paper, Chip, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, LinearProgress, Alert,
  Skeleton, IconButton,
} from '@mui/material';
import SpeedIcon from '@mui/icons-material/Speed';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { getRiskPortfolio } from '@/api/healthcare';
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

interface StatCardProps {
  label: string;
  value: string | number;
  color?: string;
}

function StatCard({ label, value, color }: StatCardProps) {
  return (
    <Paper sx={{ p: 2.5, textAlign: 'center' }}>
      <Typography variant="h4" sx={{ fontWeight: 700, color: color ?? 'text.primary' }}>
        {value}
      </Typography>
      <Typography variant="body2" color="text.secondary">{label}</Typography>
    </Paper>
  );
}

function SkeletonStatCards() {
  return (
    <>
      {[0, 1, 2, 3].map((i) => (
        <Grid item xs={12} sm={6} md={3} key={i}>
          <Paper sx={{ p: 2.5, textAlign: 'center' }}>
            <Skeleton variant="text" width="60%" sx={{ mx: 'auto' }} height={48} />
            <Skeleton variant="text" width="80%" sx={{ mx: 'auto' }} />
          </Paper>
        </Grid>
      ))}
    </>
  );
}

function SkeletonRows() {
  return (
    <>
      {[0, 1, 2, 3, 4].map((i) => (
        <TableRow key={i}>
          {[0, 1, 2, 3, 4, 5].map((j) => (
            <TableCell key={j}><Skeleton variant="text" /></TableCell>
          ))}
        </TableRow>
      ))}
    </>
  );
}

const RiskPortfolio: React.FC = () => {
  const navigate = useNavigate();
  const { data, isLoading, isError } = useQuery({
    queryKey: ['riskPortfolio'],
    queryFn: getRiskPortfolio,
  });

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 3 }}>
        <SpeedIcon sx={{ color: 'primary.main', fontSize: 28 }} />
        <Box>
          <Typography variant="h4">Risk Portfolio</Typography>
          <Typography variant="body2" color="text.secondary">
            Total Risk = (Severity × Exposure) + Regulatory Penalty
          </Typography>
        </Box>
      </Box>

      {isError && (
        <Alert severity="error" sx={{ mb: 3 }}>
          Failed to load risk portfolio data. Please try again.
        </Alert>
      )}

      <Grid container spacing={2} sx={{ mb: 3 }}>
        {isLoading ? (
          <SkeletonStatCards />
        ) : data ? (
          <>
            <Grid item xs={12} sm={6} md={3}>
              <StatCard label="Total Models" value={data.total_models} />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <StatCard label="Avg Risk Score" value={data.avg_risk.toFixed(1)} />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <StatCard
                label="Critical Count"
                value={data.by_risk_level.critical}
                color={RISK_COLORS.critical}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <StatCard
                label="High Count"
                value={data.by_risk_level.high}
                color={RISK_COLORS.high}
              />
            </Grid>
          </>
        ) : null}
      </Grid>

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Model ID</TableCell>
              <TableCell>Total Risk</TableCell>
              <TableCell>Risk Level</TableCell>
              <TableCell>Trend</TableCell>
              <TableCell>Computed At</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading ? (
              <SkeletonRows />
            ) : !data || data.models.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} align="center" sx={{ py: 4 }}>
                  <Typography color="text.secondary">No models found</Typography>
                </TableCell>
              </TableRow>
            ) : (
              data.models.map((row) => {
                const trend = trendDisplay(row.trend);
                return (
                  <TableRow key={row.model_id} hover>
                    <TableCell sx={{ fontFamily: 'monospace', fontSize: 13 }}>
                      {row.model_id}
                    </TableCell>
                    <TableCell sx={{ minWidth: 160 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <LinearProgress
                          variant="determinate"
                          value={Math.min(row.total_risk, 100)}
                          sx={{
                            flex: 1, height: 8, borderRadius: 4,
                            '& .MuiLinearProgress-bar': { backgroundColor: riskColor(row.risk_level) },
                          }}
                        />
                        <Typography variant="caption" sx={{ minWidth: 28 }}>
                          {row.total_risk.toFixed(0)}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={row.risk_level}
                        size="small"
                        sx={{
                          backgroundColor: riskColor(row.risk_level),
                          color: '#fff',
                          fontWeight: 600,
                          textTransform: 'capitalize',
                        }}
                      />
                    </TableCell>
                    <TableCell>
                      <Typography sx={{ color: trend.color, fontWeight: 700, fontSize: 18 }}>
                        {trend.label}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      {new Date(row.computed_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <IconButton
                        size="small"
                        onClick={() => navigate(`/risk/scores/${row.model_id}`)}
                        aria-label="View Detail"
                      >
                        <OpenInNewIcon fontSize="small" />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};

export default RiskPortfolio;
