import React, { useState, useEffect } from 'react';
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
  List,
  ListItem,
  ListItemText,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  SmartToy as AgentIcon,
  Block as BlockIcon,
  CheckCircle as AllowIcon,
  FiberManualRecord as StatusIcon,
  Timeline as TimelineIcon,
  Storage as SystemIcon,
  Warning as ViolationIcon,
} from '@mui/icons-material';
import { format, formatDistanceToNow } from 'date-fns';
import agentsApi from '@/api/agents';
import apiClient from '@/api/client';
import { Agent, AgentActivityMetrics, AuditLog } from '@/types';

const AgentDetail: React.FC = () => {
  const { agentId } = useParams<{ agentId: string }>();
  const navigate = useNavigate();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [metrics, setMetrics] = useState<AgentActivityMetrics | null>(null);
  const [recentActivity, setRecentActivity] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

      // Fetch agent details and metrics in parallel
      const [agentData, metricsData] = await Promise.all([
        agentsApi.getAgent(agentId),
        agentsApi.getAgentMetrics(agentId),
      ]);

      setAgent(agentData);
      setMetrics(metricsData);

      // Fetch recent activity (audit logs)
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

  const getStatusColor = (status: string): 'success' | 'default' | 'error' => {
    switch (status) {
      case 'active':
        return 'success';
      case 'inactive':
        return 'default';
      case 'suspended':
        return 'error';
      default:
        return 'default';
    }
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

  const getDecisionColor = (decision: string): 'success' | 'error' | 'warning' => {
    switch (decision.toLowerCase()) {
      case 'allowed':
      case 'approved':
        return 'success';
      case 'blocked':
        return 'error';
      default:
        return 'warning';
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <CircularProgress size={60} />
      </Box>
    );
  }

  if (error || !agent || !metrics) {
    return (
      <Box>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
          <IconButton onClick={() => navigate('/agents')} sx={{ mr: 2 }}>
            <ArrowBackIcon />
          </IconButton>
          <Typography variant="h4" sx={{ fontWeight: 'bold' }}>
            Agent Details
          </Typography>
        </Box>
        <Alert severity="error">{error || 'Agent not found'}</Alert>
      </Box>
    );
  }

  const blockedActions = recentActivity.filter(
    (log) => log.decision === 'blocked'
  );

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
        <IconButton onClick={() => navigate('/agents')} sx={{ mr: 2 }}>
          <ArrowBackIcon />
        </IconButton>
        <Box sx={{ flex: 1 }}>
          <Typography variant="h4" sx={{ fontWeight: 'bold' }}>
            {agent.name}
          </Typography>
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ fontFamily: 'monospace', mt: 0.5 }}
          >
            {agent.agent_id}
          </Typography>
        </Box>
        <Chip
          icon={<StatusIcon sx={{ fontSize: 12 }} />}
          label={agent.status.toUpperCase()}
          color={getStatusColor(agent.status)}
        />
      </Box>

      <Grid container spacing={3}>
        {/* Agent Metadata */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <AgentIcon sx={{ mr: 1, color: 'primary.main' }} />
                <Typography variant="h6">Agent Information</Typography>
              </Box>
              <Divider sx={{ mb: 2 }} />
              <List dense>
                <ListItem>
                  <ListItemText
                    primary="Status"
                    secondary={
                      <Chip
                        label={agent.status.toUpperCase()}
                        color={getStatusColor(agent.status)}
                        size="small"
                      />
                    }
                  />
                </ListItem>
                {agent.description && (
                  <ListItem>
                    <ListItemText primary="Description" secondary={agent.description} />
                  </ListItem>
                )}
                <ListItem>
                  <ListItemText
                    primary="First Seen"
                    secondary={format(new Date(metrics.first_seen), 'MMM dd, yyyy HH:mm')}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="Last Active"
                    secondary={
                      metrics.last_active
                        ? `${format(new Date(metrics.last_active), 'MMM dd, yyyy HH:mm')} (${formatDistanceToNow(new Date(metrics.last_active), { addSuffix: true })})`
                        : 'Never'
                    }
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="Created"
                    secondary={format(new Date(agent.created_at), 'MMM dd, yyyy HH:mm')}
                  />
                </ListItem>
              </List>
            </CardContent>
          </Card>
        </Grid>

        {/* Activity Metrics */}
        <Grid item xs={12} md={8}>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={4}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" variant="body2">
                    Total Actions
                  </Typography>
                  <Typography variant="h4" sx={{ fontWeight: 'bold', my: 1 }}>
                    {metrics.total_actions.toLocaleString()}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" variant="body2">
                    Allowed Actions
                  </Typography>
                  <Typography variant="h4" sx={{ fontWeight: 'bold', my: 1, color: 'success.main' }}>
                    {metrics.allowed_actions.toLocaleString()}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary" variant="body2">
                    Blocked Actions
                  </Typography>
                  <Typography variant="h4" sx={{ fontWeight: 'bold', my: 1, color: 'error.main' }}>
                    {metrics.blocked_actions.toLocaleString()}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          {/* Systems Accessed */}
          <Card sx={{ mt: 2 }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <SystemIcon sx={{ mr: 1, color: 'info.main' }} />
                <Typography variant="h6">Systems Accessed</Typography>
              </Box>
              <Divider sx={{ mb: 2 }} />
              {metrics.systems_accessed && metrics.systems_accessed.length > 0 ? (
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                  {metrics.systems_accessed.map((system, idx) => (
                    <Chip key={idx} label={system} variant="outlined" />
                  ))}
                </Box>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  No systems accessed yet
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Policy Violations */}
        {blockedActions.length > 0 && (
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <ViolationIcon sx={{ mr: 1, color: 'error.main' }} />
                  <Typography variant="h6">Recent Policy Violations</Typography>
                  <Chip
                    label={blockedActions.length}
                    size="small"
                    color="error"
                    sx={{ ml: 1 }}
                  />
                </Box>
                <Divider sx={{ mb: 2 }} />
                <TableContainer>
                  <Table size="small">
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
                        <TableRow key={log.id}>
                          <TableCell>
                            <Typography variant="body2">
                              {format(new Date(log.timestamp), 'MMM dd, HH:mm:ss')}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                              {log.tool_name || 'N/A'}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Chip label={log.system_accessed} size="small" variant="outlined" />
                          </TableCell>
                          <TableCell>
                            <Typography variant="caption" color="text.secondary">
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

        {/* Activity Timeline */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <TimelineIcon sx={{ mr: 1, color: 'primary.main' }} />
                <Typography variant="h6">Recent Activity</Typography>
              </Box>
              <Divider sx={{ mb: 2 }} />
              {recentActivity.length > 0 ? (
                <TableContainer>
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell width="40px"></TableCell>
                        <TableCell>Timestamp</TableCell>
                        <TableCell>Action</TableCell>
                        <TableCell>System</TableCell>
                        <TableCell>Decision</TableCell>
                        <TableCell>User</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {recentActivity.map((log) => (
                        <TableRow key={log.id}>
                          <TableCell>{getDecisionIcon(log.decision)}</TableCell>
                          <TableCell>
                            <Typography variant="body2">
                              {format(new Date(log.timestamp), 'MMM dd, yyyy HH:mm:ss')}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {formatDistanceToNow(new Date(log.timestamp), { addSuffix: true })}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                              {log.tool_name || 'N/A'}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Chip label={log.system_accessed} size="small" variant="outlined" />
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={log.decision.toUpperCase()}
                              color={getDecisionColor(log.decision)}
                              size="small"
                            />
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2" color="text.secondary">
                              {log.user_id || 'N/A'}
                            </Typography>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <Typography variant="body2" color="text.secondary">
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
