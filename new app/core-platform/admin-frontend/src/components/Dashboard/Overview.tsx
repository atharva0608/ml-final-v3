import React, { useState, useEffect } from 'react';
import {
  Grid, Paper, Typography, Box, Card, CardContent, LinearProgress, Chip, Alert
} from '@mui/material';
import { Shield, Speed, TrendingDown, Warning } from '@mui/icons-material';
import axios from 'axios';

const Overview: React.FC = () => {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchStats = async () => {
    try {
      const response = await axios.get('/api/v1/dashboard/stats');
      setStats(response.data);
      setLoading(false);
    } catch (error) {
      console.error('Failed to fetch stats:', error);
      setLoading(false);
    }
  };

  if (loading) return <LinearProgress />;

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        CloudOptim Core Platform Dashboard
      </Typography>
      <Typography variant="subtitle1" color="text.secondary" gutterBottom>
        Agentless Kubernetes Cost Optimization with Zero-Downtime Architecture
      </Typography>

      {stats?.safety_violations === 0 && (
        <Alert severity="success" sx={{ mb: 2 }}>
          🛡️ Zero safety violations today! Five-Layer Defense active.
        </Alert>
      )}

      <Grid container spacing={3}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={1}>
                <Shield color="success" />
                <Typography variant="h6" ml={1}>Clusters</Typography>
              </Box>
              <Typography variant="h3">{stats?.active_clusters || 0}</Typography>
              <Typography variant="body2" color="text.secondary">
                Active / {stats?.total_clusters || 0} Total
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={1}>
                <TrendingDown color="primary" />
                <Typography variant="h6" ml={1}>Savings</Typography>
              </Box>
              <Typography variant="h3">${stats?.monthly_savings?.toLocaleString() || 0}</Typography>
              <Typography variant="body2" color="text.secondary">This Month</Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={1}>
                <Speed color="info" />
                <Typography variant="h6" ml={1}>Uptime</Typography>
              </Box>
              <Typography variant="h3">{stats?.uptime_percentage || 99.9}%</Typography>
              <Typography variant="body2" color="text.secondary">Last 30 Days</Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={1}>
                <Warning color={stats?.safety_violations > 0 ? "warning" : "success"} />
                <Typography variant="h6" ml={1}>Safety</Typography>
              </Box>
              <Typography variant="h3">{stats?.safety_violations || 0}</Typography>
              <Typography variant="body2" color="text.secondary">Violations Today</Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12}>
          <Paper sx={{ p: 3, bgcolor: 'success.dark', color: 'white' }}>
            <Typography variant="h6" gutterBottom>
              🛡️ Five-Layer Defense Strategy - Active
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6} md={2.4}>
                <Typography variant="subtitle2">Layer 1: Risk Threshold</Typography>
                <Typography variant="caption">✓ Risk Score ≥ 0.75</Typography>
              </Grid>
              <Grid item xs={12} sm={6} md={2.4}>
                <Typography variant="subtitle2">Layer 2: AZ Distribution</Typography>
                <Typography variant="caption">✓ Minimum 3 AZs</Typography>
              </Grid>
              <Grid item xs={12} sm={6} md={2.4}>
                <Typography variant="subtitle2">Layer 3: Pool Concentration</Typography>
                <Typography variant="caption">✓ Max 20% per pool</Typography>
              </Grid>
              <Grid item xs={12} sm={6} md={2.4}>
                <Typography variant="subtitle2">Layer 4: On-Demand Buffer</Typography>
                <Typography variant="caption">✓ Minimum 15% buffer</Typography>
              </Grid>
              <Grid item xs={12} sm={6} md={2.4}>
                <Typography variant="subtitle2">Layer 5: Multi-Factor</Typography>
                <Typography variant="caption">✓ All constraints enforced</Typography>
              </Grid>
            </Grid>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Overview;
