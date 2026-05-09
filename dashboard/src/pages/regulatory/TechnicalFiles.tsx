// src/pages/regulatory/TechnicalFiles.tsx
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
import FolderSpecialIcon from '@mui/icons-material/FolderSpecial';
import { useQuery } from '@tanstack/react-query';
import { listTechnicalFiles } from '@/api/healthcare';
import { TechnicalFile, TechnicalFileLifecycle, RegulatoryType } from '@/types';
import EmptyState from '@/components/common/EmptyState';

const LIFECYCLE_STAGES: Array<{ value: TechnicalFileLifecycle | 'all'; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'draft', label: 'Draft' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'under_review', label: 'Under Review' },
  { value: 'approved', label: 'Approved' },
  { value: 'retired', label: 'Retired' },
];

function lifecycleColor(
  stage: TechnicalFileLifecycle
): 'default' | 'info' | 'warning' | 'success' {
  switch (stage) {
    case 'draft':
      return 'default';
    case 'submitted':
      return 'info';
    case 'under_review':
      return 'warning';
    case 'approved':
      return 'success';
    case 'retired':
      return 'default';
  }
}

function regulatoryLabel(type: RegulatoryType): string {
  switch (type) {
    case 'fda_510k':
      return 'FDA 510(k)';
    case 'eu_mdr':
      return 'EU MDR';
    case 'both':
      return 'Both';
  }
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

const TechnicalFiles: React.FC = () => {
  const [lifecycleFilter, setLifecycleFilter] = useState<TechnicalFileLifecycle | 'all'>('all');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['technical-files', lifecycleFilter, page, rowsPerPage],
    queryFn: () =>
      listTechnicalFiles({
        lifecycle_stage: lifecycleFilter === 'all' ? undefined : lifecycleFilter,
        page: page + 1,
      }),
  });

  const items: TechnicalFile[] = data?.items ?? [];

  const fdaCount = items.filter((f) => f.regulatory_type === 'fda_510k').length;
  const euMdrCount = items.filter((f) => f.regulatory_type === 'eu_mdr').length;
  const bothCount = items.filter((f) => f.regulatory_type === 'both').length;

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
        <FolderSpecialIcon sx={{ color: 'primary.main', fontSize: 28 }} />
        <Box>
          <Typography variant="h4">Technical Files</Typography>
          <Typography variant="body2" color="text.secondary">
            FDA 510(k) and EU MDR regulatory documentation
          </Typography>
        </Box>
      </Box>

      {/* Summary chips */}
      <Stack direction="row" spacing={1} sx={{ mb: 2 }} flexWrap="wrap">
        <Chip label={`Total: ${data?.total ?? 0}`} size="small" />
        <Chip label={`FDA 510(k): ${fdaCount}`} size="small" color="primary" variant="outlined" />
        <Chip label={`EU MDR: ${euMdrCount}`} size="small" color="secondary" variant="outlined" />
        <Chip label={`Both: ${bothCount}`} size="small" color="info" variant="outlined" />
      </Stack>

      {/* Lifecycle filter chips */}
      <Stack direction="row" spacing={1} sx={{ mb: 2 }} flexWrap="wrap">
        {LIFECYCLE_STAGES.map((stage) => (
          <Chip
            key={stage.value}
            label={stage.label}
            onClick={() => {
              setLifecycleFilter(stage.value);
              setPage(0);
            }}
            color={lifecycleFilter === stage.value ? 'primary' : 'default'}
            variant={lifecycleFilter === stage.value ? 'filled' : 'outlined'}
            clickable
          />
        ))}
      </Stack>

      {/* Error */}
      {isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Failed to load technical files.
        </Alert>
      )}

      {/* Table */}
      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Title</TableCell>
              <TableCell>Regulatory Type</TableCell>
              <TableCell>Product</TableCell>
              <TableCell>Version</TableCell>
              <TableCell>Lifecycle Stage</TableCell>
              <TableCell>Created</TableCell>
              <TableCell>Updated</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading ? (
              <SkeletonRows cols={7} />
            ) : items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} sx={{ p: 0, border: 0 }}>
                  <EmptyState
                    title={lifecycleFilter !== 'all' ? `No ${lifecycleFilter} files` : 'No technical files yet'}
                    description="FDA 510(k) and EU MDR submissions live here. Each file aggregates device description, intended use, performance data, risk management, and clinical evaluation sections."
                    ingestHint="Today: create per-submission, fill sections by hand. Roadmap: auto-populate sections from linked model cards, bias audits, and PMS reports — and re-version when the underlying data changes."
                    icon={<FolderSpecialIcon />}
                  />
                </TableCell>
              </TableRow>
            ) : (
              items.map((file) => (
                <TableRow key={file.id} hover>
                  <TableCell>
                    <Typography variant="body2" fontWeight={500}>
                      {file.title}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip label={regulatoryLabel(file.regulatory_type)} size="small" />
                  </TableCell>
                  <TableCell>{file.product_name}</TableCell>
                  <TableCell>{file.device_version}</TableCell>
                  <TableCell>
                    <Chip
                      label={file.lifecycle_stage}
                      color={lifecycleColor(file.lifecycle_stage)}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">
                      {new Date(file.created_at).toLocaleDateString()}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">
                      {new Date(file.updated_at).toLocaleDateString()}
                    </Typography>
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

export default TechnicalFiles;
