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
  Button,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  alpha,
} from '@mui/material';
import {
  Search as SearchIcon,
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  VpnKey as KeyIcon,
  FiberManualRecord as DotIcon,
} from '@mui/icons-material';
import { useTheme } from '@mui/material/styles';
import { format } from 'date-fns';
import usersApi, { UserResponse, UserCreateRequest, UserUpdateRequest } from '@/api/users';

const ROLE_COLORS: Record<string, string> = {
  admin: '#ef4444',
  analyst: '#f59e0b',
  viewer: '#3b82f6',
};

const Users: React.FC = () => {
  const theme = useTheme();
  const [users, setUsers] = useState<UserResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('all');
  const [searchDebounce, setSearchDebounce] = useState('');

  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [passwordOpen, setPasswordOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<UserResponse | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    full_name: '',
    role: 'viewer',
  });

  const [passwordData, setPasswordData] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  });

  useEffect(() => {
    const timer = setTimeout(() => {
      setSearchDebounce(search);
      setPage(0);
    }, 400);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    fetchUsers();
  }, [page, rowsPerPage, searchDebounce, roleFilter]);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await usersApi.listUsers({
        page: page + 1,
        page_size: rowsPerPage,
        search: searchDebounce || undefined,
        role_filter: roleFilter === 'all' ? undefined : roleFilter,
      });
      setUsers(response.users);
      setTotal(response.total);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch users');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    try {
      setSaving(true);
      setFormError(null);
      const data: UserCreateRequest = {
        username: formData.username,
        email: formData.email,
        password: formData.password,
        role: formData.role,
        full_name: formData.full_name || undefined,
      };
      await usersApi.createUser(data);
      setCreateOpen(false);
      resetForm();
      fetchUsers();
    } catch (err: any) {
      setFormError(err.response?.data?.detail || 'Failed to create user');
    } finally {
      setSaving(false);
    }
  };

  const handleUpdate = async () => {
    if (!selectedUser) return;
    try {
      setSaving(true);
      setFormError(null);
      const data: UserUpdateRequest = {};
      if (formData.email !== selectedUser.email) data.email = formData.email;
      if (formData.full_name !== (selectedUser.full_name || '')) data.full_name = formData.full_name;
      if (formData.role !== selectedUser.role) data.role = formData.role;
      await usersApi.updateUser(selectedUser.id, data);
      setEditOpen(false);
      resetForm();
      fetchUsers();
    } catch (err: any) {
      setFormError(err.response?.data?.detail || 'Failed to update user');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedUser) return;
    try {
      setSaving(true);
      setFormError(null);
      await usersApi.deleteUser(selectedUser.id);
      setDeleteOpen(false);
      setSelectedUser(null);
      fetchUsers();
    } catch (err: any) {
      setFormError(err.response?.data?.detail || 'Failed to delete user');
    } finally {
      setSaving(false);
    }
  };

  const handleToggleActive = async (user: UserResponse) => {
    try {
      await usersApi.updateUser(user.id, { is_active: !user.is_active });
      fetchUsers();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update user status');
    }
  };

  const handleChangePassword = async () => {
    if (!selectedUser) return;
    if (passwordData.new_password !== passwordData.confirm_password) {
      setFormError('Passwords do not match');
      return;
    }
    try {
      setSaving(true);
      setFormError(null);
      await usersApi.updateUser(selectedUser.id, { password: passwordData.new_password });
      setPasswordOpen(false);
      setPasswordData({ current_password: '', new_password: '', confirm_password: '' });
    } catch (err: any) {
      setFormError(err.response?.data?.detail || 'Failed to change password');
    } finally {
      setSaving(false);
    }
  };

  const resetForm = () => {
    setFormData({ username: '', email: '', password: '', full_name: '', role: 'viewer' });
    setFormError(null);
  };

  const openEdit = (user: UserResponse) => {
    setSelectedUser(user);
    setFormData({
      username: user.username,
      email: user.email,
      password: '',
      full_name: user.full_name || '',
      role: user.role,
    });
    setFormError(null);
    setEditOpen(true);
  };

  const openDelete = (user: UserResponse) => {
    setSelectedUser(user);
    setFormError(null);
    setDeleteOpen(true);
  };

  const openPassword = (user: UserResponse) => {
    setSelectedUser(user);
    setPasswordData({ current_password: '', new_password: '', confirm_password: '' });
    setFormError(null);
    setPasswordOpen(true);
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700, letterSpacing: '-0.02em' }}>
            Users
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5 }}>
            Manage platform users and roles
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => { resetForm(); setCreateOpen(true); }}
          sx={{ background: `linear-gradient(135deg, ${theme.palette.primary.main} 0%, ${theme.palette.primary.dark} 100%)` }}
        >
          Add user
        </Button>
      </Box>

      <Paper sx={{ p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <TextField
            placeholder="Search users..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            size="small"
            sx={{ flex: 1, minWidth: 250 }}
            InputProps={{
              startAdornment: <InputAdornment position="start"><SearchIcon sx={{ fontSize: 18, color: 'text.secondary' }} /></InputAdornment>,
            }}
          />
          <FormControl size="small" sx={{ minWidth: 130 }}>
            <InputLabel>Role</InputLabel>
            <Select value={roleFilter} label="Role" onChange={(e) => { setRoleFilter(e.target.value); setPage(0); }}>
              <MenuItem value="all">All roles</MenuItem>
              <MenuItem value="admin">Admin</MenuItem>
              <MenuItem value="analyst">Analyst</MenuItem>
              <MenuItem value="viewer">Viewer</MenuItem>
            </Select>
          </FormControl>
        </Box>
      </Paper>

      {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>User</TableCell>
              <TableCell>Role</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Created</TableCell>
              <TableCell>Last login</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={6} align="center" sx={{ py: 8 }}>
                  <CircularProgress size={32} sx={{ color: 'primary.main' }} />
                </TableCell>
              </TableRow>
            ) : users.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} align="center" sx={{ py: 8 }}>
                  <Typography color="text.secondary">No users found</Typography>
                </TableCell>
              </TableRow>
            ) : (
              users.map((user) => {
                const roleColor = ROLE_COLORS[user.role] || '#64748b';
                return (
                  <TableRow key={user.id}>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                        <Box
                          sx={{
                            width: 34,
                            height: 34,
                            borderRadius: '8px',
                            bgcolor: alpha(roleColor, 0.1),
                            color: roleColor,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontWeight: 700,
                            fontSize: '0.8rem',
                            flexShrink: 0,
                          }}
                        >
                          {user.username.charAt(0).toUpperCase()}
                        </Box>
                        <Box>
                          <Typography variant="body2" sx={{ fontWeight: 600 }}>
                            {user.full_name || user.username}
                          </Typography>
                          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                            {user.email}
                          </Typography>
                        </Box>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={user.role}
                        size="small"
                        sx={{
                          bgcolor: alpha(roleColor, 0.1),
                          color: roleColor,
                          border: `1px solid ${alpha(roleColor, 0.2)}`,
                          fontWeight: 600,
                          textTransform: 'uppercase',
                          fontSize: '0.65rem',
                          letterSpacing: '0.05em',
                          minWidth: 72,
                          justifyContent: 'center',
                        }}
                      />
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <DotIcon sx={{ fontSize: 8, color: user.is_active ? 'success.main' : 'text.secondary' }} />
                        <Typography variant="body2" sx={{ color: user.is_active ? 'success.main' : 'text.secondary', fontSize: '0.8rem' }}>
                          {user.is_active ? 'Active' : 'Inactive'}
                        </Typography>
                        <Switch
                          checked={user.is_active}
                          onChange={() => handleToggleActive(user)}
                          size="small"
                          sx={{ ml: 0.5 }}
                        />
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{ fontSize: '0.8rem' }}>
                        {format(new Date(user.created_at), 'MMM dd, yyyy')}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{ fontSize: '0.8rem', color: user.last_login ? 'text.primary' : 'text.secondary' }}>
                        {user.last_login ? format(new Date(user.last_login), 'MMM dd, yyyy HH:mm') : 'Never'}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 0.5 }}>
                        <Tooltip title="Edit user">
                          <IconButton size="small" onClick={() => openEdit(user)}><EditIcon sx={{ fontSize: 16 }} /></IconButton>
                        </Tooltip>
                        <Tooltip title="Reset password">
                          <IconButton size="small" onClick={() => openPassword(user)}><KeyIcon sx={{ fontSize: 16 }} /></IconButton>
                        </Tooltip>
                        <Tooltip title="Delete user">
                          <IconButton size="small" onClick={() => openDelete(user)} sx={{ '&:hover': { color: 'error.main' } }}>
                            <DeleteIcon sx={{ fontSize: 16 }} />
                          </IconButton>
                        </Tooltip>
                      </Box>
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
          onPageChange={(_, p) => setPage(p)}
          rowsPerPage={rowsPerPage}
          onRowsPerPageChange={(e) => { setRowsPerPage(parseInt(e.target.value, 10)); setPage(0); }}
          rowsPerPageOptions={[10, 25, 50]}
        />
      </TableContainer>

      {/* Create User Dialog */}
      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 600, pb: 1 }}>Create user</DialogTitle>
        <DialogContent>
          {formError && <Alert severity="error" sx={{ mb: 2, mt: 1 }}>{formError}</Alert>}
          <TextField fullWidth label="Username" size="small" sx={{ mt: 1, mb: 2 }}
            value={formData.username} onChange={(e) => setFormData({ ...formData, username: e.target.value })} required />
          <TextField fullWidth label="Email" size="small" sx={{ mb: 2 }}
            value={formData.email} onChange={(e) => setFormData({ ...formData, email: e.target.value })} required />
          <TextField fullWidth label="Full name" size="small" sx={{ mb: 2 }}
            value={formData.full_name} onChange={(e) => setFormData({ ...formData, full_name: e.target.value })} />
          <TextField fullWidth label="Password" type="password" size="small" sx={{ mb: 2 }}
            value={formData.password} onChange={(e) => setFormData({ ...formData, password: e.target.value })} required />
          <FormControl fullWidth size="small">
            <InputLabel>Role</InputLabel>
            <Select value={formData.role} label="Role" onChange={(e) => setFormData({ ...formData, role: e.target.value })}>
              <MenuItem value="admin">Admin</MenuItem>
              <MenuItem value="analyst">Analyst</MenuItem>
              <MenuItem value="viewer">Viewer</MenuItem>
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setCreateOpen(false)} variant="outlined" size="small">Cancel</Button>
          <Button onClick={handleCreate} variant="contained" size="small" disabled={saving || !formData.username || !formData.email || !formData.password}>
            {saving ? 'Creating...' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Edit User Dialog */}
      <Dialog open={editOpen} onClose={() => setEditOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 600, pb: 1 }}>Edit user</DialogTitle>
        <DialogContent>
          {formError && <Alert severity="error" sx={{ mb: 2, mt: 1 }}>{formError}</Alert>}
          <TextField fullWidth label="Username" size="small" sx={{ mt: 1, mb: 2 }} value={formData.username} disabled />
          <TextField fullWidth label="Email" size="small" sx={{ mb: 2 }}
            value={formData.email} onChange={(e) => setFormData({ ...formData, email: e.target.value })} />
          <TextField fullWidth label="Full name" size="small" sx={{ mb: 2 }}
            value={formData.full_name} onChange={(e) => setFormData({ ...formData, full_name: e.target.value })} />
          <FormControl fullWidth size="small">
            <InputLabel>Role</InputLabel>
            <Select value={formData.role} label="Role" onChange={(e) => setFormData({ ...formData, role: e.target.value })}>
              <MenuItem value="admin">Admin</MenuItem>
              <MenuItem value="analyst">Analyst</MenuItem>
              <MenuItem value="viewer">Viewer</MenuItem>
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setEditOpen(false)} variant="outlined" size="small">Cancel</Button>
          <Button onClick={handleUpdate} variant="contained" size="small" disabled={saving}>
            {saving ? 'Saving...' : 'Save changes'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete User Dialog */}
      <Dialog open={deleteOpen} onClose={() => setDeleteOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ fontWeight: 600, pb: 1 }}>Delete user</DialogTitle>
        <DialogContent>
          {formError && <Alert severity="error" sx={{ mb: 2 }}>{formError}</Alert>}
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            Are you sure you want to delete <strong style={{ color: theme.palette.text.primary }}>{selectedUser?.username}</strong>? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setDeleteOpen(false)} variant="outlined" size="small">Cancel</Button>
          <Button onClick={handleDelete} variant="contained" color="error" size="small" disabled={saving}>
            {saving ? 'Deleting...' : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Reset Password Dialog */}
      <Dialog open={passwordOpen} onClose={() => setPasswordOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 600, pb: 1 }}>Reset password</DialogTitle>
        <DialogContent>
          {formError && <Alert severity="error" sx={{ mb: 2, mt: 1 }}>{formError}</Alert>}
          <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2, mt: 1 }}>
            Set a new password for <strong style={{ color: theme.palette.text.primary }}>{selectedUser?.username}</strong>
          </Typography>
          <TextField fullWidth label="New password" type="password" size="small" sx={{ mb: 2 }}
            value={passwordData.new_password} onChange={(e) => setPasswordData({ ...passwordData, new_password: e.target.value })} />
          <TextField fullWidth label="Confirm password" type="password" size="small"
            value={passwordData.confirm_password} onChange={(e) => setPasswordData({ ...passwordData, confirm_password: e.target.value })} />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setPasswordOpen(false)} variant="outlined" size="small">Cancel</Button>
          <Button onClick={handleChangePassword} variant="contained" size="small"
            disabled={saving || !passwordData.new_password || !passwordData.confirm_password}>
            {saving ? 'Saving...' : 'Reset password'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Users;
