import React from 'react';
import { Box, Typography, Paper } from '@mui/material';

const Alerts: React.FC = () => {
  return (
    <Box>
      <Typography variant="h4" gutterBottom sx={{ fontWeight: 'bold', mb: 3 }}>
        Alerts
      </Typography>
      <Paper sx={{ p: 3 }}>
        <Typography color="text.secondary">
          Alert management UI will be implemented in Task 17
        </Typography>
      </Paper>
    </Box>
  );
};

export default Alerts;
