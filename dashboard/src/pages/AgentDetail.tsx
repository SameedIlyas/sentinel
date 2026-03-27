import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Alert,
  Divider,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  useTheme,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import {
  ArrowBack as ArrowBackIcon,
  Block as BlockIcon,
  CheckCircle as AllowIcon,
  Timeline as TimelineIcon,
  Storage as SystemIcon,
  Warning as ViolationIcon,
} from '@mui/icons-material';
import { format, formatDistanceToNow } from 'date-fns';
import agentsApi from '@/api/agents';
import apiClient from '@/api/client';
import { Agent, AgentActivityMetrics, AuditLog } from '@/types';
import { useAppStyles } from '@/hooks/useAppStyles';

function useSurfaceCardSx() {
  const styles = useAppStyles();
  return useMemo(
    () => ({
      bgcolor: 'background.paper' as const,
      border: `1px solid ${styles.theme.palette.divider}`,
      borderRadius: 2,
      boxShadow: styles.dark ? 'none' : '0 1px 3px rgba(0,0,0,0.08)',
    }),
    [styles.dark, styles.theme.palette.divider]
  );
}

function StatusBadge({ status }: { status: string }) {
  const theme = useTheme();
  const c =
    status === 'active'
      ? theme.palette.success.main
      : status === 'suspended'
        ? theme.palette.error.main
        : theme.palette.text.secondary;

  return (
    <Box
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 1,
        px: 1.5,
        py: 0.75,
        borderRadius: 999,
        bgcolor: alpha(c, 0.12),
        border: `1px solid ${alpha(c, 0.35)}`,
      }}
    >
      <Box
        component="span"
        sx={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          bgcolor: c,
          boxShadow: `0 0 0 2px ${alpha(c, 0.25)}`,
        }}
      />
      <Typography
        component="span"
        sx={{
          color: c,
          fontWeight: 600,
          fontSize: '0.75rem',
          letterSpacing: '0.06em',
        }}
      >
        {status.toUpperCase()}
      </Typography>
    </Box>
  );
}

