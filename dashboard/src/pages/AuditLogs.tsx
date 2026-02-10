import React from 'react';
import { Box, Typography, Paper } from '@mui/material';

const AuditLogs: React.FC = () => {
  return (
    <Box>
      <Typography variant="h4" gutterBottom sx={{ fontWeight: 'bold', mb: 3 }}>
        Audit Logs
      </Typography>
      <Paper sx={{ p: 3 }}>
        <Typography color="text.secondary">
          Audit log viewer will be implemented in Task 16
        </Typography>
      </Paper>
    </Box>
  );
};

export default AuditLogs;
