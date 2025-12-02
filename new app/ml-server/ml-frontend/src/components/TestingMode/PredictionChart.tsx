import React, { useState, useEffect } from 'react';
import { Box, Typography, Alert, CircularProgress } from '@mui/material';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine
} from 'recharts';
import axios from 'axios';

interface PredictionData {
  timestamp: string;
  actual_price: number | null;
  predicted_price: number;
  is_historical: boolean;
}

interface PredictionChartProps {
  sessionId: string;
  config: {
    instanceType: string;
    availabilityZone: string;
    region: string;
  };
}

const PredictionChart: React.FC<PredictionChartProps> = ({ sessionId, config }) => {
  const [data, setData] = useState<PredictionData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000); // Update every 30 seconds
    return () => clearInterval(interval);
  }, [sessionId]);

  const fetchData = async () => {
    try {
      const response = await axios.get(`/api/v1/testing/predictions/${sessionId}`);
      setData(response.data.predictions);
      setLoading(false);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to fetch predictions');
      setLoading(false);
    }
  };

  if (loading && data.length === 0) {
    return (
      <Box display="flex" justifyContent="center" p={4}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error">{error}</Alert>
    );
  }

  // Find the boundary between historical and live data
  const nowIndex = data.findIndex(d => !d.is_historical);
  const nowTimestamp = nowIndex >= 0 ? data[nowIndex].timestamp : null;

  return (
    <Box>
      <Box display="flex" gap={2} mb={2}>
        <Box display="flex" alignItems="center" gap={1}>
          <Box sx={{ width: 12, height: 12, bgcolor: '#8884d8', borderRadius: '50%' }} />
          <Typography variant="caption">Actual Price</Typography>
        </Box>
        <Box display="flex" alignItems="center" gap={1}>
          <Box sx={{ width: 12, height: 12, bgcolor: '#82ca9d', borderRadius: '50%' }} />
          <Typography variant="caption">Predicted Price</Typography>
        </Box>
        <Box display="flex" alignItems="center" gap={1}>
          <Box sx={{ width: 2, height: 12, bgcolor: '#ff7300' }} />
          <Typography variant="caption">Current Time</Typography>
        </Box>
      </Box>

      <ResponsiveContainer width="100%" height={400}>
        <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="timestamp"
            tickFormatter={(value) => {
              const date = new Date(value);
              return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}:00`;
            }}
          />
          <YAxis
            label={{ value: 'Price ($/hour)', angle: -90, position: 'insideLeft' }}
            domain={['auto', 'auto']}
          />
          <Tooltip
            labelFormatter={(value) => new Date(value).toLocaleString()}
            formatter={(value: any) => [`$${value.toFixed(4)}`, '']}
          />
          <Legend />

          {/* Reference line for "now" */}
          {nowTimestamp && (
            <ReferenceLine
              x={nowTimestamp}
              stroke="#ff7300"
              strokeWidth={2}
              label={{ value: 'Now', position: 'top' }}
            />
          )}

          {/* Actual price (only for historical data) */}
          <Line
            type="monotone"
            dataKey="actual_price"
            stroke="#8884d8"
            strokeWidth={2}
            dot={false}
            name="Actual Price"
            connectNulls={false}
          />

          {/* Predicted price */}
          <Line
            type="monotone"
            dataKey="predicted_price"
            stroke="#82ca9d"
            strokeWidth={2}
            dot={false}
            name="Predicted Price"
            strokeDasharray={nowIndex >= 0 ? undefined : "5 5"}
          />
        </LineChart>
      </ResponsiveContainer>

      <Box mt={2}>
        <Typography variant="body2" color="text.secondary">
          Instance: {config.instanceType} | AZ: {config.availabilityZone} | Region: {config.region}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Showing {data.filter(d => d.is_historical).length} hours of historical data
          and {data.filter(d => !d.is_historical).length} hours of predictions
        </Typography>
      </Box>
    </Box>
  );
};

export default PredictionChart;
