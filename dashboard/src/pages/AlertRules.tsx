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
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
  Chip,
  IconButton,
  Tooltip,
  Alert as MuiAlert,
  CircularProgress,
  Grid,
  Divider,
  Card,
  CardContent,
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Notifications as NotificationsIcon,
  Send as SendIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
} from '@mui/icons-material';
import alertsApi, { AlertRule, AlertRuleCreate, SlackConfig } from '@/api/alerts';

const AlertRules: React.FC = () => {
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Slack webhook configuration
  const [slackWebhook, setSlackWebhook] = useState('');
  const [slackChannel, setSlackChannel] = useState('');
  const [slackEnabled, setSlackEnabled] = useState(true);
  const [testingWebhook, setTestingWebhook] = useState(false);

  // Rule dialog
  const [ruleDialogOpen, setRuleDialogOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<AlertRule | null>(null);
  const [ruleForm, setRuleForm] = useState<AlertRuleCreate>({
    alert_type: '',
    severity: 'medium',
    enabled: true,
  });

  useEffect(() => {
    fetchRules();
  }, []);

  const fetchRules = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await alertsApi.listAlertRules();
      setRules(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch alert rules');
    } finally {
      setLoading(false);
    }
  };

  const handleOpenRuleDialog = (rule?: AlertRule) => {
    if (rule) {
      setEditingRule(rule);
      setRuleForm({
        policy_type: rule.policy_type as any,
        alert_type: rule.alert_type,
        severity: rule.severity,
        conditions: rule.conditions || undefined,
        slack_webhook_url: rule.slack_webhook_url || undefined,
        enabled: rule.enabled,
      });
    } else {
      setEditingRule(null);
      setRuleForm({
        alert_type: '',
        severity: 'medium',
        enabled: true,
      });
    }
    setRuleDialogOpen(true);
  };

  const handleCloseRuleDialog = () => {
    setRuleDialogOpen(false);
    setEditingRule(null);
  };

  const handleSaveRule = async () => {
    try {
      setError(null);
      await alertsApi.configureAlerts({
        alert_rules: [ruleForm],
      });
      setSuccess('Alert rule created successfully');
      handleCloseRuleDialog();
      fetchRules();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save alert rule');
    }
  };

  const handleSaveSlackConfig = async () => {
    try {
      setError(null);
      await alertsApi.configureAlerts({
        global_slack_webhook: slackWebhook,
      });
      setSuccess('Slack configuration saved successfully');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save Slack configuration');
    }
  };

  const handleTestSlackWebhook = async () => {
    if (!slackWebhook) {
      setError('Please enter a Slack webhook URL');
      return;
    }

    try {
      setTestingWebhook(true);
      setError(null);
      const config: SlackConfig = {
        webhook_url: slackWebhook,
        channel: slackChannel || undefined,
        enabled: slackEnabled,
      };
      const result = await alertsApi.testSlackWebhook(config);
      setSuccess(result.message);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to send test message');
    } finally {
      setTestingWebhook(false);
    }
  };

  const getSeverityColor = (severity: string): 'default' | 'success' | 'warning' | 'error' => {
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

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" sx={{ fontWeight: 'bold' }}>
          Alert Configuration
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => handleOpenRuleDialog()}
        >
          Add Alert Rule
        </Button>
      </Box>

      {error && (
        <MuiAlert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </MuiAlert>
      )}

      {success && (
        <MuiAlert severity="success" sx={{ mb: 3 }} onClose={() => setSuccess(null)}>
          {success}
        </MuiAlert>
      )}

      {/* Slack Configuration */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <NotificationsIcon sx={{ mr: 1, color: 'primary.main' }} />
            <Typography variant="h6">Slack Integration</Typography>
          </Box>
          <Divider sx={{ mb: 2 }} />

          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Slack Webhook URL"
                value={slackWebhook}
                onChange={(e) => setSlackWebhook(e.target.value)}
                placeholder="https://hooks.slack.com/services/..."
                helperText="Enter your Slack webhook URL for sending alerts"
              />
            </Grid>

            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                label="Channel (Optional)"
                value={slackChannel}
                onChange={(e) => setSlackChannel(e.target.value)}
                placeholder="#security-alerts"
                helperText="Override default webhook channel"
              />
            </Grid>

            <Grid item xs={12} md={3}>
              <FormControlLabel
                control={
                  <Switch
                    checked={slackEnabled}
                    onChange={(e) => setSlackEnabled(e.target.checked)}
                  />
                }
                label="Enabled"
              />
            </Grid>

            <Grid item xs={12}>
              <Box sx={{ display: 'flex', gap: 2 }}>
                <Button
                  variant="outlined"
                  startIcon={testingWebhook ? <CircularProgress size={16} /> : <SendIcon />}
                  onClick={handleTestSlackWebhook}
                  disabled={testingWebhook || !slackWebhook}
                >
                  Test Webhook
                </Button>
                <Button
                  variant="contained"
                  onClick={handleSaveSlackConfig}
                  disabled={!slackWebhook}
                >
                  Save Configuration
                </Button>
              </Box>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Alert Rules Table */}
      <Typography variant="h6" sx={{ mb: 2 }}>
        Alert Rules
      </Typography>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Status</TableCell>
              <TableCell>Alert Type</TableCell>
              <TableCell>Policy Type</TableCell>
              <TableCell>Severity</TableCell>
              <TableCell>Webhook</TableCell>
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
            ) : rules.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 8 }}>
                  <Typography color="text.secondary">
                    No alert rules configured. Click "Add Alert Rule" to create one.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              rules.map((rule) => (
                <TableRow key={rule.id} hover>
                  <TableCell>
                    {rule.enabled ? (
                      <Chip
                        icon={<CheckIcon />}
                        label="Enabled"
                        color="success"
                        size="small"
                      />
                    ) : (
                      <Chip
                        icon={<ErrorIcon />}
                        label="Disabled"
                        color="default"
                        size="small"
                      />
                    )}
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                      {rule.alert_type}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    {rule.policy_type ? (
                      <Chip label={rule.policy_type} size="small" variant="outlined" />
                    ) : (
                      <Typography variant="body2" color="text.secondary">
                        All
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={rule.severity.toUpperCase()}
                      color={getSeverityColor(rule.severity)}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    {rule.slack_webhook_url ? (
                      <Tooltip title={rule.slack_webhook_url}>
                        <Chip
                          icon={<NotificationsIcon />}
                          label="Custom"
                          size="small"
                          variant="outlined"
                        />
                      </Tooltip>
                    ) : (
                      <Typography variant="body2" color="text.secondary">
                        Global
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {new Date(rule.created_at).toLocaleDateString()}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title="Edit">
                      <IconButton size="small" onClick={() => handleOpenRuleDialog(rule)}>
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Rule Dialog */}
      <Dialog open={ruleDialogOpen} onClose={handleCloseRuleDialog} maxWidth="sm" fullWidth>
        <DialogTitle>
          {editingRule ? 'Edit Alert Rule' : 'Create Alert Rule'}
        </DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Alert Type"
                value={ruleForm.alert_type}
                onChange={(e) => setRuleForm({ ...ruleForm, alert_type: e.target.value })}
                placeholder="blocked_access, high_transaction, new_agent"
                helperText="Type of event that triggers this alert"
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Policy Type</InputLabel>
                <Select
                  value={ruleForm.policy_type || ''}
                  label="Policy Type"
                  onChange={(e) =>
                    setRuleForm({ ...ruleForm, policy_type: e.target.value as any || null })
                  }
                >
                  <MenuItem value="">All Policies</MenuItem>
                  <MenuItem value="data_access">Data Access</MenuItem>
                  <MenuItem value="financial">Financial</MenuItem>
                  <MenuItem value="data_protection">Data Protection</MenuItem>
                  <MenuItem value="system_access">System Access</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Severity</InputLabel>
                <Select
                  value={ruleForm.severity}
                  label="Severity"
                  onChange={(e) =>
                    setRuleForm({ ...ruleForm, severity: e.target.value as any })
                  }
                >
                  <MenuItem value="low">Low</MenuItem>
                  <MenuItem value="medium">Medium</MenuItem>
                  <MenuItem value="high">High</MenuItem>
                  <MenuItem value="critical">Critical</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Slack Webhook URL (Optional)"
                value={ruleForm.slack_webhook_url || ''}
                onChange={(e) =>
                  setRuleForm({ ...ruleForm, slack_webhook_url: e.target.value || undefined })
                }
                placeholder="Leave empty to use global webhook"
                helperText="Optional: Use a different Slack webhook for this rule"
              />
            </Grid>

            <Grid item xs={12}>
              <FormControlLabel
                control={
                  <Switch
                    checked={ruleForm.enabled}
                    onChange={(e) => setRuleForm({ ...ruleForm, enabled: e.target.checked })}
                  />
                }
                label="Enable this rule"
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseRuleDialog}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleSaveRule}
            disabled={!ruleForm.alert_type}
          >
            {editingRule ? 'Save Changes' : 'Create Rule'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default AlertRules;
