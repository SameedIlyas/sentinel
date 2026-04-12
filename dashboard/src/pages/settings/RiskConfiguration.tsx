import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  Alert,
  Skeleton,
  Button,
  TextField,
  Grid,
  Divider,
  Slider,
  Stack,
} from '@mui/material';
import TuneIcon from '@mui/icons-material/Tune';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getRiskConfiguration, updateRiskConfiguration } from '@/api/healthcare';
import type { RiskConfiguration as RiskConfig } from '@/types';

const RiskConfiguration: React.FC = () => {
  const queryClient = useQueryClient();

  const [regulatoryMultiplier, setRegulatoryMultiplier] = useState<number>(1.0);
  const [criticalThreshold, setCriticalThreshold] = useState<string>('80');
  const [highThreshold, setHighThreshold] = useState<string>('60');
  const [mediumThreshold, setMediumThreshold] = useState<string>('40');
  const [saveSuccess, setSaveSuccess] = useState(false);

  const { data: config, isLoading, isError } = useQuery({
    queryKey: ['riskConfiguration'],
    queryFn: getRiskConfiguration,
  });

  useEffect(() => {
    if (config) {
      setRegulatoryMultiplier(config.regulatory_multiplier ?? 1.0);
      setCriticalThreshold(String(config.critical_threshold ?? 80));
      setHighThreshold(String(config.high_threshold ?? 60));
      setMediumThreshold(String(config.medium_threshold ?? 40));
    }
  }, [config]);

  const mutation = useMutation({
    mutationFn: (data: Partial<RiskConfig>) => updateRiskConfiguration(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['riskConfiguration'] });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    },
  });

  const handleSave = () => {
    setSaveSuccess(false);
    mutation.mutate({
      regulatory_multiplier: regulatoryMultiplier,
      critical_threshold: Number(criticalThreshold),
      high_threshold: Number(highThreshold),
      medium_threshold: Number(mediumThreshold),
    });
  };

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 3 }}>
        <TuneIcon sx={{ color: 'primary.main', fontSize: 28 }} />
        <Box>
          <Typography variant="h4">Risk Configuration</Typography>
          <Typography variant="body2" color="text.secondary">
            Adjust risk scoring thresholds and regulatory multipliers
          </Typography>
        </Box>
      </Box>

      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Risk Scoring Parameters
        </Typography>
        <Divider sx={{ mb: 3 }} />

        {isLoading && (
          <Stack spacing={3}>
            <Skeleton variant="rectangular" height={40} />
            <Skeleton variant="rectangular" height={56} />
            <Skeleton variant="rectangular" height={56} />
            <Skeleton variant="rectangular" height={56} />
          </Stack>
        )}

        {isError && (
          <Alert severity="error">Failed to load risk configuration.</Alert>
        )}

        {!isLoading && !isError && (
          <Grid container spacing={3}>
            {/* Formula info */}
            <Grid item xs={12}>
              <Alert severity="info">
                Formula: Total Risk = (Severity × Exposure) + Regulatory Penalty × Multiplier
              </Alert>
            </Grid>

            {/* Regulatory Multiplier slider */}
            <Grid item xs={12}>
              <Typography variant="body2" gutterBottom>
                Regulatory Multiplier
              </Typography>
              <Slider
                value={regulatoryMultiplier}
                onChange={(_e, val) => setRegulatoryMultiplier(val as number)}
                min={0.5}
                max={3}
                step={0.1}
                marks
                valueLabelDisplay="auto"
                aria-label="Regulatory Multiplier"
              />
              <Typography variant="caption" color="text.secondary">
                Current value: {regulatoryMultiplier.toFixed(1)}
              </Typography>
            </Grid>

            {/* Threshold fields */}
            <Grid item xs={12} sm={4}>
              <TextField
                label="Critical Threshold"
                type="number"
                value={criticalThreshold}
                onChange={(e) => setCriticalThreshold(e.target.value)}
                fullWidth
                helperText="Risk score above this = Critical"
                inputProps={{ min: 0, max: 100 }}
              />
            </Grid>
            <Grid item xs={12} sm={4}>
              <TextField
                label="High Threshold"
                type="number"
                value={highThreshold}
                onChange={(e) => setHighThreshold(e.target.value)}
                fullWidth
                helperText="Risk score above this = High"
                inputProps={{ min: 0, max: 100 }}
              />
            </Grid>
            <Grid item xs={12} sm={4}>
              <TextField
                label="Medium Threshold"
                type="number"
                value={mediumThreshold}
                onChange={(e) => setMediumThreshold(e.target.value)}
                fullWidth
                helperText="Risk score above this = Medium"
                inputProps={{ min: 0, max: 100 }}
              />
            </Grid>

            {/* Save */}
            <Grid item xs={12}>
              {saveSuccess && (
                <Alert severity="success" sx={{ mb: 2 }}>
                  Risk configuration saved successfully.
                </Alert>
              )}
              {mutation.isError && (
                <Alert severity="error" sx={{ mb: 2 }}>
                  Failed to save risk configuration. Please try again.
                </Alert>
              )}
              <Button
                variant="contained"
                onClick={handleSave}
                disabled={mutation.isPending}
              >
                {mutation.isPending ? 'Saving…' : 'Save Configuration'}
              </Button>
            </Grid>
          </Grid>
        )}
      </Paper>
    </Box>
  );
};

export default RiskConfiguration;