function InfoCard({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  const surfaceCardSx = useSurfaceCardSx();

  return (
    <Card sx={surfaceCardSx}>
      <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
        <Typography
          variant="caption"
          sx={{
            color: 'text.secondary',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            fontWeight: 600,
          }}
        >
          {label}
        </Typography>
        <Box sx={{ mt: 1 }}>{children}</Box>
      </CardContent>
    </Card>
  );
}

const AgentDetail: React.FC = () => {
  const { agentId } = useParams<{ agentId: string }>();
  const navigate = useNavigate();
  const theme = useTheme();
  const styles = useAppStyles();
  const surfaceCardSx = useSurfaceCardSx();
  const { dark } = styles;

  const [agent, setAgent] = useState<Agent | null>(null);
  const [metrics, setMetrics] = useState<AgentActivityMetrics | null>(null);
  const [recentActivity, setRecentActivity] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const tableSx = useMemo(
    () => ({
      '& .MuiTableCell-root': {
        fontSize: '0.8rem',
        borderColor: theme.palette.divider,
        color: 'text.primary',
      },
      '& .MuiTableHead-root .MuiTableCell-root': {
        fontWeight: 600,
        color: 'text.secondary',
        borderBottom: `1px solid ${theme.palette.divider}`,
      },
      '& .MuiTableBody-root .MuiTableRow-root:last-of-type .MuiTableCell-root': {
        borderBottom: 'none',
      },
    }),
    [theme.palette.divider]
  );

  const headerIconButtonSx = useMemo(
    () => ({
      color: 'text.primary',
      border: `1px solid ${theme.palette.divider}`,
      borderRadius: 1.5,
      bgcolor: 'background.paper',
      '&:hover': { bgcolor: styles.hoverBg },
    }),
    [theme.palette.divider, styles.hoverBg]
  );

  const pageTitleSx = {
    fontWeight: 700,
    letterSpacing: '-0.02em',
    color: 'text.primary',
  };

  const decisionChipSx = (decision: string) => {
    const d = decision.toLowerCase();
    if (d === 'allowed' || d === 'approved') {
      const c = theme.palette.success.main;
      return { bgcolor: alpha(c, 0.15), color: c, border: `1px solid ${alpha(c, 0.35)}` };
    }
    if (d === 'blocked') {
      const c = theme.palette.error.main;
      return { bgcolor: alpha(c, 0.12), color: c, border: `1px solid ${alpha(c, 0.35)}` };
    }
    const c = theme.palette.warning.main;
    return { bgcolor: alpha(c, 0.12), color: c, border: `1px solid ${alpha(c, 0.35)}` };
  };

  const getDecisionIcon = (decision: string) => {
    switch (decision.toLowerCase()) {
      case 'allowed':
      case 'approved':
        return <AllowIcon sx={{ color: 'success.main', fontSize: 18 }} />;
      case 'blocked':
        return <BlockIcon sx={{ color: 'error.main', fontSize: 18 }} />;
      default:
        return null;
    }
  };

  const chipBorder = `1px solid ${theme.palette.divider}`;
  const mutedCellColor = dark ? 'rgba(255,255,255,0.5)' : 'rgba(0,0,0,0.5)';
  const userCellColor = dark ? 'rgba(255,255,255,0.55)' : 'rgba(0,0,0,0.55)';

  useEffect(() => {
    if (agentId) {
      fetchAgentDetails();
    }
  }, [agentId]);

  const fetchAgentDetails = async () => {
    if (!agentId) return;

    try {
      setLoading(true);
      setError(null);

      const [agentData, metricsData] = await Promise.all([
        agentsApi.getAgent(agentId),
        agentsApi.getAgentMetrics(agentId),
      ]);

      setAgent(agentData);
      setMetrics(metricsData);

      const activityResponse = await apiClient.get<{ logs: AuditLog[]; total: number }>(
        '/v1/audit/logs',
        {
          params: {
            filter_agent_id: agentId,
            page: 1,
            page_size: 20,
          },
        }
      );
      setRecentActivity(activityResponse.logs);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch agent details');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '60vh',
          bgcolor: 'background.default',
        }}
      >
        <CircularProgress size={60} sx={{ color: 'primary.main' }} />
      </Box>
    );
  }

  if (error || !agent || !metrics) {
    return (
      <Box sx={{ bgcolor: 'background.default', minHeight: '100%', color: 'text.primary', pb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
          <IconButton onClick={() => navigate('/agents')} sx={headerIconButtonSx} aria-label="Back to agents">
            <ArrowBackIcon />
          </IconButton>
          <Typography variant="h4" sx={pageTitleSx}>
            Agent Details
          </Typography>
        </Box>
        <Alert
          severity="error"
          sx={{
            bgcolor: alpha(theme.palette.error.main, 0.12),
            color: 'text.primary',
            border: `1px solid ${alpha(theme.palette.error.main, 0.35)}`,
            '& .MuiAlert-icon': { color: theme.palette.error.main },
          }}
        >
          {error || 'Agent not found'}
        </Alert>
      </Box>
    );
  }

  const blockedActions = recentActivity.filter(
    (log) => log.decision === 'blocked'
  );

  const primaryMain = theme.palette.primary.main;
  const errorMain = theme.palette.error.main;

  return (
    <Box sx={{ bgcolor: 'background.default', minHeight: '100%', color: 'text.primary', pb: 4 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3, flexWrap: 'wrap' }}>
        <IconButton onClick={() => navigate('/agents')} sx={headerIconButtonSx} aria-label="Back to agents">
          <ArrowBackIcon />
        </IconButton>
        <Box sx={{ flex: 1, minWidth: 200 }}>
          <Typography variant="h4" sx={pageTitleSx}>
            {agent.name}
          </Typography>
        </Box>
        <StatusBadge status={agent.status} />
      </Box>

      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={4}>
          <InfoCard label="Agent ID">
            <Typography
              sx={{ fontFamily: styles.mono, fontSize: '0.85rem', color: 'text.primary', wordBreak: 'break-all' }}
            >
              {agent.agent_id || agent.id}
            </Typography>
          </InfoCard>
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <InfoCard label="Status">
            <StatusBadge status={agent.status} />
          </InfoCard>
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <InfoCard label="First seen">
            <Typography sx={{ fontSize: '0.9rem' }}>
              {format(new Date(metrics.first_seen), 'MMM dd, yyyy HH:mm')}
            </Typography>
          </InfoCard>
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <InfoCard label="Last active">
            <Typography sx={{ fontSize: '0.9rem' }}>
              {metrics.last_active
                ? `${format(new Date(metrics.last_active), 'MMM dd, yyyy HH:mm')} (${formatDistanceToNow(new Date(metrics.last_active), { addSuffix: true })})`
                : 'Never'}
            </Typography>
          </InfoCard>
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <InfoCard label="Created">
            <Typography sx={{ fontSize: '0.9rem' }}>
              {format(new Date(agent.created_at), 'MMM dd, yyyy HH:mm')}
            </Typography>
          </InfoCard>
        </Grid>
        {agent.description && (
          <Grid item xs={12}>
            <InfoCard label="Description">
              <Typography sx={{ fontSize: '0.9rem', color: 'text.secondary' }}>{agent.description}</Typography>
            </InfoCard>
          </Grid>
        )}
      </Grid>

      <Grid container spacing={2}>
        <Grid item xs={12}>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={4}>
              <Card sx={surfaceCardSx}>
                <CardContent sx={{ p: 2 }}>
                  <Typography
                    variant="caption"
                    sx={{
                      color: 'text.secondary',
                      textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                      fontWeight: 600,
                    }}
                  >
                    Total actions
                  </Typography>
                  <Typography variant="h4" sx={{ fontWeight: 700, my: 1, color: 'text.primary', letterSpacing: '-0.02em' }}>
                    {metrics.total_actions.toLocaleString()}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Card sx={surfaceCardSx}>
                <CardContent sx={{ p: 2 }}>
                  <Typography
                    variant="caption"
                    sx={{
                      color: 'text.secondary',
                      textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                      fontWeight: 600,
                    }}
                  >
                    Allowed actions
                  </Typography>
                  <Typography variant="h4" sx={{ fontWeight: 700, my: 1, color: 'success.main', letterSpacing: '-0.02em' }}>
                    {metrics.allowed_actions.toLocaleString()}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Card sx={surfaceCardSx}>
                <CardContent sx={{ p: 2 }}>
                  <Typography
                    variant="caption"
                    sx={{
                      color: 'text.secondary',
                      textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                      fontWeight: 600,
                    }}
                  >
                    Blocked actions
                  </Typography>
                  <Typography variant="h4" sx={{ fontWeight: 700, my: 1, color: 'error.main', letterSpacing: '-0.02em' }}>
                    {metrics.blocked_actions.toLocaleString()}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          <Card sx={{ ...surfaceCardSx, mt: 2 }}>
            <CardContent sx={{ p: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <SystemIcon sx={{ mr: 1, color: primaryMain }} />
                <Typography variant="h6" sx={{ fontWeight: 600, color: 'text.primary' }}>
                  Systems accessed
                </Typography>
              </Box>
              <Divider sx={{ mb: 2, borderColor: theme.palette.divider }} />
              {metrics.systems_accessed && metrics.systems_accessed.length > 0 ? (
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                  {metrics.systems_accessed.map((system, idx) => (
                    <Chip
                      key={idx}
                      label={system}
                      size="small"
                      sx={{
                        fontFamily: styles.mono,
                        fontSize: '0.75rem',
                        bgcolor: alpha(primaryMain, 0.1),
                        color: 'text.primary',
                        border: `1px solid ${alpha(primaryMain, 0.25)}`,
                      }}
                    />
                  ))}
                </Box>
              ) : (
                <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                  No systems accessed yet
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        {blockedActions.length > 0 && (
          <Grid item xs={12}>
            <Card sx={surfaceCardSx}>
              <CardContent sx={{ p: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2, flexWrap: 'wrap', gap: 1 }}>
                  <ViolationIcon sx={{ color: 'error.main' }} />
                  <Typography variant="h6" sx={{ fontWeight: 600, color: 'text.primary' }}>
                    Recent policy violations
                  </Typography>
                  <Chip
                    label={blockedActions.length}
                    size="small"
                    sx={{
                      bgcolor: alpha(errorMain, 0.15),
                      color: errorMain,
                      border: `1px solid ${alpha(errorMain, 0.35)}`,
                      fontWeight: 600,
                    }}
                  />
                </Box>
                <Divider sx={{ mb: 2, borderColor: theme.palette.divider }} />
                <TableContainer>
                  <Table size="small" sx={tableSx}>
                    <TableHead>
                      <TableRow>
                        <TableCell>Timestamp</TableCell>
                        <TableCell>Action</TableCell>
                        <TableCell>System</TableCell>
                        <TableCell>Reason</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {blockedActions.slice(0, 10).map((log) => (
                        <TableRow key={log.id} sx={{ '&:hover': { bgcolor: styles.hoverBg } }}>
                          <TableCell>
                            <Typography sx={{ fontSize: '0.8rem' }}>
                              {format(new Date(log.timestamp), 'MMM dd, HH:mm:ss')}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography sx={{ fontFamily: styles.mono, fontSize: '0.8rem' }}>
                              {log.tool_name || 'N/A'}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={log.system_accessed}
                              size="small"
                              sx={{
                                fontSize: '0.7rem',
                                fontFamily: styles.mono,
                                bgcolor: styles.surfaceBg,
                                color: 'text.primary',
                                border: chipBorder,
                              }}
                            />
                          </TableCell>
                          <TableCell>
                            <Typography sx={{ fontSize: '0.75rem', color: mutedCellColor }}>
                              {log.reason || 'Policy violation'}
                            </Typography>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </CardContent>
            </Card>
          </Grid>
        )}

        <Grid item xs={12}>
          <Card sx={surfaceCardSx}>
            <CardContent sx={{ p: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <TimelineIcon sx={{ mr: 1, color: primaryMain }} />
                <Typography variant="h6" sx={{ fontWeight: 600, color: 'text.primary' }}>
                  Recent activity
                </Typography>
              </Box>
              <Divider sx={{ mb: 2, borderColor: theme.palette.divider }} />
              {recentActivity.length > 0 ? (
                <TableContainer>
                  <Table sx={tableSx}>
                    <TableHead>
                      <TableRow>
                        <TableCell width="40px" />
                        <TableCell>Timestamp</TableCell>
                        <TableCell>Action</TableCell>
                        <TableCell>System</TableCell>
                        <TableCell>Decision</TableCell>
                        <TableCell>User</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {recentActivity.map((log) => (
                        <TableRow key={log.id} sx={{ '&:hover': { bgcolor: styles.hoverBg } }}>
                          <TableCell>{getDecisionIcon(log.decision)}</TableCell>
                          <TableCell>
                            <Typography sx={{ fontSize: '0.8rem' }}>
                              {format(new Date(log.timestamp), 'MMM dd, yyyy HH:mm:ss')}
                            </Typography>
                            <Typography sx={{ fontSize: '0.7rem', color: 'text.secondary', display: 'block' }}>
                              {formatDistanceToNow(new Date(log.timestamp), { addSuffix: true })}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography sx={{ fontFamily: styles.mono, fontSize: '0.8rem' }}>
                              {log.tool_name || 'N/A'}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={log.system_accessed}
                              size="small"
                              sx={{
                                fontSize: '0.7rem',
                                fontFamily: styles.mono,
                                bgcolor: styles.surfaceBg,
                                color: 'text.primary',
                                border: chipBorder,
                              }}
                            />
                          </TableCell>
                          <TableCell>
                            <Chip label={log.decision.toUpperCase()} size="small" sx={decisionChipSx(log.decision)} />
                          </TableCell>
                          <TableCell>
                            <Typography
                              sx={{
                                fontSize: '0.8rem',
                                color: userCellColor,
                                fontFamily: log.user_id ? styles.mono : 'inherit',
                              }}
                            >
                              {log.user_id || 'N/A'}
                            </Typography>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                  No recent activity
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default AgentDetail;
