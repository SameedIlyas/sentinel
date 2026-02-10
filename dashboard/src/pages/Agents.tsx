import React from 'react';
import { Box, Typography, Paper } from '@mui/material';

const Agents: React.FC = () => {
  return (
    <Box>
      <Typography variant="h4" gutterBottom sx={{ fontWeight: 'bold', mb: 3 }}>
        AI Agents
      </Typography>
      <Paper sx={{ p: 3 }}>
        <Typography color="text.secondary">
          Agent list and detail views will be implemented in Task 14
        </Typography>
      </Paper>
    </Box>
  );
};

export default Agents;
