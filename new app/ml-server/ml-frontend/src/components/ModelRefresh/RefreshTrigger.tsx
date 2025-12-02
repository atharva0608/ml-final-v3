import React, { useState } from 'react';
import { Typography, Paper, Box, Button, Alert } from '@mui/material';
import { Refresh } from '@mui/icons-material';
import axios from 'axios';

const RefreshTrigger: React.FC = () => {
  const [refreshing, setRefreshing] = useState(false);
  const [message, setMessage] = useState('');

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await axios.post('/api/v1/ml/models/refresh');
      setMessage('Model refresh started successfully!');
    } catch (error) {
      setMessage('Failed to start refresh');
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>Model Refresh</Typography>
      <Typography paragraph>
        Trigger model refresh to update predictions with latest pricing data
      </Typography>
      <Button
        variant="contained"
        startIcon={<Refresh />}
        onClick={handleRefresh}
        disabled={refreshing}
      >
        Refresh Models
      </Button>
      {message && <Alert severity="info" sx={{ mt: 2 }}>{message}</Alert>}
    </Paper>
  );
};

export default RefreshTrigger;
