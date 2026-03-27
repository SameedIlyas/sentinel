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
  TextField,
  InputAdornment,
  Chip,
  CircularProgress,
  Alert,
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
  Menu,
  ListItemIcon,
  ListItemText,
  Stack,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import SearchIcon from '@mui/icons-material/Search';
import VisibilityIcon from '@mui/icons-material/Visibility';
import DownloadIcon from '@mui/icons-material/Download';
import ClearIcon from '@mui/icons-material/Clear';
import AllowedIcon from '@mui/icons-material/CheckCircle';
import BlockedIcon from '@mui/icons-material/Block';
import ApprovalIcon from '@mui/icons-material/HourglassEmpty';
import { format, formatDistanceToNow } from 'date-fns';
import auditLogsApi from '@/api/auditLogs';
import { AuditLog } from '@/types';
import { useAppStyles } from '@/hooks/useAppStyles';

const AuditLogs: React.FC = () => {
  const styles = useAppStyles();
  const { theme } = styles;

  const DECISION_COLOR = useMemo(
    () => ({
      allowed: theme.palette.success.main,
      blocked: theme.palette.error.main,
      approved: theme.palette.warning.main,
    }),
    [theme.palette.success.main, theme.palette.error.main, theme.palette.warning.main]
  );

  const smallFieldSx = useMemo(
    () => ({
      '& .MuiInputBase-root': {
        fontSize: '0.8125rem',
        bgcolor: styles.inputBg,
        borderRadius: 1,
      },
      '& .MuiOutlinedInput-notchedOutline': { borderColor: theme.palette.divider },
      '&:hover .MuiOutlinedInput-notchedOutline': {
        borderColor: alpha(theme.palette.text.primary, theme.palette.mode === 'dark' ? 0.14 : 0.23),
      },
      '& .Mui-focused .MuiOutlinedInput-notchedOutline': {
        borderColor: alpha(theme.palette.primary.main, 0.6),
      },
      '& .MuiInputLabel-root': { color: 'text.secondary', fontSize: '0.8125rem' },
      '& .MuiInputBase-input': { color: 'text.primary' },
    }),
    [styles.inputBg, theme.palette.divider, theme.palette.text.primary, theme.palette.mode, theme.palette.primary.main]
  );

  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [total, setTotal] = useState(0);

  const [search, setSearch] = useState('');
  const [searchDebounce, setSearchDebounce] = useState('');
  const [agentFilter, setAgentFilter] = useState('');
  const [userFilter, setUserFilter] = useState('');
  const [systemFilter, setSystemFilter] = useState('');
  const [decisionFilter, setDecisionFilter] = useState<string>('all');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null);

  const [exportMenuAnchor, setExportMenuAnchor] = useState<null | HTMLElement>(null);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setSearchDebounce(search);
      setPage(0);
    }, 500);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    fetchLogs();
  }, [page, rowsPerPage, searchDebounce, agentFilter, userFilter, systemFilter, decisionFilter, startDate, endDate]);

  const fetchLogs = async () => {
    try {
      setLoading(true);
      setError(null);

      const params: any = {
        page: page + 1,
        page_size: rowsPerPage,
      };

      if (searchDebounce) params.search = searchDebounce;
      if (agentFilter) params.filter_agent_id = agentFilter;
      if (userFilter) params.filter_user_id = userFilter;
      if (systemFilter) params.filter_system = systemFilter;
      if (decisionFilter !== 'all') params.filter_decision = decisionFilter;
      if (startDate) params.start_date = new Date(startDate).toISOString();
      if (endDate) params.end_date = new Date(endDate).toISOString();

      const response = await auditLogsApi.listAuditLogs(params);
      setLogs(response.logs);
      setTotal(response.total);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch audit logs');
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

  const handleViewDetails = (log: AuditLog) => {
    setSelectedLog(log);
    setDetailModalOpen(true);
  };

  const handleCloseDetail = () => {
    setDetailModalOpen(false);
    setSelectedLog(null);
  };

  const handleClearFilters = () => {
    setSearch('');
    setAgentFilter('');
    setUserFilter('');
    setSystemFilter('');
    setDecisionFilter('all');
    setStartDate('');
    setEndDate('');
    setPage(0);
  };

  const handleExportClick = (event: React.MouseEvent<HTMLElement>) => {
    setExportMenuAnchor(event.currentTarget);
  };

  const handleExportClose = () => {
    setExportMenuAnchor(null);
  };

  const handleExport = async (format: 'json' | 'csv') => {
    handleExportClose();
    setExporting(true);

    try {
      const params: any = {
        limit: 10000,
      };

      if (agentFilter) params.filter_agent_id = agentFilter;
      if (userFilter) params.filter_user_id = userFilter;
      if (systemFilter) params.filter_system = systemFilter;
      if (decisionFilter !== 'all') params.filter_decision = decisionFilter;
      if (startDate) params.start_date = new Date(startDate).toISOString();
      if (endDate) params.end_date = new Date(endDate).toISOString();

      const blob =
        format === 'json'
          ? await auditLogsApi.exportToJson(params)
          : await auditLogsApi.exportToCsv(params);

      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `audit_logs_${format}_${Date.now()}.${format}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.response?.data?.detail || `Failed to export logs as ${format.toUpperCase()}`);
    } finally {
      setExporting(false);
    }
  };

  const decisionHue = (decision: string) =>
    DECISION_COLOR[decision as keyof typeof DECISION_COLOR] ?? theme.palette.text.disabled;

  const getDecisionIcon = (decision: string): React.ReactElement | undefined => {
    const c = decisionHue(decision);
    switch (decision) {
      case 'allowed':
        return <AllowedIcon sx={{ color: c, fontSize: 18 }} />;
      case 'blocked':
        return <BlockedIcon sx={{ color: c, fontSize: 18 }} />;
      case 'approved':
        return <ApprovalIcon sx={{ color: c, fontSize: 18 }} />;
      default:
        return undefined;
    }
  };

  const decisionChipSx = (decision: string) => {
    const main = decisionHue(decision);
    return {
      bgcolor: alpha(main, 0.15),
      color: main,
      fontWeight: 600,
      fontSize: '0.7rem',
      height: 22,
      border: `1px solid ${alpha(main, 0.35)}`,
    };
  };

  const activeFiltersCount = [
    agentFilter,
    userFilter,
    systemFilter,
    decisionFilter !== 'all' ? decisionFilter : '',
    startDate,
    endDate,
  ].filter(Boolean).length;

  const tableCellSx = {
    fontSize: '0.8rem',
    color: 'text.primary',
    borderColor: theme.palette.divider,
    py: 1.25,
  };

  const headCellSx = {
    ...tableCellSx,
    fontWeight: 600,
    color: 'text.secondary',
    bgcolor: styles.surfaceBg,
  };

  const primaryMain = theme.palette.primary.main;

  return (
    <Box sx={{ bgcolor: 'background.default', px: 3, py: 3, minHeight: '100%' }}>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
          gap: 2,
          mb: 3,
        }}
      >
        <Box>
          <Typography
            variant="h4"
            sx={{
              fontWeight: 700,
              letterSpacing: '-0.02em',
              color: 'text.primary',
            }}
          >
            Audit Logs
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.75, maxWidth: 520 }}>
            Search, filter, and export policy decision history across agents and systems.
          </Typography>
        </Box>
        <Button
          variant="outlined"
          size="medium"
          startIcon={
            exporting ? (
              <CircularProgress size={16} sx={{ color: 'primary.main' }} />
            ) : (
              <DownloadIcon />
            )
          }
          onClick={handleExportClick}
          disabled={exporting}
          sx={{
            borderColor: alpha(primaryMain, 0.45),
            color: primaryMain,
            textTransform: 'none',
            fontWeight: 600,
            '&:hover': { borderColor: primaryMain, bgcolor: alpha(primaryMain, 0.08) },
          }}
        >
          Export
        </Button>
      </Box>

      <Paper
        elevation={0}
        sx={{
          p: 2,
          mb: 3,
          bgcolor: 'background.paper',
          backgroundImage: 'none',
          border: `1px solid ${theme.palette.divider}`,
          borderRadius: 2,
        }}
      >
        <Grid container spacing={1.5}>
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              size="small"
              placeholder="Search logs..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              sx={smallFieldSx}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon sx={{ color: 'text.secondary', fontSize: 20 }} />
                  </InputAdornment>
                ),
              }}
            />
          </Grid>

          <Grid item xs={12} md={3}>
            <TextField
              fullWidth
              size="small"
              label="Agent ID"
              value={agentFilter}
              onChange={(e) => {
                setAgentFilter(e.target.value);
                setPage(0);
              }}
              placeholder="Filter by agent"
              sx={smallFieldSx}
            />
          </Grid>

          <Grid item xs={12} md={3}>
            <TextField
              fullWidth
              size="small"
              label="User ID"
              value={userFilter}
              onChange={(e) => {
                setUserFilter(e.target.value);
                setPage(0);
              }}
              placeholder="Filter by user"
              sx={smallFieldSx}
            />
          </Grid>

          <Grid item xs={12} md={3}>
            <TextField
              fullWidth
              size="small"
              label="System"
              value={systemFilter}
              onChange={(e) => {
                setSystemFilter(e.target.value);
                setPage(0);
              }}
              placeholder="Filter by system"
              sx={smallFieldSx}
            />
          </Grid>

          <Grid item xs={12} md={3}>
            <FormControl fullWidth size="small" sx={smallFieldSx}>
              <InputLabel id="decision-filter-label" sx={{ color: 'text.secondary', fontSize: '0.8125rem' }}>
                Decision
              </InputLabel>
              <Select
                labelId="decision-filter-label"
                value={decisionFilter}
                label="Decision"
                onChange={(e) => {
                  setDecisionFilter(e.target.value);
                  setPage(0);
                }}
                sx={{
                  fontSize: '0.8125rem',
                  color: 'text.primary',
                  bgcolor: styles.inputBg,
                  '& .MuiOutlinedInput-notchedOutline': { borderColor: theme.palette.divider },
                  '&:hover .MuiOutlinedInput-notchedOutline': {
                    borderColor: alpha(theme.palette.text.primary, theme.palette.mode === 'dark' ? 0.14 : 0.23),
                  },
                  '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                    borderColor: alpha(primaryMain, 0.6),
                  },
                }}
                MenuProps={{
                  PaperProps: {
                    sx: {
                      bgcolor: theme.palette.background.paper,
                      border: `1px solid ${theme.palette.divider}`,
                      mt: 0.5,
                    },
                  },
                }}
              >
                <MenuItem value="all" sx={{ fontSize: '0.8125rem' }}>
                  All
                </MenuItem>
                <MenuItem value="allowed" sx={{ fontSize: '0.8125rem' }}>
                  Allowed
                </MenuItem>
                <MenuItem value="blocked" sx={{ fontSize: '0.8125rem' }}>
                  Blocked
                </MenuItem>
                <MenuItem value="approved" sx={{ fontSize: '0.8125rem' }}>
                  Approved
                </MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} md={3}>
            <TextField
              fullWidth
              size="small"
              label="Start Date"
              type="datetime-local"
              value={startDate}
              onChange={(e) => {
                setStartDate(e.target.value);
                setPage(0);
              }}
              InputLabelProps={{ shrink: true }}
              sx={smallFieldSx}
            />
          </Grid>

          <Grid item xs={12} md={3}>
            <TextField
              fullWidth
              size="small"
              label="End Date"
              type="datetime-local"
              value={endDate}
              onChange={(e) => {
                setEndDate(e.target.value);
                setPage(0);
              }}
              InputLabelProps={{ shrink: true }}
              sx={smallFieldSx}
            />
          </Grid>

          {activeFiltersCount > 0 && (
            <Grid item xs={12}>
              <Button
                size="small"
                startIcon={<ClearIcon sx={{ fontSize: 18 }} />}
                onClick={handleClearFilters}
                sx={{ color: 'text.secondary', textTransform: 'none', '&:hover': { color: 'text.primary' } }}
              >
                Clear Filters ({activeFiltersCount})
              </Button>
            </Grid>
          )}
        </Grid>
      </Paper>

      {error && (
        <Alert
          severity="error"
          onClose={() => setError(null)}
          sx={{
            mb: 3,
            bgcolor: alpha(theme.palette.error.main, 0.12),
            color: theme.palette.error.main,
            border: `1px solid ${alpha(theme.palette.error.main, 0.35)}`,
            '& .MuiAlert-icon': { color: theme.palette.error.main },
          }}
        >
          {error}
        </Alert>
      )}

      <TableContainer
        component={Paper}
        elevation={0}
        sx={{
          bgcolor: 'background.paper',
          backgroundImage: 'none',
          border: `1px solid ${theme.palette.divider}`,
          borderRadius: 2,
          overflow: 'hidden',
        }}
      >
        <Table size="small" sx={{ borderCollapse: 'separate' }}>
          <TableHead>
            <TableRow>
              <TableCell sx={headCellSx}>Decision</TableCell>
              <TableCell sx={headCellSx}>Timestamp</TableCell>
              <TableCell sx={headCellSx}>Agent</TableCell>
              <TableCell sx={headCellSx}>Tool</TableCell>
              <TableCell sx={headCellSx}>System</TableCell>
              <TableCell sx={headCellSx}>User</TableCell>
              <TableCell align="right" sx={headCellSx}>
                Actions
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ ...tableCellSx, py: 8, border: 0 }}>
                  <CircularProgress size={32} sx={{ color: 'primary.main' }} />
                </TableCell>
              </TableRow>
            ) : logs.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ ...tableCellSx, py: 8, border: 0 }}>
                  <Typography sx={{ color: 'text.secondary', fontSize: '0.8rem' }}>
                    {activeFiltersCount > 0 || searchDebounce
                      ? 'No audit logs found matching your filters'
                      : 'No audit logs available'}
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              logs.map((log) => (
                <TableRow
                  key={log.id}
                  hover
                  sx={{
                    '&:hover': { bgcolor: styles.hoverBg },
                    '&:last-child td': { borderBottom: 0 },
                  }}
                >
                  <TableCell sx={tableCellSx}>
                    <Stack direction="row" alignItems="center" spacing={0.75}>
                      {getDecisionIcon(log.decision)}
                      <Chip label={log.decision.toUpperCase()} size="small" sx={decisionChipSx(log.decision)} />
                    </Stack>
                  </TableCell>
                  <TableCell sx={{ ...tableCellSx, fontFamily: styles.mono }}>
                    <Typography sx={{ fontSize: '0.8rem', fontFamily: styles.mono, color: 'text.primary' }}>
                      {format(new Date(log.timestamp), 'MMM dd, yyyy HH:mm:ss')}
                    </Typography>
                    <Typography sx={{ fontSize: '0.7rem', fontFamily: styles.mono, color: 'text.secondary' }}>
                      {formatDistanceToNow(new Date(log.timestamp), { addSuffix: true })}
                    </Typography>
                  </TableCell>
                  <TableCell sx={tableCellSx}>
                    <Typography sx={{ fontSize: '0.8rem', fontFamily: styles.mono, color: 'text.primary' }}>
                      {log.agent_id}
                    </Typography>
                    {log.agent_name && (
                      <Typography sx={{ fontSize: '0.7rem', color: 'text.secondary', display: 'block' }}>
                        {log.agent_name}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell sx={{ ...tableCellSx, fontFamily: styles.mono }}>
                    <Typography sx={{ fontSize: '0.8rem', fontFamily: styles.mono }}>{log.tool_name || 'N/A'}</Typography>
                  </TableCell>
                  <TableCell sx={tableCellSx}>
                    <Chip
                      label={log.system_accessed}
                      size="small"
                      variant="outlined"
                      sx={{
                        fontSize: '0.7rem',
                        height: 22,
                        color: 'text.secondary',
                        borderColor: alpha(theme.palette.text.primary, 0.15),
                        bgcolor: styles.surfaceBg,
                      }}
                    />
                  </TableCell>
                  <TableCell sx={{ ...tableCellSx, fontFamily: styles.mono }}>
                    <Typography sx={{ fontSize: '0.8rem', fontFamily: styles.mono }}>{log.user_id || 'N/A'}</Typography>
                  </TableCell>
                  <TableCell align="right" sx={tableCellSx}>
                    <Tooltip title="View Details">
                      <IconButton
                        size="small"
                        onClick={() => handleViewDetails(log)}
                        sx={{
                          color: 'text.secondary',
                          '&:hover': { color: primaryMain, bgcolor: alpha(primaryMain, 0.1) },
                        }}
                      >
                        <VisibilityIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
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
            color: 'text.secondary',
            borderTop: `1px solid ${theme.palette.divider}`,
            bgcolor: styles.surfaceBg,
            '& .MuiTablePagination-toolbar': { minHeight: 52 },
            '& .MuiTablePagination-selectLabel, & .MuiTablePagination-displayedRows': {
              fontSize: '0.8rem',
              color: 'text.secondary',
            },
            '& .MuiIconButton-root': { color: 'text.secondary' },
            '& .MuiSelect-select': { fontSize: '0.8rem', color: 'text.primary' },
          }}
        />
      </TableContainer>

      <Dialog
        open={detailModalOpen}
        onClose={handleCloseDetail}
        maxWidth="md"
        fullWidth
        PaperProps={{
          elevation: 0,
          sx: {
            bgcolor: styles.dialogBg,
            backgroundImage: 'none',
            border: `1px solid ${theme.palette.divider}`,
            borderRadius: 2,
          },
        }}
      >
        <DialogTitle sx={{ color: 'text.primary', fontWeight: 700, letterSpacing: '-0.02em', pb: 1 }}>
          Audit Log Details
        </DialogTitle>
        <DialogContent sx={{ pt: 0 }}>
          {selectedLog && (
            <Grid container spacing={2} sx={{ mt: 0.5 }}>
              <Grid item xs={12} md={6}>
                <Typography variant="caption" sx={{ color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  Log ID
                </Typography>
                <Typography variant="body2" sx={{ fontFamily: styles.mono, mb: 2, color: 'text.primary', fontSize: '0.85rem' }}>
                  {selectedLog.id}
                </Typography>
              </Grid>

              <Grid item xs={12} md={6}>
                <Typography variant="caption" sx={{ color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  Timestamp
                </Typography>
                <Typography variant="body2" sx={{ mb: 2, color: 'text.primary', fontFamily: styles.mono, fontSize: '0.85rem' }}>
                  {format(new Date(selectedLog.timestamp), 'PPpp')}
                </Typography>
              </Grid>

              <Grid item xs={12} md={6}>
                <Typography variant="caption" sx={{ color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  Agent ID
                </Typography>
                <Typography variant="body2" sx={{ fontFamily: styles.mono, mb: 2, color: 'text.primary', fontSize: '0.85rem' }}>
                  {selectedLog.agent_id}
                </Typography>
              </Grid>

              <Grid item xs={12} md={6}>
                <Typography variant="caption" sx={{ color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  Agent Name
                </Typography>
                <Typography variant="body2" sx={{ mb: 2, color: 'text.primary' }}>
                  {selectedLog.agent_name || 'N/A'}
                </Typography>
              </Grid>

              <Grid item xs={12} md={6}>
                <Typography variant="caption" sx={{ color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  User ID
                </Typography>
                <Typography variant="body2" sx={{ fontFamily: styles.mono, mb: 2, color: 'text.primary', fontSize: '0.85rem' }}>
                  {selectedLog.user_id || 'N/A'}
                </Typography>
              </Grid>

              <Grid item xs={12} md={6}>
                <Typography variant="caption" sx={{ color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  Tool Name
                </Typography>
                <Typography variant="body2" sx={{ fontFamily: styles.mono, mb: 2, color: 'text.primary', fontSize: '0.85rem' }}>
                  {selectedLog.tool_name || 'N/A'}
                </Typography>
              </Grid>

              <Grid item xs={12} md={6}>
                <Typography variant="caption" sx={{ color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  System Accessed
                </Typography>
                <Typography variant="body2" sx={{ mb: 2, color: 'text.primary' }}>
                  {selectedLog.system_accessed}
                </Typography>
              </Grid>

              <Grid item xs={12} md={6}>
                <Typography variant="caption" sx={{ color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  Decision
                </Typography>
                <Box sx={{ mb: 2 }}>
                  <Chip
                    label={selectedLog.decision.toUpperCase()}
                    size="small"
                    icon={getDecisionIcon(selectedLog.decision)}
                    sx={{
                      ...decisionChipSx(selectedLog.decision),
                      '& .MuiChip-icon': { ml: 0.75 },
                    }}
                  />
                </Box>
              </Grid>

              {selectedLog.policy_ids && selectedLog.policy_ids.length > 0 && (
                <Grid item xs={12}>
                  <Typography variant="caption" sx={{ color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                    Policy IDs
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mt: 0.5 }}>
                    {selectedLog.policy_ids.map((policyId, idx) => (
                      <Chip
                        key={idx}
                        label={policyId}
                        size="small"
                        variant="outlined"
                        sx={{
                          fontSize: '0.7rem',
                          color: 'text.secondary',
                          borderColor: alpha(theme.palette.text.primary, 0.15),
                          bgcolor: styles.surfaceBg,
                        }}
                      />
                    ))}
                  </Box>
                </Grid>
              )}

              {selectedLog.reason && (
                <Grid item xs={12}>
                  <Typography variant="caption" sx={{ color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                    Reason
                  </Typography>
                  <Typography variant="body2" sx={{ mb: 2, color: 'text.primary' }}>
                    {selectedLog.reason}
                  </Typography>
                </Grid>
              )}

              {selectedLog.data_touched && (
                <Grid item xs={12}>
                  <Typography variant="caption" sx={{ color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                    Data Touched
                  </Typography>
                  <Typography variant="body2" sx={{ mb: 2, color: 'text.primary' }}>
                    {selectedLog.data_touched}
                  </Typography>
                </Grid>
              )}

              {selectedLog.arguments && Object.keys(selectedLog.arguments).length > 0 && (
                <Grid item xs={12}>
                  <Typography variant="caption" sx={{ color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                    Arguments
                  </Typography>
                  <Paper
                    elevation={0}
                    sx={{
                      p: 2,
                      mt: 0.5,
                      bgcolor: styles.codeBg,
                      border: `1px solid ${theme.palette.divider}`,
                      borderRadius: 1.5,
                    }}
                  >
                    <pre
                      style={{
                        margin: 0,
                        overflow: 'auto',
                        fontSize: '0.8rem',
                        fontFamily: styles.mono,
                        color: theme.palette.text.primary,
                      }}
                    >
                      {JSON.stringify(selectedLog.arguments, null, 2)}
                    </pre>
                  </Paper>
                </Grid>
              )}

              {selectedLog.metadata && Object.keys(selectedLog.metadata).length > 0 && (
                <Grid item xs={12}>
                  <Typography variant="caption" sx={{ color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                    Metadata
                  </Typography>
                  <Paper
                    elevation={0}
                    sx={{
                      p: 2,
                      mt: 0.5,
                      bgcolor: styles.codeBg,
                      border: `1px solid ${theme.palette.divider}`,
                      borderRadius: 1.5,
                    }}
                  >
                    <pre
                      style={{
                        margin: 0,
                        overflow: 'auto',
                        fontSize: '0.8rem',
                        fontFamily: styles.mono,
                        color: theme.palette.text.primary,
                      }}
                    >
                      {JSON.stringify(selectedLog.metadata, null, 2)}
                    </pre>
                  </Paper>
                </Grid>
              )}
            </Grid>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2, borderTop: `1px solid ${theme.palette.divider}` }}>
          <Button
            onClick={handleCloseDetail}
            sx={{
              color: 'text.secondary',
              textTransform: 'none',
              '&:hover': { bgcolor: styles.hoverBg, color: 'text.primary' },
            }}
          >
            Close
          </Button>
        </DialogActions>
      </Dialog>

      <Menu
        anchorEl={exportMenuAnchor}
        open={Boolean(exportMenuAnchor)}
        onClose={handleExportClose}
        PaperProps={{
          elevation: 0,
          sx: {
            bgcolor: theme.palette.background.paper,
            border: `1px solid ${theme.palette.divider}`,
            mt: 0.5,
            minWidth: 200,
          },
        }}
      >
        <MenuItem
          onClick={() => handleExport('json')}
          sx={{
            fontSize: '0.875rem',
            color: 'text.primary',
            py: 1.25,
            '&:hover': { bgcolor: alpha(primaryMain, 0.1) },
          }}
        >
          <ListItemIcon>
            <DownloadIcon fontSize="small" sx={{ color: primaryMain }} />
          </ListItemIcon>
          <ListItemText primary="Export as JSON" primaryTypographyProps={{ fontSize: '0.875rem' }} />
        </MenuItem>
        <MenuItem
          onClick={() => handleExport('csv')}
          sx={{
            fontSize: '0.875rem',
            color: 'text.primary',
            py: 1.25,
            '&:hover': { bgcolor: alpha(primaryMain, 0.1) },
          }}
        >
          <ListItemIcon>
            <DownloadIcon fontSize="small" sx={{ color: primaryMain }} />
          </ListItemIcon>
          <ListItemText primary="Export as CSV" primaryTypographyProps={{ fontSize: '0.875rem' }} />
        </MenuItem>
      </Menu>
    </Box>
  );
};

export default AuditLogs;
