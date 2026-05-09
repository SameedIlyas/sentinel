import React, { useState } from 'react';
import {
  Box, Typography, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, Paper, Chip, Alert, Skeleton,
} from '@mui/material';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import { useQuery } from '@tanstack/react-query';
import { listDriftMeasurements } from '@/api/healthcare';
import type { DriftMeasurement } from '@/types';
import EmptyState from '@/components/common/EmptyState';

const STATUS_FILTERS = ['All', 'low', 'medium', 'high', 'critical'] as const;
type FilterValue = typeof STATUS_FILTERS[number];

const DriftMonitor: React.FC = () => {
  const [filter, setFilter] = useState<FilterValue>('All');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['driftMeasurements'],
    queryFn: () => listDriftMeasurements(),
  });

  const allItems: DriftMeasurement[] = data?.items ?? [];
  const severityOf = (m: DriftMeasurement): string =>
    ((m as unknown as { severity?: string }).severity ?? 'medium').toLowerCase();

  const filtered = filter === 'All' ? allItems : allItems.filter((m) => severityOf(m) === filter);

  const lowCount      = allItems.filter((m) => severityOf(m) === 'low').length;
  const mediumCount   = allItems.filter((m) => severityOf(m) === 'medium').length;
  const highCount     = allItems.filter((m) => severityOf(m) === 'high').length;
  const criticalCount = allItems.filter((m) => severityOf(m) === 'critical').length;

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 3 }}>
        <ShowChartIcon sx={{ color: 'primary.main', fontSize: 28 }} />
        <Typography variant="h4">Drift Monitor</Typography>
      </Box>

      <Box sx={{ display: 'flex', gap: 1.5, mb: 2, flexWrap: 'wrap' }}>
        <Chip label={`Low: ${lowCount}`} color="success" size="small" variant="outlined" />
        <Chip label={`Medium: ${mediumCount}`} color="warning" size="small" variant="outlined" />
        <Chip label={`High: ${highCount}`} color="error" size="small" variant="outlined" />
        <Chip label={`Critical: ${criticalCount}`} color="error" size="small" variant="filled" />
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
              <TableCell>Alert Type</TableCell>
              <TableCell>Severity / PSI</TableCell>
              <TableCell>Message</TableCell>
              <TableCell>Acknowledged</TableCell>
              <TableCell>Created At</TableCell>
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
                    <TableCell colSpan={5} sx={{ p: 0, border: 0 }}>
                      <EmptyState
                        title={filter !== 'All' ? `No ${filter} drift measurements` : 'No drift measurements yet'}
                        description="Drift monitoring tracks how each model's input distribution and performance change over time vs. its training baseline. PSI > 0.2 or KS p-value < 0.01 suggests the model may need retraining."
                        ingestHint="Today: register a baseline via POST /v1/clinical/drift/baselines and POST measurements as you score new data. Roadmap: SDK helper that streams inference logs continuously and computes PSI/KS automatically."
                        icon={<ShowChartIcon />}
                      />
                    </TableCell>
                  </TableRow>
                )
              : filtered.slice(0, 50).map((m) => {
                  // The /drift/alerts endpoint returns DriftAlert rows
                  // ({alert_type, severity, message, acknowledged, created_at}),
                  // not DriftMeasurement rows. Render whichever shape arrived.
                  const r = m as unknown as {
                    id: string;
                    alert_type?: string;
                    severity?: string;
                    message?: string;
                    acknowledged?: boolean;
                    created_at?: string;
                    psi_score?: number;
                    measured_at?: string;
                  };
                  const alertType = r.alert_type ?? 'data_drift';
                  const severity = (r.severity ?? 'medium').toLowerCase();
                  const message = r.message ?? '—';
                  const ackText = r.acknowledged ? 'Yes' : 'No';
                  const createdAt = r.created_at ?? r.measured_at;
                  const created = createdAt ? new Date(createdAt).toLocaleString() : '—';
                  // Try to parse the PSI value out of the alert message ("PSI=0.2843, ...")
                  const psiMatch = /(?:PSI|psi)[\s=:]*([0-9.]+)/.exec(message);
                  const psi =
                    typeof r.psi_score === 'number' && Number.isFinite(r.psi_score)
                      ? r.psi_score
                      : psiMatch ? parseFloat(psiMatch[1]) : NaN;
                  const sevColor =
                    severity === 'critical' ? 'error.main' :
                    severity === 'high'     ? 'error.main' :
                    severity === 'medium'   ? 'warning.main' :
                    severity === 'low'      ? 'success.main' :
                                              'text.primary';
                  return (
                    <TableRow key={r.id} hover>
                      <TableCell>{alertType}</TableCell>
                      <TableCell sx={{ color: sevColor, fontWeight: 600 }}>
                        {Number.isFinite(psi)
                          ? `${severity} • PSI ${psi.toFixed(3)}`
                          : severity}
                      </TableCell>
                      <TableCell sx={{ maxWidth: 360, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={message}>
                        {message}
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={ackText}
                          color={r.acknowledged ? 'success' : 'default'}
                          size="small"
                          variant={r.acknowledged ? 'filled' : 'outlined'}
                        />
                      </TableCell>
                      <TableCell>{created}</TableCell>
                    </TableRow>
                  );
                })}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};

export default DriftMonitor;
