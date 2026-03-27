import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { alpha, useTheme } from '@mui/material/styles';
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
} from '@mui/material';
import {
  Search as SearchIcon,
  Visibility as VisibilityIcon,
  FiberManualRecord as DotIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import agentsApi from '@/api/agents';
import { Agent } from '@/types';
import { useAppStyles } from '@/hooks/useAppStyles';
import { utc } from '@/utils/date';

const AgentList: React.FC = () => {
  const navigate = useNavigate();
  const theme = useTheme();
  const styles = useAppStyles();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive' | 'suspended'>('all');
  const [searchDebounce, setSearchDebounce] = useState('');

  const getStatusDotColor = (status: string): string => {
    switch (status) {
      case 'active':
        return theme.palette.success.main;
      case 'inactive':
        return theme.palette.text.secondary;
      case 'suspended':
        return theme.palette.error.main;
      default:
        return theme.palette.text.secondary;
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      setSearchDebounce(search);
      setPage(0);
    }, 500);

    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    fetchAgents();
  }, [page, rowsPerPage, searchDebounce, statusFilter]);

  const fetchAgents = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await agentsApi.listAgents({
        page: page + 1,
        page_size: rowsPerPage,
        search: searchDebounce || undefined,
        status_filter: statusFilter === 'all' ? undefined : statusFilter,
      });
      setAgents(response.agents);
      setTotal(response.total);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch agents');
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

  const handleViewAgent = (agentId: string) => {
    navigate(`/agents/${agentId}`);
  };

  const renderStatus = (status: string) => (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
      <DotIcon sx={{ fontSize: 8, color: getStatusDotColor(status) }} />
      <Typography
        component="span"
        variant="body2"
        sx={{
          fontSize: '0.8rem',
          fontWeight: 500,
          color: 'text.primary',
          letterSpacing: '0.02em',
        }}
      >
        {status.toUpperCase()}
      </Typography>
    </Box>
  );

  const tableCellSx = {
    fontSize: '0.8rem',
    borderColor: theme.palette.divider,
    color: 'text.primary',
  };
  const headCellSx = {
    ...tableCellSx,
    fontWeight: 600,
    color: 'text.secondary',
    bgcolor: styles.surfaceBg,
    whiteSpace: 'nowrap' as const,
  };

  const primaryMain = theme.palette.primary.main;

  return (
    <Box sx={{ bgcolor: 'background.default', minHeight: '100%', px: 0, pt: 0, pb: 4 }}>
      <Box sx={{ mb: 3 }}>
        <Typography
          variant="h4"
          sx={{
            fontWeight: 700,
            letterSpacing: '-0.02em',
            color: 'text.primary',
          }}
        >
          AI Agents
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          Search, filter, and open agent details from the table below.
        </Typography>
      </Box>

      <Paper
        elevation={0}
        sx={{
          p: 2,
          mb: 2,
          bgcolor: 'background.paper',
          border: `1px solid ${theme.palette.divider}`,
          borderRadius: 2,
        }}
      >
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
          <TextField
            size="small"
            placeholder="Search agents..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            sx={{
              flex: 1,
              minWidth: 220,
              '& .MuiOutlinedInput-root': { fontSize: '0.8125rem', bgcolor: styles.inputBg },
            }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                </InputAdornment>
              ),
            }}
          />
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel id="agent-status-filter">Status</InputLabel>
            <Select
              labelId="agent-status-filter"
              value={statusFilter}
              label="Status"
              onChange={(e) => {
                setStatusFilter(e.target.value as 'all' | 'active' | 'inactive' | 'suspended');
                setPage(0);
              }}
              sx={{ fontSize: '0.8125rem', bgcolor: styles.inputBg }}
            >
              <MenuItem value="all" sx={{ fontSize: '0.8125rem' }}>
                All
              </MenuItem>
              <MenuItem value="active" sx={{ fontSize: '0.8125rem' }}>
                Active
              </MenuItem>
              <MenuItem value="inactive" sx={{ fontSize: '0.8125rem' }}>
                Inactive
              </MenuItem>
              <MenuItem value="suspended" sx={{ fontSize: '0.8125rem' }}>
                Suspended
              </MenuItem>
            </Select>
          </FormControl>
        </Box>
      </Paper>

      {error && (
        <Alert
          severity="error"
          sx={{
            mb: 2,
            bgcolor: alpha(theme.palette.error.main, 0.12),
            color: 'text.primary',
            border: `1px solid ${alpha(theme.palette.error.main, 0.25)}`,
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
          border: `1px solid ${theme.palette.divider}`,
          borderRadius: 2,
          overflow: 'hidden',
        }}
      >
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell sx={headCellSx}>Agent ID</TableCell>
              <TableCell sx={headCellSx}>Name</TableCell>
              <TableCell sx={headCellSx}>Status</TableCell>
              <TableCell sx={headCellSx}>Systems Accessed</TableCell>
              <TableCell sx={headCellSx}>Last Active</TableCell>
              <TableCell sx={headCellSx}>Created</TableCell>
              <TableCell align="right" sx={headCellSx}>
                Actions
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ ...tableCellSx, py: 8, border: 0 }}>
                  <CircularProgress size={36} sx={{ color: 'primary.main' }} />
                </TableCell>
              </TableRow>
            ) : agents.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ ...tableCellSx, py: 8, border: 0 }}>
                  <Typography color="text.secondary" sx={{ fontSize: '0.875rem' }}>
                    {searchDebounce || statusFilter !== 'all'
                      ? 'No agents found'
                      : 'No agents registered yet'}
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              agents.map((agent) => (
                <TableRow
                  key={agent.id}
                  hover
                  sx={{
                    cursor: 'pointer',
                    '&:hover': { bgcolor: styles.hoverBg },
                    '& td': { borderColor: theme.palette.divider },
                  }}
                  onClick={() => handleViewAgent(agent.agent_id || agent.id)}
                >
                  <TableCell sx={{ ...tableCellSx, fontFamily: styles.mono, fontSize: '0.8rem' }}>
                    {agent.agent_id || agent.id}
                  </TableCell>
                  <TableCell sx={tableCellSx}>
                    <Typography sx={{ fontSize: '0.8rem', fontWeight: 500 }}>{agent.name}</Typography>
                    {agent.description && (
                      <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.25 }}>
                        {agent.description}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell sx={tableCellSx}>{renderStatus(agent.status)}</TableCell>
                  <TableCell sx={tableCellSx}>
                    {agent.systems_accessed && agent.systems_accessed.length > 0 ? (
                      <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                        {agent.systems_accessed.slice(0, 3).map((system, idx) => (
                          <Chip
                            key={idx}
                            label={system}
                            size="small"
                            variant="outlined"
                            sx={{
                              height: 22,
                              fontSize: '0.7rem',
                              fontFamily: styles.mono,
                              borderColor: theme.palette.divider,
                              color: 'text.secondary',
                              bgcolor: styles.surfaceBg,
                              '& .MuiChip-label': { px: 1 },
                            }}
                          />
                        ))}
                        {agent.systems_accessed.length > 3 && (
                          <Chip
                            label={`+${agent.systems_accessed.length - 3} more`}
                            size="small"
                            variant="outlined"
                            sx={{
                              height: 22,
                              fontSize: '0.7rem',
                              borderColor: alpha(primaryMain, 0.35),
                              color: primaryMain,
                              bgcolor: alpha(primaryMain, 0.08),
                              '& .MuiChip-label': { px: 1 },
                            }}
                          />
                        )}
                      </Box>
                    ) : (
                      <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                        None
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell sx={tableCellSx}>
                    {agent.last_active ? (
                      <Typography sx={{ fontSize: '0.8rem' }}>
                        {format(utc(agent.last_active), 'MMM dd, yyyy HH:mm')}
                      </Typography>
                    ) : (
                      <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                        Never
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell sx={tableCellSx}>
                    <Typography sx={{ fontSize: '0.8rem' }}>
                      {format(utc(agent.created_at), 'MMM dd, yyyy')}
                    </Typography>
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={tableCellSx}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Tooltip title="View Details">
                      <IconButton
                        size="small"
                        onClick={() => handleViewAgent(agent.agent_id || agent.id)}
                        sx={{
                          color: 'text.secondary',
                          '&:hover': {
                            color: primaryMain,
                            bgcolor: alpha(primaryMain, 0.12),
                          },
                        }}
                      >
                        <VisibilityIcon sx={{ fontSize: 18 }} />
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
            borderTop: `1px solid ${theme.palette.divider}`,
            color: 'text.secondary',
            '& .MuiTablePagination-selectLabel, & .MuiTablePagination-displayedRows': {
              fontSize: '0.8125rem',
            },
            '& .MuiIconButton-root': { color: 'text.secondary' },
            '& .MuiIconButton-root:hover': {
              color: primaryMain,
              bgcolor: alpha(primaryMain, 0.08),
            },
            '& .MuiSelect-icon': { color: 'text.secondary' },
          }}
        />
      </TableContainer>
    </Box>
  );
};

export default AgentList;
