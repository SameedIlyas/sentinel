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
import EmptyState from '@/components/common/EmptyState';

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
              <TableCell>Session</TableCell>
              <TableCell sx={{ minWidth: 150 }}>Completeness</TableCell>
              <TableCell>Hallucination</TableCell>
              <TableCell>Attribution</TableCell>
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
                    <TableCell colSpan={7} sx={{ p: 0, border: 0 }}>
                      <EmptyState
                        title={statusFilter !== 'all' ? `No ${statusFilter} audits` : 'No scribe audits yet'}
                        description="Scribe audits check AI-generated clinical notes (Nuance DAX, Abridge, Nabla) for hallucinations, completeness, and attribution against the source encounter audio."
                        ingestHint="Today: POST audits manually via /v1/admin/scribe-audits. Roadmap: Epic / Cerner pre-signature webhook + LLM fact-checker. See docs/ROADMAP_TIER3_NO_DATA_SOURCE.md."
                        icon={<EditNoteIcon />}
                      />
                    </TableCell>
                  </TableRow>
                )
              : items.map((audit) => {
                  // Backend returns: session_id, completeness_score (0..100),
                  // attribution_score (0..100), hallucination_detected,
                  // audit_score, status, created_at, completed_at.
                  // The TS type lists encounter_id / audited_at / icd10_accuracy
                  // — those don't exist server-side. Tolerate both shapes.
                  const r = audit as unknown as {
                    id: string;
                    session_id?: string;
                    encounter_id?: string;
                    audited_at?: string;
                    created_at?: string;
                    completed_at?: string;
                    completeness_score?: number;
                    attribution_score?: number;
                    icd10_accuracy?: number;
                    hallucination_detected?: boolean;
                    findings_count?: number;
                    findings?: unknown[];
                    status?: string;
                  };
                  const ts = r.audited_at ?? r.completed_at ?? r.created_at;
                  const auditedAt = ts ? new Date(ts).toLocaleString() : '—';
                  const session = r.session_id ?? r.encounter_id ?? '—';
                  const completeness = typeof r.completeness_score === 'number' ? r.completeness_score : 0;
                  const attribution = typeof r.attribution_score === 'number' ? r.attribution_score
                    : typeof r.icd10_accuracy === 'number' ? r.icd10_accuracy
                    : null;
                  const findingsCount =
                    typeof r.findings_count === 'number'
                      ? r.findings_count
                      : Array.isArray(r.findings) ? r.findings.length : '—';
                  return (
                    <TableRow key={r.id} hover>
                      <TableCell sx={{ whiteSpace: 'nowrap' }}>{auditedAt}</TableCell>
                      <TableCell sx={{ fontFamily: 'monospace', fontSize: 12 }}>{session}</TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <LinearProgress
                            variant="determinate"
                            value={Math.min(100, Math.max(0, completeness))}
                            sx={{ flexGrow: 1, height: 8, borderRadius: 4 }}
                          />
                          <Typography variant="caption" sx={{ whiteSpace: 'nowrap' }}>
                            {Math.round(completeness)}%
                          </Typography>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={r.hallucination_detected ? 'Detected' : 'None'}
                          color={r.hallucination_detected ? 'error' : 'success'}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        {attribution != null ? `${Math.round(attribution)}%` : '—'}
                      </TableCell>
                      <TableCell>{findingsCount}</TableCell>
                      <TableCell>
                        <Chip
                          label={r.status ?? 'pending'}
                          color={statusColor((r.status ?? 'pending') as never)}
                          size="small"
                        />
                      </TableCell>
                    </TableRow>
                  );
                })}
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
