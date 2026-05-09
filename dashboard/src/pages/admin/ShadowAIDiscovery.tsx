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
import EmptyState from '@/components/common/EmptyState';

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
                    <TableCell colSpan={8} sx={{ p: 0, border: 0 }}>
                      <EmptyState
                        title={severityFilter !== 'all' ? `No ${severityFilter}-severity detections` : 'No shadow AI detected yet'}
                        description="Shadow AI = unauthorized AI tools (ChatGPT, Claude, Gemini, etc.) being used outside your governance perimeter, often with PHI exposure risk."
                        ingestHint="Detection requires a network/API-gateway integration (Cloudflare Zero Trust, Zscaler, Netskope, Palo Alto NGFW) to forward egress logs. See docs/ROADMAP_TIER3_NO_DATA_SOURCE.md for the integration plan."
                        icon={<SecurityIcon />}
                      />
                    </TableCell>
                  </TableRow>
                )
              : items.map((detection) => {
                  // Backend returns: ai_provider, destination_host, source_ip,
                  // phi_risk_level ("none"/"low"/"medium"/"high"), status
                  // ("detected"/"investigating"/"approved"/"blocked"). The TS
                  // type names are different — read both shapes here.
                  const r = detection as unknown as {
                    id: string;
                    detected_at?: string;
                    detected_tool?: string;
                    ai_provider?: string;
                    endpoint_domain?: string;
                    destination_host?: string;
                    staff_ip?: string;
                    source_ip?: string;
                    hipaa_risk?: boolean;
                    phi_risk_level?: string;
                    severity?: string;
                    allowlisted?: boolean;
                    status?: string;
                    department?: string;
                  };
                  const tool = r.detected_tool ?? r.ai_provider ?? '—';
                  const domain = r.endpoint_domain ?? r.destination_host ?? '—';
                  const ip = r.staff_ip ?? r.source_ip ?? '—';
                  const phiRisk = r.phi_risk_level ?? (r.hipaa_risk ? 'high' : 'none');
                  const phiHigh = phiRisk === 'high';
                  // Severity falls out of phi_risk_level when no explicit field exists
                  const severity =
                    r.severity
                    ?? (phiRisk === 'high'   ? 'high'
                       : phiRisk === 'medium' ? 'medium'
                       : phiRisk === 'low'    ? 'low'
                       : 'low');
                  const isAllowlisted = r.allowlisted === true || r.status === 'approved';
                  const status = r.status ?? (isAllowlisted ? 'approved' : 'detected');
                  const detectedAt = r.detected_at
                    ? new Date(r.detected_at).toLocaleDateString()
                    : '—';
                  return (
                    <TableRow key={r.id} hover>
                      <TableCell>{detectedAt}</TableCell>
                      <TableCell>{tool}</TableCell>
                      <TableCell>{domain}</TableCell>
                      <TableCell sx={{ fontFamily: 'monospace', fontSize: 12 }}>{ip}</TableCell>
                      <TableCell>
                        <Chip
                          label={phiHigh ? 'HIGH' : phiRisk.toUpperCase()}
                          color={phiHigh ? 'error' : phiRisk === 'medium' ? 'warning' : 'success'}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={severity}
                          color={severityColor(severity as ShadowAISeverity)}
                          size="small"
                          sx={
                            severity === 'critical'
                              ? { backgroundColor: 'error.dark', color: 'error.contrastText' }
                              : undefined
                          }
                        />
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={status}
                          color={isAllowlisted ? 'success' : status === 'blocked' ? 'error' : 'default'}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        <Button
                          size="small"
                          variant="outlined"
                          disabled={isAllowlisted || allowlistMutation.isPending}
                          onClick={() => allowlistMutation.mutate(r.id)}
                        >
                          {isAllowlisted ? 'Allowlisted' : 'Allowlist'}
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
    </Box>
  );
};

export default ShadowAIDiscovery;
