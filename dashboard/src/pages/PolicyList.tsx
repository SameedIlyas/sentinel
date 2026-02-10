import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
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
  Switch,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
} from '@mui/material';
import {
  Search as SearchIcon,
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Visibility as VisibilityIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import policiesApi from '@/api/policies';
import { Policy } from '@/types';

const PolicyList: React.FC = () => {
  const navigate = useNavigate();
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [policyTypeFilter, setPolicyTypeFilter] = useState<string>('all');
  const [enabledFilter, setEnabledFilter] = useState<string>('all');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [policyToDelete, setPolicyToDelete] = useState<Policy | null>(null);
  const [searchDebounce, setSearchDebounce] = useState('');

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearchDebounce(search);
      setPage(0);
    }, 500);

    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    fetchPolicies();
  }, [page, rowsPerPage, searchDebounce, policyTypeFilter, enabledFilter]);

  const fetchPolicies = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await policiesApi.listPolicies({
        page: page + 1,
        page_size: rowsPerPage,
        policy_type: policyTypeFilter === 'all' ? undefined : policyTypeFilter,
        enabled: enabledFilter === 'all' ? undefined : enabledFilter === 'enabled',
      });
      
      // Filter by search term on frontend (since backend doesn't have search)
      let filteredPolicies = response.policies;
      if (searchDebounce) {
        const searchLower = searchDebounce.toLowerCase();
        filteredPolicies = filteredPolicies.filter(
          (p) =>
            p.name.toLowerCase().includes(searchLower) ||
            p.description?.toLowerCase().includes(searchLower) ||
            p.id.toLowerCase().includes(searchLower)
        );
      }
      
      setPolicies(filteredPolicies);
      setTotal(searchDebounce ? filteredPolicies.length : response.total);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch policies');
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

  const handleToggleEnabled = async (policy: Policy) => {
    try {
      await policiesApi.togglePolicy(policy.id, !policy.enabled);
      fetchPolicies(); // Refresh list
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to toggle policy');
    }
  };

  const handleDeleteClick = (policy: Policy) => {
    setPolicyToDelete(policy);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!policyToDelete) return;

    try {
      await policiesApi.deletePolicy(policyToDelete.id);
      setDeleteDialogOpen(false);
      setPolicyToDelete(null);
      fetchPolicies(); // Refresh list
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete policy');
      setDeleteDialogOpen(false);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false);
    setPolicyToDelete(null);
  };

  const getPolicyTypeColor = (type: string): 'primary' | 'secondary' | 'success' | 'warning' | 'error' => {
    switch (type.toLowerCase()) {
      case 'access_control':
        return 'primary';
      case 'financial':
        return 'warning';
      case 'data_protection':
        return 'error';
      case 'approval':
        return 'secondary';
      default:
        return 'primary';
    }
  };

  const formatPolicyType = (type: string): string => {
    return type
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" sx={{ fontWeight: 'bold' }}>
          Policies
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => navigate('/policies/create')}
        >
          Create Policy
        </Button>
      </Box>

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <TextField
            placeholder="Search policies..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            sx={{ flex: 1, minWidth: 250 }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon />
                </InputAdornment>
              ),
            }}
          />
          <FormControl sx={{ minWidth: 180 }}>
            <InputLabel>Policy Type</InputLabel>
            <Select
              value={policyTypeFilter}
              label="Policy Type"
              onChange={(e) => {
                setPolicyTypeFilter(e.target.value);
                setPage(0);
              }}
            >
              <MenuItem value="all">All Types</MenuItem>
              <MenuItem value="access_control">Access Control</MenuItem>
              <MenuItem value="financial">Financial</MenuItem>
              <MenuItem value="data_protection">Data Protection</MenuItem>
              <MenuItem value="approval">Approval</MenuItem>
            </Select>
          </FormControl>
          <FormControl sx={{ minWidth: 150 }}>
            <InputLabel>Status</InputLabel>
            <Select
              value={enabledFilter}
              label="Status"
              onChange={(e) => {
                setEnabledFilter(e.target.value);
                setPage(0);
              }}
            >
              <MenuItem value="all">All</MenuItem>
              <MenuItem value="enabled">Enabled</MenuItem>
              <MenuItem value="disabled">Disabled</MenuItem>
            </Select>
          </FormControl>
        </Box>
      </Paper>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Policies Table */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Name</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Applies To</TableCell>
              <TableCell>Priority</TableCell>
              <TableCell>Enabled</TableCell>
              <TableCell>Created</TableCell>
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
            ) : policies.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 8 }}>
                  <Typography color="text.secondary">
                    {searchDebounce || policyTypeFilter !== 'all' || enabledFilter !== 'all'
                      ? 'No policies found matching your filters'
                      : 'No policies created yet'}
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              policies.map((policy) => (
                <TableRow key={policy.id} hover>
                  <TableCell>
                    <Typography variant="body1" sx={{ fontWeight: 500 }}>
                      {policy.name}
                    </Typography>
                    {policy.description && (
                      <Typography variant="caption" color="text.secondary" display="block">
                        {policy.description}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={formatPolicyType(policy.policy_type)}
                      color={getPolicyTypeColor(policy.policy_type)}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    {policy.applies_to.length === 0 ? (
                      <Typography variant="caption" color="text.secondary">
                        None
                      </Typography>
                    ) : policy.applies_to.includes('*') ? (
                      <Chip label="All Agents" size="small" variant="outlined" />
                    ) : (
                      <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                        {policy.applies_to.slice(0, 2).map((agent, idx) => (
                          <Chip key={idx} label={agent} size="small" variant="outlined" />
                        ))}
                        {policy.applies_to.length > 2 && (
                          <Chip
                            label={`+${policy.applies_to.length - 2}`}
                            size="small"
                            variant="outlined"
                          />
                        )}
                      </Box>
                    )}
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={policy.priority ?? 'Default'}
                      size="small"
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell>
                    <Switch
                      checked={policy.enabled}
                      onChange={() => handleToggleEnabled(policy)}
                      color="success"
                    />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {format(new Date(policy.created_at), 'MMM dd, yyyy')}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title="View Details">
                      <IconButton
                        size="small"
                        onClick={() => navigate(`/policies/${policy.id}`)}
                      >
                        <VisibilityIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Edit Policy">
                      <IconButton
                        size="small"
                        onClick={() => navigate(`/policies/${policy.id}/edit`)}
                      >
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Delete Policy">
                      <IconButton
                        size="small"
                        onClick={() => handleDeleteClick(policy)}
                        color="error"
                      >
                        <DeleteIcon fontSize="small" />
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

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={handleDeleteCancel}>
        <DialogTitle>Delete Policy</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete the policy "{policyToDelete?.name}"? This action
            cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleDeleteCancel}>Cancel</Button>
          <Button onClick={handleDeleteConfirm} color="error" variant="contained">
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default PolicyList;
