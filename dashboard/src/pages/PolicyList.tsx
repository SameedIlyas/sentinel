import React, { useState, useEffect, useMemo } from 'react';
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
  DialogActions,
} from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
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
import { useAppStyles } from '@/hooks/useAppStyles';
import { utc } from '@/utils/date';

const PolicyList: React.FC = () => {
  const navigate = useNavigate();
  const theme = useTheme();
  const styles = useAppStyles();
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

  const primary = theme.palette.primary;

  const surfacePaperSx = useMemo(
    () =>
      ({
        bgcolor: 'background.paper',
        backgroundImage: 'none',
        border: `1px solid ${theme.palette.divider}`,
        borderRadius: 2,
        boxShadow: 'none',
      }) as const,
    [theme.palette.divider]
  );

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

  const getPolicyTypeAccent = (type: string): string => {
    switch (type.toLowerCase()) {
      case 'access_control':
        return primary.main;
      case 'financial':
        return '#f59e0b';
      case 'data_protection':
        return '#f87171';
      case 'approval':
        return '#a855f7';
      default:
        return primary.main;
    }
  };

  const formatPolicyType = (type: string): string => {
    return type
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  const smallFieldSx = {
    '& .MuiOutlinedInput-root': {
      fontSize: '0.8125rem',
      bgcolor: styles.inputBg,
    },
    '& .MuiInputLabel-root': { fontSize: '0.8125rem' },
  };

  const tableCellSx = {
    fontSize: '0.8rem',
    borderColor: theme.palette.divider,
    py: 1.25,
  };

  const tableHeadCellSx = {
    ...tableCellSx,
    fontSize: '0.7rem',
    fontWeight: 700,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.06em',
    color: 'text.secondary',
    borderBottom: `1px solid ${theme.palette.divider}`,
  };

  return (
    <Box sx={{ bgcolor: 'background.default', color: 'text.primary', py: 1, minHeight: '100%' }}>
      <Box sx={{ mb: 3 }}>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            flexWrap: 'wrap',
            gap: 2,
          }}
        >
          <Box>
            <Typography
              variant="h4"
              component="h1"
              sx={{
                fontWeight: 700,
                letterSpacing: '-0.02em',
                color: 'text.primary',
              }}
            >
              Policies
            </Typography>
            <Typography
              variant="body2"
              sx={{
                mt: 0.5,
                color: 'text.secondary',
                maxWidth: 480,
                lineHeight: 1.5,
              }}
            >
              Create, filter, and manage enforcement rules. Toggle policies on or off without leaving
              the list.
            </Typography>
          </Box>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => navigate('/policies/create')}
            sx={{
              textTransform: 'none',
              fontWeight: 600,
              px: 2.5,
              py: 1,
              borderRadius: 2,
              color: '#fff',
              background: `linear-gradient(135deg, ${primary.main} 0%, ${primary.dark} 45%, ${alpha(primary.main, 0.85)} 100%)`,
              boxShadow: `0 4px 20px ${alpha(primary.main, 0.35)}`,
              border: `1px solid ${theme.palette.divider}`,
              '&:hover': {
                background: `linear-gradient(135deg, ${primary.light} 0%, ${primary.main} 50%, ${alpha(primary.dark, 0.9)} 100%)`,
                boxShadow: `0 6px 24px ${alpha(primary.main, 0.45)}`,
              },
            }}
          >
            Create policy
          </Button>
        </Box>
      </Box>

      {/* Filters */}
      <Paper sx={{ ...surfacePaperSx, p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap', alignItems: 'flex-start' }}>
          <TextField
            placeholder="Search policies..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            size="small"
            sx={{ flex: 1, minWidth: 220, ...smallFieldSx }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                </InputAdornment>
              ),
            }}
          />
          <FormControl sx={{ minWidth: 160 }} size="small">
            <InputLabel id="policy-type-filter-label">Policy type</InputLabel>
            <Select
              labelId="policy-type-filter-label"
              value={policyTypeFilter}
              label="Policy type"
              onChange={(e) => {
                setPolicyTypeFilter(e.target.value);
                setPage(0);
              }}
              sx={{ fontSize: '0.8125rem', bgcolor: styles.inputBg }}
            >
              <MenuItem value="all" sx={{ fontSize: '0.8125rem' }}>
                All types
              </MenuItem>
              <MenuItem value="access_control" sx={{ fontSize: '0.8125rem' }}>
                Access control
              </MenuItem>
              <MenuItem value="financial" sx={{ fontSize: '0.8125rem' }}>
                Financial
              </MenuItem>
              <MenuItem value="data_protection" sx={{ fontSize: '0.8125rem' }}>
                Data protection
              </MenuItem>
              <MenuItem value="approval" sx={{ fontSize: '0.8125rem' }}>
                Approval
              </MenuItem>
            </Select>
          </FormControl>
          <FormControl sx={{ minWidth: 130 }} size="small">
            <InputLabel id="status-filter-label">Status</InputLabel>
            <Select
              labelId="status-filter-label"
              value={enabledFilter}
              label="Status"
              onChange={(e) => {
                setEnabledFilter(e.target.value);
                setPage(0);
              }}
              sx={{ fontSize: '0.8125rem', bgcolor: styles.inputBg }}
            >
              <MenuItem value="all" sx={{ fontSize: '0.8125rem' }}>
                All
              </MenuItem>
              <MenuItem value="enabled" sx={{ fontSize: '0.8125rem' }}>
                Enabled
              </MenuItem>
              <MenuItem value="disabled" sx={{ fontSize: '0.8125rem' }}>
                Disabled
              </MenuItem>
            </Select>
          </FormControl>
        </Box>
      </Paper>

      {error && (
        <Alert
          severity="error"
          sx={{
            mb: 3,
            bgcolor: alpha(theme.palette.error.main, 0.12),
            color: theme.palette.error.light,
            border: `1px solid ${alpha(theme.palette.error.main, 0.35)}`,
            '& .MuiAlert-icon': { color: theme.palette.error.main },
          }}
          onClose={() => setError(null)}
        >
          {error}
        </Alert>
      )}

      {/* Policies Table */}
      <TableContainer component={Paper} sx={{ ...surfacePaperSx, overflow: 'hidden' }}>
        <Table size="small" sx={{ '& .MuiTableCell-root': tableCellSx }}>
          <TableHead>
            <TableRow>
              <TableCell sx={tableHeadCellSx}>Name</TableCell>
              <TableCell sx={tableHeadCellSx}>Type</TableCell>
              <TableCell sx={tableHeadCellSx}>Applies to</TableCell>
              <TableCell sx={tableHeadCellSx}>Priority</TableCell>
              <TableCell sx={tableHeadCellSx}>Enabled</TableCell>
              <TableCell sx={tableHeadCellSx}>Created</TableCell>
              <TableCell align="right" sx={tableHeadCellSx}>
                Actions
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ ...tableCellSx, py: 8 }}>
                  <CircularProgress size={36} sx={{ color: 'primary.main' }} />
                </TableCell>
              </TableRow>
            ) : policies.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ ...tableCellSx, py: 8 }}>
                  <Typography sx={{ color: 'text.secondary', fontSize: '0.8rem' }}>
                    {searchDebounce || policyTypeFilter !== 'all' || enabledFilter !== 'all'
                      ? 'No policies found matching your filters'
                      : 'No policies created yet'}
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              policies.map((policy) => {
                const typeAccent = getPolicyTypeAccent(policy.policy_type);
                return (
                  <TableRow
                    key={policy.id}
                    hover
                    sx={{
                      '&:hover': { bgcolor: styles.hoverBg },
                      '&:last-child td': { borderBottom: 0 },
                    }}
                  >
                    <TableCell sx={tableCellSx}>
                      <Typography sx={{ fontWeight: 600, fontSize: '0.8rem', color: 'text.primary' }}>
                        {policy.name}
                      </Typography>
                      <Typography
                        component="span"
                        sx={{
                          display: 'block',
                          mt: 0.25,
                          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                          fontSize: '0.7rem',
                          color: 'text.secondary',
                          letterSpacing: '0.02em',
                          wordBreak: 'break-all',
                        }}
                      >
                        {policy.id}
                      </Typography>
                      {policy.description && (
                        <Typography
                          sx={{
                            mt: 0.5,
                            fontSize: '0.75rem',
                            color: 'text.secondary',
                            display: 'block',
                            lineHeight: 1.45,
                          }}
                        >
                          {policy.description}
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell sx={tableCellSx}>
                      <Chip
                        label={formatPolicyType(policy.policy_type)}
                        size="small"
                        sx={{
                          height: 24,
                          minWidth: 110,
                          justifyContent: 'center',
                          fontSize: '0.7rem',
                          fontWeight: 600,
                          bgcolor: alpha(typeAccent, 0.18),
                          color: typeAccent,
                          border: `1px solid ${alpha(typeAccent, 0.35)}`,
                          '& .MuiChip-label': { px: 1 },
                        }}
                      />
                    </TableCell>
                    <TableCell sx={tableCellSx}>
                      {policy.applies_to.length === 0 ? (
                        <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>
                          None
                        </Typography>
                      ) : policy.applies_to.includes('*') ? (
                        <Chip
                          label="All agents"
                          size="small"
                          sx={{
                            height: 22,
                            fontSize: '0.7rem',
                            fontFamily:
                              'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                            bgcolor: styles.surfaceBg,
                            color: 'text.primary',
                            border: `1px solid ${theme.palette.divider}`,
                          }}
                        />
                      ) : (
                        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                          {policy.applies_to.slice(0, 2).map((agent, idx) => (
                            <Chip
                              key={idx}
                              label={agent}
                              size="small"
                              sx={{
                                height: 22,
                                fontSize: '0.7rem',
                                fontFamily:
                                  'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                                bgcolor: styles.surfaceBg,
                                color: 'text.primary',
                                border: `1px solid ${theme.palette.divider}`,
                              }}
                            />
                          ))}
                          {policy.applies_to.length > 2 && (
                            <Chip
                              label={`+${policy.applies_to.length - 2}`}
                              size="small"
                              sx={{
                                height: 22,
                                fontSize: '0.7rem',
                                fontFamily:
                                  'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                                bgcolor: styles.surfaceBg,
                                color: 'text.secondary',
                                border: `1px solid ${theme.palette.divider}`,
                              }}
                            />
                          )}
                        </Box>
                      )}
                    </TableCell>
                    <TableCell sx={tableCellSx}>
                      <Box
                        component="span"
                        sx={{
                          display: 'inline-block',
                          px: 1,
                          py: 0.35,
                          borderRadius: 1,
                          fontSize: '0.7rem',
                          fontWeight: 500,
                          letterSpacing: '0.02em',
                          bgcolor: styles.surfaceBg,
                          color: 'text.secondary',
                          border: `1px solid ${theme.palette.divider}`,
                        }}
                      >
                        {policy.priority ?? 'Default'}
                      </Box>
                    </TableCell>
                    <TableCell sx={tableCellSx}>
                      <Switch
                        checked={policy.enabled}
                        onChange={() => handleToggleEnabled(policy)}
                        size="small"
                        sx={{
                          '& .MuiSwitch-switchBase.Mui-checked': {
                            color: theme.palette.primary.main,
                            '&:hover': {
                              bgcolor: alpha(theme.palette.primary.main, 0.16),
                            },
                          },
                          '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                            backgroundColor: alpha(theme.palette.primary.main, 0.55),
                            opacity: 1,
                          },
                          '& .MuiSwitch-track': {
                            bgcolor: alpha(theme.palette.text.primary, 0.15),
                            opacity: 1,
                          },
                        }}
                      />
                    </TableCell>
                    <TableCell sx={tableCellSx}>
                      <Typography sx={{ fontSize: '0.8rem', color: 'text.primary' }}>
                        {format(utc(policy.created_at), 'MMM dd, yyyy')}
                      </Typography>
                    </TableCell>
                    <TableCell align="right" sx={tableCellSx}>
                      <Tooltip title="View details">
                        <IconButton
                          size="small"
                          onClick={() => navigate(`/policies/${policy.id}`)}
                          sx={{
                            color: 'text.secondary',
                            '&:hover': {
                              bgcolor: styles.hoverBg,
                              color: 'text.primary',
                            },
                          }}
                        >
                          <VisibilityIcon sx={{ fontSize: 18 }} />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Edit policy">
                        <IconButton
                          size="small"
                          onClick={() => navigate(`/policies/${policy.id}/edit`)}
                          sx={{
                            color: 'text.secondary',
                            '&:hover': {
                              bgcolor: styles.hoverBg,
                              color: 'text.primary',
                            },
                          }}
                        >
                          <EditIcon sx={{ fontSize: 18 }} />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Delete policy">
                        <IconButton
                          size="small"
                          onClick={() => handleDeleteClick(policy)}
                          sx={{
                            color: alpha(theme.palette.error.main, 0.85),
                            '&:hover': {
                              bgcolor: alpha(theme.palette.error.main, 0.12),
                              color: theme.palette.error.light,
                            },
                          }}
                        >
                          <DeleteIcon sx={{ fontSize: 18 }} />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                );
              })
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
            color: 'text.primary',
            '& .MuiTablePagination-toolbar': { minHeight: 52 },
            '& .MuiTablePagination-selectLabel, & .MuiTablePagination-displayedRows': {
              fontSize: '0.8rem',
              color: 'text.secondary',
            },
            '& .MuiIconButton-root': { color: 'text.secondary' },
          }}
        />
      </TableContainer>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={deleteDialogOpen}
        onClose={handleDeleteCancel}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          sx: {
            bgcolor: styles.dialogBg,
            border: `1px solid ${theme.palette.divider}`,
            borderRadius: 2,
            boxShadow: 'none',
            p: 0.5,
          },
        }}
      >
        <DialogTitle
          sx={{
            fontWeight: 700,
            letterSpacing: '-0.02em',
            color: 'text.primary',
            pb: 1,
          }}
        >
          Delete policy
        </DialogTitle>
        <DialogContent sx={{ pt: 0 }}>
          <Typography
            variant="body2"
            sx={{
              color: 'text.secondary',
              lineHeight: 1.65,
            }}
          >
            Are you sure you want to delete the policy{' '}
            <Box component="span" sx={{ color: 'text.primary', fontWeight: 600 }}>
              &quot;{policyToDelete?.name}&quot;
            </Box>
            ? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2.5, pt: 0, gap: 1 }}>
          <Button
            onClick={handleDeleteCancel}
            sx={{
              textTransform: 'none',
              color: 'text.secondary',
              '&:hover': { bgcolor: styles.hoverBg },
            }}
          >
            Cancel
          </Button>
          <Button
            onClick={handleDeleteConfirm}
            variant="contained"
            sx={{
              textTransform: 'none',
              fontWeight: 600,
              bgcolor: alpha(theme.palette.error.main, 0.9),
              color: '#fff',
              boxShadow: `0 4px 16px ${alpha(theme.palette.error.main, 0.35)}`,
              '&:hover': {
                bgcolor: theme.palette.error.main,
                boxShadow: `0 6px 20px ${alpha(theme.palette.error.main, 0.45)}`,
              },
            }}
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default PolicyList;
