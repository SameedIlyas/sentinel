import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  Chip,
  Alert,
  Skeleton,
  Button,
  TextField,
  Grid,
  Divider,
  Stack,
} from '@mui/material';
import BusinessIcon from '@mui/icons-material/Business';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getOrganization, updateOrganization } from '@/api/healthcare';

const ORG_TYPE_OPTIONS = [
  { value: 'hospital', label: 'Hospital' },
  { value: 'payer', label: 'Payer' },
  { value: 'medtech', label: 'MedTech' },
];

const OrganizationSettings: React.FC = () => {
  const queryClient = useQueryClient();

  const [name, setName] = useState('');
  const [orgType, setOrgType] = useState('');
  const [saveSuccess, setSaveSuccess] = useState(false);

  const { data: org, isLoading, isError } = useQuery({
    queryKey: ['organization'],
    queryFn: getOrganization,
  });

  useEffect(() => {
    if (org) {
      setName(org.name ?? '');
      setOrgType(org.org_type ?? '');
    }
  }, [org]);

  const mutation = useMutation({
    mutationFn: (data: { name?: string; org_type?: string }) => updateOrganization(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['organization'] });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    },
  });

  const handleSave = () => {
    setSaveSuccess(false);
    mutation.mutate({ name, org_type: orgType });
  };

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 3 }}>
        <BusinessIcon sx={{ color: 'primary.main', fontSize: 28 }} />
        <Box>
          <Typography variant="h4">Organization Settings</Typography>
          <Typography variant="body2" color="text.secondary">
            Manage your organization's profile and configuration
          </Typography>
        </Box>
      </Box>

      <Stack spacing={3}>
        {/* Organization Profile */}
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Organization Profile
          </Typography>
          <Divider sx={{ mb: 3 }} />

          {isLoading && (
            <Stack spacing={2}>
              <Skeleton variant="rectangular" height={56} />
              <Skeleton variant="rectangular" height={56} />
              <Skeleton variant="rectangular" height={56} />
            </Stack>
          )}

          {isError && (
            <Alert severity="error">Failed to load organization settings.</Alert>
          )}

          {!isLoading && !isError && (
            <Grid container spacing={2}>
              <Grid item xs={12}>
                <TextField
                  label="Organization Name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  fullWidth
                />
              </Grid>
              <Grid item xs={12}>
                <TextField
                  label="Organization Type"
                  value={orgType}
                  onChange={(e) => setOrgType(e.target.value)}
                  fullWidth
                  select
                  SelectProps={{ native: true }}
                >
                  {ORG_TYPE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </TextField>
              </Grid>
              <Grid item xs={12}>
                <TextField
                  label="Slug"
                  value={org?.slug ?? ''}
                  fullWidth
                  disabled
                  inputProps={{ readOnly: true }}
                  helperText="Slug cannot be changed after creation."
                />
              </Grid>
              <Grid item xs={12}>
                {saveSuccess && (
                  <Alert severity="success" sx={{ mb: 2 }}>
                    Organization profile saved successfully.
                  </Alert>
                )}
                {mutation.isError && (
                  <Alert severity="error" sx={{ mb: 2 }}>
                    Failed to save organization profile. Please try again.
                  </Alert>
                )}
                <Button
                  variant="contained"
                  onClick={handleSave}
                  disabled={mutation.isPending}
                >
                  {mutation.isPending ? 'Saving…' : 'Save Changes'}
                </Button>
              </Grid>
            </Grid>
          )}
        </Paper>

        {/* HIPAA Status */}
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            HIPAA Status
          </Typography>
          <Divider sx={{ mb: 3 }} />

          {isLoading && (
            <Stack spacing={2}>
              <Skeleton variant="rectangular" height={32} />
              <Skeleton variant="rectangular" height={32} />
              <Skeleton variant="rectangular" height={32} />
            </Stack>
          )}

          {isError && (
            <Alert severity="error">Failed to load HIPAA status.</Alert>
          )}

          {!isLoading && !isError && org && (
            <Stack spacing={2}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Typography variant="body2" color="text.secondary" sx={{ minWidth: 140 }}>
                  BAA Signed:
                </Typography>
                <Chip
                  label={org.hipaa_baa_signed ? 'Signed' : 'Not Signed'}
                  color={org.hipaa_baa_signed ? 'success' : 'error'}
                  size="small"
                />
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Typography variant="body2" color="text.secondary" sx={{ minWidth: 140 }}>
                  BAA Date:
                </Typography>
                <Typography variant="body2">
                  {org.hipaa_baa_date ?? '—'}
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Typography variant="body2" color="text.secondary" sx={{ minWidth: 140 }}>
                  Status:
                </Typography>
                <Chip
                  label={org.is_active ? 'Active' : 'Inactive'}
                  color={org.is_active ? 'success' : 'default'}
                  size="small"
                />
              </Box>
            </Stack>
          )}
        </Paper>
      </Stack>
    </Box>
  );
};

export default OrganizationSettings;
