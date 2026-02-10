import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Chip,
  CircularProgress,
  Alert as MuiAlert,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  IconButton,
  Tooltip,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Grid,
  Card,
  CardContent,
  Divider,
} from '@mui/material';
import {
  Visibility as VisibilityIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
  Clear as ClearIcon,
} from '@mui/icons-material';
import { format, formatDistanceToNow } from 'date-fns';
import alertsApi, { Alert } from '@/api/alerts';
import { useAuth } from '@/contexts/AuthContext';

const AlertHistory: React.FC = () => {
  const { user } = useAuth();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [total, setTotal] = useState(0);

  // Filters
  const [alertTypeFilter, setAlertTypeFilter] = useState<string>('all');
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [acknowledgedFilter, setAcknowledgedFilter] = useState<string>('all');

  // Detail modal
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);

  // Acknowledge dialog
  const [ackDialogOpen, setAckDialogOpen] = useState(false);
  const [ackAlert, setAckAlert] = useState<Alert | null>(null);

  useEffect(() => {
    fetchAlerts();
  }, [page, rowsPerPage, alertTypeFilter, severityFilter, acknowledgedFilter]);

  const fetchAlerts = async () => {
    try {
      setLoading(true);
      setError(null);

      const params: any = {
        page: page + 1,
        page_size: rowsPerPage,
      };

      if (alertTypeFilter !== 'all') params.alert_type = alertTypeFilter;
      if (severityFilter !== 'all') params.severity = severityFilter;
      if (acknowledgedFilter !== 'all') {
        params.acknowledged = acknowledgedFilter === 'acknowledged';
      }

      const response = await alertsApi.listAlerts(params);
      setAlerts(response.alerts);
      setTotal(response.total);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch alerts');
    } finally {
      setLoading(false);
    }
  };

  const handleChangePage = (_event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleViewDetails = (alert: Alert) => {
    setSelectedAlert(alert);
    setDetailModalOpen(true);
  };

  const handleCloseDetail = () => {
    setDetailModalOpen(false);
    setSelectedAlert(null);
  };

  const handleOpenAckDialog = (alert: Alert) => {
    setAckAlert(alert);
    setAckDialogOpen(true);
  };

  const handleCloseAckDialog = () => {
    setAckDialogOpen(false);
    setAckAlert(null);
  };

  const handleAcknowledge = async () => {
    if (!ackAlert || !user) return;

    try {
      setError(null);
      await alertsApi.acknowledgeAlert(ackAlert.id, user.email);
      fetchAlerts();
      handleCloseAckDialog();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to acknowledge alert');
    }
  };

  const handleClearFilters = () => {
    setAlertTypeFilter('all');
    setSeverityFilter('all');
    setAcknowledgedFilter('all');
    setPage(0);
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical':
        return <ErrorIcon sx={{ color: 'error.main', fontSize: 20 }} />;
      case 'high':
        return <WarningIcon sx={{ color: 'error.main', fontSize: 20 }} />;
      case 'medium':
        return <WarningIcon sx={{ color: 'warning.main', fontSize: 20 }} />;
      case 'low':
        return <InfoIcon sx={{ color: 'success.main', fontSize: 20 }} />;
      default:
        return null;
    }
  };

  const getSeverityColor = (
    severity: string
  ): 'default' | 'success' | 'warning' | 'error' => {
    switch (severity) {
      case 'low':
        return 'success';
      case 'medium':
        return 'warning';
      case 'high':
      case 'critical':
        return 'error';
      default:
        return 'default';
    }
  };

  const activeFiltersCount = [
    alertTypeFilter !== 'all' ? alertTypeFilter : '',
    severityFilter !== 'all' ? severityFilter : '',
    acknowledgedFilter !== 'all' ? acknowledgedFilter : '',
  ].filter(Boolean).length;

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 'bold', mb: 3 }}>
        Alert History
      </Typography>

      {error && (
        <MuiAlert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </MuiAlert>
      )}

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2}>
          <Grid item xs={12} md={3}>
            <FormControl fullWidth>
              <InputLabel>Alert Type</InputLabel>
              <Select
                value={alertTypeFilter}
                label="Alert Type"
                onChange={(e) => {
                  setAlertTypeFilter(e.target.value);
                  setPage(0);
                }}
              >
                <MenuItem value="all">All Types</MenuItem>
                <MenuItem value="blocked_access">Blocked Access</MenuItem>
                <MenuItem value="high_transaction">High Transaction</MenuItem>
                <MenuItem value="new_agent">New Agent</MenuItem>
                <MenuItem value="policy_violation">Policy Violation</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} md={3}>
            <FormControl fullWidth>
              <InputLabel>Severity</InputLabel>
              <Select
                value={severityFilter}
                label="Severity"
                onChange={(e) => {
                  setSeverityFilter(e.target.value);
                  setPage(0);
                }}
              >
                <MenuItem value="all">All Severities</MenuItem>
                <MenuItem value="low">Low</MenuItem>
                <MenuItem value="medium">Medium</MenuItem>
                <MenuItem value="high">High</MenuItem>
                <MenuItem value="critical">Critical</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} md={3}>
            <FormControl fullWidth>
              <InputLabel>Status</InputLabel>
              <Select
                value={acknowledgedFilter}
                label="Status"
                onChange={(e) => {
                  setAcknowledgedFilter(e.target.value);
                  setPage(0);
                }}
              >
                <MenuItem value="all">All</MenuItem>
                <MenuItem value="acknowledged">Acknowledged</MenuItem>
                <MenuItem value="unacknowledged">Unacknowledged</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          {activeFiltersCount > 0 && (
            <Grid item xs={12}>
              <Button size="small" startIcon={<ClearIcon />} onClick={handleClearFilters}>
                Clear Filters ({activeFiltersCount})
              </Button>
            </Grid>
          )}
        </Grid>
      </Paper>

      {/* Alerts Table */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Severity</TableCell>
              <TableCell>Timestamp</TableCell>
              <TableCell>Alert Type</TableCell>
              <TableCell>Agent</TableCell>
              <TableCell>Description</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 8 }}>
                  <CircularProgress />
                </TableCell>
              </TableRow>
            ) : alerts.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 8 }}>
                  <Typography color="text.secondary">
                    {activeFiltersCount > 0
                      ? 'No alerts found matching your filters'
                      : 'No alerts to display'}
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              alerts.map((alert) => (
                <TableRow key={alert.id} hover>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      {getSeverityIcon(alert.severity)}
                      <Chip
                        label={alert.severity.toUpperCase()}
                        color={getSeverityColor(alert.severity)}
                        size="small"
                      />
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {format(new Date(alert.timestamp), 'MMM dd, yyyy HH:mm:ss')}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {formatDistanceToNow(new Date(alert.timestamp), { addSuffix: true })}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip label={alert.alert_type} size="small" variant="outlined" />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                      {alert.agent_id}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ maxWidth: 300 }} noWrap>
                      {alert.description}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    {alert.acknowledged ? (
                      <Tooltip
                        title={`Acknowledged by ${alert.acknowledged_by} at ${
                          alert.acknowledged_at
                            ? format(new Date(alert.acknowledged_at), 'MMM dd, yyyy HH:mm')
                            : 'unknown'
                        }`}
                      >
                        <Chip
                          icon={<CheckCircleIcon />}
                          label="Acknowledged"
                          color="success"
                          size="small"
                          variant="outlined"
                        />
                      </Tooltip>
                    ) : (
                      <Chip label="Unacknowledged" color="warning" size="small" />
                    )}
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title="View Details">
                      <IconButton size="small" onClick={() => handleViewDetails(alert)}>
                        <VisibilityIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    {!alert.acknowledged && (
                      <Tooltip title="Acknowledge">
                        <IconButton
                          size="small"
                          onClick={() => handleOpenAckDialog(alert)}
                          color="primary"
                        >
                          <CheckCircleIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
        <TablePagination
          component="div"
          count={total}
          page={page}
          onPageChange={handleChangePage}
          rowsPerPage={rowsPerPage}
          onRowsPerPageChange={handleChangeRowsPerPage}
          rowsPerPageOptions={[10, 25, 50, 100]}
        />
      </TableContainer>

      {/* Detail Modal */}
      <Dialog open={detailModalOpen} onClose={handleCloseDetail} maxWidth="md" fullWidth>
        <DialogTitle>Alert Details</DialogTitle>
        <DialogContent>
          {selectedAlert && (
            <Grid container spacing={2} sx={{ mt: 1 }}>
              <Grid item xs={12} md={6}>
                <Typography variant="caption" color="text.secondary">
                  Alert ID
                </Typography>
                <Typography variant="body2" sx={{ fontFamily: 'monospace', mb: 2 }}>
                  {selectedAlert.id}
                </Typography>
              </Grid>

              <Grid item xs={12} md={6}>
                <Typography variant="caption" color="text.secondary">
                  Timestamp
                </Typography>
                <Typography variant="body2" sx={{ mb: 2 }}>
                  {format(new Date(selectedAlert.timestamp), 'PPpp')}
                </Typography>
              </Grid>

              <Grid item xs={12} md={6}>
                <Typography variant="caption" color="text.secondary">
                  Severity
                </Typography>
                <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                  {getSeverityIcon(selectedAlert.severity)}
                  <Chip
                    label={selectedAlert.severity.toUpperCase()}
                    color={getSeverityColor(selectedAlert.severity)}
                    size="small"
                  />
                </Box>
              </Grid>

              <Grid item xs={12} md={6}>
                <Typography variant="caption" color="text.secondary">
                  Alert Type
                </Typography>
                <Typography variant="body2" sx={{ mb: 2 }}>
                  {selectedAlert.alert_type}
                </Typography>
              </Grid>

              <Grid item xs={12}>
                <Typography variant="caption" color="text.secondary">
                  Agent ID
                </Typography>
                <Typography variant="body2" sx={{ fontFamily: 'monospace', mb: 2 }}>
                  {selectedAlert.agent_id}
                </Typography>
              </Grid>

              <Grid item xs={12}>
                <Typography variant="caption" color="text.secondary">
                  Description
                </Typography>
                <Typography variant="body2" sx={{ mb: 2 }}>
                  {selectedAlert.description}
                </Typography>
              </Grid>

              {selectedAlert.audit_log_id && (
                <Grid item xs={12}>
                  <Typography variant="caption" color="text.secondary">
                    Related Audit Log
                  </Typography>
                  <Typography variant="body2" sx={{ fontFamily: 'monospace', mb: 2 }}>
                    {selectedAlert.audit_log_id}
                  </Typography>
                </Grid>
              )}

              {selectedAlert.acknowledged && (
                <>
                  <Grid item xs={12}>
                    <Divider sx={{ my: 1 }} />
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <Typography variant="caption" color="text.secondary">
                      Acknowledged By
                    </Typography>
                    <Typography variant="body2" sx={{ mb: 2 }}>
                      {selectedAlert.acknowledged_by}
                    </Typography>
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <Typography variant="caption" color="text.secondary">
                      Acknowledged At
                    </Typography>
                    <Typography variant="body2" sx={{ mb: 2 }}>
                      {selectedAlert.acknowledged_at
                        ? format(new Date(selectedAlert.acknowledged_at), 'PPpp')
                        : 'N/A'}
                    </Typography>
                  </Grid>
                </>
              )}
            </Grid>
          )}
        </DialogContent>
        <DialogActions>
          {selectedAlert && !selectedAlert.acknowledged && (
            <Button
              variant="contained"
              color="primary"
              onClick={() => {
                handleCloseDetail();
                handleOpenAckDialog(selectedAlert);
              }}
            >
              Acknowledge
            </Button>
          )}
          <Button onClick={handleCloseDetail}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Acknowledge Dialog */}
      <Dialog open={ackDialogOpen} onClose={handleCloseAckDialog} maxWidth="xs" fullWidth>
        <DialogTitle>Acknowledge Alert</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to acknowledge this alert? This action cannot be undone.
          </Typography>
          {ackAlert && (
            <Card sx={{ mt: 2, bgcolor: 'grey.50' }}>
              <CardContent>
                <Typography variant="caption" color="text.secondary">
                  Alert Type
                </Typography>
                <Typography variant="body2" sx={{ mb: 1 }}>
                  {ackAlert.alert_type}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Description
                </Typography>
                <Typography variant="body2">{ackAlert.description}</Typography>
              </CardContent>
            </Card>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseAckDialog}>Cancel</Button>
          <Button variant="contained" color="primary" onClick={handleAcknowledge}>
            Acknowledge
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default AlertHistory;
