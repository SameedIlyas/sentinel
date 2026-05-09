import React, { useState } from 'react';
import {
  Box, Typography, Paper, Chip, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, TablePagination, LinearProgress,
  Alert, Skeleton,
} from '@mui/material';
import AttachMoneyIcon from '@mui/icons-material/AttachMoney';
import { useQuery } from '@tanstack/react-query';
import { listRevenueCycleAudits } from '@/api/healthcare';
import { RevenueCycleAudit as RevenueCycleAuditType } from '@/types/index';
import EmptyState from '@/components/common/EmptyState';

function riskScoreColor(score: number): 'error' | 'warning' | 'success' {
  if (score > 70) return 'error';
  if (score >= 40) return 'warning';
  return 'success';
}

function riskScoreBarColor(score: number): string {
  if (score > 70) return '#df1b41';
  if (score >= 40) return '#f59e0b';
  return '#0ea371';
}

function FlagCell({ count }: { count: number }) {
  if (count === 0) {
    return <Typography color="text.secondary">—</Typography>;
  }
  return (
    <Chip
      label={count}
      size="small"
      sx={{ backgroundColor: '#df1b41', color: '#fff', fontWeight: 700 }}
    />
  );
}

function countFlagged(items: RevenueCycleAuditType[]): number {
  return items.filter(
    (a) => a.upcoding_flags > 0 || a.unbundling_flags > 0 || a.modifier_flags > 0
  ).length;
}

const RevenueCycleAudit: React.FC = () => {
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['revenueCycleAudits', page],
    queryFn: () => listRevenueCycleAudits({ page: page + 1 }),
  });

  const handleChangePage = (_: unknown, newPage: number) => setPage(newPage);
  const handleChangeRowsPerPage = (e: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(e.target.value, 10));
    setPage(0);
  };

  const items = Array.isArray(data?.items) ? data!.items : [];
  const flaggedCount = countFlagged(items);
  const cleanCount = items.length - flaggedCount;

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 3 }}>
        <AttachMoneyIcon sx={{ color: 'primary.main', fontSize: 28 }} />
        <Box>
          <Typography variant="h4">Revenue Cycle Integrity</Typography>
          <Typography variant="body2" color="text.secondary">
            AI-assisted billing audit — upcoding, unbundling, and modifier flag detection
          </Typography>
        </Box>
      </Box>

      {isError && (
        <Alert severity="error" sx={{ mb: 3 }}>
          Failed to load revenue cycle audit data. Please try again.
        </Alert>
      )}

      <Box sx={{ display: 'flex', gap: 1.5, mb: 3, flexWrap: 'wrap' }}>
        {isLoading ? (
          [0, 1, 2].map((i) => <Skeleton key={i} variant="rounded" width={120} height={32} />)
        ) : data ? (
          <>
            <Chip label={`Total Audited: ${data.total}`} variant="outlined" />
            <Chip
              label={`Flagged: ${flaggedCount}`}
              sx={{ backgroundColor: flaggedCount > 0 ? '#df1b41' : undefined, color: flaggedCount > 0 ? '#fff' : undefined }}
            />
            <Chip
              label={`Clean: ${cleanCount}`}
              sx={{ backgroundColor: '#0ea371', color: '#fff' }}
            />
          </>
        ) : null}
      </Box>

      <Paper>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Claim ID</TableCell>
                <TableCell>Risk Score</TableCell>
                <TableCell>Upcoding</TableCell>
                <TableCell>Unbundling</TableCell>
                <TableCell>Modifier</TableCell>
                <TableCell>Recommendation</TableCell>
                <TableCell>Audited At</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {isLoading ? (
                [0, 1, 2, 3, 4].map((i) => (
                  <TableRow key={i}>
                    {[0, 1, 2, 3, 4, 5, 6].map((j) => (
                      <TableCell key={j}><Skeleton variant="text" /></TableCell>
                    ))}
                  </TableRow>
                ))
              ) : items.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} sx={{ p: 0, border: 0 }}>
                    <EmptyState
                      title="No claims audited yet"
                      description="Each claim is scored for upcoding, unbundling, and modifier misuse risk against CMS national billing benchmarks. Anything above 0.7 is flagged for human review."
                      ingestHint="Audits are created when your billing pipeline POSTs claim metadata to /v1/finance/revenue-cycle. Roadmap: automatic scoring against the bundled coding-benchmarks dataset (CMS Medicare 2025)."
                      icon={<AttachMoneyIcon />}
                    />
                  </TableCell>
                </TableRow>
              ) : (
                items.map((audit) => {
                  const scoreColor = riskScoreColor(audit.risk_score);
                  const barColor = riskScoreBarColor(audit.risk_score);
                  // Backend stores findings as list[{type, severity, description}]
                  // — derive flag counts by counting matching types.
                  const findings = (audit as unknown as {
                    findings?: Array<{ type?: string; finding_type?: string }>;
                  }).findings;
                  const findingsList = Array.isArray(findings) ? findings : [];
                  const countOf = (kind: string): number => {
                    const fromExplicit = (audit as unknown as Record<string, unknown>)[
                      `${kind}_flags`
                    ];
                    if (typeof fromExplicit === 'number') return fromExplicit;
                    return findingsList.filter(
                      (f) => (f.type ?? f.finding_type) === kind,
                    ).length;
                  };
                  const upcoding = countOf('upcoding');
                  const unbundling = countOf('unbundling');
                  const modifier = countOf('modifier');
                  return (
                    <TableRow key={audit.id} hover>
                      <TableCell sx={{ fontFamily: 'monospace', fontSize: 12 }}>
                        {audit.claim_id}
                      </TableCell>
                      <TableCell sx={{ minWidth: 140 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <LinearProgress
                            variant="determinate"
                            value={Math.min(audit.risk_score, 100)}
                            color={scoreColor}
                            sx={{
                              flex: 1, height: 8, borderRadius: 4,
                              '& .MuiLinearProgress-bar': { backgroundColor: barColor },
                            }}
                          />
                          <Typography variant="caption" sx={{ minWidth: 28 }}>
                            {audit.risk_score}
                          </Typography>
                        </Box>
                      </TableCell>
                      <TableCell><FlagCell count={upcoding} /></TableCell>
                      <TableCell><FlagCell count={unbundling} /></TableCell>
                      <TableCell><FlagCell count={modifier} /></TableCell>
                      <TableCell sx={{ maxWidth: 220 }}>
                        {(() => {
                          // Backend returns `findings` (list of {type, severity, description});
                          // older API returned a single `recommendation` string. Render either.
                          const findings = (audit as unknown as {
                            findings?: Array<{ description?: string }>;
                          }).findings;
                          const recText: string =
                            typeof audit.recommendation === 'string' && audit.recommendation
                              ? audit.recommendation
                              : Array.isArray(findings) && findings.length > 0
                                ? findings.map((f) => f?.description ?? '').filter(Boolean).join('; ')
                                : '—';
                          const display = recText.length > 50
                            ? recText.slice(0, 50) + '…'
                            : recText;
                          return (
                            <Typography variant="body2" noWrap title={recText}>
                              {display}
                            </Typography>
                          );
                        })()}
                      </TableCell>
                      <TableCell sx={{ whiteSpace: 'nowrap' }}>
                        {(() => {
                          const ts =
                            audit.audited_at
                            ?? (audit as unknown as { created_at?: string }).created_at;
                          return ts ? new Date(ts).toLocaleDateString() : '—';
                        })()}
                      </TableCell>
                    </TableRow>
                  );
                })
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

export default RevenueCycleAudit;
