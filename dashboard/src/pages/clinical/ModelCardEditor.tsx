// src/pages/clinical/ModelCardEditor.tsx
import React, { useState, useEffect, useMemo } from 'react';
import {
  Box,
  Typography,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Skeleton,
  Alert,
  Stack,
  Paper,
  Grid,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  LinearProgress,
  Chip,
  IconButton,
  Tooltip,
  Drawer,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Tab,
  Tabs,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
} from '@mui/material';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import ArticleIcon from '@mui/icons-material/Article';
import SaveIcon from '@mui/icons-material/Save';
import PublishIcon from '@mui/icons-material/Publish';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import FactCheckIcon from '@mui/icons-material/FactCheck';
import HubIcon from '@mui/icons-material/Hub';
import DownloadIcon from '@mui/icons-material/Download';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import {
  getModelCard,
  createModelCard,
  updateModelCard,
  publishModelCard,
  autoFillModelCard,
  getCHAICompliance,
  getRelatedArtifacts,
  exportModelCard,
  type CHAICompliance,
  type RelatedArtifacts,
  type ModelCardAutoFillResult,
} from '@/api/healthcare';
import { ModelCardLifecycle } from '@/types';

// ───────────────────────────────────────────────────────────────────────────
// Form state — covers every CHAI v2.0 field including pinned lineage
// ───────────────────────────────────────────────────────────────────────────

type PerformanceMetrics = Record<string, number | string>;
type BiasSubgroup = { name: string; type: string; auc: number; reference_auc: number; disparity_ratio?: number };
type BiasSummary = { subgroups?: BiasSubgroup[]; max_disparity_ratio?: number; passes_4_5ths_rule?: boolean; notes?: string };

type FormState = {
  name: string;
  version: string;
  intended_use: string;
  clinical_indications: string;
  contraindications: string;
  training_data_source: string;
  performance_metrics: PerformanceMetrics;
  bias_summary: BiasSummary;
  fda_status: string;
  lifecycle_stage: ModelCardLifecycle;
  // Pinned lineage
  model_artifact_uri: string;
  training_dataset_sha256: string;
  evaluation_dataset_sha256: string;
  git_commit_sha: string;
  framework_version: string;
  // CHAI sections 5/9/11
  external_validation: Record<string, any>;
  monitoring_plan: Record<string, any>;
  pccp: Record<string, any>;
};

const EMPTY_FORM: FormState = {
  name: '',
  version: '1.0',
  intended_use: '',
  clinical_indications: '',
  contraindications: '',
  training_data_source: '',
  performance_metrics: {},
  bias_summary: {},
  fda_status: '',
  lifecycle_stage: 'draft',
  model_artifact_uri: '',
  training_dataset_sha256: '',
  evaluation_dataset_sha256: '',
  git_commit_sha: '',
  framework_version: '',
  external_validation: {},
  monitoring_plan: {},
  pccp: {},
};

function cardToForm(card: any): FormState {
  return {
    name: card.name ?? card.model_name ?? '',
    version: card.version ?? card.model_version ?? '',
    intended_use: card.intended_use ?? '',
    clinical_indications: card.clinical_indications ?? '',
    contraindications: card.contraindications ?? '',
    training_data_source: card.training_data_source ?? '',
    performance_metrics: card.performance_metrics ?? {},
    bias_summary: card.bias_summary ?? {},
    fda_status: card.fda_status ?? '',
    lifecycle_stage: card.lifecycle_stage ?? 'draft',
    model_artifact_uri: card.model_artifact_uri ?? '',
    training_dataset_sha256: card.training_dataset_sha256 ?? '',
    evaluation_dataset_sha256: card.evaluation_dataset_sha256 ?? '',
    git_commit_sha: card.git_commit_sha ?? '',
    framework_version: card.framework_version ?? '',
    external_validation: card.external_validation ?? {},
    monitoring_plan: card.monitoring_plan ?? {},
    pccp: card.pccp ?? {},
  };
}

// ───────────────────────────────────────────────────────────────────────────
// Auto-fill dialog
// ───────────────────────────────────────────────────────────────────────────

interface AutoFillDialogProps {
  open: boolean;
  onClose: () => void;
  cardId: string;
  onApply: (result: ModelCardAutoFillResult) => void;
}

