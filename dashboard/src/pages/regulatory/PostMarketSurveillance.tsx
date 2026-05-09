// src/pages/regulatory/PostMarketSurveillance.tsx
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
} from '@mui/material';
import MonitorHeartIcon from '@mui/icons-material/MonitorHeart';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listPMSReports, generatePSUR } from '@/api/healthcare';
import { PMSReport, PMSReportStatus } from '@/types';
import EmptyState from '@/components/common/EmptyState';

function statusColor(
  status: PMSReportStatus
): 'default' | 'success' | 'info' {
  switch (status) {
    case 'draft':
      return 'default';
    case 'published':
      return 'success';
    case 'submitted':
      return 'info';
  }
}

function truncate(text: string, maxLen = 80): string {
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

const PostMarketSurveillance: React.FC = () => {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [psurSuccess, setPsurSuccess] = useState(false);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['pms-reports', page, rowsPerPage],
    queryFn: () =>
      listPMSReports({
        page: page + 1,
      }),
  });

  const generateMutation = useMutation({
    mutationFn: generatePSUR,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pms-reports'] });
      setPsurSuccess(true);
    },
  });

  const items: PMSReport[] = data?.items ?? [];

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
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <MonitorHeartIcon sx={{ color: 'primary.main', fontSize: 28 }} />
          <Box>
            <Typography variant="h4">Post-Market Surveillance</Typography>
            <Typography variant="body2" color="text.secondary">
              Periodic Safety Update Reports (PSUR) and PMS monitoring
            </Typography>
          </Box>
        </Box>
        <Button
          variant="contained"
          onClick={() => {
            setPsurSuccess(false);
            generateMutation.mutate();
          }}
          disabled={generateMutation.isPending}
        >
          Generate PSUR
        </Button>
      </Box>

      {/* Success alert */}
      {psurSuccess && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setPsurSuccess(false)}>
          PSUR generated successfully.
        </Alert>
      )}

      {/* Error from generate */}
      {generateMutation.isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Failed to generate PSUR.
        </Alert>
      )}

      {/* Error from list */}
      {isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Failed to load PMS reports.
        </Alert>
      )}

      {/* Table */}
      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Period</TableCell>
              <TableCell>Report Type</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Generated At</TableCell>
              <TableCell>Summary</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading ? (
              <SkeletonRows cols={5} />
            ) : items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} sx={{ p: 0, border: 0 }}>
                  <EmptyState
                    title="No PMS reports yet"
                    description="Periodic Safety Update Reports (PSUR) consolidate adverse-event counts, drift alerts, decision volume, and bias-audit deltas over each reporting period — required annually by EU MDR and quarterly for FDA-registered devices."
                    ingestHint="Click 'Generate PSUR' to draft a report from the last reporting period. Roadmap: scheduled job that auto-drafts each quarter and pings the compliance officer to review."
                    icon={<MonitorHeartIcon />}
                    primaryAction={{
                      label: 'Generate PSUR',
                      onClick: () => {
                        setPsurSuccess(false);
                        generateMutation.mutate();
                      },
                    }}
                  />
                </TableCell>
              </TableRow>
            ) : (
              items.map((report) => (
                <TableRow key={report.id} hover>
                  <TableCell>
                    <Typography variant="body2">
                      {new Date(report.period_start).toLocaleDateString()} →{' '}
                      {new Date(report.period_end).toLocaleDateString()}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={report.report_type.toUpperCase()}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={report.status}
                      color={statusColor(report.status)}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    {report.generated_at ? (
                      <Typography variant="body2" color="text.secondary">
                        {new Date(report.generated_at).toLocaleDateString()}
                      </Typography>
                    ) : (
                      <Typography variant="body2" color="text.disabled">
                        —
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    {report.summary ? (
                      <Typography variant="body2">
                        {truncate(report.summary, 80)}
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

export default PostMarketSurveillance;
