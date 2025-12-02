import React from 'react';
import { Typography, Paper, Box } from '@mui/material';

const PredictionChart: React.FC = () => {
  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>Live Predictions</Typography>
      <Typography>Real-time prediction charts and accuracy metrics</Typography>
    </Paper>
  );
};

export default PredictionChart;
