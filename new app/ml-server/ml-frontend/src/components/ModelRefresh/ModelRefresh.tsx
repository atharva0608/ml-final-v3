import React, { useState } from 'react';
import { Typography, Paper, Box, Button, Alert, CircularProgress } from '@mui/material';
import { Autorenew } from '@mui/icons-material';
import axios from 'axios';

const ModelRefresh: React.FC = () => {
  const [refreshing, setRefreshing] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const triggerRefresh = async () => {
    setRefreshing(true);
    setError(null);
    try {
      const response = await axios.post('/api/v1/models/refresh');
      setLastRefresh(new Date().toISOString());
      setRefreshing(false);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to refresh model');
      setRefreshing(false);
    }
  };

  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>Model Refresh</Typography>
      <Typography variant="body1" color="text.secondary" gutterBottom>
        Trigger model retraining with latest data
      </Typography>

      <Box mt={3}>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {lastRefresh && (
          <Alert severity="success" sx={{ mb: 2 }}>
            Model refresh completed at {new Date(lastRefresh).toLocaleString()}
          </Alert>
        )}

        <Button
          variant="contained"
          startIcon={refreshing ? <CircularProgress size={20} color="inherit" /> : <Autorenew />}
          onClick={triggerRefresh}
          disabled={refreshing}
          size="large"
        >
          {refreshing ? 'Refreshing Model...' : 'Trigger Model Refresh'}
        </Button>

        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          This will retrain all active models with the latest pricing and interruption data.
          Typically takes 5-10 minutes to complete.
        </Typography>
      </Box>
    </Paper>
  );
};

export default ModelRefresh;
