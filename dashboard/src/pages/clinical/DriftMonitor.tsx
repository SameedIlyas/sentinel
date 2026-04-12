import React, { useState } from 'react';
import {
  Box, Typography, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, Paper, Chip, Alert, Skeleton,
} from '@mui/material';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import { useQuery } from '@tanstack/react-query';
import { listDriftMeasurements } from '@/api/healthcare';
import type { DriftStatus, DriftMeasurement } from '@/types';

const STATUS_FILTERS = ['All', 'ok', 'warning', 'alert'] as const;
type FilterValue = typeof STATUS_FILTERS[number];

const statusColor = (s: DriftStatus): 'success' | 'warning' | 'error' => {
  if (s === 'ok') return 'success';
  if (s === 'warning') return 'warning';
  return 'error';
};

const psiColor = (psi: number): string => {
  if (psi < 0.1) return 'success.main';
  if (psi <= 0.25) return 'warning.main';
  return 'error.main';
};

const DriftMonitor: React.FC = () => {
  const [filter, setFilter] = useState<FilterValue>('All');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['driftMeasurements'],
    queryFn: () => listDriftMeasurements(),
  });

  const allItems: DriftMeasurement[] = data?.items ?? [];

  const filtered = filter === 'All' ? allItems : allItems.filter((m) => m.status === filter);

  const okCount = allItems.filter((m) => m.status === 'ok').length;
  const warnCount = allItems.filter((m) => m.status === 'warning').length;
  const alertCount = allItems.filter((m) => m.status === 'alert').length;

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 3 }}>
        <ShowChartIcon sx={{ color: 'primary.main', fontSize: 28 }} />
        <Typography variant="h4">Drift Monitor</Typography>
      </Box>

      <Box sx={{ display: 'flex', gap: 1.5, mb: 2, flexWrap: 'wrap' }}>
        <Chip label={`OK: ${okCount}`} color="success" size="small" variant="outlined" />
        <Chip label={`Warning: ${warnCount}`} color="warning" size="small" variant="outlined" />
        <Chip label={`Alert: ${alertCount}`} color="error" size="small" variant="outlined" />
      </Box>

      <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
        {STATUS_FILTERS.map((s) => (
          <Chip
            key={s}
            label={s === 'All' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
            onClick={() => setFilter(s)}
            color={filter === s ? 'primary' : 'default'}
            variant={filter === s ? 'filled' : 'outlined'}
          />
        ))}
      </Box>

      {isError && <Alert severity="error" sx={{ mb: 2 }}>Failed to load drift measurements.</Alert>}

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Baseline ID</TableCell>
              <TableCell>PSI Score</TableCell>
              <TableCell>KS Statistic</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Measured At</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading
              ? Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    {Array.from({ length: 5 }).map((__, j) => (
                      <TableCell key={j}><Skeleton variant="text" /></TableCell>
                    ))}
                  </TableRow>
                ))
              : !filtered.length
              ? (
                  <TableRow>
                    <TableCell colSpan={5} align="center" sx={{ py: 4 }}>
                      <Typography color="text.secondary">No drift measurements found</Typography>
                    </TableCell>
                  </TableRow>
                )
              : filtered.slice(0, 50).map((m) => (
                  <TableRow key={m.id} hover>
                    <TableCell>
                      {m.baseline_id.length > 20
                        ? `${m.baseline_id.slice(0, 20)}…`
                        : m.baseline_id}
                    </TableCell>
                    <TableCell sx={{ color: psiColor(m.psi_score), fontWeight: 600 }}>
                      {m.psi_score.toFixed(4)}
                    </TableCell>
                    <TableCell>
                      {m.ks_statistic != null ? m.ks_statistic.toFixed(4) : '—'}
                    </TableCell>
                    <TableCell>
                      <Chip label={m.status} color={statusColor(m.status)} size="small" />
                    </TableCell>
                    <TableCell>{new Date(m.measured_at).toLocaleString()}</TableCell>
                  </TableRow>
                ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};

export default DriftMonitor;
