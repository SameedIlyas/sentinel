import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Box,
  Typography,
  Paper,
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
import {
  ArrowBack as BackIcon,
  Add as AddIcon,
  Delete as DeleteIcon,
  Save as SaveIcon,
} from '@mui/icons-material';
import policiesApi from '@/api/policies';
import { PolicyRule, PolicyCondition, PolicyCreate } from '@/types';

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

const PolicyEditor: React.FC = () => {
  const navigate = useNavigate();
  const { policyId } = useParams<{ policyId: string }>();
  const isEditMode = Boolean(policyId);

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
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
        <IconButton onClick={() => navigate('/policies')} sx={{ mr: 2 }}>
          <BackIcon />
        </IconButton>
        <Typography variant="h4" sx={{ fontWeight: 'bold' }}>
          {isEditMode ? 'Edit Policy' : 'Create Policy'}
        </Typography>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Paper sx={{ p: 3 }}>
        <Tabs value={activeTab} onChange={(_, v) => setActiveTab(v)} sx={{ mb: 3 }}>
          <Tab label="Basic Information" />
          <Tab label="Rules" />
          <Tab label="Templates" />
        </Tabs>

        {/* Basic Information Tab */}
        <TabPanel value={activeTab} index={0}>
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Policy Name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                placeholder="e.g., Production Database Read-Only Access"
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
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <FormControl fullWidth required>
                <InputLabel>Policy Type</InputLabel>
                <Select
                  value={policyType}
                  label="Policy Type"
                  onChange={(e) => setPolicyType(e.target.value)}
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
                    />
                  ))
                }
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Applies To Agents"
                    placeholder="Enter agent IDs or '*' for all agents"
                    helperText="Type agent ID and press Enter, or use '*' for all agents"
                  />
                )}
              />
            </Grid>

            <Grid item xs={12}>
              <FormControlLabel
                control={
                  <Switch checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
                }
                label="Policy Enabled"
              />
            </Grid>
          </Grid>
        </TabPanel>

        {/* Rules Tab */}
        <TabPanel value={activeTab} index={1}>
          <Box sx={{ mb: 2 }}>
            <Button variant="outlined" startIcon={<AddIcon />} onClick={handleAddRule}>
              Add Rule
            </Button>
          </Box>

          {rules.length === 0 ? (
            <Alert severity="info">No rules defined. Add at least one rule to create the policy.</Alert>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              {rules.map((rule, ruleIndex) => (
                <Card key={ruleIndex} variant="outlined">
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                      <Typography variant="h6">Rule {ruleIndex + 1}</Typography>
                      <IconButton
                        size="small"
                        color="error"
                        onClick={() => handleRemoveRule(ruleIndex)}
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
                        />
                      </Grid>

                      <Grid item xs={12}>
                        <FormControl fullWidth>
                          <InputLabel>Action</InputLabel>
                          <Select
                            value={rule.action}
                            label="Action"
                            onChange={(e) => handleRuleChange(ruleIndex, 'action', e.target.value)}
                          >
                            <MenuItem value="allow">Allow</MenuItem>
                            <MenuItem value="block">Block</MenuItem>
                            <MenuItem value="require_approval">Require Approval</MenuItem>
                          </Select>
                        </FormControl>
                      </Grid>

                      <Grid item xs={12}>
                        <Divider sx={{ my: 2 }}>Conditions</Divider>
                        
                        {rule.conditions.map((condition, conditionIndex) => (
                          <Box
                            key={conditionIndex}
                            sx={{ display: 'flex', gap: 1, mb: 2, alignItems: 'flex-start' }}
                          >
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
                              sx={{ flex: 1 }}
                              placeholder="e.g., action, system, amount"
                            />

                            <FormControl sx={{ flex: 1 }}>
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
                              sx={{ flex: 1 }}
                              placeholder="e.g., write, production_db, 1000"
                            />

                            <IconButton
                              color="error"
                              onClick={() => handleRemoveCondition(ruleIndex, conditionIndex)}
                              disabled={rule.conditions.length === 1}
                            >
                              <DeleteIcon />
                            </IconButton>
                          </Box>
                        ))}

                        <Button
                          size="small"
                          startIcon={<AddIcon />}
                          onClick={() => handleAddCondition(ruleIndex)}
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
        </TabPanel>

        {/* Templates Tab */}
        <TabPanel value={activeTab} index={2}>
          <Typography variant="body1" sx={{ mb: 3 }}>
            Select a template to quickly configure a common policy type:
          </Typography>

          <Grid container spacing={2}>
            <Grid item xs={12} md={4}>
              <Card
                variant="outlined"
                sx={{ cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' } }}
                onClick={() => handleLoadTemplate('access_control')}
              >
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Access Control
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Read-only database access with write operation blocking
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={4}>
              <Card
                variant="outlined"
                sx={{ cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' } }}
                onClick={() => handleLoadTemplate('financial')}
              >
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Financial Limit
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Require approval for transactions above threshold
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={4}>
              <Card
                variant="outlined"
                sx={{ cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' } }}
                onClick={() => handleLoadTemplate('data_protection')}
              >
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Data Protection
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Prevent export of documents containing PII
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </TabPanel>

        {/* Action Buttons */}
        <Box sx={{ mt: 4, display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
          <Button variant="outlined" onClick={() => navigate('/policies')}>
            Cancel
          </Button>
          <Button
            variant="contained"
            startIcon={saving ? <CircularProgress size={20} /> : <SaveIcon />}
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? 'Saving...' : isEditMode ? 'Update Policy' : 'Create Policy'}
          </Button>
        </Box>
      </Paper>
    </Box>
  );
};

export default PolicyEditor;
