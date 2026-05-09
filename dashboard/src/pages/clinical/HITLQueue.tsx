import React, { useState } from 'react';
import {
  Box, Typography, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, Paper, Chip, TablePagination, Alert,
  Skeleton, Button,
} from '@mui/material';
import HowToRegIcon from '@mui/icons-material/HowToReg';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { listHITLReviews } from '@/api/healthcare';
import type { HITLStatus } from '@/types';
import EmptyState from '@/components/common/EmptyState';

const STATUS_FILTERS = ['All', 'pending', 'approved', 'rejected', 'modified'] as const;
type FilterValue = typeof STATUS_FILTERS[number];

const statusColor = (s: HITLStatus): 'warning' | 'success' | 'error' | 'info' => {
  if (s === 'pending') return 'warning';
  if (s === 'approved') return 'success';
  if (s === 'rejected') return 'error';
  return 'info';
};

const HITLQueue: React.FC = () => {
  const navigate = useNavigate();
  const [filter, setFilter] = useState<FilterValue>('All');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  const statusParam = filter === 'All' ? undefined : filter;

  const { data, isLoading, isError } = useQuery({
    queryKey: ['hitlReviews', statusParam, page, rowsPerPage],
    queryFn: () => listHITLReviews({ status: statusParam, page: page + 1, page_size: rowsPerPage }),
  });

  const handleChangePage = (_: unknown, newPage: number) => setPage(newPage);
  const handleChangeRowsPerPage = (e: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(e.target.value, 10));
    setPage(0);
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 3 }}>
        <HowToRegIcon sx={{ color: 'primary.main', fontSize: 28 }} />
        <Typography variant="h4">HITL Review Queue</Typography>
      </Box>

      <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
        {STATUS_FILTERS.map((s) => (
          <Chip
            key={s}
            label={s === 'All' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
            onClick={() => { setFilter(s); setPage(0); }}
            color={filter === s ? 'primary' : 'default'}
            variant={filter === s ? 'filled' : 'outlined'}
          />
        ))}
      </Box>

      {isError && <Alert severity="error" sx={{ mb: 2 }}>Failed to load reviews. Please try again.</Alert>}

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Created</TableCell>
              <TableCell>Model ID</TableCell>
              <TableCell>AI Decision</TableCell>
              <TableCell>Confidence</TableCell>
              <TableCell>Risk Score</TableCell>
              <TableCell>SLA Deadline</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading
              ? Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    {Array.from({ length: 8 }).map((__, j) => (
                      <TableCell key={j}><Skeleton variant="text" /></TableCell>
                    ))}
                  </TableRow>
                ))
              : !data?.items?.length
              ? (
                  <TableRow>
                    <TableCell colSpan={8} sx={{ p: 0, border: 0 }}>
                      <EmptyState
                        title={filter !== 'All' ? `No ${filter} reviews` : 'No reviews waiting for human approval'}
                        description="Human-in-the-loop reviews queue here when a policy decision needs a human's sign-off — for example, transactions over $1k or AI recommendations against guidelines."
                        ingestHint="Reviews are auto-created by the policy engine when a check returns 'requires approval' (action: require_approval). When you wire a policy with that action, decisions land here automatically."
                        icon={<HowToRegIcon />}
                      />
                    </TableCell>
                  </TableRow>
                )
              : data.items.map((row) => {
                  const isOverdue = row.sla_deadline ? new Date(row.sla_deadline) < new Date() : false;
                  // ai_decision can come back as a string OR an object like
                  // { recommendation, confidence, reason, ... } — render either form.
                  const decision: unknown = (row as unknown as { ai_decision?: unknown }).ai_decision;
                  const decisionText: string =
                    typeof decision === 'string'
                      ? decision
                      : decision && typeof decision === 'object'
                        ? String(
                            (decision as { recommendation?: unknown; reason?: unknown }).recommendation
                              ?? (decision as { reason?: unknown }).reason
                              ?? JSON.stringify(decision),
                          )
                        : '—';
                  const decisionConfidence: number | undefined =
                    decision && typeof decision === 'object'
                      ? (decision as { confidence?: number }).confidence
                      : undefined;
                  return (
                    <TableRow key={row.id} hover>
                      <TableCell>{new Date(row.created_at).toLocaleDateString()}</TableCell>
                      <TableCell>{(row as { title?: string }).title ?? row.model_id ?? '—'}</TableCell>
                      <TableCell>
                        {decisionText.length > 60
                          ? `${decisionText.slice(0, 60)}…`
                          : decisionText}
                      </TableCell>
                      <TableCell>
                        {decisionConfidence != null
                          ? `${(decisionConfidence * 100).toFixed(0)}%`
                          : row.ai_confidence != null
                            ? `${(row.ai_confidence * 100).toFixed(0)}%`
                            : '—'}
                      </TableCell>
                      <TableCell>{row.risk_score ?? '—'}</TableCell>
                      <TableCell sx={{ color: isOverdue ? 'error.main' : 'inherit' }}>
                        {row.sla_deadline ? new Date(row.sla_deadline).toLocaleDateString() : '—'}
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={row.status}
                          color={statusColor(row.status)}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        <Button
                          size="small"
                          variant="outlined"
                          onClick={() => navigate(`/clinical/hitl/${row.id}`)}
                        >
                          Review
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
          </TableBody>
        </Table>
      </TableContainer>

      {data && typeof data.total === 'number' && (
        <TablePagination
          component="div"
          count={data.total}
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

export default HITLQueue;
