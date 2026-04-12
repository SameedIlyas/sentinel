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
  LinearProgress,
} from '@mui/material';
import EditNoteIcon from '@mui/icons-material/EditNote';
import { useQuery } from '@tanstack/react-query';
import { listScribeAudits } from '@/api/healthcare';
import type { ScribeAuditStatus } from '@/types';

const STATUS_FILTERS: Array<ScribeAuditStatus | 'all'> = ['all', 'pass', 'warning', 'fail'];

function statusColor(status: ScribeAuditStatus): 'success' | 'warning' | 'error' {
  if (status === 'pass') return 'success';
  if (status === 'warning') return 'warning';
  return 'error';
}

const ScribeAuditList: React.FC = () => {
  const [statusFilter, setStatusFilter] = useState<ScribeAuditStatus | 'all'>('all');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['scribeAudits', statusFilter, page, rowsPerPage],
    queryFn: () =>
      listScribeAudits({
        status: statusFilter === 'all' ? undefined : statusFilter,
        page: page + 1,
      }),
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  const passedCount = items.filter((a) => a.status === 'pass').length;
  const warningCount = items.filter((a) => a.status === 'warning').length;
  const failedCount = items.filter((a) => a.status === 'fail').length;

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 3 }}>
        <EditNoteIcon sx={{ color: 'primary.main', fontSize: 28 }} />
        <Box>
          <Typography variant="h4">Ambient Scribe Audit</Typography>
          <Typography variant="body2" color="text.secondary">
            AI-generated clinical note quality and accuracy monitoring
          </Typography>
        </Box>
      </Box>

      <Box sx={{ display: 'flex', gap: 1.5, mb: 3, flexWrap: 'wrap' }}>
        <Chip label={`Total: ${total}`} variant="outlined" />
        <Chip label={`Passed: ${passedCount}`} color="success" />
        <Chip label={`Warnings: ${warningCount}`} color="warning" />
        <Chip label={`Failed: ${failedCount}`} color="error" />
      </Box>

      <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
        {STATUS_FILTERS.map((s) => (
          <Chip
            key={s}
            label={s === 'all' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
            variant={statusFilter === s ? 'filled' : 'outlined'}
            color={s === 'all' ? 'default' : statusColor(s as ScribeAuditStatus)}
            onClick={() => {
              setStatusFilter(s);
              setPage(0);
            }}
            clickable
          />
        ))}
      </Box>

      {isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Failed to load scribe audits
        </Alert>
      )}

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Audited At</TableCell>
              <TableCell>Encounter ID</TableCell>
              <TableCell sx={{ minWidth: 150 }}>Completeness</TableCell>
              <TableCell>Hallucination</TableCell>
              <TableCell>ICD-10 Accuracy</TableCell>
              <TableCell>Findings</TableCell>
              <TableCell>Status</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading
              ? Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    {Array.from({ length: 7 }).map((__, j) => (
                      <TableCell key={j}>
                        <Skeleton variant="text" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              : items.length === 0
              ? (
                  <TableRow>
                    <TableCell colSpan={7} align="center">
                      <Typography variant="body2" color="text.secondary" sx={{ py: 3 }}>
                        No scribe audits found
                      </Typography>
                    </TableCell>
                  </TableRow>
                )
              : items.map((audit) => (
                  <TableRow key={audit.id} hover>
                    <TableCell>
                      {new Date(audit.audited_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>{audit.encounter_id}</TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <LinearProgress
                          variant="determinate"
                          value={audit.completeness_score}
                          sx={{ flexGrow: 1, height: 8, borderRadius: 4 }}
                        />
                        <Typography variant="caption" sx={{ whiteSpace: 'nowrap' }}>
                          {audit.completeness_score}%
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={audit.hallucination_detected ? 'Detected' : 'None'}
                        color={audit.hallucination_detected ? 'error' : 'success'}
                        size="small"
                      />
                    </TableCell>
                    <TableCell>
                      {audit.icd10_accuracy != null ? `${audit.icd10_accuracy}%` : '—'}
                    </TableCell>
                    <TableCell>{audit.findings_count}</TableCell>
                    <TableCell>
                      <Chip
                        label={audit.status}
                        color={statusColor(audit.status)}
                        size="small"
                      />
                    </TableCell>
                  </TableRow>
                ))}
          </TableBody>
        </Table>
        <TablePagination
          rowsPerPageOptions={[10, 25, 50]}
          component="div"
          count={total}
          rowsPerPage={rowsPerPage}
          page={page}
          onPageChange={(_, newPage) => setPage(newPage)}
          onRowsPerPageChange={(e) => {
            setRowsPerPage(parseInt(e.target.value, 10));
            setPage(0);
          }}
        />
      </TableContainer>
    </Box>
  );
};

export default ScribeAuditList;
