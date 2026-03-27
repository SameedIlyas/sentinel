import React, { useState, useEffect, useMemo } from 'react';
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
  useTheme,
} from '@mui/material';
import {
  Visibility as VisibilityIcon,
  CheckCircle as CheckCircleIcon,
  FiberManualRecord,
} from '@mui/icons-material';
import { alpha } from '@mui/material/styles';
import { format, formatDistanceToNow } from 'date-fns';
import alertsApi, { Alert } from '@/api/alerts';
import { useAuth } from '@/contexts/AuthContext';
import { useAppStyles } from '@/hooks/useAppStyles';
import { utc } from '@/utils/date';

function SeverityBadge({ severity }: { severity: string }) {
  const theme = useTheme();
  const key = severity.toLowerCase();
  const SEVERITY_HEX: Record<string, string> = {
    critical: theme.palette.error.main,
    high: theme.palette.warning.dark ?? theme.palette.warning.main,
    medium: theme.palette.warning.main,
    low: theme.palette.info.main,
  };
  const color = SEVERITY_HEX[key] ?? theme.palette.text.disabled;
  return (
    <Box
      component="span"
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        minWidth: 72,
        px: 1.25,
        py: 0.35,
        borderRadius: 1,
        fontSize: '0.6875rem',
        fontWeight: 700,
        letterSpacing: '0.05em',
        color,
        bgcolor: alpha(color, 0.14),
        border: `1px solid ${alpha(color, 0.4)}`,
      }}
    >
      {severity.toUpperCase()}
    </Box>
  );
}

function StatusIndicator({
  acknowledged,
  acknowledgedBy,
  acknowledgedAt,
}: {
  acknowledged: boolean;
  acknowledgedBy: string | null;
  acknowledgedAt: string | null;
}) {
  const theme = useTheme();
  const dotColor = acknowledged ? theme.palette.success.main : theme.palette.warning.main;
  const label = acknowledged ? 'Acknowledged' : 'Open';
  const title =
    acknowledged && acknowledgedBy
      ? `Acknowledged by ${acknowledgedBy}${
          acknowledgedAt
            ? ` at ${format(utc(acknowledgedAt), 'MMM dd, yyyy HH:mm')}`
            : ''
        }`
      : undefined;

  const inner = (
    <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.75 }}>
      <FiberManualRecord sx={{ fontSize: 10, color: dotColor }} />
      <Typography variant="body2" sx={{ color: 'text.primary', fontWeight: 500, fontSize: '0.8125rem' }}>
        {label}
      </Typography>
    </Box>
  );

  if (title) {
    return <Tooltip title={title}>{inner}</Tooltip>;
  }
  return inner;
}

