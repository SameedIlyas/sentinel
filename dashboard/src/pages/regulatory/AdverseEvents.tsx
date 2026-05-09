// src/pages/regulatory/AdverseEvents.tsx
import React, { useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Alert,
  Skeleton,
  Stack,
} from '@mui/material';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import { useQuery } from '@tanstack/react-query';
import { listAdverseEvents } from '@/api/healthcare';
import { AdverseEvent, AdverseEventSeverity, AdverseEventStatus } from '@/types';
import EmptyState from '@/components/common/EmptyState';

const SEVERITY_FILTERS: Array<{ value: AdverseEventSeverity | 'all'; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'critical', label: 'Critical' },
];

function severityColor(
  severity: AdverseEventSeverity
): 'default' | 'warning' | 'error' {
  switch (severity) {
    case 'low':
      return 'default';
    case 'medium':
      return 'warning';
    case 'high':
      return 'error';
    case 'critical':
      return 'error';
  }
}

function statusColor(
  status: AdverseEventStatus
): 'error' | 'warning' | 'success' | 'info' {
  switch (status) {
    case 'open':
      return 'error';
    case 'investigating':
      return 'warning';
    case 'resolved':
      return 'success';
    case 'reported_to_fda':
      return 'info';
  }
}

function statusLabel(status: AdverseEventStatus): string {
  switch (status) {
    case 'open':
      return 'Open';
    case 'investigating':
      return 'Investigating';
    case 'resolved':
      return 'Resolved';
    case 'reported_to_fda':
      return 'Reported to FDA';
  }
}

function truncate(text: string, maxLen = 60): string {
  return text.length > maxLen ? `${text.slice(0, maxLen)}…` : text;
}

function SkeletonRows({ cols }: { cols: number }) {
  return (
    <>
      {Array.from({ length: 5 }).map((_, i) => (
        <TableRow key={i}>
          {Array.from({ length: cols }).map((__, j) => (
            <TableCell key={j}>
              <Skeleton variant="text" />
            </TableCell>
          ))}
        </TableRow>
      ))}
    </>
  );
}

const AdverseEvents: React.FC = () => {
  const [severityFilter, setSeverityFilter] = useState<AdverseEventSeverity | 'all'>('all');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['adverse-events', severityFilter, page, rowsPerPage],
    queryFn: () =>
      listAdverseEvents({
        severity: severityFilter === 'all' ? undefined : severityFilter,
        page: page + 1,
      }),
  });

  const items: AdverseEvent[] = data?.items ?? [];

  const openCount = items.filter((e) => e.status === 'open').length;
  const investigatingCount = items.filter((e) => e.status === 'investigating').length;
  const resolvedCount = items.filter((e) => e.status === 'resolved').length;
  const reportedCount = items.filter((e) => e.status === 'reported_to_fda').length;

  const handleChangePage = (_: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 3 }}>
        <WarningAmberIcon sx={{ color: 'warning.main', fontSize: 28 }} />
        <Box>
          <Typography variant="h4">Adverse Events</Typography>
          <Typography variant="body2" color="text.secondary">
            Post-market AI performance incidents and patient safety reports
          </Typography>
        </Box>
      </Box>

      {/* Summary chips */}
      <Stack direction="row" spacing={1} sx={{ mb: 2 }} flexWrap="wrap">
        <Chip label={`Total: ${data?.total ?? 0}`} size="small" />
        <Chip label={`Open: ${openCount}`} size="small" color="error" variant="outlined" />
        <Chip label={`Investigating: ${investigatingCount}`} size="small" color="warning" variant="outlined" />
        <Chip label={`Resolved: ${resolvedCount}`} size="small" color="success" variant="outlined" />
        <Chip label={`Reported to FDA: ${reportedCount}`} size="small" color="info" variant="outlined" />
      </Stack>

      {/* Severity filter chips */}
      <Stack direction="row" spacing={1} sx={{ mb: 2 }} flexWrap="wrap">
        {SEVERITY_FILTERS.map((filter) => (
          <Chip
            key={filter.value}
            label={filter.label}
            onClick={() => {
              setSeverityFilter(filter.value);
              setPage(0);
            }}
            color={severityFilter === filter.value ? 'primary' : 'default'}
            variant={severityFilter === filter.value ? 'filled' : 'outlined'}
            clickable
          />
        ))}
      </Stack>

      {/* Error */}
      {isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Failed to load adverse events.
        </Alert>
      )}

      {/* Table */}
      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Reported At</TableCell>
              <TableCell>Model ID</TableCell>
              <TableCell>Event Type</TableCell>
              <TableCell>Severity</TableCell>
              <TableCell>Patient Impact</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Description</TableCell>
              <TableCell>Resolved At</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading ? (
              <SkeletonRows cols={8} />
            ) : items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} sx={{ p: 0, border: 0 }}>
                  <EmptyState
                    title={severityFilter !== 'all' ? `No ${severityFilter}-severity events` : 'No adverse events recorded'}
                    description="Adverse events are post-market AI failures that affected (or could have affected) patient safety. Each is classified, investigated, and — if reportable — submitted to FDA via the MAUDE portal."
                    ingestHint="Events are auto-classified by the policy engine when blocked decisions match safety-critical patterns, OR can be manually reported by clinicians and care teams via /v1/regulatory/adverse-events."
                    icon={<WarningAmberIcon />}
                  />
                </TableCell>
              </TableRow>
            ) : (
              items.map((event) => (
                <TableRow key={event.id} hover>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">
                      {new Date(event.reported_at).toLocaleDateString()}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">{event.model_id}</Typography>
                  </TableCell>
                  <TableCell>{event.event_type}</TableCell>
                  <TableCell>
                    <Chip
                      label={event.severity}
                      color={severityColor(event.severity)}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    {event.patient_impact ? (
                      <Typography variant="body2">{event.patient_impact}</Typography>
                    ) : (
                      <Typography variant="body2" color="text.disabled">
                        —
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={statusLabel(event.status)}
                      color={statusColor(event.status)}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    <Typography
                      variant="body2"
                      noWrap
                      title={event.description}
                      sx={{ maxWidth: 200 }}
                    >
                      {truncate(event.description, 60)}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    {event.resolved_at ? (
                      <Typography variant="body2" color="text.secondary">
                        {new Date(event.resolved_at).toLocaleDateString()}
                      </Typography>
                    ) : (
                      <Typography variant="body2" color="text.disabled">
                        —
                      </Typography>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Pagination */}
      {!isLoading && (data?.total ?? 0) > 0 && (
        <TablePagination
          component="div"
          count={data?.total ?? 0}
          page={page}
          onPageChange={handleChangePage}
          rowsPerPage={rowsPerPage}
          onRowsPerPageChange={handleChangeRowsPerPage}
          rowsPerPageOptions={[10, 25, 50]}
        />
      )}
    </Box>
  );
};

export default AdverseEvents;
