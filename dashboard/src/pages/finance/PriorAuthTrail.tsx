import React, { useState } from 'react';
import {
  Box, Typography, Alert, Paper, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, TablePagination, Chip,
  Skeleton, IconButton,
} from '@mui/material';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import VerifiedIcon from '@mui/icons-material/Verified';
import { useQuery, useMutation } from '@tanstack/react-query';
import { listPriorAuthRecords, verifyPriorAuthChain } from '@/api/healthcare';
import EmptyState from '@/components/common/EmptyState';

type DecisionColor = 'success' | 'error' | 'warning' | 'default';

function decisionChipColor(decision: string): DecisionColor {
  if (decision === 'approved') return 'success';
  if (decision === 'denied') return 'error';
  if (decision === 'pending') return 'warning';
  return 'default';
}

interface VerifyAlertState {
  recordId: string;
  valid: boolean;
  message: string;
}

const PriorAuthTrail: React.FC = () => {
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [verifyAlert, setVerifyAlert] = useState<VerifyAlertState | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['priorAuthRecords', page, rowsPerPage],
    queryFn: () => listPriorAuthRecords({ page: page + 1, page_size: rowsPerPage }),
  });

  const verifyMutation = useMutation({
    mutationFn: (id: string) => verifyPriorAuthChain(id),
    onSuccess: (result, id) => {
      setVerifyAlert({ recordId: id, valid: result.valid, message: result.message });
    },
    onError: (_err, id) => {
      setVerifyAlert({ recordId: id, valid: false, message: 'Chain verification failed.' });
    },
  });

  const handleChangePage = (_: unknown, newPage: number) => setPage(newPage);
  const handleChangeRowsPerPage = (e: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(e.target.value, 10));
    setPage(0);
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
        <AccountTreeIcon sx={{ color: 'primary.main', fontSize: 28 }} />
        <Box>
          <Typography variant="h4">Prior Authorization Audit Trail</Typography>
          <Typography variant="body2" color="text.secondary">
            Immutable hash-chained record of all AI-assisted prior auth decisions
          </Typography>
        </Box>
      </Box>

      <Alert severity="info" sx={{ mb: 3 }}>
        Records are append-only per CMS-0057-F compliance. Chain integrity is verified.
      </Alert>

      {isError && (
        <Alert severity="error" sx={{ mb: 3 }}>
          Failed to load prior authorization records. Please try again.
        </Alert>
      )}

      {verifyAlert && (
        <Alert
          severity={verifyAlert.valid ? 'success' : 'error'}
          onClose={() => setVerifyAlert(null)}
          sx={{ mb: 2 }}
        >
          {verifyAlert.message}
        </Alert>
      )}

      <Paper>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Created</TableCell>
                <TableCell>Claim ID</TableCell>
                <TableCell>Service Type</TableCell>
                <TableCell>AI Recommendation</TableCell>
                <TableCell>AI Confidence</TableCell>
                <TableCell>Final Decision</TableCell>
                <TableCell>Denial Reason</TableCell>
                <TableCell>Chain Hash</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {isLoading ? (
                [0, 1, 2, 3, 4].map((i) => (
                  <TableRow key={i}>
                    {[0, 1, 2, 3, 4, 5, 6, 7, 8].map((j) => (
                      <TableCell key={j}><Skeleton variant="text" /></TableCell>
                    ))}
                  </TableRow>
                ))
              ) : !data || !Array.isArray(data.items) || data.items.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={9} sx={{ p: 0, border: 0 }}>
                    <EmptyState
                      title="No prior auth decisions yet"
                      description="An immutable hash-chained log of every AI-assisted prior-authorization decision. Each record is linked to the previous one by SHA-256 — tampering breaks the chain."
                      ingestHint="Records are written automatically when your AI prior-auth service POSTs to /v1/finance/prior-auth (CMS-0057-F compliant). The chain is verified on demand and on a daily schedule."
                      icon={<AccountTreeIcon />}
                    />
                  </TableCell>
                </TableRow>
              ) : (
                data.items.map((record) => (
                  <TableRow key={record.id} hover>
                    <TableCell sx={{ whiteSpace: 'nowrap' }}>
                      {new Date(record.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell sx={{ fontFamily: 'monospace', fontSize: 12 }}>
                      {record.claim_id}
                    </TableCell>
                    <TableCell>{record.service_type ?? '—'}</TableCell>
                    <TableCell sx={{ maxWidth: 200 }}>
                      {(() => {
                        const rec = record.ai_recommendation ?? '—';
                        return (
                          <Typography variant="body2" noWrap title={rec}>
                            {rec.length > 50 ? rec.slice(0, 50) + '…' : rec}
                          </Typography>
                        );
                      })()}
                    </TableCell>
                    <TableCell>
                      {typeof record.ai_confidence === 'number' && Number.isFinite(record.ai_confidence)
                        ? `${(record.ai_confidence * 100).toFixed(0)}%`
                        : '—'}
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={record.final_decision}
                        size="small"
                        color={decisionChipColor(record.final_decision)}
                        sx={{ textTransform: 'capitalize', fontWeight: 600 }}
                      />
                    </TableCell>
                    <TableCell>{record.denial_reason_code ?? '—'}</TableCell>
                    <TableCell>
                      <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                        …{record.record_hash.slice(-8)}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <IconButton
                        size="small"
                        onClick={() => verifyMutation.mutate(record.id)}
                        aria-label="Verify Chain"
                        disabled={verifyMutation.isPending}
                      >
                        <VerifiedIcon fontSize="small" />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
        <TablePagination
          rowsPerPageOptions={[10, 25, 50]}
          component="div"
          count={data?.total ?? 0}
          rowsPerPage={rowsPerPage}
          page={page}
          onPageChange={handleChangePage}
          onRowsPerPageChange={handleChangeRowsPerPage}
        />
      </Paper>
    </Box>
  );
};

export default PriorAuthTrail;