const AlertHistory: React.FC = () => {
  const styles = useAppStyles();
  const { theme } = styles;
  const { user } = useAuth();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [total, setTotal] = useState(0);

  const [alertTypeFilter, setAlertTypeFilter] = useState<string>('all');
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [acknowledgedFilter, setAcknowledgedFilter] = useState<string>('all');

  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);

  const [ackDialogOpen, setAckDialogOpen] = useState(false);
  const [ackAlert, setAckAlert] = useState<Alert | null>(null);

  const selectMenuProps = useMemo(
    () => ({
      PaperProps: {
        sx: {
          bgcolor: styles.dialogBg,
          border: `1px solid ${theme.palette.divider}`,
          mt: 0.5,
          '& .MuiMenuItem-root': {
            color: alpha(theme.palette.text.primary, 0.85),
            fontSize: '0.875rem',
            '&:hover': { bgcolor: alpha(theme.palette.primary.main, 0.12) },
            '&.Mui-selected': { bgcolor: alpha(theme.palette.primary.main, 0.18) },
          },
        },
      },
    }),
    [styles.dialogBg, theme.palette.divider, theme.palette.text.primary, theme.palette.primary.main]
  );

  useEffect(() => {
    fetchAlerts();
  }, [page, rowsPerPage, alertTypeFilter, severityFilter, acknowledgedFilter]);

  const fetchAlerts = async () => {
    try {
      setLoading(true);
      setError(null);

      const params: Record<string, unknown> = {
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
    } catch (err: unknown) {
      const detail =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      setError(detail || 'Failed to fetch alerts');
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
    } catch (err: unknown) {
      const detail =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      setError(detail || 'Failed to acknowledge alert');
    }
  };

  const handleClearFilters = () => {
    setAlertTypeFilter('all');
    setSeverityFilter('all');
    setAcknowledgedFilter('all');
    setPage(0);
  };

  const activeFiltersCount = [
    alertTypeFilter !== 'all' ? alertTypeFilter : '',
    severityFilter !== 'all' ? severityFilter : '',
    acknowledgedFilter !== 'all' ? acknowledgedFilter : '',
  ].filter(Boolean).length;

  const primaryMain = theme.palette.primary.main;

  const subtleOutlinedButton = {
    textTransform: 'none' as const,
    fontWeight: 500,
    borderColor: alpha(primaryMain, 0.35),
    color: alpha(theme.palette.text.primary, 0.9),
    '&:hover': {
      borderColor: alpha(primaryMain, 0.65),
      bgcolor: alpha(primaryMain, 0.1),
    },
  };

  const iconBtnSx = {
    color: alpha(theme.palette.text.primary, 0.5),
    '&:hover': { color: primaryMain, bgcolor: alpha(primaryMain, 0.1) },
  };

  const dialogPaperSx = {
    bgcolor: styles.dialogBg,
    backgroundImage: 'none',
    border: `1px solid ${theme.palette.divider}`,
    color: 'text.primary',
  };

  const selectFieldSx = {
    color: 'text.primary',
    bgcolor: styles.inputBg,
    borderRadius: 1,
    '& .MuiOutlinedInput-notchedOutline': { borderColor: theme.palette.divider },
    '&:hover .MuiOutlinedInput-notchedOutline': {
      borderColor: alpha(theme.palette.text.primary, theme.palette.mode === 'dark' ? 0.12 : 0.2),
    },
    '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
      borderColor: alpha(primaryMain, 0.5),
    },
  };

  return (
    <Box>
      {error && (
        <MuiAlert
          severity="error"
          variant="outlined"
          sx={{
            mb: 3,
            bgcolor: alpha(theme.palette.error.main, 0.08),
            borderColor: alpha(theme.palette.error.main, 0.35),
            color: theme.palette.error.main,
            '& .MuiAlert-icon': { color: theme.palette.error.main },
          }}
          onClose={() => setError(null)}
        >
          {error}
        </MuiAlert>
      )}

      <Paper
        elevation={0}
        sx={{
          p: 2,
          mb: 3,
          bgcolor: 'background.paper',
          border: `1px solid ${theme.palette.divider}`,
          borderRadius: 2,
        }}
      >
        <Typography
          variant="overline"
          sx={{ color: 'text.secondary', letterSpacing: '0.08em', display: 'block', mb: 1.5 }}
        >
          Filters
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} md={4}>
            <FormControl fullWidth size="small">
              <InputLabel sx={{ color: 'text.secondary' }}>Alert type</InputLabel>
              <Select
                value={alertTypeFilter}
                label="Alert type"
                onChange={(e) => {
                  setAlertTypeFilter(e.target.value);
                  setPage(0);
                }}
                MenuProps={selectMenuProps}
                sx={selectFieldSx}
              >
                <MenuItem value="all">All types</MenuItem>
                <MenuItem value="blocked_access">Blocked access</MenuItem>
                <MenuItem value="high_transaction">High transaction</MenuItem>
                <MenuItem value="new_agent">New agent</MenuItem>
                <MenuItem value="policy_violation">Policy violation</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} md={4}>
            <FormControl fullWidth size="small">
              <InputLabel sx={{ color: 'text.secondary' }}>Severity</InputLabel>
              <Select
                value={severityFilter}
                label="Severity"
                onChange={(e) => {
                  setSeverityFilter(e.target.value);
                  setPage(0);
                }}
                MenuProps={selectMenuProps}
                sx={selectFieldSx}
              >
                <MenuItem value="all">All severities</MenuItem>
                <MenuItem value="low">Low</MenuItem>
                <MenuItem value="medium">Medium</MenuItem>
                <MenuItem value="high">High</MenuItem>
                <MenuItem value="critical">Critical</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} md={4}>
            <FormControl fullWidth size="small">
              <InputLabel sx={{ color: 'text.secondary' }}>Status</InputLabel>
              <Select
                value={acknowledgedFilter}
                label="Status"
                onChange={(e) => {
                  setAcknowledgedFilter(e.target.value);
                  setPage(0);
                }}
                MenuProps={selectMenuProps}
                sx={selectFieldSx}
              >
                <MenuItem value="all">All</MenuItem>
                <MenuItem value="acknowledged">Acknowledged</MenuItem>
                <MenuItem value="unacknowledged">Unacknowledged</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          {activeFiltersCount > 0 && (
            <Grid item xs={12}>
              <Button
                size="small"
                variant="text"
                onClick={handleClearFilters}
                sx={{
                  textTransform: 'none',
                  color: 'text.secondary',
                  '&:hover': { color: 'text.primary', bgcolor: styles.hoverBg },
                }}
              >
                Clear filters ({activeFiltersCount})
              </Button>
            </Grid>
          )}
        </Grid>
      </Paper>

      <TableContainer
        component={Paper}
        elevation={0}
        sx={{
          bgcolor: 'background.paper',
          border: `1px solid ${theme.palette.divider}`,
          borderRadius: 2,
          overflow: 'hidden',
        }}
      >
        <Table size="small">
          <TableHead>
            <TableRow
              sx={{
                '& th': {
                  bgcolor: styles.surfaceBg,
                  borderBottom: `1px solid ${theme.palette.divider}`,
                  color: alpha(theme.palette.text.primary, 0.45),
                  fontSize: '0.7rem',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  py: 1.5,
                },
              }}
            >
              <TableCell>Severity</TableCell>
              <TableCell>Timestamp</TableCell>
              <TableCell>Alert type</TableCell>
              <TableCell>Agent</TableCell>
              <TableCell>Description</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 8, borderColor: theme.palette.divider }}>
                  <CircularProgress size={32} sx={{ color: 'primary.main' }} />
                </TableCell>
              </TableRow>
            ) : alerts.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 8, borderColor: theme.palette.divider }}>
                  <Typography sx={{ color: 'text.secondary' }}>
                    {activeFiltersCount > 0
                      ? 'No alerts match your filters'
                      : 'No alerts to display'}
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              alerts.map((alert) => (
                <TableRow
                  key={alert.id}
                  hover
                  sx={{
                    '&:hover': { bgcolor: styles.hoverBg },
                    '& td': {
                      borderColor: theme.palette.divider,
                      color: 'text.primary',
                      py: 1.75,
                    },
                  }}
                >
                  <TableCell>
                    <SeverityBadge severity={alert.severity} />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ color: 'text.primary', fontWeight: 500 }}>
                      {format(utc(alert.timestamp), 'MMM dd, yyyy HH:mm:ss')}
                    </Typography>
                    <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
                      {formatDistanceToNow(utc(alert.timestamp), { addSuffix: true })}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Box
                      component="span"
                      sx={{
                        display: 'inline-block',
                        px: 1,
                        py: 0.25,
                        borderRadius: 1,
                        fontSize: '0.75rem',
                        fontFamily: 'ui-monospace, monospace',
                        color: alpha(theme.palette.text.primary, 0.85),
                        border: `1px solid ${alpha(theme.palette.text.primary, 0.1)}`,
                        bgcolor: styles.inputBg,
                      }}
                    >
                      {alert.alert_type}
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: 'ui-monospace, monospace', fontSize: '0.8rem' }}>
                      {alert.agent_id}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ maxWidth: 300 }} noWrap>
                      {alert.description}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <StatusIndicator
                      acknowledged={alert.acknowledged}
                      acknowledgedBy={alert.acknowledged_by}
                      acknowledgedAt={alert.acknowledged_at}
                    />
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title="View details">
                      <IconButton size="small" onClick={() => handleViewDetails(alert)} sx={iconBtnSx}>
                        <VisibilityIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    {!alert.acknowledged && (
                      <Tooltip title="Acknowledge">
                        <IconButton
                          size="small"
                          onClick={() => handleOpenAckDialog(alert)}
                          sx={iconBtnSx}
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
          sx={{
            borderTop: `1px solid ${theme.palette.divider}`,
            color: 'text.secondary',
            '& .MuiTablePagination-toolbar': { minHeight: 52 },
            '& .MuiTablePagination-selectIcon': { color: 'text.secondary' },
            '& .MuiIconButton-root': { color: 'text.secondary' },
          }}
        />
      </TableContainer>

      <Dialog
        open={detailModalOpen}
        onClose={handleCloseDetail}
        maxWidth="md"
        fullWidth
        PaperProps={{ sx: dialogPaperSx }}
      >
        <DialogTitle sx={{ fontWeight: 700, borderBottom: `1px solid ${theme.palette.divider}`, pb: 2 }}>
          Alert details
        </DialogTitle>
        <DialogContent sx={{ pt: 3 }}>
          {selectedAlert && (
            <Grid container spacing={2}>
              <Grid item xs={12} md={6}>
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                  Alert ID
                </Typography>
                <Typography variant="body2" sx={{ fontFamily: 'monospace', mb: 2, color: 'text.primary' }}>
                  {selectedAlert.id}
                </Typography>
              </Grid>

              <Grid item xs={12} md={6}>
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                  Timestamp
                </Typography>
                <Typography variant="body2" sx={{ mb: 2, color: 'text.primary' }}>
                  {format(utc(selectedAlert.timestamp), 'PPpp')}
                </Typography>
              </Grid>

              <Grid item xs={12} md={6}>
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                  Severity
                </Typography>
                <Box sx={{ mb: 2 }}>
                  <SeverityBadge severity={selectedAlert.severity} />
                </Box>
              </Grid>

              <Grid item xs={12} md={6}>
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                  Alert type
                </Typography>
                <Typography variant="body2" sx={{ mb: 2, color: 'text.primary' }}>
                  {selectedAlert.alert_type}
                </Typography>
              </Grid>

              <Grid item xs={12}>
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                  Agent ID
                </Typography>
                <Typography variant="body2" sx={{ fontFamily: 'monospace', mb: 2, color: 'text.primary' }}>
                  {selectedAlert.agent_id}
                </Typography>
              </Grid>

              <Grid item xs={12}>
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                  Description
                </Typography>
                <Typography variant="body2" sx={{ mb: 2, color: 'text.primary' }}>
                  {selectedAlert.description}
                </Typography>
              </Grid>

              {selectedAlert.audit_log_id && (
                <Grid item xs={12}>
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                    Related audit log
                  </Typography>
                  <Typography variant="body2" sx={{ fontFamily: 'monospace', mb: 2, color: 'text.primary' }}>
                    {selectedAlert.audit_log_id}
                  </Typography>
                </Grid>
              )}

              {selectedAlert.acknowledged && (
                <>
                  <Grid item xs={12}>
                    <Divider sx={{ borderColor: theme.palette.divider, my: 1 }} />
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                      Acknowledged by
                    </Typography>
                    <Typography variant="body2" sx={{ mb: 2, color: 'text.primary' }}>
                      {selectedAlert.acknowledged_by}
                    </Typography>
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                      Acknowledged at
                    </Typography>
                    <Typography variant="body2" sx={{ mb: 2, color: 'text.primary' }}>
                      {selectedAlert.acknowledged_at
                        ? format(utc(selectedAlert.acknowledged_at), 'PPpp')
                        : 'N/A'}
                    </Typography>
                  </Grid>
                </>
              )}
            </Grid>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2, borderTop: `1px solid ${theme.palette.divider}`, pt: 2 }}>
          {selectedAlert && !selectedAlert.acknowledged && (
            <Button
              variant="outlined"
              size="small"
              onClick={() => {
                handleCloseDetail();
                handleOpenAckDialog(selectedAlert);
              }}
              sx={subtleOutlinedButton}
            >
              Acknowledge
            </Button>
          )}
          <Button
            onClick={handleCloseDetail}
            sx={{
              textTransform: 'none',
              color: 'text.secondary',
              '&:hover': { bgcolor: styles.hoverBg },
            }}
          >
            Close
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={ackDialogOpen}
        onClose={handleCloseAckDialog}
        maxWidth="xs"
        fullWidth
        PaperProps={{ sx: dialogPaperSx }}
      >
        <DialogTitle sx={{ fontWeight: 700, borderBottom: `1px solid ${theme.palette.divider}`, pb: 2 }}>
          Acknowledge alert
        </DialogTitle>
        <DialogContent sx={{ pt: 3 }}>
          <Typography sx={{ color: alpha(theme.palette.text.primary, 0.75), fontSize: '0.9375rem' }}>
            Are you sure you want to acknowledge this alert? This action cannot be undone.
          </Typography>
          {ackAlert && (
            <Card
              elevation={0}
              sx={{
                mt: 2,
                bgcolor: styles.inputBg,
                border: `1px solid ${theme.palette.divider}`,
                borderRadius: 2,
              }}
            >
              <CardContent sx={{ '&:last-child': { pb: 2 } }}>
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                  Alert type
                </Typography>
                <Typography variant="body2" sx={{ mb: 1, color: 'text.primary' }}>
                  {ackAlert.alert_type}
                </Typography>
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                  Description
                </Typography>
                <Typography variant="body2" sx={{ color: 'text.primary' }}>
                  {ackAlert.description}
                </Typography>
              </CardContent>
            </Card>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button
            onClick={handleCloseAckDialog}
            sx={{
              textTransform: 'none',
              color: 'text.secondary',
              '&:hover': { bgcolor: styles.hoverBg },
            }}
          >
            Cancel
          </Button>
          <Button variant="outlined" size="small" onClick={handleAcknowledge} sx={subtleOutlinedButton}>
            Acknowledge
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default AlertHistory;
