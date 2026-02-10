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
} from '@mui/material';
import {
  Search as SearchIcon,
  Visibility as VisibilityIcon,
  Download as DownloadIcon,
  FilterList as FilterIcon,
  Clear as ClearIcon,
  CheckCircle as AllowedIcon,
  Block as BlockedIcon,
  HourglassEmpty as ApprovalIcon,
} from '@mui/icons-material';
import { format, formatDistanceToNow } from 'date-fns';
import auditLogsApi from '@/api/auditLogs';
import { AuditLog } from '@/types';

const AuditLogs: React.FC = () => {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [total, setTotal] = useState(0);
  
  // Filters
  const [search, setSearch] = useState('');
  const [searchDebounce, setSearchDebounce] = useState('');
  const [agentFilter, setAgentFilter] = useState('');
  const [userFilter, setUserFilter] = useState('');
  const [systemFilter, setSystemFilter] = useState('');
  const [decisionFilter, setDecisionFilter] = useState<string>('all');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  
  // Detail modal
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null);
  
  // Export menu
  const [exportMenuAnchor, setExportMenuAnchor] = useState<null | HTMLElement>(null);
  const [exporting, setExporting] = useState(false);

  // Debounce search
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
      
      const blob = format === 'json' 
        ? await auditLogsApi.exportToJson(params)
        : await auditLogsApi.exportToCsv(params);
      
      // Download file
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

  const getDecisionIcon = (decision: string) => {
    switch (decision) {
      case 'allowed':
        return <AllowedIcon sx={{ color: 'success.main', fontSize: 20 }} />;
      case 'blocked':
        return <BlockedIcon sx={{ color: 'error.main', fontSize: 20 }} />;
      case 'approved':
        return <ApprovalIcon sx={{ color: 'warning.main', fontSize: 20 }} />;
      default:
        return null;
    }
  };

  const getDecisionColor = (decision: string): 'success' | 'error' | 'warning' => {
    switch (decision) {
      case 'allowed':
        return 'success';
      case 'blocked':
        return 'error';
      case 'approved':
        return 'warning';
      default:
        return 'success';
    }
  };

  const activeFiltersCount = [
    agentFilter,
    userFilter,
    systemFilter,
    decisionFilter !== 'all' ? decisionFilter : '',
    startDate,
    endDate,
  ].filter(Boolean).length;

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" sx={{ fontWeight: 'bold' }}>
          Audit Logs
        </Typography>
        <Button
          variant="outlined"
          startIcon={exporting ? <CircularProgress size={16} /> : <DownloadIcon />}
          onClick={handleExportClick}
          disabled={exporting}
        >
          Export
        </Button>
      </Box>

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2}>
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              placeholder="Search logs..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon />
                  </InputAdornment>
                ),
              }}
            />
          </Grid>

          <Grid item xs={12} md={3}>
            <TextField
              fullWidth
              label="Agent ID"
              value={agentFilter}
              onChange={(e) => {
                setAgentFilter(e.target.value);
                setPage(0);
              }}
              placeholder="Filter by agent"
            />
          </Grid>

          <Grid item xs={12} md={3}>
            <TextField
              fullWidth
              label="User ID"
              value={userFilter}
              onChange={(e) => {
                setUserFilter(e.target.value);
                setPage(0);
              }}
              placeholder="Filter by user"
            />
          </Grid>

          <Grid item xs={12} md={3}>
            <TextField
              fullWidth
              label="System"
              value={systemFilter}
              onChange={(e) => {
                setSystemFilter(e.target.value);
                setPage(0);
              }}
              placeholder="Filter by system"
            />
          </Grid>

          <Grid item xs={12} md={3}>
            <FormControl fullWidth>
              <InputLabel>Decision</InputLabel>
              <Select
                value={decisionFilter}
                label="Decision"
                onChange={(e) => {
                  setDecisionFilter(e.target.value);
                  setPage(0);
                }}
              >
                <MenuItem value="all">All</MenuItem>
                <MenuItem value="allowed">Allowed</MenuItem>
                <MenuItem value="blocked">Blocked</MenuItem>
                <MenuItem value="approved">Approved</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} md={3}>
            <TextField
              fullWidth
              label="Start Date"
              type="datetime-local"
              value={startDate}
              onChange={(e) => {
                setStartDate(e.target.value);
                setPage(0);
              }}
              InputLabelProps={{ shrink: true }}
            />
          </Grid>

          <Grid item xs={12} md={3}>
            <TextField
              fullWidth
              label="End Date"
              type="datetime-local"
              value={endDate}
              onChange={(e) => {
                setEndDate(e.target.value);
                setPage(0);
              }}
              InputLabelProps={{ shrink: true }}
            />
          </Grid>

          {activeFiltersCount > 0 && (
            <Grid item xs={12}>
              <Button
                size="small"
                startIcon={<ClearIcon />}
                onClick={handleClearFilters}
              >
                Clear Filters ({activeFiltersCount})
              </Button>
            </Grid>
          )}
        </Grid>
      </Paper>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Logs Table */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Decision</TableCell>
              <TableCell>Timestamp</TableCell>
              <TableCell>Agent</TableCell>
              <TableCell>Tool</TableCell>
              <TableCell>System</TableCell>
              <TableCell>User</TableCell>
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
            ) : logs.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 8 }}>
                  <Typography color="text.secondary">
                    {activeFiltersCount > 0 || searchDebounce
                      ? 'No audit logs found matching your filters'
                      : 'No audit logs available'}
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              logs.map((log) => (
                <TableRow key={log.id} hover>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      {getDecisionIcon(log.decision)}
                      <Chip
                        label={log.decision.toUpperCase()}
                        color={getDecisionColor(log.decision)}
                        size="small"
                      />
                    </Box>
                  </TableCell>
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
                      {log.agent_id}
                    </Typography>
                    {log.agent_name && (
                      <Typography variant="caption" color="text.secondary">
                        {log.agent_name}
                      </Typography>
                    )}
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
                    <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>
                      {log.user_id || 'N/A'}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title="View Details">
                      <IconButton size="small" onClick={() => handleViewDetails(log)}>
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
        />
      </TableContainer>

      {/* Detail Modal */}
      <Dialog
        open={detailModalOpen}
        onClose={handleCloseDetail}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Audit Log Details</DialogTitle>
        <DialogContent>
          {selectedLog && (
            <Grid container spacing={2} sx={{ mt: 1 }}>
              <Grid item xs={12} md={6}>
                <Typography variant="caption" color="text.secondary">
                  Log ID
                </Typography>
                <Typography variant="body2" sx={{ fontFamily: 'monospace', mb: 2 }}>
                  {selectedLog.id}
                </Typography>
              </Grid>

              <Grid item xs={12} md={6}>
                <Typography variant="caption" color="text.secondary">
                  Timestamp
                </Typography>
                <Typography variant="body2" sx={{ mb: 2 }}>
                  {format(new Date(selectedLog.timestamp), 'PPpp')}
                </Typography>
              </Grid>

              <Grid item xs={12} md={6}>
                <Typography variant="caption" color="text.secondary">
                  Agent ID
                </Typography>
                <Typography variant="body2" sx={{ fontFamily: 'monospace', mb: 2 }}>
                  {selectedLog.agent_id}
                </Typography>
              </Grid>

              <Grid item xs={12} md={6}>
                <Typography variant="caption" color="text.secondary">
                  Agent Name
                </Typography>
                <Typography variant="body2" sx={{ mb: 2 }}>
                  {selectedLog.agent_name || 'N/A'}
                </Typography>
              </Grid>

              <Grid item xs={12} md={6}>
                <Typography variant="caption" color="text.secondary">
                  User ID
                </Typography>
                <Typography variant="body2" sx={{ fontFamily: 'monospace', mb: 2 }}>
                  {selectedLog.user_id || 'N/A'}
                </Typography>
              </Grid>

              <Grid item xs={12} md={6}>
                <Typography variant="caption" color="text.secondary">
                  Tool Name
                </Typography>
                <Typography variant="body2" sx={{ fontFamily: 'monospace', mb: 2 }}>
                  {selectedLog.tool_name || 'N/A'}
                </Typography>
              </Grid>

              <Grid item xs={12} md={6}>
                <Typography variant="caption" color="text.secondary">
                  System Accessed
                </Typography>
                <Typography variant="body2" sx={{ mb: 2 }}>
                  {selectedLog.system_accessed}
                </Typography>
              </Grid>

              <Grid item xs={12} md={6}>
                <Typography variant="caption" color="text.secondary">
                  Decision
                </Typography>
                <Box sx={{ mb: 2 }}>
                  <Chip
                    label={selectedLog.decision.toUpperCase()}
                    color={getDecisionColor(selectedLog.decision)}
                    size="small"
                    icon={getDecisionIcon(selectedLog.decision)}
                  />
                </Box>
              </Grid>

              {selectedLog.policy_ids && selectedLog.policy_ids.length > 0 && (
                <Grid item xs={12}>
                  <Typography variant="caption" color="text.secondary">
                    Policy IDs
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mt: 0.5 }}>
                    {selectedLog.policy_ids.map((policyId, idx) => (
                      <Chip key={idx} label={policyId} size="small" variant="outlined" />
                    ))}
                  </Box>
                </Grid>
              )}

              {selectedLog.reason && (
                <Grid item xs={12}>
                  <Typography variant="caption" color="text.secondary">
                    Reason
                  </Typography>
                  <Typography variant="body2" sx={{ mb: 2 }}>
                    {selectedLog.reason}
                  </Typography>
                </Grid>
              )}

              {selectedLog.data_touched && (
                <Grid item xs={12}>
                  <Typography variant="caption" color="text.secondary">
                    Data Touched
                  </Typography>
                  <Typography variant="body2" sx={{ mb: 2 }}>
                    {selectedLog.data_touched}
                  </Typography>
                </Grid>
              )}

              {selectedLog.arguments && Object.keys(selectedLog.arguments).length > 0 && (
                <Grid item xs={12}>
                  <Typography variant="caption" color="text.secondary">
                    Arguments
                  </Typography>
                  <Paper sx={{ p: 2, bgcolor: 'grey.100', mt: 0.5 }}>
                    <pre style={{ margin: 0, overflow: 'auto', fontSize: '0.85rem' }}>
                      {JSON.stringify(selectedLog.arguments, null, 2)}
                    </pre>
                  </Paper>
                </Grid>
              )}

              {selectedLog.metadata && Object.keys(selectedLog.metadata).length > 0 && (
                <Grid item xs={12}>
                  <Typography variant="caption" color="text.secondary">
                    Metadata
                  </Typography>
                  <Paper sx={{ p: 2, bgcolor: 'grey.100', mt: 0.5 }}>
                    <pre style={{ margin: 0, overflow: 'auto', fontSize: '0.85rem' }}>
                      {JSON.stringify(selectedLog.metadata, null, 2)}
                    </pre>
                  </Paper>
                </Grid>
              )}
            </Grid>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDetail}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Export Menu */}
      <Menu
        anchorEl={exportMenuAnchor}
        open={Boolean(exportMenuAnchor)}
        onClose={handleExportClose}
      >
        <MenuItem onClick={() => handleExport('json')}>
          <ListItemIcon>
            <DownloadIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>Export as JSON</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => handleExport('csv')}>
          <ListItemIcon>
            <DownloadIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>Export as CSV</ListItemText>
        </MenuItem>
      </Menu>
    </Box>
  );
};

export default AuditLogs;
