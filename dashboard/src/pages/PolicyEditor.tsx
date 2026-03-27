import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Box,
  Typography,
  TextField,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  Grid,
  Divider,
  IconButton,
  Alert,
  CircularProgress,
  Card,
  CardContent,
  Tabs,
  Tab,
  Autocomplete,
  Switch,
  FormControlLabel,
} from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import {
  ArrowBack as BackIcon,
  Add as AddIcon,
  Delete as DeleteIcon,
  Save as SaveIcon,
} from '@mui/icons-material';
import policiesApi from '@/api/policies';
import { PolicyRule, PolicyCondition, PolicyCreate } from '@/types';
import { useAppStyles } from '@/hooks/useAppStyles';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div hidden={value !== index} {...other}>
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  );
}

const POLICY_TYPES = [
  { value: 'access_control', label: 'Access Control' },
  { value: 'financial', label: 'Financial' },
  { value: 'data_protection', label: 'Data Protection' },
  { value: 'approval', label: 'Approval' },
];

const CONDITION_OPERATORS = [
  { value: 'equals', label: 'Equals' },
  { value: 'not_equals', label: 'Not Equals' },
  { value: 'contains', label: 'Contains' },
  { value: 'not_contains', label: 'Not Contains' },
  { value: 'greater_than', label: 'Greater Than' },
  { value: 'less_than', label: 'Less Than' },
  { value: 'in', label: 'In List' },
  { value: 'not_in', label: 'Not In List' },
];

const POLICY_TEMPLATES = {
  access_control: {
    name: 'Read-Only Database Access',
    description: 'Restricts agent to read-only operations on specified databases',
    policy_type: 'access_control',
    rules: [
      {
        description: 'Block write operations to production database',
        conditions: [
          { field: 'action', operator: 'in', value: ['write', 'update', 'delete'] },
          { field: 'system', operator: 'equals', value: 'production_db' },
        ],
        action: 'block' as const,
      },
    ],
  },
  financial: {
    name: 'Transaction Limit Policy',
    description: 'Requires approval for transactions above threshold',
    policy_type: 'financial',
    rules: [
      {
        description: 'Require approval for transactions > $1000',
        conditions: [
          { field: 'action', operator: 'contains', value: 'payment' },
          { field: 'amount', operator: 'greater_than', value: 1000 },
        ],
        action: 'require_approval' as const,
      },
    ],
  },
  data_protection: {
    name: 'PII Protection Policy',
    description: 'Prevents export of sensitive documents containing PII',
    policy_type: 'data_protection',
    rules: [
      {
        description: 'Block export of documents with PII',
        conditions: [
          { field: 'action', operator: 'contains', value: 'export' },
          { field: 'data_classification', operator: 'equals', value: 'PII' },
        ],
        action: 'block' as const,
      },
    ],
  },
};

function actionChipColor(action: string, fallbackPrimary: string): string {
  if (action === 'allow') return '#22c55e';
  if (action === 'block') return '#ef4444';
  if (action === 'require_approval') return '#f59e0b';
  return fallbackPrimary;
}

