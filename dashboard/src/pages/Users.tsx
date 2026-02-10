import React from 'react';
import { Box, Typography, Paper } from '@mui/material';

const Users: React.FC = () => {
  return (
    <Box>
      <Typography variant="h4" gutterBottom sx={{ fontWeight: 'bold', mb: 3 }}>
        User Management
      </Typography>
      <Paper sx={{ p: 3 }}>
        <Typography color="text.secondary">
          User management UI will be implemented in a future task
        </Typography>
      </Paper>
    </Box>
  );
};

export default Users;
