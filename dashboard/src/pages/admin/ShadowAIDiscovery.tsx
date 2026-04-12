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
import SecurityIcon from '@mui/icons-material/Security';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listShadowAIDetections, allowlistShadowAI } from '@/api/healthcare';
import type { ShadowAISeverity } from '@/types';

const SEVERITY_FILTERS: Array<ShadowAISeverity | 'all'> = ['all', 'low', 'medium', 'high', 'critical'];

function severityColor(severity: ShadowAISeverity): 'default' | 'warning' | 'error' {
  if (severity === 'low') return 'default';
  if (severity === 'medium') return 'warning';
  return 'error';
}

const ShadowAIDiscovery: React.FC = () => {
  const queryClient = useQueryClient();
  const [severityFilter, setSeverityFilter] = useState<ShadowAISeverity | 'all'>('all');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['shadowAI', severityFilter, page, rowsPerPage],
    queryFn: () =>
      listShadowAIDetections({
        severity: severityFilter === 'all' ? undefined : severityFilter,
        page: page + 1,
      }),
  });

  const allowlistMutation = useMutation({
    mutationFn: (id: string) => allowlistShadowAI(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['shadowAI'] });
    },
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  const hipaaCount = items.filter((d) => d.hipaa_risk).length;
  const allowlistedCount = items.filter((d) => d.allowlisted).length;

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 3 }}>
        <SecurityIcon sx={{ color: 'primary.main', fontSize: 28 }} />
        <Box>
          <Typography variant="h4">Shadow AI Discovery</Typography>
          <Typography variant="body2" color="text.secondary">
            Unauthorized AI tool detection and risk assessment
          </Typography>
        </Box>
      </Box>

      <Box sx={{ display: 'flex', gap: 1.5, mb: 3, flexWrap: 'wrap' }}>
        <Chip label={`Total detected: ${total}`} variant="outlined" />
        <Chip label={`HIPAA Risk: ${hipaaCount}`} color="error" />
        <Chip label={`Allowlisted: ${allowlistedCount}`} color="success" />
      </Box>

      <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
        {SEVERITY_FILTERS.map((s) => (
          <Chip
            key={s}
            label={s === 'all' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
            variant={severityFilter === s ? 'filled' : 'outlined'}
            color={s === 'all' ? 'default' : severityColor(s as ShadowAISeverity)}
            onClick={() => {
              setSeverityFilter(s);
              setPage(0);
            }}
            clickable
          />
        ))}
      </Box>

      {isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Failed to load shadow AI detections
        </Alert>
      )}

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Detected At</TableCell>
              <TableCell>Tool</TableCell>
              <TableCell>Domain</TableCell>
              <TableCell>Staff IP</TableCell>
              <TableCell>HIPAA Risk</TableCell>
              <TableCell>Severity</TableCell>
              <TableCell>Allowlisted</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading
              ? Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    {Array.from({ length: 8 }).map((__, j) => (
                      <TableCell key={j}>
                        <Skeleton variant="text" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              : items.length === 0
              ? (
                  <TableRow>
                    <TableCell colSpan={8} align="center">
                      <Typography variant="body2" color="text.secondary" sx={{ py: 3 }}>
                        No shadow AI detections found
                      </Typography>
                    </TableCell>
                  </TableRow>
                )
              : items.map((detection) => (
                  <TableRow key={detection.id} hover>
                    <TableCell>
                      {new Date(detection.detected_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>{detection.detected_tool}</TableCell>
                    <TableCell>{detection.endpoint_domain}</TableCell>
                    <TableCell>{detection.staff_ip ?? '—'}</TableCell>
                    <TableCell>
                      <Chip
                        label={detection.hipaa_risk ? 'YES' : 'NO'}
                        color={detection.hipaa_risk ? 'error' : 'success'}
                        size="small"
                      />
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={detection.severity}
                        color={severityColor(detection.severity)}
                        size="small"
                        sx={
                          detection.severity === 'critical'
                            ? { backgroundColor: 'error.dark', color: 'error.contrastText' }
                            : undefined
                        }
                      />
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={detection.allowlisted ? 'Allowlisted' : 'Active'}
                        color={detection.allowlisted ? 'success' : 'default'}
                        size="small"
                      />
                    </TableCell>
                    <TableCell>
                      <Button
                        size="small"
                        variant="outlined"
                        disabled={detection.allowlisted || allowlistMutation.isPending}
                        onClick={() => allowlistMutation.mutate(detection.id)}
                      >
                        Allowlist
                      </Button>
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

export default ShadowAIDiscovery;
