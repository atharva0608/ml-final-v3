import React from 'react';
import { Typography, Paper, Box } from '@mui/material';

const SpotPriceViewer: React.FC = () => {
  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>Spot Price Viewer</Typography>
      <Typography>View historical Spot pricing data and trends</Typography>
    </Paper>
  );
};

export default SpotPriceViewer;
