/**
 * BiasAuditList — index page for /clinical/bias-audits.
 *
 * Without this page the nav item silently fell back to the dashboard
 * because only the detail route (`/clinical/bias-audits/:id`) was
 * registered. This list view shows every audit, its status (pending /
 * running / complete / failed), and lets the user drill into a result
 * report.
 */
import React, { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Chip,
  IconButton,
  MenuItem,
  Paper,
  Skeleton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import BalanceIcon from '@mui/icons-material/Balance';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { listBiasAudits, listModelCards } from '@/api/healthcare';
import type { BiasAudit, ModelCard } from '@/types';
import EmptyState from '@/components/common/EmptyState';

// Note: the backend persists status as 'complete' (no -ed). The TS
// `BiasAuditStatus` type currently spells it 'completed'. Accept either at
// runtime so the page works against the live API regardless of which side
// is normalised.
type StatusFilter = 'all' | 'pending' | 'running' | 'complete' | 'completed' | 'failed';

const STATUSES: Array<{ value: StatusFilter; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'running', label: 'Running' },
  { value: 'complete', label: 'Complete' },
  { value: 'failed', label: 'Failed' },
];

function statusColor(
  status: string,
): 'default' | 'warning' | 'success' | 'error' | 'info' {
  switch (status) {
    case 'pending':
      return 'warning';
    case 'running':
      return 'info';
    case 'complete':
    case 'completed':
      return 'success';
    case 'failed':
      return 'error';
    default:
      return 'default';
  }
}

function formatDate(value?: string): string {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function SkeletonRows({ count }: { count: number }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <TableRow key={i}>
          {Array.from({ length: 6 }).map((__, j) => (
            <TableCell key={j}>
              <Skeleton variant="text" />
            </TableCell>
          ))}
        </TableRow>
      ))}
    </>
  );
}

const BiasAuditList: React.FC = () => {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['bias-audits', statusFilter, page, rowsPerPage],
    queryFn: () =>
      listBiasAudits({
        status: statusFilter === 'all' ? undefined : statusFilter,
        page: page + 1,
      }),
  });

  // Pull model-card list once so we can show a friendly model name next to each audit
  const { data: cards } = useQuery({
    queryKey: ['model-cards-for-bias-list'],
    queryFn: () => listModelCards({ page: 1, page_size: 100 }),
  });

  const cardNameById = useMemo(() => {
    const map = new Map<string, string>();
    const items = Array.isArray(cards?.items) ? cards!.items : [];
    items.forEach((c: ModelCard) => {
      map.set(c.id, c.model_name);
    });
    return map;
  }, [cards]);

  const items = Array.isArray(data?.items) ? data!.items : [];
  const filteredItems = items.filter((audit) => {
    if (!search) return true;
    const haystack = [
      audit.id,
      audit.model_card_id,
      cardNameById.get(audit.model_card_id) ?? '',
      audit.findings_summary ?? '',
    ]
      .join(' ')
      .toLowerCase();
    return haystack.includes(search.toLowerCase());
  });

  const handleChangePage = (_: unknown, newPage: number) => setPage(newPage);
  const handleChangeRowsPerPage = (e: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(e.target.value, 10));
    setPage(0);
  };

  const handleRowClick = (id: string) => navigate(`/clinical/bias-audits/${id}`);

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <BalanceIcon sx={{ color: 'primary.main', fontSize: 28 }} />
          <Box>
            <Typography variant="h4">Bias Audits</Typography>
            <Typography variant="body2" color="text.secondary">
              Subgroup fairness reports for every clinical AI model — required before publish.
            </Typography>
          </Box>
        </Box>
      </Box>

      <Alert severity="info" sx={{ mb: 3 }}>
        A model card cannot be published without a complete bias audit less than 90 days old. Audits flag
        subgroups that fail the 4/5ths rule (or equalized-odds ratio); failures auto-create a HITL review.
      </Alert>

      {isError && (
        <Alert severity="error" sx={{ mb: 3 }}>
          Failed to load bias audits. Please try again.
        </Alert>
      )}

      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ mb: 2 }}>
        <TextField
          select
          size="small"
          label="Status"
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value as StatusFilter);
            setPage(0);
          }}
          sx={{ minWidth: 180 }}
        >
          {STATUSES.map((s) => (
            <MenuItem key={s.value} value={s.value}>
              {s.label}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          size="small"
          label="Search audits"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          sx={{ flex: 1 }}
        />
      </Stack>

      <Paper variant="outlined">
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Audit ID</TableCell>
                <TableCell>Model</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Subgroups</TableCell>
                <TableCell>Created</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {isLoading ? (
                <SkeletonRows count={5} />
              ) : filteredItems.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} sx={{ p: 0, border: 0 }}>
                    <EmptyState
                      title={search ? 'No audits match your search' : 'No bias audits yet'}
                      description="Bias audits measure subgroup-level performance to catch fairness issues before they reach patients. The publish gate blocks model cards until a passing audit exists."
                      ingestHint="Audits are created automatically when a model card enters review, and can be re-run with synthetic or production datasets via POST /v1/clinical/bias-audits/{id}/run."
                      icon={<BalanceIcon />}
                    />
                  </TableCell>
                </TableRow>
              ) : (
                filteredItems.map((audit: BiasAudit) => (
                  <TableRow
                    key={audit.id}
                    hover
                    sx={{ cursor: 'pointer' }}
                    onClick={() => handleRowClick(audit.id)}
                  >
                    <TableCell sx={{ fontFamily: 'monospace', fontSize: 12 }}>
                      {audit.id.slice(0, 14)}…
                    </TableCell>
                    <TableCell>
                      <Box>
                        <Typography variant="body2" sx={{ fontWeight: 500 }}>
                          {cardNameById.get(audit.model_card_id) ?? '—'}
                        </Typography>
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          sx={{ fontFamily: 'monospace' }}
                        >
                          {audit.model_card_id}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={audit.status}
                        color={statusColor(audit.status)}
                        size="small"
                        sx={{ textTransform: 'capitalize' }}
                      />
                    </TableCell>
                    <TableCell>
                      {Array.isArray(audit.subgroups) ? audit.subgroups.length : 0}
                    </TableCell>
                    <TableCell sx={{ whiteSpace: 'nowrap' }}>
                      {formatDate(audit.created_at)}
                    </TableCell>
                    <TableCell align="right">
                      <Tooltip title="View details">
                        <IconButton
                          size="small"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRowClick(audit.id);
                          }}
                        >
                          <VisibilityIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
        <TablePagination
          component="div"
          count={typeof data?.total === 'number' ? data.total : items.length}
          page={page}
          onPageChange={handleChangePage}
          rowsPerPage={rowsPerPage}
          onRowsPerPageChange={handleChangeRowsPerPage}
          rowsPerPageOptions={[10, 25, 50]}
        />
      </Paper>
    </Box>
  );
};

export default BiasAuditList;
