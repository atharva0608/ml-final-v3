import React from 'react';
import { Typography, Paper, Box, Grid, Alert } from '@mui/material';

const LiveDashboard: React.FC = () => {
  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>Live Monitoring</Typography>
      <Grid container spacing={2}>
        <Grid item xs={12}>
          <Alert severity="info">
            Real-time Spot interruption warnings and cluster health monitoring
          </Alert>
        </Grid>
      </Grid>
    </Paper>
  );
};

export default LiveDashboard;