const AutoFillDialog: React.FC<AutoFillDialogProps> = ({ open, onClose, cardId, onApply }) => {
  const [repoUrl, setRepoUrl] = useState('');
  const [mlflowRunId, setMlflowRunId] = useState('');
  const [experimentId, setExperimentId] = useState('');

  const mutation = useMutation({
    mutationFn: () =>
      autoFillModelCard(cardId, {
        repo_url: repoUrl,
        mlflow_run_id: mlflowRunId || undefined,
        experiment_id: experimentId || undefined,
      }),
    onSuccess: (result) => {
      onApply(result);
      onClose();
      setRepoUrl('');
      setMlflowRunId('');
      setExperimentId('');
    },
  });

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <AutoFixHighIcon color="primary" />
        Auto-fill from sources
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          We'll pull description, topics, and recent commits from GitHub, plus performance metrics and training params from MLflow.
          Contraindications and human-judgment fields are never auto-filled.
        </Typography>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <TextField
            label="GitHub repository URL"
            placeholder="https://github.com/owner/repo"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            fullWidth
            required
          />
          <TextField
            label="MLflow run ID (optional)"
            placeholder="abc123def4567890"
            value={mlflowRunId}
            onChange={(e) => setMlflowRunId(e.target.value)}
            fullWidth
            helperText="Pulls performance_metrics + training params"
          />
          <TextField
            label="MLflow experiment ID (optional)"
            value={experimentId}
            onChange={(e) => setExperimentId(e.target.value)}
            fullWidth
            helperText="Use if you don't have a specific run ID"
          />
          {mutation.isError && (
            <Alert severity="error">
              {(mutation.error as Error)?.message ?? 'Auto-fill failed.'}
            </Alert>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          variant="contained"
          startIcon={<AutoFixHighIcon />}
          onClick={() => mutation.mutate()}
          disabled={!repoUrl || mutation.isPending}
        >
          {mutation.isPending ? 'Pulling…' : 'Auto-fill'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

// ───────────────────────────────────────────────────────────────────────────
// CHAI compliance drawer
// ───────────────────────────────────────────────────────────────────────────

interface CHAIComplianceDrawerProps {
  open: boolean;
  onClose: () => void;
  compliance?: CHAICompliance;
}

function statusIcon(status: string) {
  if (status === 'complete') return <CheckCircleIcon sx={{ color: 'success.main' }} fontSize="small" />;
  if (status === 'partial') return <WarningAmberIcon sx={{ color: 'warning.main' }} fontSize="small" />;
  return <RadioButtonUncheckedIcon sx={{ color: 'text.disabled' }} fontSize="small" />;
}

const CHAIComplianceDrawer: React.FC<CHAIComplianceDrawerProps> = ({ open, onClose, compliance }) => (
  <Drawer anchor="right" open={open} onClose={onClose} PaperProps={{ sx: { width: { xs: '100%', sm: 420 } } }}>
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
        <FactCheckIcon color="primary" />
        <Typography variant="h5">CHAI v2.0 Compliance</Typography>
      </Box>
      {compliance && (
        <>
          <Box sx={{ mb: 2 }}>
            <Typography variant="h3" sx={{ fontWeight: 700, lineHeight: 1 }}>
              {compliance.score} / {compliance.total}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {compliance.percent}% of CHAI sections complete
            </Typography>
            <LinearProgress
              variant="determinate"
              value={compliance.percent}
              sx={{ mt: 1, height: 8, borderRadius: 4 }}
              color={compliance.percent >= 80 ? 'success' : compliance.percent >= 50 ? 'warning' : 'error'}
            />
          </Box>

          {!compliance.publishable && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              <strong>Publish blocked.</strong> Required sections missing: {compliance.blockers.join(', ')}
            </Alert>
          )}

          <List dense disablePadding>
            {compliance.sections.map((s, i) => (
              <ListItem key={s.key} disableGutters sx={{ py: 0.75, borderTop: i > 0 ? '1px solid' : 'none', borderColor: 'divider' }}>
                <ListItemIcon sx={{ minWidth: 32 }}>{statusIcon(s.status)}</ListItemIcon>
                <ListItemText
                  primary={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography variant="body2" fontWeight={600}>{i + 1}. {s.label}</Typography>
                      <Chip label={s.status} size="small" color={s.status === 'complete' ? 'success' : s.status === 'partial' ? 'warning' : 'default'} sx={{ height: 18, fontSize: 10 }} />
                    </Box>
                  }
                  secondary={s.detail ?? null}
                  secondaryTypographyProps={{ fontSize: '0.7rem' }}
                />
              </ListItem>
            ))}
          </List>
        </>
      )}
    </Box>
  </Drawer>
);

// ───────────────────────────────────────────────────────────────────────────
// Related-artifacts drawer
// ───────────────────────────────────────────────────────────────────────────

interface RelatedDrawerProps {
  open: boolean;
  onClose: () => void;
  related?: RelatedArtifacts;
}

const RelatedDrawer: React.FC<RelatedDrawerProps> = ({ open, onClose, related }) => {
  const navigate = useNavigate();
  const sections: Array<{ title: string; items: any[]; route: (id: string) => string }> = [
    { title: 'Bias Audits', items: related?.bias_audits ?? [], route: (id) => `/clinical/bias-audits/${id}` },
    { title: 'Drift Baselines', items: related?.drift_baselines ?? [], route: () => `/clinical/drift` },
    { title: 'Drift Alerts', items: related?.drift_alerts ?? [], route: () => `/clinical/drift` },
    { title: 'Adverse Events', items: related?.adverse_events ?? [], route: () => `/regulatory/adverse-events` },
    { title: 'Risk Scores', items: related?.risk_scores ?? [], route: (id) => `/risk/scores/${id}` },
    { title: 'Transparency Records', items: related?.transparency_records ?? [], route: () => `/transparency` },
  ];

  return (
    <Drawer anchor="right" open={open} onClose={onClose} PaperProps={{ sx: { width: { xs: '100%', sm: 460 } } }}>
      <Box sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
          <HubIcon color="primary" />
          <Typography variant="h5">Linked artifacts</Typography>
        </Box>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Every governance artifact tied to this model.
        </Typography>
        {sections.map(({ title, items, route }) => (
          <Box key={title} sx={{ mb: 2 }}>
            <Typography variant="overline" sx={{ fontWeight: 700, color: 'text.secondary', fontSize: '0.65rem' }}>
              {title} ({items.length})
            </Typography>
            {items.length === 0 ? (
              <Typography variant="caption" color="text.disabled" sx={{ display: 'block', mb: 1 }}>None</Typography>
            ) : (
              <List dense disablePadding>
                {items.slice(0, 5).map((it) => (
                  <ListItem
                    key={it.id}
                    disableGutters
                    sx={{ py: 0.5, cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' }, borderRadius: 1, px: 1 }}
                    onClick={() => { onClose(); navigate(route(it.id)); }}
                    secondaryAction={<OpenInNewIcon fontSize="small" sx={{ color: 'text.secondary', fontSize: 14 }} />}
                  >
                    <ListItemText
                      primary={<Typography variant="body2">{it.title}</Typography>}
                      secondary={
                        <Box sx={{ display: 'flex', gap: 0.5, mt: 0.25 }}>
                          {it.status && <Chip label={it.status} size="small" sx={{ height: 16, fontSize: 9 }} />}
                          {it.severity && <Chip label={it.severity} size="small" color="warning" sx={{ height: 16, fontSize: 9 }} />}
                        </Box>
                      }
                    />
                  </ListItem>
                ))}
              </List>
            )}
          </Box>
        ))}
      </Box>
    </Drawer>
  );
};

// ───────────────────────────────────────────────────────────────────────────
// Structured performance metrics editor
// ───────────────────────────────────────────────────────────────────────────

const PerformanceMetricsEditor: React.FC<{
  metrics: PerformanceMetrics;
  onChange: (m: PerformanceMetrics) => void;
}> = ({ metrics, onChange }) => {
  const entries = Object.entries(metrics);
  const addRow = () => {
    let newKey = `metric_${entries.length + 1}`;
    let i = entries.length + 1;
    while (newKey in metrics) { i++; newKey = `metric_${i}`; }
    onChange({ ...metrics, [newKey]: 0 });
  };
  const updateKey = (oldKey: string, newKey: string) => {
    if (!newKey || newKey === oldKey || newKey in metrics) return;
    const next = { ...metrics };
    next[newKey] = next[oldKey];
    delete next[oldKey];
    onChange(next);
  };
  const updateValue = (key: string, value: string) => {
    const num = Number(value);
    onChange({ ...metrics, [key]: Number.isFinite(num) && value !== '' ? num : value });
  };
  const removeRow = (key: string) => {
    const next = { ...metrics };
    delete next[key];
    onChange(next);
  };
  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="caption" color="text.secondary">
          Per-metric values (e.g. AUC = 0.872, sensitivity = 0.81). These map to <code>performance_metrics</code> JSON.
        </Typography>
        <Button size="small" startIcon={<AddIcon />} onClick={addRow}>Add metric</Button>
      </Box>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell sx={{ width: '40%' }}>Metric</TableCell>
            <TableCell>Value</TableCell>
            <TableCell sx={{ width: 60 }}></TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {entries.length === 0 && (
            <TableRow><TableCell colSpan={3}><Typography variant="caption" color="text.disabled">No metrics yet — click "Add metric" or use Auto-fill.</Typography></TableCell></TableRow>
          )}
          {entries.map(([key, val]) => (
            <TableRow key={key}>
              <TableCell>
                <TextField size="small" value={key} onBlur={(e) => updateKey(key, e.target.value)} onChange={() => {}} fullWidth />
              </TableCell>
              <TableCell>
                <TextField size="small" value={val} onChange={(e) => updateValue(key, e.target.value)} fullWidth />
              </TableCell>
              <TableCell><IconButton size="small" onClick={() => removeRow(key)}><DeleteIcon fontSize="small" /></IconButton></TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Box>
  );
};

// ───────────────────────────────────────────────────────────────────────────
// Structured bias subgroup editor
// ───────────────────────────────────────────────────────────────────────────

const BiasSubgroupEditor: React.FC<{
  bias: BiasSummary;
  onChange: (b: BiasSummary) => void;
}> = ({ bias, onChange }) => {
  const subgroups = bias.subgroups ?? [];
  const addRow = () => {
    onChange({ ...bias, subgroups: [...subgroups, { name: '', type: 'sex', auc: 0, reference_auc: 0 }] });
  };
  const updateRow = (idx: number, patch: Partial<BiasSubgroup>) => {
    const next = [...subgroups];
    next[idx] = { ...next[idx], ...patch };
    if ('auc' in patch || 'reference_auc' in patch) {
      const ref = patch.reference_auc ?? next[idx].reference_auc;
      const auc = patch.auc ?? next[idx].auc;
      next[idx].disparity_ratio = ref ? Number((auc / ref).toFixed(3)) : 0;
    }
    const maxDisparity = next.length
      ? Math.max(...next.map((s) => s.disparity_ratio ?? 1).map((r) => Math.abs(1 - r)))
      : 0;
    onChange({ ...bias, subgroups: next, max_disparity_ratio: Number(maxDisparity.toFixed(3)), passes_4_5ths_rule: next.every((s) => (s.disparity_ratio ?? 1) >= 0.8) });
  };
  const removeRow = (idx: number) => {
    onChange({ ...bias, subgroups: subgroups.filter((_, i) => i !== idx) });
  };
  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="caption" color="text.secondary">
          Subgroup performance (4/5ths rule auto-computed). Maps to <code>bias_summary.subgroups</code>.
        </Typography>
        <Button size="small" startIcon={<AddIcon />} onClick={addRow}>Add subgroup</Button>
      </Box>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Subgroup</TableCell>
            <TableCell>Type</TableCell>
            <TableCell>AUC</TableCell>
            <TableCell>Reference</TableCell>
            <TableCell>Disparity</TableCell>
            <TableCell sx={{ width: 60 }}></TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {subgroups.length === 0 && (
            <TableRow><TableCell colSpan={6}><Typography variant="caption" color="text.disabled">No subgroups yet — bias audits link here automatically.</Typography></TableCell></TableRow>
          )}
          {subgroups.map((sg, idx) => {
            const dis = sg.disparity_ratio ?? 1;
            const passes = dis >= 0.8;
            return (
              <TableRow key={idx}>
                <TableCell><TextField size="small" value={sg.name} onChange={(e) => updateRow(idx, { name: e.target.value })} fullWidth /></TableCell>
                <TableCell>
                  <Select size="small" value={sg.type} onChange={(e) => updateRow(idx, { type: e.target.value })} sx={{ minWidth: 90 }}>
                    {['sex','race','age','ethnicity','insurance','language'].map((t) => <MenuItem key={t} value={t}>{t}</MenuItem>)}
                  </Select>
                </TableCell>
                <TableCell><TextField size="small" type="number" value={sg.auc} onChange={(e) => updateRow(idx, { auc: Number(e.target.value) })} sx={{ width: 80 }} inputProps={{ step: 0.01 }} /></TableCell>
                <TableCell><TextField size="small" type="number" value={sg.reference_auc} onChange={(e) => updateRow(idx, { reference_auc: Number(e.target.value) })} sx={{ width: 80 }} inputProps={{ step: 0.01 }} /></TableCell>
                <TableCell>
                  <Chip label={dis.toFixed(3)} size="small" color={passes ? 'success' : 'error'} sx={{ height: 22 }} />
                </TableCell>
                <TableCell><IconButton size="small" onClick={() => removeRow(idx)}><DeleteIcon fontSize="small" /></IconButton></TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      {subgroups.length > 0 && (
        <Box sx={{ mt: 1, display: 'flex', gap: 1 }}>
          <Chip label={`Max disparity: ${(bias.max_disparity_ratio ?? 0).toFixed(3)}`} size="small" />
          <Chip label={bias.passes_4_5ths_rule ? '4/5ths rule: PASS' : '4/5ths rule: FAIL'} size="small" color={bias.passes_4_5ths_rule ? 'success' : 'error'} />
        </Box>
      )}
    </Box>
  );
};

// ───────────────────────────────────────────────────────────────────────────
// Main editor
// ───────────────────────────────────────────────────────────────────────────

const ModelCardEditor: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { id } = useParams<{ id: string }>();
  const isNew = !id;

  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState(0);
  const [autoFillOpen, setAutoFillOpen] = useState(false);
  const [chaiOpen, setChaiOpen] = useState(false);
  const [relatedOpen, setRelatedOpen] = useState(false);
  const [autoFillResult, setAutoFillResult] = useState<ModelCardAutoFillResult | null>(null);

  const { data: existingCard, isLoading: isLoadingCard } = useQuery<any>({
    queryKey: ['model-card', id],
    queryFn: () => getModelCard(id!),
    enabled: !isNew,
  });

  const { data: chaiCompliance } = useQuery<CHAICompliance>({
    queryKey: ['model-card-chai', id],
    queryFn: () => getCHAICompliance(id!),
    enabled: !isNew,
  });

  const { data: related } = useQuery<RelatedArtifacts>({
    queryKey: ['model-card-related', id],
    queryFn: () => getRelatedArtifacts(id!),
    enabled: !isNew,
  });

  useEffect(() => {
    if (existingCard) {
      setForm(cardToForm(existingCard));
    }
  }, [existingCard]);

  const saveMutation = useMutation({
    mutationFn: (formData: FormState) => {
      const payload: any = { ...formData };
      // Server expects `name`/`version` on create; PUT accepts the same field names.
      if (isNew) {
        return createModelCard(payload);
      }
      return updateModelCard(id!, payload);
    },
    onSuccess: (saved: any) => {
      setSuccessMessage(isNew ? 'Model card created.' : 'Model card updated.');
      setSubmitError(null);
      queryClient.invalidateQueries({ queryKey: ['model-cards'] });
      queryClient.invalidateQueries({ queryKey: ['model-card', id] });
      queryClient.invalidateQueries({ queryKey: ['model-card-chai', id] });
      if (isNew && saved?.id) navigate(`/clinical/model-cards/${saved.id}`);
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail;
      setSubmitError(typeof detail === 'string' ? detail : err?.message ?? 'Save failed.');
      setSuccessMessage(null);
    },
  });

  const publishMutation = useMutation({
    mutationFn: () => publishModelCard(id!),
    onSuccess: (updated: any) => {
      setForm(cardToForm(updated));
      setSuccessMessage('Model card published.');
      setSubmitError(null);
      queryClient.invalidateQueries({ queryKey: ['model-card-chai', id] });
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail;
      if (detail?.error === 'lineage_required') {
        setSubmitError(`Publish blocked — missing lineage: ${detail.missing_fields.join(', ')}. ${detail.guidance}`);
      } else {
        setSubmitError(typeof detail === 'string' ? detail : err?.message ?? 'Publish failed.');
      }
      setSuccessMessage(null);
    },
  });

  const handleField = <K extends keyof FormState>(field: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setValidationError(null);
  };

  const handleSave = () => {
    if (!form.name.trim()) return setValidationError('Model name is required.');
    if (!form.version.trim()) return setValidationError('Model version is required.');
    if (!form.intended_use.trim()) return setValidationError('Intended use is required.');
    saveMutation.mutate(form);
  };

  const handleApplyAutoFill = (result: ModelCardAutoFillResult) => {
    setAutoFillResult(result);
    setForm((prev) => {
      const next = { ...prev };
      const f = result.pre_filled;
      if (f.intended_use) next.intended_use = f.intended_use;
      if (f.clinical_indications) next.clinical_indications = f.clinical_indications;
      if (f.training_data_description) next.training_data_source = JSON.stringify(f.training_data_description, null, 2);
      if (f.performance_metrics) next.performance_metrics = { ...prev.performance_metrics, ...f.performance_metrics };
      return next;
    });
    setSuccessMessage(`Auto-filled ${Object.keys(result.pre_filled).length} fields. ${result.requires_human_review.length} fields still need human review.`);
  };

  const handleExport = async (fmt: 'json-ld' | 'markdown') => {
    if (!id) return;
    const data = await exportModelCard(id, fmt);
    const isMd = fmt === 'markdown';
    const content = isMd ? (data as any).content : JSON.stringify(data, null, 2);
    const blob = new Blob([content], { type: isMd ? 'text/markdown' : 'application/ld+json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `model-card-${id}.${isMd ? 'md' : 'jsonld'}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const lineageComplete = useMemo(() =>
    !!form.model_artifact_uri && !!form.training_dataset_sha256 && !!form.evaluation_dataset_sha256,
    [form.model_artifact_uri, form.training_dataset_sha256, form.evaluation_dataset_sha256]
  );

  return (
    <Box>
      {/* ── Header ── */}
      <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 3, flexWrap: 'wrap', gap: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <ArticleIcon sx={{ color: 'primary.main', fontSize: 28 }} />
          <Box>
            <Typography variant="h4">{isNew ? 'New Model Card' : (existingCard?.name ?? 'Edit Model Card')}</Typography>
            <Typography variant="body2" color="text.secondary">
              {isNew ? 'Create a CHAI-compliant clinical AI model card' : `${form.name} — v${form.version} — ${form.lifecycle_stage}`}
            </Typography>
          </Box>
        </Box>

        {/* Header CTAs — auto-fill / CHAI / Related / Export */}
        <Stack direction="row" spacing={1} flexWrap="wrap">
          {!isNew && (
            <Tooltip title="Auto-fill from GitHub + MLflow">
              <Button size="small" variant="outlined" startIcon={<AutoFixHighIcon />} onClick={() => setAutoFillOpen(true)}>
                Auto-fill
              </Button>
            </Tooltip>
          )}
          {!isNew && chaiCompliance && (
            <Tooltip title="CHAI v2.0 compliance scorecard">
              <Button size="small" variant="outlined" startIcon={<FactCheckIcon />} onClick={() => setChaiOpen(true)}>
                CHAI {chaiCompliance.score}/{chaiCompliance.total}
              </Button>
            </Tooltip>
          )}
          {!isNew && (
            <Tooltip title="Linked governance artifacts">
              <Button size="small" variant="outlined" startIcon={<HubIcon />} onClick={() => setRelatedOpen(true)}>
                Linked
              </Button>
            </Tooltip>
          )}
          {!isNew && (
            <>
              <Tooltip title="Download JSON-LD">
                <Button size="small" variant="outlined" startIcon={<DownloadIcon />} onClick={() => handleExport('json-ld')}>JSON-LD</Button>
              </Tooltip>
              <Tooltip title="Download Markdown">
                <Button size="small" variant="outlined" startIcon={<DownloadIcon />} onClick={() => handleExport('markdown')}>Markdown</Button>
              </Tooltip>
            </>
          )}
        </Stack>
      </Box>

      {/* ── CHAI compliance ribbon ── */}
      {!isNew && chaiCompliance && (
        <Paper variant="outlined" sx={{ p: 1.5, mb: 2, display: 'flex', alignItems: 'center', gap: 2 }}>
          <FactCheckIcon color={chaiCompliance.publishable ? 'success' : 'warning'} />
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography variant="body2" fontWeight={600}>
              CHAI v2.0 Compliance: {chaiCompliance.score}/{chaiCompliance.total} sections ({chaiCompliance.percent}%)
            </Typography>
            <LinearProgress
              variant="determinate"
              value={chaiCompliance.percent}
              sx={{ mt: 0.5, height: 6, borderRadius: 3 }}
              color={chaiCompliance.percent >= 80 ? 'success' : chaiCompliance.percent >= 50 ? 'warning' : 'error'}
            />
          </Box>
          {!chaiCompliance.publishable && (
            <Chip label="Publish blocked" color="warning" size="small" />
          )}
        </Paper>
      )}

      {/* ── Auto-fill summary ── */}
      {autoFillResult && (
        <Alert severity="info" sx={{ mb: 2 }} onClose={() => setAutoFillResult(null)}>
          <strong>Auto-fill complete.</strong> Pre-filled: {Object.keys(autoFillResult.pre_filled).join(', ') || '(none)'}.
          Requires human review: {autoFillResult.requires_human_review.join(', ')}.
        </Alert>
      )}

      {/* ── Alerts ── */}
      {validationError && <Alert severity="warning" sx={{ mb: 2 }} onClose={() => setValidationError(null)}>{validationError}</Alert>}
      {submitError && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setSubmitError(null)}>{submitError}</Alert>}
      {successMessage && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccessMessage(null)}>{successMessage}</Alert>}

      {/* ── Form ── */}
      <Paper variant="outlined">
        <Tabs value={activeTab} onChange={(_, v) => setActiveTab(v)} sx={{ px: 2, borderBottom: 1, borderColor: 'divider' }} variant="scrollable" scrollButtons="auto">
          <Tab label="Identity" />
          <Tab label="Clinical" />
          <Tab label="Performance" />
          <Tab label="Fairness" />
          <Tab label="Lineage" />
          <Tab label="Validation" />
          <Tab label="Monitoring" />
          <Tab label="PCCP" />
          <Tab label="Regulatory" />
        </Tabs>

        <Box sx={{ p: 3 }}>
          {isLoadingCard ? (
            <Stack spacing={2}>{Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} variant="rectangular" height={56} />)}</Stack>
          ) : (
            <>
              {/* IDENTITY */}
              {activeTab === 0 && (
                <Stack spacing={3}>
                  <Grid container spacing={2}>
                    <Grid item xs={12} sm={6}>
                      <TextField label="Model Name" required fullWidth value={form.name} onChange={(e) => handleField('name', e.target.value)} />
                    </Grid>
                    <Grid item xs={12} sm={3}>
                      <TextField label="Version" required fullWidth value={form.version} onChange={(e) => handleField('version', e.target.value)} />
                    </Grid>
                    <Grid item xs={12} sm={3}>
                      <FormControl fullWidth>
                        <InputLabel>Lifecycle Stage</InputLabel>
                        <Select label="Lifecycle Stage" value={form.lifecycle_stage} onChange={(e) => handleField('lifecycle_stage', e.target.value as ModelCardLifecycle)}>
                          <MenuItem value="draft">Draft</MenuItem>
                          <MenuItem value="review">Review</MenuItem>
                          <MenuItem value="published">Published</MenuItem>
                          <MenuItem value="retired">Retired</MenuItem>
                        </Select>
                      </FormControl>
                    </Grid>
                  </Grid>
                </Stack>
              )}

              {/* CLINICAL */}
              {activeTab === 1 && (
                <Stack spacing={3}>
                  <TextField label="Intended Use" required fullWidth multiline minRows={2} value={form.intended_use} onChange={(e) => handleField('intended_use', e.target.value)} />
                  <TextField label="Clinical Indications" fullWidth multiline minRows={2} value={form.clinical_indications} onChange={(e) => handleField('clinical_indications', e.target.value)} />
                  <TextField label="Contraindications (REQUIRES HUMAN REVIEW — never auto-filled)" fullWidth multiline minRows={2} value={form.contraindications} onChange={(e) => handleField('contraindications', e.target.value)} helperText="What populations or conditions should this model NOT be used for?" />
                  <TextField label="Training Data Source" fullWidth multiline minRows={2} value={form.training_data_source} onChange={(e) => handleField('training_data_source', e.target.value)} helperText="Cohort description, n, date range, sites" />
                </Stack>
              )}

              {/* PERFORMANCE — structured editor */}
              {activeTab === 2 && (
                <Stack spacing={2}>
                  <Typography variant="subtitle2">Quantitative Analyses</Typography>
                  <PerformanceMetricsEditor metrics={form.performance_metrics} onChange={(m) => handleField('performance_metrics', m)} />
                </Stack>
              )}

              {/* FAIRNESS — structured subgroup editor */}
              {activeTab === 3 && (
                <Stack spacing={2}>
                  <Typography variant="subtitle2">Subgroup Performance & 4/5ths Rule</Typography>
                  <BiasSubgroupEditor bias={form.bias_summary} onChange={(b) => handleField('bias_summary', b)} />
                  <TextField label="Bias narrative / notes" fullWidth multiline minRows={2} value={form.bias_summary.notes ?? ''} onChange={(e) => handleField('bias_summary', { ...form.bias_summary, notes: e.target.value })} />
                </Stack>
              )}

              {/* LINEAGE — pinned identity */}
              {activeTab === 4 && (
                <Stack spacing={2}>
                  <Alert severity={lineageComplete ? 'success' : 'info'}>
                    {lineageComplete
                      ? 'Lineage is pinned — this card describes a real, immutable model artifact.'
                      : 'A published card MUST pin the artifact URI + dataset hashes. Without these, the card describes an aspiration.'}
                  </Alert>
                  <TextField label="Model Artifact URI" required fullWidth value={form.model_artifact_uri} onChange={(e) => handleField('model_artifact_uri', e.target.value)} placeholder="mlflow://runs/abc123/model  or  s3://prod-models/sepsis/v2.3/model.pkl" />
                  <Grid container spacing={2}>
                    <Grid item xs={12} md={6}>
                      <TextField label="Training Dataset SHA-256" required fullWidth value={form.training_dataset_sha256} onChange={(e) => handleField('training_dataset_sha256', e.target.value)} placeholder="64-char hex hash of training manifest" />
                    </Grid>
                    <Grid item xs={12} md={6}>
                      <TextField label="Evaluation Dataset SHA-256" required fullWidth value={form.evaluation_dataset_sha256} onChange={(e) => handleField('evaluation_dataset_sha256', e.target.value)} placeholder="64-char hex hash of eval manifest" />
                    </Grid>
                    <Grid item xs={12} md={6}>
                      <TextField label="Git Commit SHA" fullWidth value={form.git_commit_sha} onChange={(e) => handleField('git_commit_sha', e.target.value)} placeholder="7f3a2c1 or full SHA" />
                    </Grid>
                    <Grid item xs={12} md={6}>
                      <TextField label="Framework Version" fullWidth value={form.framework_version} onChange={(e) => handleField('framework_version', e.target.value)} placeholder="PyTorch 2.1.0+cu118 / Python 3.11" />
                    </Grid>
                  </Grid>
                </Stack>
              )}

              {/* EXTERNAL VALIDATION */}
              {activeTab === 5 && (
                <Stack spacing={2}>
                  <Typography variant="caption" color="text.secondary">
                    External validation evidence — sites, sample sizes, performance per site. CHAI section 5.
                  </Typography>
                  <TextField label="External validation (JSON)" fullWidth multiline minRows={6} value={JSON.stringify(form.external_validation, null, 2)} onChange={(e) => { try { handleField('external_validation', JSON.parse(e.target.value)); } catch { /* ignore until valid */ } }} placeholder='{"sites":["Mass General","UCSF"],"n":[12420,8810],"auc":[0.87,0.86]}' />
                </Stack>
              )}

              {/* MONITORING */}
              {activeTab === 6 && (
                <Stack spacing={2}>
                  <Typography variant="caption" color="text.secondary">
                    Continuous monitoring plan — drift baseline + cadence. CHAI section 9.
                  </Typography>
                  <TextField label="Monitoring plan (JSON)" fullWidth multiline minRows={4} value={JSON.stringify(form.monitoring_plan, null, 2)} onChange={(e) => { try { handleField('monitoring_plan', JSON.parse(e.target.value)); } catch { /* ignore */ } }} placeholder='{"drift_baseline_id":"dbl_abc","cadence":"weekly","owner":"cmio"}' />
                </Stack>
              )}

              {/* PCCP */}
              {activeTab === 7 && (
                <Stack spacing={2}>
                  <Typography variant="caption" color="text.secondary">
                    Predetermined Change Control Plan (FDA 2023 guidance). Lists which model changes are pre-approved vs. require resubmission.
                  </Typography>
                  <TextField label="PCCP (JSON)" fullWidth multiline minRows={6} value={JSON.stringify(form.pccp, null, 2)} onChange={(e) => { try { handleField('pccp', JSON.parse(e.target.value)); } catch { /* ignore */ } }} placeholder='{"pre_approved":["retraining on new site data"],"requires_resubmission":["adding features"]}' />
                </Stack>
              )}

              {/* REGULATORY */}
              {activeTab === 8 && (
                <TextField label="FDA Status" fullWidth value={form.fda_status} onChange={(e) => handleField('fda_status', e.target.value)} placeholder="e.g. 510(k) Cleared (K231847), De Novo, PMA, Not a medical device" />
              )}
            </>
          )}
        </Box>
      </Paper>

      {/* ── Action buttons ── */}
      <Stack direction="row" spacing={2} sx={{ mt: 3 }} flexWrap="wrap">
        <Button variant="contained" startIcon={<SaveIcon />} onClick={handleSave} disabled={saveMutation.isPending || isLoadingCard}>
          {saveMutation.isPending ? 'Saving…' : 'Save'}
        </Button>
        {!isNew && (form.lifecycle_stage === 'draft' || form.lifecycle_stage === 'review') && (
          <Tooltip title={!lineageComplete ? 'Lineage required (Lineage tab) before publish' : ''}>
            <span>
              <Button variant="outlined" color="success" startIcon={<PublishIcon />} onClick={() => publishMutation.mutate()} disabled={publishMutation.isPending || !lineageComplete}>
                {publishMutation.isPending ? 'Publishing…' : 'Publish'}
              </Button>
            </span>
          </Tooltip>
        )}
        <Button variant="text" onClick={() => navigate(-1)}>Cancel</Button>
      </Stack>

      {/* ── Drawers + Dialogs ── */}
      {!isNew && id && (
        <>
          <AutoFillDialog open={autoFillOpen} onClose={() => setAutoFillOpen(false)} cardId={id} onApply={handleApplyAutoFill} />
          <CHAIComplianceDrawer open={chaiOpen} onClose={() => setChaiOpen(false)} compliance={chaiCompliance} />
          <RelatedDrawer open={relatedOpen} onClose={() => setRelatedOpen(false)} related={related} />
        </>
      )}
    </Box>
  );
};

export default ModelCardEditor;
