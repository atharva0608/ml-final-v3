import React, { useState, useEffect } from 'react';
import {
  Grid, Paper, Typography, Box, Card, CardContent,
  LinearProgress, Chip, Alert
} from '@mui/material';
import {
  TrendingUp, Speed, Shield, GroupWork, Assessment
} from '@mui/icons-material';
import axios from 'axios';

interface DashboardStats {
  total_models: number;
  active_models: number;
  total_predictions_today: number;
  avg_response_time_ms: number;
  feedback_weight: number;
  total_instance_hours: number;
  safety_violations_today: number;
  cross_client_patterns_detected: number;
}

const Overview: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  const fetchStats = async () => {
    try {
      const response = await axios.get('/api/v1/ml/dashboard/stats');
      setStats(response.data);
      setLoading(false);
    } catch (error) {
      console.error('Failed to fetch stats:', error);
      setLoading(false);
    }
  };

  if (loading) {
    return <LinearProgress />;
  }

  const feedbackProgress = stats ? (stats.total_instance_hours / 500000) * 100 : 0;
  const moatAchieved = feedbackProgress >= 100;

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        CloudOptim ML Server Dashboard
      </Typography>
      <Typography variant="subtitle1" color="text.secondary" gutterBottom>
        Revolutionary Zero-Downtime Architecture with Cross-Client Learning
      </Typography>

      {moatAchieved && (
        <Alert severity="success" sx={{ mb: 2 }}>
          🎯 COMPETITIVE MOAT ACHIEVED! 500K+ instance-hours collected.
          Risk prediction accuracy: ~85%
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Models Stats */}
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={1}>
                <Assessment color="primary" />
                <Typography variant="h6" ml={1}>Models</Typography>
              </Box>
              <Typography variant="h3">{stats?.active_models || 0}</Typography>
              <Typography variant="body2" color="text.secondary">
                Active / {stats?.total_models || 0} Total
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Predictions Today */}
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={1}>
                <TrendingUp color="success" />
                <Typography variant="h6" ml={1}>Predictions</Typography>
              </Box>
              <Typography variant="h3">
                {stats?.total_predictions_today?.toLocaleString() || 0}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Today
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Response Time */}
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={1}>
                <Speed color="info" />
                <Typography variant="h6" ml={1}>Response Time</Typography>
              </Box>
              <Typography variant="h3">{stats?.avg_response_time_ms || 0}ms</Typography>
              <Typography variant="body2" color="text.secondary">
                Average
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Safety Violations */}
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={1}>
                <Shield color={stats?.safety_violations_today === 0 ? 'success' : 'warning'} />
                <Typography variant="h6" ml={1}>Safety</Typography>
              </Box>
              <Typography variant="h3">{stats?.safety_violations_today || 0}</Typography>
              <Typography variant="body2" color="text.secondary">
                Violations Today
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Customer Feedback Loop - Competitive Moat */}
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              🏆 Customer Feedback Loop - Competitive Moat Progress
            </Typography>
            <Box mb={2}>
              <Box display="flex" justifyContent="space-between" mb={1}>
                <Typography variant="body2">
                  Current Weight: {((stats?.feedback_weight || 0) * 100).toFixed(1)}%
                </Typography>
                <Typography variant="body2">
                  {stats?.total_instance_hours?.toLocaleString() || 0} / 500,000 instance-hours
                </Typography>
              </Box>
              <LinearProgress
                variant="determinate"
                value={Math.min(feedbackProgress, 100)}
                sx={{ height: 10, borderRadius: 5 }}
              />
            </Box>

            <Grid container spacing={2}>
              <Grid item xs={6} sm={3}>
                <Chip
                  label="Month 1 (0%)"
                  color={feedbackProgress > 2 ? 'success' : 'default'}
                  size="small"
                />
                <Typography variant="caption" display="block">0-10K hours</Typography>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Chip
                  label="Month 3 (10%)"
                  color={feedbackProgress > 10 ? 'success' : 'default'}
                  size="small"
                />
                <Typography variant="caption" display="block">10K-50K hours</Typography>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Chip
                  label="Month 6 (15%)"
                  color={feedbackProgress > 40 ? 'success' : 'default'}
                  size="small"
                />
                <Typography variant="caption" display="block">50K-200K hours</Typography>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Chip
                  label="Month 12+ (25%)"
                  color={moatAchieved ? 'success' : 'default'}
                  size="small"
                />
                <Typography variant="caption" display="block">500K+ hours 🎯</Typography>
              </Grid>
            </Grid>
          </Paper>
        </Grid>

        {/* Cross-Client Pattern Detection */}
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 3, height: '100%' }}>
            <Box display="flex" alignItems="center" mb={2}>
              <GroupWork color="secondary" fontSize="large" />
              <Box ml={2}>
                <Typography variant="h6">Cross-Client Learning</Typography>
                <Typography variant="body2" color="text.secondary">
                  Network Effect Active
                </Typography>
              </Box>
            </Box>
            <Typography variant="h3" color="secondary.main">
              {stats?.cross_client_patterns_detected || 0}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Patterns Detected Today
            </Typography>
            <Typography variant="caption" display="block" mt={2}>
              Proactive rebalancing protecting all clients from risky pools
            </Typography>
          </Paper>
        </Grid>

        {/* Revolutionary Features Summary */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3, bgcolor: 'primary.dark', color: 'white' }}>
            <Typography variant="h6" gutterBottom>
              ⚡ Revolutionary Features Active
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6} md={3}>
                <Typography variant="subtitle2">Five-Layer Defense</Typography>
                <Typography variant="caption">
                  ✓ Risk ≥0.75 • ✓ 3+ AZs • ✓ Pool ≤20% • ✓ On-Demand ≥15%
                </Typography>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Typography variant="subtitle2">Adaptive Risk Scoring</Typography>
                <Typography variant="caption">
                  {((stats?.feedback_weight || 0) * 100).toFixed(0)}% Customer +
                  {(60 - (stats?.feedback_weight || 0) * 100).toFixed(0)}% AWS Spot Advisor
                </Typography>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Typography variant="subtitle2">Hybrid Rightsizing</Typography>
                <Typography variant="caption">
                  Day Zero ready • ML-enhanced Month 3+
                </Typography>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Typography variant="subtitle2">Cross-Client Patterns</Typography>
                <Typography variant="caption">
                  2 clients → UNCERTAIN • 3+ → Proactive Rebalance
                </Typography>
              </Grid>
            </Grid>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Overview;