const PolicyEditor: React.FC = () => {
  const navigate = useNavigate();
  const { policyId } = useParams<{ policyId: string }>();
  const isEditMode = Boolean(policyId);
  const theme = useTheme();
  const styles = useAppStyles();
  const { dark } = styles;

  const primaryMain = theme.palette.primary.main;

  const darkInputSx = useMemo(
    () => ({
      '& .MuiOutlinedInput-root': {
        color: 'text.primary',
        '& fieldset': { borderColor: theme.palette.divider },
        '&:hover fieldset': {
          borderColor: dark ? 'rgba(255,255,255,0.18)' : 'rgba(0,0,0,0.2)',
        },
        '&.Mui-focused fieldset': {
          borderColor: primaryMain,
          borderWidth: 1,
        },
      },
      '& .MuiInputLabel-root': {
        color: 'text.secondary',
        '&.Mui-focused': { color: primaryMain },
      },
      '& .MuiFormHelperText-root': { color: 'text.secondary' },
    }),
    [theme.palette.divider, dark, primaryMain]
  );

  const selectMenuProps = useMemo(
    () => ({
      PaperProps: {
        sx: {
          bgcolor: styles.dialogBg,
          border: `1px solid ${theme.palette.divider}`,
          '& .MuiMenuItem-root': {
            color: 'text.primary',
            '&:hover': { bgcolor: styles.hoverBg },
            '&.Mui-selected': { bgcolor: alpha(primaryMain, 0.16) },
          },
        },
      },
    }),
    [styles.dialogBg, styles.hoverBg, theme.palette.divider, primaryMain]
  );

  const selectOutlinedSx = useMemo(
    () => ({
      color: 'text.primary',
      '& .MuiOutlinedInput-notchedOutline': {
        borderColor: theme.palette.divider,
      },
      '&:hover .MuiOutlinedInput-notchedOutline': {
        borderColor: dark ? 'rgba(255,255,255,0.18)' : 'rgba(0,0,0,0.2)',
      },
      '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
        borderColor: primaryMain,
      },
    }),
    [theme.palette.divider, dark, primaryMain]
  );

  const surfaceCardSx = useMemo(
    () => ({
      bgcolor: 'background.paper',
      border: `1px solid ${theme.palette.divider}`,
      borderRadius: 2,
      boxShadow: 'none' as const,
    }),
    [theme.palette.divider]
  );

  const ruleCardSx = useMemo(
    () => ({
      bgcolor: dark ? '#0c0c0e' : theme.palette.grey[50],
      border: `1px solid ${theme.palette.divider}`,
      borderRadius: 2,
      boxShadow: 'none' as const,
    }),
    [dark, theme.palette.divider, theme.palette.grey]
  );

  const [loading, setLoading] = useState(isEditMode);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState(0);

  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [policyType, setPolicyType] = useState('access_control');
  const [rules, setRules] = useState<PolicyRule[]>([]);
  const [appliesTo, setAppliesTo] = useState<string[]>(['*']);
  const [enabled, setEnabled] = useState(true);
  const [priority, setPriority] = useState<number>(100);

  const policyPreview = useMemo(
    (): PolicyCreate => ({
      name: name.trim(),
      description: description.trim() || undefined,
      policy_type: policyType,
      rules,
      applies_to: appliesTo,
      enabled,
      priority,
    }),
    [name, description, policyType, rules, appliesTo, enabled, priority]
  );

  useEffect(() => {
    if (isEditMode && policyId) {
      fetchPolicy();
    }
  }, [isEditMode, policyId]);

  const fetchPolicy = async () => {
    try {
      setLoading(true);
      const policy = await policiesApi.getPolicy(policyId!);
      setName(policy.name);
      setDescription(policy.description || '');
      setPolicyType(policy.policy_type);
      setRules(policy.rules);
      setAppliesTo(policy.applies_to);
      setEnabled(policy.enabled);
      setPriority(policy.priority || 100);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load policy');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!name.trim()) {
      setError('Policy name is required');
      return;
    }

    if (rules.length === 0) {
      setError('At least one rule is required');
      return;
    }

    try {
      setSaving(true);
      setError(null);

      const policyData: PolicyCreate = {
        name: name.trim(),
        description: description.trim() || undefined,
        policy_type: policyType,
        rules,
        applies_to: appliesTo,
        enabled,
        priority,
      };

      if (isEditMode && policyId) {
        await policiesApi.updatePolicy(policyId, policyData);
      } else {
        await policiesApi.createPolicy(policyData);
      }

      navigate('/policies');
    } catch (err: any) {
      const errorDetail = err.response?.data?.detail;
      if (typeof errorDetail === 'object' && errorDetail.message) {
        setError(errorDetail.message);
      } else {
        setError(errorDetail || `Failed to ${isEditMode ? 'update' : 'create'} policy`);
      }
    } finally {
      setSaving(false);
    }
  };

  const handleAddRule = () => {
    setRules([
      ...rules,
      {
        description: '',
        conditions: [{ field: '', operator: 'equals', value: '' }],
        action: 'block',
      },
    ]);
  };

  const handleRemoveRule = (index: number) => {
    setRules(rules.filter((_, i) => i !== index));
  };

  const handleRuleChange = (index: number, field: keyof PolicyRule, value: any) => {
    const updatedRules = [...rules];
    updatedRules[index] = { ...updatedRules[index], [field]: value };
    setRules(updatedRules);
  };

  const handleAddCondition = (ruleIndex: number) => {
    const updatedRules = [...rules];
    updatedRules[ruleIndex].conditions.push({ field: '', operator: 'equals', value: '' });
    setRules(updatedRules);
  };

  const handleRemoveCondition = (ruleIndex: number, conditionIndex: number) => {
    const updatedRules = [...rules];
    updatedRules[ruleIndex].conditions = updatedRules[ruleIndex].conditions.filter(
      (_, i) => i !== conditionIndex
    );
    setRules(updatedRules);
  };

  const handleConditionChange = (
    ruleIndex: number,
    conditionIndex: number,
    field: keyof PolicyCondition,
    value: any
  ) => {
    const updatedRules = [...rules];
    updatedRules[ruleIndex].conditions[conditionIndex] = {
      ...updatedRules[ruleIndex].conditions[conditionIndex],
      [field]: value,
    };
    setRules(updatedRules);
  };

  const handleLoadTemplate = (templateKey: keyof typeof POLICY_TEMPLATES) => {
    const template = POLICY_TEMPLATES[templateKey];
    setName(template.name);
    setDescription(template.description);
    setPolicyType(template.policy_type);
    setRules(template.rules);
  };

  if (loading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '60vh',
          bgcolor: 'background.default',
        }}
      >
        <CircularProgress sx={{ color: 'primary.main' }} />
      </Box>
    );
  }

  return (
    <Box sx={{ bgcolor: 'background.default', minHeight: '100%', pb: 4, color: 'text.primary' }}>
      <Box sx={{ display: 'flex', alignItems: 'flex-start', mb: 3, gap: 2 }}>
        <IconButton
          onClick={() => navigate('/policies')}
          sx={{
            mt: 0.5,
            color: 'text.secondary',
            '&:hover': { bgcolor: styles.hoverBg },
          }}
        >
          <BackIcon />
        </IconButton>
        <Box>
          <Typography
            variant="h4"
            sx={{
              fontWeight: 700,
              letterSpacing: '-0.02em',
              color: 'text.primary',
              lineHeight: 1.2,
            }}
          >
            {isEditMode ? 'Edit Policy' : 'Create Policy'}
          </Typography>
          <Typography variant="body2" sx={{ mt: 0.75, color: 'text.secondary', maxWidth: 560 }}>
            {isEditMode
              ? 'Update metadata, rules, and conditions. Changes apply on save.'
              : 'Define name, type, and rules. Use templates for a quick start.'}
          </Typography>
        </Box>
      </Box>

      {error && (
        <Alert
          severity="error"
          onClose={() => setError(null)}
          sx={{
            mb: 3,
            bgcolor: alpha(theme.palette.error.main, 0.12),
            color: theme.palette.error.light,
            border: `1px solid ${alpha(theme.palette.error.main, 0.35)}`,
            '& .MuiAlert-icon': { color: theme.palette.error.main },
          }}
        >
          {error}
        </Alert>
      )}

      <Card sx={surfaceCardSx}>
        <CardContent sx={{ pb: 1 }}>
          <Tabs
            value={activeTab}
            onChange={(_, v) => setActiveTab(v)}
            sx={{
              borderBottom: `1px solid ${theme.palette.divider}`,
              minHeight: 48,
              '& .MuiTabs-indicator': {
                backgroundColor: primaryMain,
                height: 3,
                borderRadius: '3px 3px 0 0',
              },
              '& .MuiTab-root': {
                color: 'text.secondary',
                textTransform: 'none',
                fontWeight: 500,
                fontSize: '0.9375rem',
                '&.Mui-selected': { color: 'text.primary' },
              },
            }}
          >
            <Tab label="Basic Information" />
            <Tab label="Rules" />
            <Tab label="Templates" />
          </Tabs>
        </CardContent>

        {/* Basic Information Tab */}
        <TabPanel value={activeTab} index={0}>
          <Card sx={{ ...surfaceCardSx, mx: 2, mb: 2 }}>
            <CardContent>
              <Grid container spacing={3}>
                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    label="Policy Name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                    placeholder="e.g., Production Database Read-Only Access"
                    sx={darkInputSx}
                  />
                </Grid>

                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    label="Description"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    multiline
                    rows={3}
                    placeholder="Describe what this policy does and when it applies"
                    sx={darkInputSx}
                  />
                </Grid>

                <Grid item xs={12} md={6}>
                  <FormControl fullWidth required sx={darkInputSx}>
                    <InputLabel>Policy Type</InputLabel>
                    <Select
                      value={policyType}
                      label="Policy Type"
                      onChange={(e) => setPolicyType(e.target.value)}
                      MenuProps={selectMenuProps}
                      sx={selectOutlinedSx}
                    >
                      {POLICY_TYPES.map((type) => (
                        <MenuItem key={type.value} value={type.value}>
                          {type.label}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>

                <Grid item xs={12} md={6}>
                  <TextField
                    fullWidth
                    label="Priority"
                    type="number"
                    value={priority}
                    onChange={(e) => setPriority(parseInt(e.target.value) || 0)}
                    helperText="Higher values = higher priority (1-1000)"
                    sx={darkInputSx}
                  />
                </Grid>

                <Grid item xs={12}>
                  <Autocomplete
                    multiple
                    freeSolo
                    options={[]}
                    value={appliesTo}
                    onChange={(_, newValue) => setAppliesTo(newValue)}
                    renderTags={(value, getTagProps) =>
                      value.map((option, index) => (
                        <Chip
                          label={option === '*' ? 'All Agents' : option}
                          {...getTagProps({ index })}
                          sx={{
                            bgcolor: alpha(primaryMain, 0.2),
                            color: 'primary.main',
                            border: `1px solid ${alpha(primaryMain, 0.35)}`,
                            '& .MuiChip-deleteIcon': { color: 'text.secondary' },
                          }}
                        />
                      ))
                    }
                    renderInput={(params) => (
                      <TextField
                        {...params}
                        label="Applies To Agents"
                        placeholder="Enter agent IDs or '*' for all agents"
                        helperText="Type agent ID and press Enter, or use '*' for all agents"
                        sx={darkInputSx}
                      />
                    )}
                  />
                </Grid>

                <Grid item xs={12}>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={enabled}
                        onChange={(e) => setEnabled(e.target.checked)}
                        sx={{
                          '& .MuiSwitch-switchBase.Mui-checked': { color: primaryMain },
                          '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                            bgcolor: alpha(primaryMain, 0.5),
                          },
                        }}
                      />
                    }
                    label="Policy Enabled"
                    sx={{ '& .MuiFormControlLabel-label': { color: 'text.primary' } }}
                  />
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </TabPanel>

        {/* Rules Tab */}
        <TabPanel value={activeTab} index={1}>
          <Card sx={{ ...surfaceCardSx, mx: 2, mb: 2 }}>
            <CardContent>
              <Box sx={{ mb: 2 }}>
                <Button
                  variant="outlined"
                  startIcon={<AddIcon />}
                  onClick={handleAddRule}
                  sx={{
                    borderColor: theme.palette.divider,
                    color: 'text.primary',
                    '&:hover': {
                      borderColor: alpha(primaryMain, 0.5),
                      bgcolor: alpha(primaryMain, 0.08),
                    },
                  }}
                >
                  Add Rule
                </Button>
              </Box>

              {rules.length === 0 ? (
                <Alert
                  severity="info"
                  sx={{
                    bgcolor: alpha(primaryMain, 0.1),
                    color: 'text.primary',
                    border: `1px solid ${alpha(primaryMain, 0.25)}`,
                    '& .MuiAlert-icon': { color: primaryMain },
                  }}
                >
                  No rules defined. Add at least one rule to create the policy.
                </Alert>
              ) : (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                  {rules.map((rule, ruleIndex) => (
                    <Card key={ruleIndex} sx={ruleCardSx}>
                      <CardContent>
                        <Box
                          sx={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            mb: 2,
                            flexWrap: 'wrap',
                            gap: 1,
                          }}
                        >
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                            <Typography variant="h6" sx={{ color: 'text.primary', fontWeight: 600 }}>
                              Rule {ruleIndex + 1}
                            </Typography>
                            <Chip
                              size="small"
                              label={rule.action.replace(/_/g, ' ')}
                              sx={{
                                textTransform: 'capitalize',
                                bgcolor: alpha(actionChipColor(rule.action, primaryMain), 0.18),
                                color: actionChipColor(rule.action, primaryMain),
                                border: `1px solid ${alpha(actionChipColor(rule.action, primaryMain), 0.35)}`,
                                fontWeight: 500,
                              }}
                            />
                          </Box>
                          <IconButton
                            size="small"
                            onClick={() => handleRemoveRule(ruleIndex)}
                            sx={{
                              color: alpha(theme.palette.error.main, 0.9),
                              '&:hover': { bgcolor: alpha(theme.palette.error.main, 0.12) },
                            }}
                          >
                            <DeleteIcon />
                          </IconButton>
                        </Box>

                        <Grid container spacing={2}>
                          <Grid item xs={12}>
                            <TextField
                              fullWidth
                              label="Rule Description"
                              value={rule.description || ''}
                              onChange={(e) =>
                                handleRuleChange(ruleIndex, 'description', e.target.value)
                              }
                              placeholder="e.g., Block write operations to production database"
                              sx={darkInputSx}
                            />
                          </Grid>

                          <Grid item xs={12}>
                            <FormControl fullWidth sx={darkInputSx}>
                              <InputLabel>Action</InputLabel>
                              <Select
                                value={rule.action}
                                label="Action"
                                onChange={(e) => handleRuleChange(ruleIndex, 'action', e.target.value)}
                                MenuProps={selectMenuProps}
                                sx={selectOutlinedSx}
                              >
                                <MenuItem value="allow">Allow</MenuItem>
                                <MenuItem value="block">Block</MenuItem>
                                <MenuItem value="require_approval">Require Approval</MenuItem>
                              </Select>
                            </FormControl>
                          </Grid>

                          <Grid item xs={12}>
                            <Divider
                              sx={{
                                my: 2,
                                borderColor: theme.palette.divider,
                                '&::before, &::after': { borderColor: theme.palette.divider },
                                color: 'text.secondary',
                              }}
                            >
                              Conditions
                            </Divider>

                            {rule.conditions.map((condition, conditionIndex) => (
                              <Box
                                key={conditionIndex}
                                sx={{
                                  display: 'flex',
                                  flexWrap: 'wrap',
                                  gap: 1,
                                  mb: 2,
                                  alignItems: 'flex-start',
                                  p: 2,
                                  borderRadius: 1,
                                  bgcolor: alpha(primaryMain, 0.06),
                                  border: `1px solid ${alpha(primaryMain, 0.14)}`,
                                }}
                              >
                                <Chip
                                  size="small"
                                  label={`Condition ${conditionIndex + 1}`}
                                  sx={{
                                    width: '100%',
                                    maxWidth: 'fit-content',
                                    mb: 0.5,
                                    bgcolor: alpha(primaryMain, 0.2),
                                    color: 'primary.main',
                                    border: `1px solid ${alpha(primaryMain, 0.3)}`,
                                    fontWeight: 600,
                                  }}
                                />
                                <TextField
                                  label="Field"
                                  value={condition.field}
                                  onChange={(e) =>
                                    handleConditionChange(
                                      ruleIndex,
                                      conditionIndex,
                                      'field',
                                      e.target.value
                                    )
                                  }
                                  sx={{ flex: '1 1 140px', minWidth: 120, ...darkInputSx }}
                                  placeholder="e.g., action, system, amount"
                                />

                                <FormControl sx={{ flex: '1 1 140px', minWidth: 120, ...darkInputSx }}>
                                  <InputLabel>Operator</InputLabel>
                                  <Select
                                    value={condition.operator}
                                    label="Operator"
                                    onChange={(e) =>
                                      handleConditionChange(
                                        ruleIndex,
                                        conditionIndex,
                                        'operator',
                                        e.target.value
                                      )
                                    }
                                    MenuProps={selectMenuProps}
                                    sx={selectOutlinedSx}
                                  >
                                    {CONDITION_OPERATORS.map((op) => (
                                      <MenuItem key={op.value} value={op.value}>
                                        {op.label}
                                      </MenuItem>
                                    ))}
                                  </Select>
                                </FormControl>

                                <TextField
                                  label="Value"
                                  value={condition.value}
                                  onChange={(e) =>
                                    handleConditionChange(
                                      ruleIndex,
                                      conditionIndex,
                                      'value',
                                      e.target.value
                                    )
                                  }
                                  sx={{ flex: '1 1 140px', minWidth: 120, ...darkInputSx }}
                                  placeholder="e.g., write, production_db, 1000"
                                />

                                <IconButton
                                  onClick={() => handleRemoveCondition(ruleIndex, conditionIndex)}
                                  disabled={rule.conditions.length === 1}
                                  sx={{
                                    color: alpha(theme.palette.error.main, 0.85),
                                    '&:hover': { bgcolor: alpha(theme.palette.error.main, 0.1) },
                                    '&.Mui-disabled': { color: 'action.disabled' },
                                  }}
                                >
                                  <DeleteIcon />
                                </IconButton>
                              </Box>
                            ))}

                            <Button
                              size="small"
                              startIcon={<AddIcon />}
                              onClick={() => handleAddCondition(ruleIndex)}
                              sx={{
                                color: primaryMain,
                                '&:hover': { bgcolor: alpha(primaryMain, 0.08) },
                              }}
                            >
                              Add Condition
                            </Button>
                          </Grid>
                        </Grid>
                      </CardContent>
                    </Card>
                  ))}
                </Box>
              )}
            </CardContent>
          </Card>
        </TabPanel>

        {/* Templates Tab */}
        <TabPanel value={activeTab} index={2}>
          <Card sx={{ ...surfaceCardSx, mx: 2, mb: 2 }}>
            <CardContent>
              <Typography variant="body1" sx={{ mb: 3, color: 'text.secondary' }}>
                Select a template to quickly configure a common policy type:
              </Typography>

              <Grid container spacing={2}>
                <Grid item xs={12} md={4}>
                  <Card
                    sx={{
                      ...ruleCardSx,
                      cursor: 'pointer',
                      transition: 'border-color 0.15s, background-color 0.15s',
                      '&:hover': {
                        bgcolor: alpha(primaryMain, 0.06),
                        borderColor: alpha(primaryMain, 0.25),
                      },
                    }}
                    onClick={() => handleLoadTemplate('access_control')}
                  >
                    <CardContent>
                      <Typography variant="h6" gutterBottom sx={{ color: 'text.primary' }}>
                        Access Control
                      </Typography>
                      <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                        Read-only database access with write operation blocking
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>

                <Grid item xs={12} md={4}>
                  <Card
                    sx={{
                      ...ruleCardSx,
                      cursor: 'pointer',
                      transition: 'border-color 0.15s, background-color 0.15s',
                      '&:hover': {
                        bgcolor: alpha(primaryMain, 0.06),
                        borderColor: alpha(primaryMain, 0.25),
                      },
                    }}
                    onClick={() => handleLoadTemplate('financial')}
                  >
                    <CardContent>
                      <Typography variant="h6" gutterBottom sx={{ color: 'text.primary' }}>
                        Financial Limit
                      </Typography>
                      <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                        Require approval for transactions above threshold
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>

                <Grid item xs={12} md={4}>
                  <Card
                    sx={{
                      ...ruleCardSx,
                      cursor: 'pointer',
                      transition: 'border-color 0.15s, background-color 0.15s',
                      '&:hover': {
                        bgcolor: alpha(primaryMain, 0.06),
                        borderColor: alpha(primaryMain, 0.25),
                      },
                    }}
                    onClick={() => handleLoadTemplate('data_protection')}
                  >
                    <CardContent>
                      <Typography variant="h6" gutterBottom sx={{ color: 'text.primary' }}>
                        Data Protection
                      </Typography>
                      <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                        Prevent export of documents containing PII
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </TabPanel>

        {/* JSON preview */}
        <Box sx={{ px: 2, pb: 2 }}>
          <Typography variant="subtitle2" sx={{ mb: 1, color: 'text.secondary', fontWeight: 600 }}>
            Payload preview (JSON)
          </Typography>
          <Box
            component="pre"
            sx={{
              m: 0,
              p: 2,
              borderRadius: 1,
              bgcolor: styles.codeBg,
              border: `1px solid ${theme.palette.divider}`,
              overflow: 'auto',
              maxHeight: 280,
              fontFamily: styles.mono,
              fontSize: '0.8125rem',
              lineHeight: 1.55,
              color: 'text.primary',
            }}
          >
            {JSON.stringify(policyPreview, null, 2)}
          </Box>
        </Box>

        {/* Action Buttons */}
        <CardContent sx={{ pt: 0, pb: 3, display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
          <Button
            variant="outlined"
            onClick={() => navigate('/policies')}
            sx={{
              borderColor: theme.palette.divider,
              color: 'text.primary',
              textTransform: 'none',
              fontWeight: 600,
              px: 2.5,
              '&:hover': {
                borderColor: theme.palette.text.secondary,
                bgcolor: styles.hoverBg,
              },
            }}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            disableElevation
            startIcon={
              saving ? <CircularProgress size={20} sx={{ color: '#fff' }} /> : <SaveIcon />
            }
            onClick={handleSave}
            disabled={saving}
            sx={{
              textTransform: 'none',
              fontWeight: 600,
              px: 2.5,
              color: '#fff',
              background: `linear-gradient(135deg, ${theme.palette.primary.main} 0%, ${theme.palette.primary.dark} 100%)`,
              '&:hover': {
                background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.92)} 0%, ${alpha(theme.palette.primary.dark, 0.95)} 100%)`,
              },
              '&.Mui-disabled': {
                color: 'text.disabled',
                background: theme.palette.action.disabledBackground,
              },
            }}
          >
            {saving ? 'Saving...' : isEditMode ? 'Update Policy' : 'Create Policy'}
          </Button>
        </CardContent>
      </Card>
    </Box>
  );
};

export default PolicyEditor;
