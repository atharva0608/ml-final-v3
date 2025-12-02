import React, { useState, useEffect } from 'react';
import { Typography, Paper, Box, Grid, Card, CardContent, Chip } from '@mui/material';
import { TrendingUp, TrendingDown } from '@mui/icons-material';
import axios from 'axios';

interface Prediction {
  instance_type: string;
  availability_zone: string;
  predicted_price: number;
  current_price: number;
  price_trend: 'up' | 'down' | 'stable';
  interruption_risk: number;
  recommendation: string;
}

const LivePredictions: React.FC = () => {
  const [predictions, setPredictions] = useState<Prediction[]>([]);

  useEffect(() => {
    fetchPredictions();
    const interval = setInterval(fetchPredictions, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchPredictions = async () => {
    try {
      const response = await axios.get('/api/v1/predictions/live');
      setPredictions(response.data.predictions || []);
    } catch (error) {
      console.error('Failed to fetch predictions:', error);
    }
  };

  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>Live Predictions</Typography>
      <Typography variant="body2" color="text.secondary" gutterBottom>
        Real-time price and risk predictions
      </Typography>

      <Grid container spacing={2} sx={{ mt: 2 }}>
        {predictions.map((pred, idx) => (
          <Grid item xs={12} md={6} lg={4} key={idx}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  {pred.instance_type}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {pred.availability_zone}
                </Typography>

                <Box mt={2}>
                  <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Typography variant="body2">Current:</Typography>
                    <Typography variant="h6">${pred.current_price.toFixed(4)}</Typography>
                  </Box>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mt={1}>
                    <Typography variant="body2">Predicted:</Typography>
                    <Box display="flex" alignItems="center">
                      <Typography variant="h6" mr={1}>${pred.predicted_price.toFixed(4)}</Typography>
                      {pred.price_trend === 'up' && <TrendingUp color="error" />}
                      {pred.price_trend === 'down' && <TrendingDown color="success" />}
                    </Box>
                  </Box>

                  <Box mt={2}>
                    <Typography variant="body2" gutterBottom>Interruption Risk:</Typography>
                    <Chip
                      label={`${(pred.interruption_risk * 100).toFixed(1)}%`}
                      color={pred.interruption_risk > 0.75 ? 'error' : pred.interruption_risk > 0.5 ? 'warning' : 'success'}
                      size="small"
                    />
                  </Box>

                  <Typography variant="body2" sx={{ mt: 2 }} color="text.secondary">
                    {pred.recommendation}
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Paper>
  );
};

export default LivePredictions;
