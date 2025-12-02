import React, { useState, useEffect } from 'react';
import {
  Typography, Paper, Box, Grid, Card, CardContent, Button,
  Select, MenuItem, FormControl, InputLabel, Alert, LinearProgress,
  Switch, FormControlLabel, Chip
} from '@mui/material';
import { CloudUpload, PlayArrow, Stop } from '@mui/icons-material';
import axios from 'axios';
import PredictionChart from './PredictionChart';

interface TestingConfig {
  modelFile: File | null;
  instanceType: string;
  availabilityZone: string;
  region: string;
}

const INSTANCE_TYPES = ['t3.medium', 't3.large', 't3.xlarge', 't3.2xlarge'];
const AVAILABILITY_ZONES = ['ap-south-1a', 'ap-south-1b', 'ap-south-1c'];

const TestingDashboard: React.FC = () => {
  const [config, setConfig] = useState<TestingConfig>({
    modelFile: null,
    instanceType: 't3.medium',
    availabilityZone: 'ap-south-1a',
    region: 'ap-south-1'
  });

  const [isRunning, setIsRunning] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file && file.name.endsWith('.pkl')) {
      setConfig({ ...config, modelFile: file });
      setError(null);
    } else {
      setError('Please upload a valid .pkl model file');
    }
  };

  const startTesting = async () => {
    if (!config.modelFile) {
      setError('Please upload a model file first');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Upload model
      const formData = new FormData();
      formData.append('model_file', config.modelFile);
      formData.append('instance_type', config.instanceType);
      formData.append('availability_zone', config.availabilityZone);
      formData.append('region', config.region);

      const response = await axios.post('/api/v1/testing/start-session', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      setSessionId(response.data.session_id);
      setIsRunning(true);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to start testing session');
    } finally {
      setLoading(false);
    }
  };

  const stopTesting = async () => {
    if (!sessionId) return;

    try {
      await axios.post(`/api/v1/testing/stop-session/${sessionId}`);
      setIsRunning(false);
      setSessionId(null);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to stop testing session');
    }
  };

  return (
    <Box>
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Typography variant="h5">Testing Mode - Standalone ML Server</Typography>
          <Chip
            label={isRunning ? "Testing Active" : "Ready"}
            color={isRunning ? "success" : "default"}
          />
        </Box>

        <Alert severity="info" sx={{ mb: 3 }}>
          Testing mode works independently from production. Upload a model, select instance configuration,
          and visualize predictions with 3 days of historical data + live predictions.
        </Alert>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <Grid container spacing={3}>
          {/* Model Upload */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>1. Upload Model</Typography>
                <Button
                  variant="outlined"
                  component="label"
                  fullWidth
                  startIcon={<CloudUpload />}
                  disabled={isRunning}
                >
                  {config.modelFile ? config.modelFile.name : 'Select Model File (.pkl)'}
                  <input
                    type="file"
                    hidden
                    accept=".pkl"
                    onChange={handleFileUpload}
                    disabled={isRunning}
                  />
                </Button>
              </CardContent>
            </Card>
          </Grid>

          {/* Instance Configuration */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>2. Configure Instance</Typography>

                <FormControl fullWidth sx={{ mb: 2 }}>
                  <InputLabel>Instance Type</InputLabel>
                  <Select
                    value={config.instanceType}
                    onChange={(e) => setConfig({ ...config, instanceType: e.target.value })}
                    disabled={isRunning}
                  >
                    {INSTANCE_TYPES.map(type => (
                      <MenuItem key={type} value={type}>{type}</MenuItem>
                    ))}
                  </Select>
                </FormControl>

                <FormControl fullWidth>
                  <InputLabel>Availability Zone</InputLabel>
                  <Select
                    value={config.availabilityZone}
                    onChange={(e) => setConfig({ ...config, availabilityZone: e.target.value })}
                    disabled={isRunning}
                  >
                    {AVAILABILITY_ZONES.map(az => (
                      <MenuItem key={az} value={az}>{az}</MenuItem>
                    ))}
                  </Select>
                </FormControl>

                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                  Region: Mumbai (ap-south-1)
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          {/* Control Buttons */}
          <Grid item xs={12}>
            <Box display="flex" gap={2}>
              {!isRunning ? (
                <Button
                  variant="contained"
                  size="large"
                  startIcon={<PlayArrow />}
                  onClick={startTesting}
                  disabled={loading || !config.modelFile}
                >
                  {loading ? 'Starting...' : 'Start Testing'}
                </Button>
              ) : (
                <Button
                  variant="contained"
                  color="error"
                  size="large"
                  startIcon={<Stop />}
                  onClick={stopTesting}
                >
                  Stop Testing
                </Button>
              )}
            </Box>
          </Grid>
        </Grid>

        {loading && <LinearProgress sx={{ mt: 2 }} />}
      </Paper>

      {/* Prediction Chart */}
      {isRunning && sessionId && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Prediction Visualization
          </Typography>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Historical data (3 days) + Live predictions
          </Typography>
          <PredictionChart sessionId={sessionId} config={config} />
        </Paper>
      )}
    </Box>
  );
};

export default TestingDashboard;
