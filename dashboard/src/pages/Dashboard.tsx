import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Grid,
  Paper,
  Card,
  CardContent,
  CircularProgress,
  Alert as MuiAlert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  alpha,
} from '@mui/material';
import {
  SmartToy,
  Block,
  Warning,
  TrendingUp,
  FiberManualRecord as DotIcon,
} from '@mui/icons-material';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { format } from 'date-fns';
import dashboardApi from '@/api/dashboard';
import { DashboardMetrics } from '@/types';
import { useDashboardWebSocket } from '@/hooks/useWebSocket';
import { useAppStyles } from '@/hooks/useAppStyles';

const Dashboard: React.FC = () => {
  const { theme, chartTooltip, chartGrid, chartAxis } = useAppStyles();

  const CHART_COLORS = [
    theme.palette.primary.main,
    theme.palette.success.main,
    theme.palette.warning.main,
    theme.palette.error.main,
    theme.palette.info.main,
    '#a78bfa',
    '#ec4899',
  ];

  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  const handleMetricsUpdate = (newMetrics: DashboardMetrics) => {
    setMetrics(newMetrics);
    setLastUpdate(new Date());
    setLoading(false);
  };

  const { isConnected } = useDashboardWebSocket(handleMetricsUpdate);

  const fetchMetrics = async () => {
    try {
      setError(null);
      const data = await dashboardApi.getMetrics();
      setMetrics(data);
      setLastUpdate(new Date());
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch dashboard metrics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 60000);
    return () => clearInterval(interval);
  }, []);

  const StatCard: React.FC<{
    title: string;
    value: string | number;
    icon: React.ReactNode;
    color: string;
    subtitle?: string;
  }> = ({ title, value, icon, color, subtitle }) => (
    <Card>
      <CardContent sx={{ p: '20px !important' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box>
            <Typography variant="body2" sx={{ color: 'text.secondary', fontSize: '0.75rem', fontWeight: 500, mb: 1 }}>
              {title}
            </Typography>
            <Typography variant="h3" sx={{ fontWeight: 700, fontSize: '2rem', lineHeight: 1, mb: 0.5 }}>
              {value}
            </Typography>
            {subtitle && (
              <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.7rem' }}>
                {subtitle}
              </Typography>
            )}
          </Box>
          <Box
            sx={{
              bgcolor: alpha(color, 0.1),
              border: `1px solid ${alpha(color, 0.15)}`,
              borderRadius: '10px',
              p: 1.25,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {icon}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );

  const getSeverityColor = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical': return '#ef4444';
      case 'high': return '#f97316';
      case 'medium': return '#f59e0b';
      case 'low': return '#3b82f6';
      default: return '#64748b';
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <CircularProgress size={40} sx={{ color: 'primary.main' }} />
      </Box>
    );
  }

  if (error) {
    return (
      <Box>
        <Typography variant="h4" sx={{ fontWeight: 700, mb: 3, letterSpacing: '-0.02em' }}>Dashboard</Typography>
        <MuiAlert severity="error">{error}</MuiAlert>
      </Box>
    );
  }

  if (!metrics) {
    return (
      <Box>
        <Typography variant="h4" sx={{ fontWeight: 700, mb: 3, letterSpacing: '-0.02em' }}>Dashboard</Typography>
        <MuiAlert severity="info">No data available</MuiAlert>
      </Box>
    );
  }

  const activityData = metrics.activity_timeline.map((item) => ({
    time: format(new Date(item.timestamp), 'HH:mm'),
    count: item.count,
  }));

  const topAgentsData = metrics.top_agents.slice(0, 8).map((agent) => ({
    name: agent.agent_id.length > 16 ? agent.agent_id.substring(0, 16) + '...' : agent.agent_id,
    actions: agent.action_count,
  }));

  const systemsData = metrics.systems_accessed.slice(0, 8).map((system) => ({
    name: system.system,
    accesses: system.access_count,
  }));

  const totalAlerts = Object.values(metrics.alerts_by_severity).reduce((a, b) => a + b, 0);
  const alertsData = Object.entries(metrics.alerts_by_severity).map(([severity, count]) => ({
    name: severity,
    value: count,
  }));

  const primaryMain = theme.palette.primary.main;
  const paperBg = theme.palette.background.paper;

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700, letterSpacing: '-0.02em' }}>Dashboard</Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5 }}>
            Platform overview and real-time metrics
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
            <DotIcon sx={{ fontSize: 8, color: isConnected ? 'success.main' : 'text.secondary', animation: isConnected ? 'pulse 2s infinite' : 'none', '@keyframes pulse': { '0%, 100%': { opacity: 1 }, '50%': { opacity: 0.4 } } }} />
            <Typography variant="caption" sx={{ color: isConnected ? 'success.main' : 'text.secondary', fontWeight: 500 }}>
              {isConnected ? 'Live' : 'Offline'}
            </Typography>
          </Box>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            {format(lastUpdate, 'HH:mm:ss')}
          </Typography>
        </Box>
      </Box>

      <Grid container spacing={2.5}>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Active Agents"
            value={metrics.active_agents}
            icon={<SmartToy sx={{ color: 'primary.main', fontSize: 24 }} />}
            color={theme.palette.primary.main}
            subtitle="Last 24 hours"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Total Actions"
            value={metrics.total_actions.toLocaleString()}
            icon={<TrendingUp sx={{ color: 'info.main', fontSize: 24 }} />}
            color={theme.palette.info.main}
            subtitle="Last 30 days"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Blocked"
            value={metrics.blocked_actions}
            icon={<Block sx={{ color: 'error.main', fontSize: 24 }} />}
            color={theme.palette.error.main}
            subtitle="Last 30 days"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Active Alerts"
            value={totalAlerts}
            icon={<Warning sx={{ color: 'warning.main', fontSize: 24 }} />}
            color={theme.palette.warning.main}
            subtitle="Unacknowledged"
          />
        </Grid>

        <Grid item xs={12} md={6}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 0.5 }}>Financial Impact</Typography>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>Blocked vs approved transactions</Typography>
              <Box sx={{ display: 'flex', gap: 4, mt: 3 }}>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>Saved</Typography>
                  <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 0.5, mt: 0.5 }}>
                    <Typography variant="h4" sx={{ fontWeight: 700, color: 'success.main' }}>
                      ${metrics.money_saved.toLocaleString()}
                    </Typography>
                  </Box>
                </Box>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>Spent</Typography>
                  <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 0.5, mt: 0.5 }}>
                    <Typography variant="h4" sx={{ fontWeight: 700, color: 'warning.main' }}>
                      ${metrics.money_spent.toLocaleString()}
                    </Typography>
                  </Box>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 0.5 }}>Alerts by Severity</Typography>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>Last 7 days</Typography>
              {alertsData.length > 0 ? (
                <ResponsiveContainer width="100%" height={180}>
                  <PieChart>
                    <Pie data={alertsData} cx="50%" cy="50%" innerRadius={45} outerRadius={70} paddingAngle={3} dataKey="value" stroke="none">
                      {alertsData.map((_e, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                    </Pie>
                    <Tooltip {...chartTooltip} />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <Box sx={{ py: 6, textAlign: 'center' }}>
                  <Typography variant="body2" sx={{ color: 'text.secondary' }}>No alerts</Typography>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 0.5 }}>Activity Timeline</Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 2 }}>Hourly actions over the last 24 hours</Typography>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={activityData}>
                <CartesianGrid strokeDasharray="3 3" stroke={chartGrid} />
                <XAxis dataKey="time" stroke={chartAxis} fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke={chartAxis} fontSize={11} tickLine={false} axisLine={false} />
                <Tooltip {...chartTooltip} />
                <Line
                  type="monotone"
                  dataKey="count"
                  stroke={primaryMain}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4, fill: primaryMain, stroke: paperBg, strokeWidth: 2 }}
                  name="Actions"
                />
              </LineChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 0.5 }}>Top Agents</Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 2 }}>By action count (7 days)</Typography>
            {topAgentsData.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={topAgentsData}>
                  <CartesianGrid strokeDasharray="3 3" stroke={chartGrid} />
                  <XAxis dataKey="name" stroke={chartAxis} fontSize={10} tickLine={false} axisLine={false} />
                  <YAxis stroke={chartAxis} fontSize={11} tickLine={false} axisLine={false} />
                  <Tooltip {...chartTooltip} />
                  <Bar dataKey="actions" fill={primaryMain} radius={[4, 4, 0, 0]} name="Actions" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <Box sx={{ py: 6, textAlign: 'center' }}><Typography variant="body2" sx={{ color: 'text.secondary' }}>No activity</Typography></Box>
            )}
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 0.5 }}>Systems Accessed</Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 2 }}>Last 7 days</Typography>
            {systemsData.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={systemsData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke={chartGrid} />
                  <XAxis type="number" stroke={chartAxis} fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis dataKey="name" type="category" width={100} stroke={chartAxis} fontSize={11} tickLine={false} axisLine={false} />
                  <Tooltip {...chartTooltip} />
                  <Bar dataKey="accesses" fill={theme.palette.success.main} radius={[0, 4, 4, 0]} name="Accesses" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <Box sx={{ py: 6, textAlign: 'center' }}><Typography variant="body2" sx={{ color: 'text.secondary' }}>No data</Typography></Box>
            )}
          </Paper>
        </Grid>

        {metrics.recent_blocked_actions.length > 0 && (
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>Recent Blocked Actions</Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Time</TableCell>
                      <TableCell>Agent</TableCell>
                      <TableCell>Action</TableCell>
                      <TableCell>System</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {metrics.recent_blocked_actions.slice(0, 8).map((action) => (
                      <TableRow key={action.id}>
                        <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '0.75rem' }}>{format(new Date(action.timestamp), 'MMM dd, HH:mm:ss')}</TableCell>
                        <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '0.75rem' }}>{action.agent_id}</TableCell>
                        <TableCell>{action.action}</TableCell>
                        <TableCell>{action.system_accessed}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </Grid>
        )}

        {metrics.recent_alerts.length > 0 && (
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>Recent Alerts</Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Time</TableCell>
                      <TableCell>Severity</TableCell>
                      <TableCell>Type</TableCell>
                      <TableCell>Message</TableCell>
                      <TableCell>Agent</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {metrics.recent_alerts.slice(0, 8).map((alert) => (
                      <TableRow key={alert.id}>
                        <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '0.75rem' }}>{format(new Date(alert.timestamp), 'MMM dd, HH:mm:ss')}</TableCell>
                        <TableCell>
                          <Chip
                            label={alert.severity}
                            size="small"
                            sx={{
                              bgcolor: alpha(getSeverityColor(alert.severity), 0.1),
                              color: getSeverityColor(alert.severity),
                              border: `1px solid ${alpha(getSeverityColor(alert.severity), 0.2)}`,
                              fontWeight: 600,
                              fontSize: '0.65rem',
                              textTransform: 'uppercase',
                              letterSpacing: '0.05em',
                              minWidth: 72,
                              justifyContent: 'center',
                            }}
                          />
                        </TableCell>
                        <TableCell>{alert.alert_type}</TableCell>
                        <TableCell>{alert.message}</TableCell>
                        <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '0.75rem' }}>{alert.agent_id || '—'}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </Grid>
        )}
      </Grid>
    </Box>
  );
};

export default Dashboard;
