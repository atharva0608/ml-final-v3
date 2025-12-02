import React, { useState, useEffect } from 'react';
import { Typography, Paper, Box, LinearProgress, Alert, Button } from '@mui/material';
import axios from 'axios';

const DataGapFiller: React.FC = () => {
  const [gaps, setGaps] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchGaps();
  }, []);

  const fetchGaps = async () => {
    try {
      const response = await axios.get('/api/v1/data-gaps/analyze');
      setGaps(response.data);
      setLoading(false);
    } catch (error) {
      console.error('Failed to fetch data gaps:', error);
      setLoading(false);
    }
  };

  const fillGaps = async () => {
    setLoading(true);
    try {
      await axios.post('/api/v1/data-gaps/fill');
      fetchGaps();
    } catch (error) {
      console.error('Failed to fill gaps:', error);
      setLoading(false);
    }
  };

  if (loading) return <LinearProgress />;

  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>Data Gap Filler</Typography>
      <Typography variant="body1" color="text.secondary" gutterBottom>
        Detect and fill missing data points in training datasets
      </Typography>

      {gaps && (
        <Box mt={3}>
          <Alert severity={gaps.gaps_found > 0 ? 'warning' : 'success'} sx={{ mb: 2 }}>
            {gaps.gaps_found > 0
              ? `Found ${gaps.gaps_found} gaps in data`
              : 'No data gaps detected - dataset is complete'}
          </Alert>

          {gaps.gaps_found > 0 && (
            <Button variant="contained" onClick={fillGaps}>
              Fill Gaps with Interpolation
            </Button>
          )}

          <Box mt={2}>
            <Typography variant="body2">
              Total Records: {gaps.total_records || 0}
            </Typography>
            <Typography variant="body2">
              Complete Records: {gaps.complete_records || 0}
            </Typography>
            <Typography variant="body2">
              Completion Rate: {gaps.completion_rate ? `${(gaps.completion_rate * 100).toFixed(2)}%` : '-'}
            </Typography>
          </Box>
        </Box>
      )}
    </Paper>
  );
};

export default DataGapFiller;
