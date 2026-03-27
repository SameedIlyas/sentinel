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
  IconButton,
  Tooltip,
  Alert as MuiAlert,
  CircularProgress,
  Grid,
  Divider,
  Card,
  CardContent,
  useTheme,
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Notifications as NotificationsIcon,
  Send as SendIcon,
  FiberManualRecord,
} from '@mui/icons-material';
import { alpha } from '@mui/material/styles';
import alertsApi, { AlertRule, AlertRuleCreate, SlackConfig } from '@/api/alerts';
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

function RuleStatusDot({ enabled }: { enabled: boolean }) {
  const theme = useTheme();
  const color = enabled ? theme.palette.success.main : alpha(theme.palette.text.primary, 0.35);
  const label = enabled ? 'Enabled' : 'Disabled';
  return (
    <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.75 }}>
      <FiberManualRecord sx={{ fontSize: 10, color }} />
      <Typography variant="body2" sx={{ color: 'text.primary', fontWeight: 500, fontSize: '0.8125rem' }}>
        {label}
      </Typography>
    </Box>
  );
}

const AlertRules: React.FC = () => {
  const styles = useAppStyles();
  const { theme } = styles;
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [slackWebhook, setSlackWebhook] = useState('');
  const [slackChannel, setSlackChannel] = useState('');
  const [slackEnabled, setSlackEnabled] = useState(true);
  const [testingWebhook, setTestingWebhook] = useState(false);

  const [ruleDialogOpen, setRuleDialogOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<AlertRule | null>(null);
  const [ruleForm, setRuleForm] = useState<AlertRuleCreate>({
    alert_type: '',
    severity: 'medium',
    enabled: true,
  });

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

  const textFieldSx = useMemo(
    () => ({
      '& .MuiOutlinedInput-root': {
        color: 'text.primary',
        bgcolor: styles.inputBg,
        '& fieldset': { borderColor: theme.palette.divider },
        '&:hover fieldset': {
          borderColor: alpha(theme.palette.text.primary, theme.palette.mode === 'dark' ? 0.12 : 0.2),
        },
        '&.Mui-focused fieldset': { borderColor: alpha(theme.palette.primary.main, 0.5) },
      },
      '& .MuiInputLabel-root': { color: 'text.secondary' },
      '& .MuiFormHelperText-root': { color: alpha(theme.palette.text.primary, 0.4) },
    }),
    [styles.inputBg, theme.palette.divider, theme.palette.text.primary, theme.palette.mode, theme.palette.primary.main]
  );

  const selectFieldSx = useMemo(
    () => ({
      color: 'text.primary',
      bgcolor: styles.inputBg,
      '& .MuiOutlinedInput-notchedOutline': { borderColor: theme.palette.divider },
      '&:hover .MuiOutlinedInput-notchedOutline': {
        borderColor: alpha(theme.palette.text.primary, theme.palette.mode === 'dark' ? 0.12 : 0.2),
      },
      '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
        borderColor: alpha(theme.palette.primary.main, 0.5),
      },
    }),
    [styles.inputBg, theme.palette.divider, theme.palette.text.primary, theme.palette.mode, theme.palette.primary.main]
  );

  useEffect(() => {
    fetchRules();
  }, []);

  const fetchRules = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await alertsApi.listAlertRules();
      setRules(data);
    } catch (err: unknown) {
      const detail =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      setError(detail || 'Failed to fetch alert rules');
    } finally {
      setLoading(false);
    }
  };

  const handleOpenRuleDialog = (rule?: AlertRule) => {
    if (rule) {
      setEditingRule(rule);
      setRuleForm({
        policy_type: rule.policy_type as AlertRuleCreate['policy_type'],
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
    } catch (err: unknown) {
      const detail =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      setError(detail || 'Failed to save alert rule');
    }
  };

  const handleSaveSlackConfig = async () => {
    try {
      setError(null);
      await alertsApi.configureAlerts({
        global_slack_webhook: slackWebhook,
      });
      setSuccess('Slack configuration saved successfully');
    } catch (err: unknown) {
      const detail =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      setError(detail || 'Failed to save Slack configuration');
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
    } catch (err: unknown) {
      const detail =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      setError(detail || 'Failed to send test message');
    } finally {
      setTestingWebhook(false);
    }
  };

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

  const primarySoftButton = {
    textTransform: 'none' as const,
    fontWeight: 600,
    bgcolor: alpha(primaryMain, 0.9),
    color: theme.palette.primary.contrastText,
    boxShadow: 'none',
    '&:hover': {
      bgcolor: primaryMain,
      boxShadow: `0 0 0 1px ${alpha(primaryMain, 0.5)}`,
    },
    '&:disabled': {
      bgcolor: alpha(theme.palette.action.disabledBackground, 0.5),
      color: theme.palette.action.disabled,
    },
  };

  const dialogPaperSx = {
    bgcolor: styles.dialogBg,
    backgroundImage: 'none',
    border: `1px solid ${theme.palette.divider}`,
    color: 'text.primary',
  };

  const iconBtnSx = {
    color: alpha(theme.palette.text.primary, 0.5),
    '&:hover': { color: primaryMain, bgcolor: alpha(primaryMain, 0.1) },
  };

  return (
    <Box>
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
            variant="h5"
            sx={{ fontWeight: 700, letterSpacing: '-0.02em', color: 'text.primary' }}
          >
            Alert configuration
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5, maxWidth: 480 }}>
            Connect Slack and define which events raise alerts and at what severity.
          </Typography>
        </Box>
        <Button
          variant="outlined"
          size="medium"
          startIcon={<AddIcon />}
          onClick={() => handleOpenRuleDialog()}
          sx={subtleOutlinedButton}
        >
          Add alert rule
        </Button>
      </Box>

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

      {success && (
        <MuiAlert
          severity="success"
          variant="outlined"
          sx={{
            mb: 3,
            bgcolor: alpha(theme.palette.success.main, 0.08),
            borderColor: alpha(theme.palette.success.main, 0.35),
            color: theme.palette.success.main,
            '& .MuiAlert-icon': { color: theme.palette.success.main },
          }}
          onClose={() => setSuccess(null)}
        >
          {success}
        </MuiAlert>
      )}

      <Card
        elevation={0}
        sx={{
          mb: 3,
          bgcolor: 'background.paper',
          border: `1px solid ${theme.palette.divider}`,
          borderRadius: 2,
        }}
      >
        <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2, gap: 1 }}>
            <NotificationsIcon sx={{ color: primaryMain, fontSize: 22 }} />
            <Typography variant="subtitle1" sx={{ fontWeight: 700, color: 'text.primary' }}>
              Slack integration
            </Typography>
          </Box>
          <Divider sx={{ borderColor: theme.palette.divider, mb: 2 }} />

          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                size="small"
                label="Slack webhook URL"
                value={slackWebhook}
                onChange={(e) => setSlackWebhook(e.target.value)}
                placeholder="https://hooks.slack.com/services/..."
                helperText="Webhook URL for outbound alert notifications"
                sx={textFieldSx}
              />
            </Grid>

            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Channel (optional)"
                value={slackChannel}
                onChange={(e) => setSlackChannel(e.target.value)}
                placeholder="#security-alerts"
                helperText="Override default channel"
                sx={textFieldSx}
              />
            </Grid>

            <Grid item xs={12} md={3} sx={{ display: 'flex', alignItems: 'center' }}>
              <FormControlLabel
                control={
                  <Switch
                    checked={slackEnabled}
                    onChange={(e) => setSlackEnabled(e.target.checked)}
                    sx={{
                      '& .MuiSwitch-switchBase.Mui-checked': { color: primaryMain },
                      '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                        bgcolor: alpha(primaryMain, 0.5),
                      },
                    }}
                  />
                }
                label={<Typography sx={{ color: 'text.primary', fontSize: '0.875rem' }}>Enabled</Typography>}
              />
            </Grid>

            <Grid item xs={12}>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5 }}>
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={
                    testingWebhook ? (
                      <CircularProgress size={14} sx={{ color: 'primary.main' }} />
                    ) : (
                      <SendIcon />
                    )
                  }
                  onClick={handleTestSlackWebhook}
                  disabled={testingWebhook || !slackWebhook}
                  sx={subtleOutlinedButton}
                >
                  Test webhook
                </Button>
                <Button
                  variant="contained"
                  size="small"
                  onClick={handleSaveSlackConfig}
                  disabled={!slackWebhook}
                  sx={primarySoftButton}
                >
                  Save configuration
                </Button>
              </Box>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      <Typography
        variant="overline"
        sx={{ color: 'text.secondary', letterSpacing: '0.08em', display: 'block', mb: 1.5 }}
      >
        Alert rules
      </Typography>

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
              <TableCell>Status</TableCell>
              <TableCell>Alert type</TableCell>
              <TableCell>Policy type</TableCell>
              <TableCell>Severity</TableCell>
              <TableCell>Webhook</TableCell>
              <TableCell>Created</TableCell>
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
            ) : rules.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 8, borderColor: theme.palette.divider }}>
                  <Typography sx={{ color: 'text.secondary' }}>
                    No alert rules configured. Use &quot;Add alert rule&quot; to create one.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              rules.map((rule) => (
                <TableRow
                  key={rule.id}
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
                    <RuleStatusDot enabled={rule.enabled} />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: 'ui-monospace, monospace', fontSize: '0.8rem' }}>
                      {rule.alert_type}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    {rule.policy_type ? (
                      <Box
                        component="span"
                        sx={{
                          display: 'inline-block',
                          px: 1,
                          py: 0.25,
                          borderRadius: 1,
                          fontSize: '0.75rem',
                          color: alpha(theme.palette.text.primary, 0.85),
                          border: `1px solid ${alpha(theme.palette.text.primary, 0.1)}`,
                          bgcolor: styles.inputBg,
                        }}
                      >
                        {rule.policy_type}
                      </Box>
                    ) : (
                      <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                        All
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <SeverityBadge severity={rule.severity} />
                  </TableCell>
                  <TableCell>
                    {rule.slack_webhook_url ? (
                      <Tooltip title={rule.slack_webhook_url}>
                        <Box
                          component="span"
                          sx={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 0.5,
                            px: 1,
                            py: 0.25,
                            borderRadius: 1,
                            fontSize: '0.75rem',
                            color: alpha(theme.palette.text.primary, 0.85),
                            border: `1px solid ${alpha(primaryMain, 0.35)}`,
                            bgcolor: alpha(primaryMain, 0.08),
                          }}
                        >
                          <NotificationsIcon sx={{ fontSize: 14 }} />
                          Custom
                        </Box>
                      </Tooltip>
                    ) : (
                      <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                        Global
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ color: 'text.primary' }}>
                      {utc(rule.created_at).toLocaleDateString()}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title="Edit">
                      <IconButton size="small" onClick={() => handleOpenRuleDialog(rule)} sx={iconBtnSx}>
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

      <Dialog
        open={ruleDialogOpen}
        onClose={handleCloseRuleDialog}
        maxWidth="sm"
        fullWidth
        PaperProps={{ sx: dialogPaperSx }}
      >
        <DialogTitle sx={{ fontWeight: 700, borderBottom: `1px solid ${theme.palette.divider}`, pb: 2 }}>
          {editingRule ? 'Edit alert rule' : 'Create alert rule'}
        </DialogTitle>
        <DialogContent sx={{ pt: 3 }}>
          <Grid container spacing={2}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                size="small"
                label="Alert type"
                value={ruleForm.alert_type}
                onChange={(e) => setRuleForm({ ...ruleForm, alert_type: e.target.value })}
                placeholder="blocked_access, high_transaction, new_agent"
                helperText="Type of event that triggers this alert"
                sx={textFieldSx}
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <FormControl fullWidth size="small">
                <InputLabel sx={{ color: 'text.secondary' }}>Policy type</InputLabel>
                <Select
                  value={ruleForm.policy_type || ''}
                  label="Policy type"
                  onChange={(e) =>
                    setRuleForm({
                      ...ruleForm,
                      policy_type: (e.target.value as AlertRuleCreate['policy_type']) || null,
                    })
                  }
                  MenuProps={selectMenuProps}
                  sx={selectFieldSx}
                >
                  <MenuItem value="">All policies</MenuItem>
                  <MenuItem value="data_access">Data access</MenuItem>
                  <MenuItem value="financial">Financial</MenuItem>
                  <MenuItem value="data_protection">Data protection</MenuItem>
                  <MenuItem value="system_access">System access</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} md={6}>
              <FormControl fullWidth size="small">
                <InputLabel sx={{ color: 'text.secondary' }}>Severity</InputLabel>
                <Select
                  value={ruleForm.severity}
                  label="Severity"
                  onChange={(e) =>
                    setRuleForm({
                      ...ruleForm,
                      severity: e.target.value as AlertRuleCreate['severity'],
                    })
                  }
                  MenuProps={selectMenuProps}
                  sx={selectFieldSx}
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
                size="small"
                label="Slack webhook URL (optional)"
                value={ruleForm.slack_webhook_url || ''}
                onChange={(e) =>
                  setRuleForm({ ...ruleForm, slack_webhook_url: e.target.value || undefined })
                }
                placeholder="Leave empty to use global webhook"
                helperText="Optional: different Slack webhook for this rule"
                sx={textFieldSx}
              />
            </Grid>

            <Grid item xs={12}>
              <FormControlLabel
                control={
                  <Switch
                    checked={ruleForm.enabled}
                    onChange={(e) => setRuleForm({ ...ruleForm, enabled: e.target.checked })}
                    sx={{
                      '& .MuiSwitch-switchBase.Mui-checked': { color: primaryMain },
                      '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                        bgcolor: alpha(primaryMain, 0.5),
                      },
                    }}
                  />
                }
                label={
                  <Typography sx={{ color: 'text.primary', fontSize: '0.875rem' }}>
                    Enable this rule
                  </Typography>
                }
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2, borderTop: `1px solid ${theme.palette.divider}`, pt: 2 }}>
          <Button
            onClick={handleCloseRuleDialog}
            sx={{
              textTransform: 'none',
              color: 'text.secondary',
              '&:hover': { bgcolor: styles.hoverBg },
            }}
          >
            Cancel
          </Button>
          <Button
            variant="outlined"
            size="small"
            onClick={handleSaveRule}
            disabled={!ruleForm.alert_type}
            sx={subtleOutlinedButton}
          >
            {editingRule ? 'Save changes' : 'Create rule'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default AlertRules;
