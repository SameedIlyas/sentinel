import React from 'react';
import { Box, Typography, Paper } from '@mui/material';

const Policies: React.FC = () => {
  return (
    <Box>
      <Typography variant="h4" gutterBottom sx={{ fontWeight: 'bold', mb: 3 }}>
        Policies
      </Typography>
      <Paper sx={{ p: 3 }}>
        <Typography color="text.secondary">
          Policy management UI will be implemented in Task 15
        </Typography>
      </Paper>
    </Box>
  );
};

export default Policies;
