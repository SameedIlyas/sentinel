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
} from '@mui/material';
import {
  SmartToy,
  Block,
  AttachMoney,
  Warning,
  TrendingUp,
  WifiOff,
  Wifi,
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
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { format } from 'date-fns';
import dashboardApi from '@/api/dashboard';
import { DashboardMetrics } from '@/types';
import { useDashboardWebSocket } from '@/hooks/useWebSocket';

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8'];

const Dashboard: React.FC = () => {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  const handleMetricsUpdate = (newMetrics: DashboardMetrics) => {
    setMetrics(newMetrics);
    setLastUpdate(new Date());
    setLoading(false);
  };

  // WebSocket connection for real-time updates
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
    // Initial fetch
    fetchMetrics();

    // Fallback polling every 60 seconds (WebSocket should push updates every 30s)
    // This ensures we have data even if WebSocket fails
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
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box>
            <Typography color="text.secondary" variant="body2" gutterBottom>
              {title}
            </Typography>
            <Typography variant="h4" component="div" sx={{ fontWeight: 'bold', mb: 1 }}>
              {value}
            </Typography>
            {subtitle && (
              <Typography variant="caption" color="text.secondary">
                {subtitle}
              </Typography>
            )}
          </Box>
          <Box
            sx={{
              bgcolor: color,
              borderRadius: 2,
              p: 1.5,
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
      case 'critical':
        return 'error';
      case 'high':
        return 'error';
      case 'medium':
        return 'warning';
      case 'low':
        return 'info';
      default:
        return 'default';
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <CircularProgress size={60} />
      </Box>
    );
  }

  if (error) {
    return (
      <Box>
        <Typography variant="h4" gutterBottom sx={{ fontWeight: 'bold', mb: 3 }}>
          Dashboard Overview
        </Typography>
        <MuiAlert severity="error">{error}</MuiAlert>
      </Box>
    );
  }

  if (!metrics) {
    return (
      <Box>
        <Typography variant="h4" gutterBottom sx={{ fontWeight: 'bold', mb: 3 }}>
          Dashboard Overview
        </Typography>
        <MuiAlert severity="info">No data available</MuiAlert>
      </Box>
    );
  }

  // Prepare data for charts
  const activityData = metrics.activity_timeline.map((item) => ({
    time: format(new Date(item.timestamp), 'HH:mm'),
    count: item.count,
  }));

  const topAgentsData = metrics.top_agents.slice(0, 10).map((agent) => ({
    name: agent.agent_id.substring(0, 20),
    actions: agent.action_count,
  }));

  const systemsData = metrics.systems_accessed.slice(0, 10).map((system) => ({
    name: system.system,
    accesses: system.access_count,
  }));

  const totalAlerts = Object.values(metrics.alerts_by_severity).reduce((a, b) => a + b, 0);
  const alertsData = Object.entries(metrics.alerts_by_severity).map(([severity, count]) => ({
    name: severity,
    value: count,
  }));

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" sx={{ fontWeight: 'bold' }}>
          Dashboard Overview
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Chip
            icon={isConnected ? <Wifi /> : <WifiOff />}
            label={isConnected ? 'Live' : 'Offline'}
            color={isConnected ? 'success' : 'default'}
            size="small"
          />
          <Typography variant="caption" color="text.secondary">
            Last updated: {format(lastUpdate, 'MMM dd, yyyy HH:mm:ss')}
          </Typography>
        </Box>
      </Box>

      <Grid container spacing={3}>
        {/* Key Metrics */}
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Active Agents"
            value={metrics.active_agents}
            icon={<SmartToy sx={{ color: 'white', fontSize: 32 }} />}
            color="primary.main"
            subtitle="Last 24 hours"
          />
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Total Actions"
            value={metrics.total_actions.toLocaleString()}
            icon={<TrendingUp sx={{ color: 'white', fontSize: 32 }} />}
            color="info.main"
            subtitle="Last 30 days"
          />
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Blocked Actions"
            value={metrics.blocked_actions}
            icon={<Block sx={{ color: 'white', fontSize: 32 }} />}
            color="error.main"
            subtitle="Last 30 days"
          />
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Active Alerts"
            value={totalAlerts}
            icon={<Warning sx={{ color: 'white', fontSize: 32 }} />}
            color="warning.main"
            subtitle="Unacknowledged"
          />
        </Grid>

        {/* Financial Metrics */}
        <Grid item xs={12} md={6}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Financial Impact
              </Typography>
              <Box sx={{ display: 'flex', gap: 4, mt: 2 }}>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Money Saved
                  </Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <AttachMoney sx={{ color: 'success.main', fontSize: 32 }} />
                    <Typography variant="h4" color="success.main" sx={{ fontWeight: 'bold' }}>
                      ${metrics.money_saved.toLocaleString()}
                    </Typography>
                  </Box>
                  <Typography variant="caption" color="text.secondary">
                    Blocked transactions
                  </Typography>
                </Box>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Money Spent
                  </Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <AttachMoney sx={{ color: 'warning.main', fontSize: 32 }} />
                    <Typography variant="h4" color="warning.main" sx={{ fontWeight: 'bold' }}>
                      ${metrics.money_spent.toLocaleString()}
                    </Typography>
                  </Box>
                  <Typography variant="caption" color="text.secondary">
                    Approved transactions
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Alert Distribution */}
        <Grid item xs={12} md={6}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Alerts by Severity
              </Typography>
              {alertsData.length > 0 ? (
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie
                      data={alertsData}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={(entry: { name: string; value: number }) => `${entry.name}: ${entry.value}`}
                      outerRadius={80}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {alertsData.map((_entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <Typography color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>
                  No alerts in the last 7 days
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Activity Timeline */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Activity Timeline (Last 24 Hours)
            </Typography>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={activityData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="count"
                  stroke="#8884d8"
                  strokeWidth={2}
                  dot={{ r: 4 }}
                  activeDot={{ r: 6 }}
                  name="Actions"
                />
              </LineChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        {/* Top Agents */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Top Agents by Activity
            </Typography>
            {topAgentsData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={topAgentsData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="actions" fill="#8884d8" name="Actions" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <Typography color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>
                No agent activity in the last 7 days
              </Typography>
            )}
          </Paper>
        </Grid>

        {/* Systems Accessed */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Systems Accessed
            </Typography>
            {systemsData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={systemsData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" />
                  <YAxis dataKey="name" type="category" width={120} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="accesses" fill="#82ca9d" name="Accesses" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <Typography color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>
                No system access in the last 7 days
              </Typography>
            )}
          </Paper>
        </Grid>

        {/* Recent Blocked Actions */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Recent Blocked Actions
            </Typography>
            {metrics.recent_blocked_actions.length > 0 ? (
              <TableContainer>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Timestamp</TableCell>
                      <TableCell>Agent ID</TableCell>
                      <TableCell>Action</TableCell>
                      <TableCell>System</TableCell>
                      <TableCell>Policy</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {metrics.recent_blocked_actions.slice(0, 10).map((action) => (
                      <TableRow key={action.id} hover>
                        <TableCell>{format(new Date(action.timestamp), 'MMM dd, HH:mm:ss')}</TableCell>
                        <TableCell>{action.agent_id}</TableCell>
                        <TableCell>{action.action}</TableCell>
                        <TableCell>{action.system_accessed}</TableCell>
                        <TableCell>
                          {action.policy_id ? `Policy #${action.policy_id}` : 'N/A'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            ) : (
              <Typography color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>
                No blocked actions in the last 7 days
              </Typography>
            )}
          </Paper>
        </Grid>

        {/* Recent Alerts */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Recent Alerts
            </Typography>
            {metrics.recent_alerts.length > 0 ? (
              <TableContainer>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Timestamp</TableCell>
                      <TableCell>Severity</TableCell>
                      <TableCell>Type</TableCell>
                      <TableCell>Message</TableCell>
                      <TableCell>Agent</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {metrics.recent_alerts.slice(0, 10).map((alert) => (
                      <TableRow key={alert.id} hover>
                        <TableCell>{format(new Date(alert.timestamp), 'MMM dd, HH:mm:ss')}</TableCell>
                        <TableCell>
                          <Chip
                            label={alert.severity}
                            color={getSeverityColor(alert.severity) as any}
                            size="small"
                          />
                        </TableCell>
                        <TableCell>{alert.alert_type}</TableCell>
                        <TableCell>{alert.message}</TableCell>
                        <TableCell>{alert.agent_id || 'N/A'}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            ) : (
              <Typography color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>
                No recent alerts
              </Typography>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Dashboard;
