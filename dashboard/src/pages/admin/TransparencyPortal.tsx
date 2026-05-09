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
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Divider,
} from '@mui/material';
import PublicIcon from '@mui/icons-material/Public';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createTransparencyRecord,
  listTransparencyRecords,
} from '@/api/healthcare';
import type { TransparencyRecord } from '@/types';
import EmptyState from '@/components/common/EmptyState';
import TextField from '@mui/material/TextField';
import Stack from '@mui/material/Stack';

const TransparencyPortal: React.FC = () => {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [selected, setSelected] = useState<TransparencyRecord | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [form, setForm] = useState({
    model_name: '',
    model_version: '1.0',
    plain_language_summary: '',
    intended_population: '',
    known_limitations: '',
    evidence_base: '',
    algorithm_description: '',
    bias_considerations: '',
    regulatory_status: '',
  });

  const { data, isLoading, isError } = useQuery({
    queryKey: ['transparencyRecords', page, rowsPerPage],
    queryFn: () => listTransparencyRecords({ page: page + 1 }),
  });

  const createMutation = useMutation({
    mutationFn: (payload: typeof form) =>
      createTransparencyRecord(payload as unknown as Omit<
        TransparencyRecord,
        'id' | 'created_at' | 'version'
      >),
    onSuccess: () => {
      setCreateOpen(false);
      setCreateError(null);
      setForm({
        model_name: '',
        model_version: '1.0',
        plain_language_summary: '',
        intended_population: '',
        known_limitations: '',
        evidence_base: '',
        algorithm_description: '',
        bias_considerations: '',
        regulatory_status: '',
      });
      queryClient.invalidateQueries({ queryKey: ['transparencyRecords'] });
    },
    onError: (err: unknown) => {
      const msg =
        err instanceof Error ? err.message : 'Failed to create transparency record';
      setCreateError(msg);
    },
  });

  const handleCreate = () => {
    setCreateError(null);
    if (!form.model_name.trim()) {
      setCreateError('Model name is required');
      return;
    }
    if (form.plain_language_summary.trim().length < 50) {
      setCreateError(
        'Plain-language summary must be at least 50 characters (ONC HTI-1 requirement)',
      );
      return;
    }
    if (!form.intended_population.trim()) {
      setCreateError('Intended population is required');
      return;
    }
    if (!form.known_limitations.trim()) {
      setCreateError('Known limitations are required');
      return;
    }
    createMutation.mutate(form);
  };

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <PublicIcon sx={{ color: 'primary.main', fontSize: 28 }} />
          <Box>
            <Typography variant="h4">Transparency Portal</Typography>
            <Typography variant="body2" color="text.secondary">
              ONC HTI-1 compliant algorithm transparency records
            </Typography>
          </Box>
        </Box>
        <Button
          variant="contained"
          onClick={() => setCreateOpen(true)}
        >
          New Record
        </Button>
      </Box>

      <Alert severity="info" sx={{ mb: 3 }}>
        These records are publicly accessible per ONC HTI-1 requirements.
      </Alert>

      {isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Failed to load transparency records
        </Alert>
      )}

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Created At</TableCell>
              <TableCell>Algorithm</TableCell>
              <TableCell sx={{ minWidth: 220 }}>Summary</TableCell>
              <TableCell>Evidence Base</TableCell>
              <TableCell>Version</TableCell>
              <TableCell>Published At</TableCell>
              <TableCell>Actions</TableCell>
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
                        title="No transparency records yet"
                        description="Transparency records are plain-language descriptions of each AI model your organization uses — required by ONC HTI-1. Patients and clinicians read these to understand what an algorithm does, who it's for, and its limitations."
                        ingestHint="Today: create manually via 'New Record'. Roadmap: auto-generate a draft from each published model card using an LLM-based plain-language rewriter (8th-grade reading level)."
                        icon={<PublicIcon />}
                        primaryAction={{
                          label: 'New Record',
                          onClick: () => setCreateOpen(true),
                        }}
                      />
                    </TableCell>
                  </TableRow>
                )
              : items.map((record) => {
                  const summary =
                    record.plain_language_summary.length > 80
                      ? `${record.plain_language_summary.slice(0, 80)}…`
                      : record.plain_language_summary;

                  return (
                    <TableRow key={record.id} hover>
                      <TableCell>
                        {new Date(record.created_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell>{record.algorithm_name}</TableCell>
                      <TableCell>
                        <Typography
                          variant="body2"
                          noWrap
                          title={record.plain_language_summary}
                          sx={{ maxWidth: 220 }}
                        >
                          {summary}
                        </Typography>
                      </TableCell>
                      <TableCell>{record.evidence_base ?? '—'}</TableCell>
                      <TableCell>
                        <Chip
                          label={`v${(record as unknown as {
                            model_version?: string;
                            version_number?: number;
                          }).model_version
                            ?? (record as unknown as { version_number?: number }).version_number
                            ?? record.version
                            ?? '?'}`}
                          size="small"
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell>
                        {record.published_at
                          ? new Date(record.published_at).toLocaleDateString()
                          : '—'}
                      </TableCell>
                      <TableCell>
                        <Button
                          size="small"
                          variant="outlined"
                          onClick={() => setSelected(record as TransparencyRecord)}
                        >
                          View
                        </Button>
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

      {/* Detail modal — replaces a non-existent /admin/transparency/:id route. */}
      <Dialog open={selected !== null} onClose={() => setSelected(null)} maxWidth="md" fullWidth>
        {selected && (() => {
          const r = selected as unknown as {
            model_name?: string;
            model_version?: string;
            version?: string;
            version_number?: number;
            algorithm_description?: string;
            plain_language_summary?: string;
            evidence_base?: string;
            intended_population?: string;
            known_limitations?: string;
            performance_summary?: Record<string, unknown>;
            bias_considerations?: string;
            regulatory_status?: string;
            published_at?: string;
            created_at?: string;
          };
          const ver = r.model_version ?? r.version_number ?? r.version ?? '?';
          return (
            <>
              <DialogTitle>
                {r.model_name ?? 'Transparency record'}
                <Typography variant="caption" sx={{ ml: 1, color: 'text.secondary' }}>
                  v{ver}
                </Typography>
              </DialogTitle>
              <DialogContent dividers>
                <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
                  <Chip
                    size="small"
                    label={r.published_at ? 'Published' : 'Draft'}
                    color={r.published_at ? 'success' : 'warning'}
                  />
                  {r.regulatory_status && (
                    <Chip size="small" label={r.regulatory_status} variant="outlined" />
                  )}
                </Box>

                <Typography variant="overline" color="text.secondary">
                  Plain-language summary
                </Typography>
                <Typography variant="body2" sx={{ mb: 2 }}>
                  {r.plain_language_summary ?? '—'}
                </Typography>

                <Divider sx={{ my: 2 }} />

                <Typography variant="overline" color="text.secondary">
                  Intended population
                </Typography>
                <Typography variant="body2" sx={{ mb: 2 }}>
                  {r.intended_population ?? '—'}
                </Typography>

                <Typography variant="overline" color="text.secondary">
                  Known limitations
                </Typography>
                <Typography variant="body2" sx={{ mb: 2 }}>
                  {r.known_limitations ?? '—'}
                </Typography>

                {r.algorithm_description && (
                  <>
                    <Typography variant="overline" color="text.secondary">
                      Algorithm description
                    </Typography>
                    <Typography variant="body2" sx={{ mb: 2 }}>
                      {r.algorithm_description}
                    </Typography>
                  </>
                )}

                {r.evidence_base && (
                  <>
                    <Typography variant="overline" color="text.secondary">
                      Evidence base
                    </Typography>
                    <Typography variant="body2" sx={{ mb: 2 }}>
                      {r.evidence_base}
                    </Typography>
                  </>
                )}

                {r.bias_considerations && (
                  <>
                    <Typography variant="overline" color="text.secondary">
                      Bias considerations
                    </Typography>
                    <Typography variant="body2" sx={{ mb: 2 }}>
                      {r.bias_considerations}
                    </Typography>
                  </>
                )}

                {r.performance_summary && Object.keys(r.performance_summary).length > 0 && (
                  <>
                    <Typography variant="overline" color="text.secondary">
                      Performance
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                      {Object.entries(r.performance_summary).map(([key, value]) => (
                        <Chip
                          key={key}
                          size="small"
                          label={`${key}: ${typeof value === 'number' ? value.toFixed(3) : String(value)}`}
                          variant="outlined"
                        />
                      ))}
                    </Box>
                  </>
                )}
              </DialogContent>
              <DialogActions>
                <Button onClick={() => setSelected(null)}>Close</Button>
              </DialogActions>
            </>
          );
        })()}
      </Dialog>

      {/* Create-record dialog — replaces a non-existent /admin/transparency/new route. */}
      <Dialog
        open={createOpen}
        onClose={() => !createMutation.isPending && setCreateOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>New transparency record</DialogTitle>
        <DialogContent dividers>
          <Alert severity="info" sx={{ mb: 2 }}>
            Required by ONC HTI-1: a plain-language description of an AI tool used in your patients'
            care. The summary must be ≥ 50 characters at an 8th-grade reading level.
          </Alert>
          {createError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {createError}
            </Alert>
          )}
          <Stack spacing={2}>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
              <TextField
                label="Model name"
                fullWidth
                required
                value={form.model_name}
                onChange={(e) => setForm({ ...form, model_name: e.target.value })}
              />
              <TextField
                label="Version"
                value={form.model_version}
                onChange={(e) => setForm({ ...form, model_version: e.target.value })}
                sx={{ minWidth: 140 }}
              />
            </Stack>
            <TextField
              label="Plain-language summary"
              fullWidth
              required
              multiline
              minRows={4}
              helperText={`${form.plain_language_summary.length}/50 chars min — 8th-grade reading level`}
              value={form.plain_language_summary}
              onChange={(e) =>
                setForm({ ...form, plain_language_summary: e.target.value })
              }
            />
            <TextField
              label="Intended population"
              fullWidth
              required
              value={form.intended_population}
              onChange={(e) =>
                setForm({ ...form, intended_population: e.target.value })
              }
            />
            <TextField
              label="Known limitations"
              fullWidth
              required
              multiline
              minRows={2}
              value={form.known_limitations}
              onChange={(e) =>
                setForm({ ...form, known_limitations: e.target.value })
              }
            />
            <TextField
              label="Algorithm description (optional)"
              fullWidth
              multiline
              minRows={2}
              value={form.algorithm_description}
              onChange={(e) =>
                setForm({ ...form, algorithm_description: e.target.value })
              }
            />
            <TextField
              label="Evidence base (optional)"
              fullWidth
              value={form.evidence_base}
              onChange={(e) => setForm({ ...form, evidence_base: e.target.value })}
            />
            <TextField
              label="Bias considerations (optional)"
              fullWidth
              multiline
              minRows={2}
              value={form.bias_considerations}
              onChange={(e) =>
                setForm({ ...form, bias_considerations: e.target.value })
              }
            />
            <TextField
              label="Regulatory status (optional)"
              fullWidth
              placeholder="e.g. 510(k) cleared, CE Mark, etc."
              value={form.regulatory_status}
              onChange={(e) =>
                setForm({ ...form, regulatory_status: e.target.value })
              }
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => setCreateOpen(false)}
            disabled={createMutation.isPending}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleCreate}
            disabled={createMutation.isPending}
          >
            {createMutation.isPending ? 'Creating…' : 'Create record'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default TransparencyPortal;
