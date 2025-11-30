/**
 * Feature Toggles Component
 *
 * Toggle advanced decision engine features on/off
 * Features:
 * - IPv4 Cost Tracker
 * - Container Image Bloat Analyzer
 * - Shadow IT Tracker
 * - Noisy Neighbor Detector
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Switch,
  FormControlLabel,
  Grid,
  Chip,
  IconButton,
  Tooltip,
  Alert,
  AlertTitle,
  Divider,
  CircularProgress
} from '@mui/material';
import {
  Info as InfoIcon,
  Public as PublicIcon,
  Image as ImageIcon,
  Search as SearchIcon,
  NetworkCheck as NetworkIcon,
  TrendingUp as TrendingUpIcon
} from '@mui/icons-material';

interface FeatureConfig {
  enabled: boolean;
  description: string;
  auto_scan_interval_hours?: number;
  bloat_threshold_mb?: number;
  min_age_days?: number;
  bandwidth_outlier_multiplier?: number;
}

interface FeatureToggles {
  ipv4_cost_tracking: FeatureConfig;
  image_bloat_analysis: FeatureConfig;
  shadow_it_detection: FeatureConfig;
  noisy_neighbor_detection: FeatureConfig;
}

const FEATURE_METADATA = {
  ipv4_cost_tracking: {
    name: 'IPv4 Cost Tracker',
    icon: <PublicIcon />,
    color: '#1976d2',
    badge: 'NEW',
    highlight: 'First-to-market',
    savings: '$500-2000/year',
    description: 'Track public IPv4 costs (AWS charges $0.005/hr since Feb 2024)'
  },
  image_bloat_analysis: {
    name: 'Container Image Bloat Tax',
    icon: <ImageIcon />,
    color: '#f57c00',
    badge: 'VIRAL',
    highlight: 'Unique insight',
    savings: '10-40% transfer costs',
    description: 'Detect oversized container images and calculate bloat tax'
  },
  shadow_it_detection: {
    name: 'Shadow IT Tracker',
    icon: <SearchIcon />,
    color: '#7b1fa2',
    badge: 'HIDDEN COSTS',
    highlight: '10-30% hidden waste',
    savings: '$150-750/month',
    description: 'Find AWS resources NOT managed by Kubernetes'
  },
  noisy_neighbor_detection: {
    name: 'Noisy Neighbor Detector',
    icon: <NetworkIcon />,
    color: '#c62828',
    badge: 'PERFORMANCE',
    highlight: 'Cost + Speed',
    savings: '60% network cost reduction',
    description: 'Detect pods causing excessive network traffic'
  }
};

export const FeatureTog gles: React.FC = () => {
  const [features, setFeatures] = useState<FeatureToggles | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Load feature toggles from backend
  useEffect(() => {
    fetchFeatureToggles();
  }, []);

  const fetchFeatureToggles = async () => {
    try {
      setLoading(true);
      const response = await fetch('http://localhost:8001/api/v1/ml/features/toggles');

      if (!response.ok) {
        throw new Error('Failed to fetch feature toggles');
      }

      const data = await response.json();
      setFeatures(data.feature_toggles);
      setError(null);
    } catch (err) {
      console.error('Error fetching feature toggles:', err);
      setError('Failed to load feature toggles');

      // Use default config if API fails
      setFeatures({
        ipv4_cost_tracking: {
          enabled: true,
          description: FEATURE_METADATA.ipv4_cost_tracking.description,
          auto_scan_interval_hours: 24
        },
        image_bloat_analysis: {
          enabled: true,
          description: FEATURE_METADATA.image_bloat_analysis.description,
          auto_scan_interval_hours: 168,
          bloat_threshold_mb: 500
        },
        shadow_it_detection: {
          enabled: true,
          description: FEATURE_METADATA.shadow_it_detection.description,
          auto_scan_interval_hours: 24,
          min_age_days: 7
        },
        noisy_neighbor_detection: {
          enabled: true,
          description: FEATURE_METADATA.noisy_neighbor_detection.description,
          auto_scan_interval_hours: 6,
          bandwidth_outlier_multiplier: 10
        }
      });
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = async (featureKey: keyof FeatureToggles) => {
    if (!features) return;

    const newEnabled = !features[featureKey].enabled;

    // Optimistic update
    setFeatures({
      ...features,
      [featureKey]: {
        ...features[featureKey],
        enabled: newEnabled
      }
    });

    try {
      setSaving(true);
      const response = await fetch(`http://localhost:8001/api/v1/ml/features/toggles/${featureKey}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          enabled: newEnabled
        })
      });

      if (!response.ok) {
        throw new Error('Failed to update feature toggle');
      }

      setSuccessMessage(
        `${FEATURE_METADATA[featureKey].name} ${newEnabled ? 'enabled' : 'disabled'} successfully`
      );
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      console.error('Error updating feature toggle:', err);
      setError('Failed to update feature toggle');

      // Revert optimistic update
      setFeatures({
        ...features,
        [featureKey]: {
          ...features[featureKey],
          enabled: !newEnabled
        }
      });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  if (!features) {
    return (
      <Alert severity="error">
        <AlertTitle>Error</AlertTitle>
        Failed to load feature toggles. Please refresh the page.
      </Alert>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <TrendingUpIcon fontSize="large" />
        Advanced Features
      </Typography>

      <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
        Enable or disable advanced decision engines. These features provide unique cost optimization insights
        that go beyond standard Kubernetes optimization.
      </Typography>

      {successMessage && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccessMessage(null)}>
          {successMessage}
        </Alert>
      )}

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3}>
        {(Object.keys(features) as Array<keyof FeatureToggles>).map((featureKey) => {
          const feature = features[featureKey];
          const metadata = FEATURE_METADATA[featureKey];

          return (
            <Grid item xs={12} md={6} key={featureKey}>
              <Card
                sx={{
                  height: '100%',
                  border: feature.enabled ? `2px solid ${metadata.color}` : '1px solid #e0e0e0',
                  transition: 'all 0.3s ease'
                }}
              >
                <CardContent>
                  <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
                    <Box display="flex" alignItems="center" gap={1}>
                      <Box sx={{ color: metadata.color }}>
                        {metadata.icon}
                      </Box>
                      <Typography variant="h6">
                        {metadata.name}
                      </Typography>
                    </Box>
                    <Box display="flex" gap={1}>
                      <Chip
                        label={metadata.badge}
                        size="small"
                        sx={{
                          bgcolor: metadata.color,
                          color: 'white',
                          fontWeight: 'bold'
                        }}
                      />
                      <Tooltip title={feature.description}>
                        <IconButton size="small">
                          <InfoIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </Box>
                  </Box>

                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    {feature.description}
                  </Typography>

                  <Divider sx={{ my: 2 }} />

                  <Box sx={{ mb: 2 }}>
                    <Typography variant="caption" color="text.secondary" display="block">
                      <strong>Value:</strong> {metadata.highlight}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" display="block">
                      <strong>Savings:</strong> {metadata.savings}
                    </Typography>
                    {feature.auto_scan_interval_hours && (
                      <Typography variant="caption" color="text.secondary" display="block">
                        <strong>Auto-scan:</strong> Every {feature.auto_scan_interval_hours}h
                      </Typography>
                    )}
                  </Box>

                  <Divider sx={{ my: 2 }} />

                  <Box display="flex" justifyContent="space-between" alignItems="center">
                    <FormControlLabel
                      control={
                        <Switch
                          checked={feature.enabled}
                          onChange={() => handleToggle(featureKey)}
                          disabled={saving}
                          sx={{
                            '& .MuiSwitch-switchBase.Mui-checked': {
                              color: metadata.color,
                            },
                            '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                              backgroundColor: metadata.color,
                            },
                          }}
                        />
                      }
                      label={
                        <Typography variant="body2" fontWeight={feature.enabled ? 'bold' : 'normal'}>
                          {feature.enabled ? 'Enabled' : 'Disabled'}
                        </Typography>
                      }
                    />
                    {feature.enabled && (
                      <Chip
                        label="Active"
                        size="small"
                        color="success"
                        variant="outlined"
                      />
                    )}
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          );
        })}
      </Grid>

      <Box sx={{ mt: 4, p: 2, bgcolor: '#f5f5f5', borderRadius: 1 }}>
        <Typography variant="body2" color="text.secondary">
          <strong>Note:</strong> All features use publicly available data and require no customer data collection.
          Features can be toggled on/off at any time without affecting existing optimization engines.
        </Typography>
      </Box>
    </Box>
  );
};

export default FeatureToggles;
