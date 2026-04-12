// src/pages/clinical/ModelCardEditor.tsx
import React, { useState, useEffect } from 'react';
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
  Divider,
  Grid,
} from '@mui/material';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import ArticleIcon from '@mui/icons-material/Article';
import SaveIcon from '@mui/icons-material/Save';
import PublishIcon from '@mui/icons-material/Publish';
import { getModelCard, createModelCard, updateModelCard, publishModelCard } from '@/api/healthcare';
import { ModelCard, ModelCardLifecycle } from '@/types';

type FormState = {
  model_name: string;
  model_version: string;
  intended_use: string;
  clinical_indications: string;
  contraindications: string;
  training_data_source: string;
  performance_summary: string;
  bias_summary: string;
  fda_status: string;
  lifecycle_stage: ModelCardLifecycle;
};

const EMPTY_FORM: FormState = {
  model_name: '',
  model_version: '',
  intended_use: '',
  clinical_indications: '',
  contraindications: '',
  training_data_source: '',
  performance_summary: '',
  bias_summary: '',
  fda_status: '',
  lifecycle_stage: 'draft',
};

function cardToForm(card: ModelCard): FormState {
  return {
    model_name: card.model_name,
    model_version: card.model_version,
    intended_use: card.intended_use,
    clinical_indications: card.clinical_indications,
    contraindications: card.contraindications ?? '',
    training_data_source: card.training_data_source ?? '',
    performance_summary: card.performance_summary ?? '',
    bias_summary: card.bias_summary ?? '',
    fda_status: card.fda_status ?? '',
    lifecycle_stage: card.lifecycle_stage,
  };
}

function FormSkeleton() {
  return (
    <Stack spacing={2}>
      {Array.from({ length: 6 }).map((_, i) => (
        <Skeleton key={i} variant="rectangular" height={56} />
      ))}
    </Stack>
  );
}

