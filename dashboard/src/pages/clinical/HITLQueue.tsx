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
                    <TableCell colSpan={8} align="center" sx={{ py: 4 }}>
                      <Typography color="text.secondary">No reviews in queue</Typography>
                    </TableCell>
                  </TableRow>
                )
              : data.items.map((row) => {
                  const isOverdue = row.sla_deadline ? new Date(row.sla_deadline) < new Date() : false;
                  return (
                    <TableRow key={row.id} hover>
                      <TableCell>{new Date(row.created_at).toLocaleDateString()}</TableCell>
                      <TableCell>{row.model_id}</TableCell>
                      <TableCell>
                        {row.ai_decision.length > 60
                          ? `${row.ai_decision.slice(0, 60)}…`
                          : row.ai_decision}
                      </TableCell>
                      <TableCell>
                        {row.ai_confidence != null ? `${(row.ai_confidence * 100).toFixed(0)}%` : '—'}
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

      {data && (
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
