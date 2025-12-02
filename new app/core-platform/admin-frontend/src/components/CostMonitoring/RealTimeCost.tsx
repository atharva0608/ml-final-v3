import React from 'react';
import { Typography, Paper } from '@mui/material';

const RealTimeCost: React.FC = () => {
  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h5">Real-Time Cost Monitoring</Typography>
      <Typography>Track costs vs predictions in real-time</Typography>
    </Paper>
  );
};

export default RealTimeCost;
