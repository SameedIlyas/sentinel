import React, { useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Chip,
  Alert,
  Divider,
  Switch,
  FormControlLabel,
  Stack,
} from '@mui/material';
import HealthAndSafetyIcon from '@mui/icons-material/HealthAndSafety';

interface ToggleState {
  phiAutoRedaction: boolean;
  auditLogPhiAccess: boolean;
  encryptPhiAtRest: boolean;
  safeHarborDeidentification: boolean;
}

const HIPAAConfiguration: React.FC = () => {
  const [toggles, setToggles] = useState<ToggleState>({
    phiAutoRedaction: true,
    auditLogPhiAccess: true,
    encryptPhiAtRest: true,
    safeHarborDeidentification: true,
  });

  const handleToggle = (key: keyof ToggleState) => {
    setToggles((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 3 }}>
        <HealthAndSafetyIcon sx={{ color: 'success.main', fontSize: 28 }} />
        <Box>
          <Typography variant="h4">HIPAA Configuration</Typography>
          <Typography variant="body2" color="text.secondary">
            Configure HIPAA compliance settings and data protection rules
          </Typography>
        </Box>
      </Box>

      <Stack spacing={3}>
        {/* Data Protection */}
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Data Protection
          </Typography>
          <Divider sx={{ mb: 2 }} />
          <Stack spacing={1}>
            <FormControlLabel
              control={
                <Switch
                  checked={toggles.phiAutoRedaction}
                  onChange={() => handleToggle('phiAutoRedaction')}
                  color="primary"
                />
              }
              label="PHI Auto-Redaction"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={toggles.auditLogPhiAccess}
                  onChange={() => handleToggle('auditLogPhiAccess')}
                  color="primary"
                />
              }
              label="Audit Log All PHI Access"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={toggles.encryptPhiAtRest}
                  onChange={() => handleToggle('encryptPhiAtRest')}
                  color="primary"
                />
              }
              label="Encrypt PHI at Rest"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={toggles.safeHarborDeidentification}
                  onChange={() => handleToggle('safeHarborDeidentification')}
                  color="primary"
                />
              }
              label="HIPAA Safe Harbor De-identification"
            />
          </Stack>
        </Paper>

        {/* Compliance Status */}
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Compliance Status
          </Typography>
          <Divider sx={{ mb: 2 }} />
          <Stack spacing={2}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Typography variant="body2" color="text.secondary" sx={{ minWidth: 240 }}>
                HIPAA Security Rule:
              </Typography>
              <Chip label="Compliant" color="success" size="small" />
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Typography variant="body2" color="text.secondary" sx={{ minWidth: 240 }}>
                HIPAA Privacy Rule:
              </Typography>
              <Chip label="Compliant" color="success" size="small" />
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Typography variant="body2" color="text.secondary" sx={{ minWidth: 240 }}>
                HITECH:
              </Typography>
              <Chip label="Compliant" color="success" size="small" />
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Typography variant="body2" color="text.secondary" sx={{ minWidth: 240 }}>
                Minimum Necessary Standard:
              </Typography>
              <Chip label="Enabled" color="success" size="small" />
            </Box>
          </Stack>
        </Paper>

        {/* Breach Notification */}
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Breach Notification
          </Typography>
          <Divider sx={{ mb: 2 }} />
          <Alert severity="info">
            Breach notifications are automatically sent within 60 days per HIPAA §164.400.
            Contact: privacy@yourorg.com
          </Alert>
        </Paper>
      </Stack>
    </Box>
  );
};

export default HIPAAConfiguration;
