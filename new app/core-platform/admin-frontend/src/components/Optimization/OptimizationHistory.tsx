import React from 'react';
import { Typography, Paper } from '@mui/material';

const OptimizationHistory: React.FC = () => {
  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h5">Optimization History</Typography>
      <Typography>View past optimization decisions and outcomes</Typography>
    </Paper>
  );
};

export default OptimizationHistory;