const ModelCardEditor: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const isNew = !id;

  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const { data: existingCard, isLoading: isLoadingCard } = useQuery({
    queryKey: ['model-card', id],
    queryFn: () => getModelCard(id!),
    enabled: !isNew,
  });

  useEffect(() => {
    if (existingCard) {
      setForm(cardToForm(existingCard));
    }
  }, [existingCard]);

  const saveMutation = useMutation({
    mutationFn: (formData: FormState) => {
      if (isNew) {
        return createModelCard(formData);
      }
      return updateModelCard(id!, formData);
    },
    onSuccess: () => {
      setSuccessMessage(isNew ? 'Model card created successfully.' : 'Model card updated successfully.');
      setSubmitError(null);
    },
    onError: (err: Error) => {
      setSubmitError(err.message ?? 'Failed to save model card.');
      setSuccessMessage(null);
    },
  });

  const publishMutation = useMutation({
    mutationFn: () => publishModelCard(id!),
    onSuccess: (updated) => {
      setForm(cardToForm(updated));
      setSuccessMessage('Model card published successfully.');
      setSubmitError(null);
    },
    onError: (err: Error) => {
      setSubmitError(err.message ?? 'Failed to publish model card.');
      setSuccessMessage(null);
    },
  });

  const handleChange = (field: keyof FormState, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setValidationError(null);
  };

  const handleSave = () => {
    if (!form.model_name.trim()) {
      setValidationError('Model name is required.');
      return;
    }
    if (!form.model_version.trim()) {
      setValidationError('Model version is required.');
      return;
    }
    if (!form.intended_use.trim()) {
      setValidationError('Intended use is required.');
      return;
    }
    setValidationError(null);
    saveMutation.mutate(form);
  };

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 3 }}>
        <ArticleIcon sx={{ color: 'primary.main', fontSize: 28 }} />
        <Box>
          <Typography variant="h4">{isNew ? 'New Model Card' : 'Edit Model Card'}</Typography>
          <Typography variant="body2" color="text.secondary">
            {isNew
              ? 'Create a CHAI-compliant model card'
              : `Editing model card: ${existingCard?.model_name ?? id}`}
          </Typography>
        </Box>
      </Box>

      {/* Alerts */}
      {validationError && (
        <Alert severity="warning" sx={{ mb: 2 }} onClose={() => setValidationError(null)}>
          {validationError}
        </Alert>
      )}
      {submitError && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setSubmitError(null)}>
          {submitError}
        </Alert>
      )}
      {successMessage && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccessMessage(null)}>
          {successMessage}
        </Alert>
      )}

      {/* Form */}
      <Paper variant="outlined" sx={{ p: 3 }}>
        {isLoadingCard ? (
          <FormSkeleton />
        ) : (
          <Stack spacing={3}>
            {/* Identity */}
            <Typography variant="subtitle1" fontWeight={600}>
              Model Identity
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <TextField
                  label="Model Name"
                  required
                  fullWidth
                  value={form.model_name}
                  onChange={(e) => handleChange('model_name', e.target.value)}
                  inputProps={{ 'data-testid': 'field-model-name' }}
                />
              </Grid>
              <Grid item xs={12} sm={3}>
                <TextField
                  label="Version"
                  required
                  fullWidth
                  value={form.model_version}
                  onChange={(e) => handleChange('model_version', e.target.value)}
                  inputProps={{ 'data-testid': 'field-model-version' }}
                />
              </Grid>
              <Grid item xs={12} sm={3}>
                <FormControl fullWidth>
                  <InputLabel id="lifecycle-label">Lifecycle Stage</InputLabel>
                  <Select
                    labelId="lifecycle-label"
                    label="Lifecycle Stage"
                    value={form.lifecycle_stage}
                    onChange={(e) =>
                      handleChange('lifecycle_stage', e.target.value as ModelCardLifecycle)
                    }
                    inputProps={{ 'data-testid': 'field-lifecycle-stage' }}
                  >
                    <MenuItem value="draft">Draft</MenuItem>
                    <MenuItem value="review">Review</MenuItem>
                    <MenuItem value="published">Published</MenuItem>
                    <MenuItem value="retired">Retired</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
            </Grid>

            <Divider />

            {/* Clinical Details */}
            <Typography variant="subtitle1" fontWeight={600}>
              Clinical Details
            </Typography>
            <TextField
              label="Intended Use"
              required
              fullWidth
              multiline
              minRows={2}
              value={form.intended_use}
              onChange={(e) => handleChange('intended_use', e.target.value)}
              inputProps={{ 'data-testid': 'field-intended-use' }}
            />
            <TextField
              label="Clinical Indications"
              fullWidth
              multiline
              minRows={2}
              value={form.clinical_indications}
              onChange={(e) => handleChange('clinical_indications', e.target.value)}
            />
            <TextField
              label="Contraindications"
              fullWidth
              multiline
              minRows={2}
              value={form.contraindications}
              onChange={(e) => handleChange('contraindications', e.target.value)}
            />

            <Divider />

            {/* Data & Performance */}
            <Typography variant="subtitle1" fontWeight={600}>
              Data &amp; Performance
            </Typography>
            <TextField
              label="Training Data Source"
              fullWidth
              value={form.training_data_source}
              onChange={(e) => handleChange('training_data_source', e.target.value)}
            />
            <TextField
              label="Performance Summary"
              fullWidth
              multiline
              minRows={2}
              value={form.performance_summary}
              onChange={(e) => handleChange('performance_summary', e.target.value)}
            />
            <TextField
              label="Bias Summary"
              fullWidth
              multiline
              minRows={2}
              value={form.bias_summary}
              onChange={(e) => handleChange('bias_summary', e.target.value)}
            />

            <Divider />

            {/* Regulatory */}
            <Typography variant="subtitle1" fontWeight={600}>
              Regulatory
            </Typography>
            <TextField
              label="FDA Status"
              fullWidth
              value={form.fda_status}
              onChange={(e) => handleChange('fda_status', e.target.value)}
              placeholder="e.g. 510(k) Exempt, De Novo, PMA"
            />
          </Stack>
        )}
      </Paper>

      {/* Action Buttons */}
      <Stack direction="row" spacing={2} sx={{ mt: 3 }}>
        <Button
          variant="contained"
          startIcon={<SaveIcon />}
          onClick={handleSave}
          disabled={saveMutation.isPending || isLoadingCard}
        >
          {saveMutation.isPending ? 'Saving…' : 'Save'}
        </Button>

        {!isNew && form.lifecycle_stage === 'review' && (
          <Button
            variant="outlined"
            color="success"
            startIcon={<PublishIcon />}
            onClick={() => publishMutation.mutate()}
            disabled={publishMutation.isPending}
          >
            {publishMutation.isPending ? 'Publishing…' : 'Publish'}
          </Button>
        )}

        <Button variant="text" onClick={() => navigate(-1)}>
          Cancel
        </Button>
      </Stack>
    </Box>
  );
};

export default ModelCardEditor;
