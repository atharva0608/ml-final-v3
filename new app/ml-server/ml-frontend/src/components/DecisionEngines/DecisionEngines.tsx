import React, { useState, useEffect } from 'react';
import { Typography, Paper, Box, Grid, Card, CardContent, Switch, FormControlLabel, Alert } from '@mui/material';
import axios from 'axios';

interface DecisionEngine {
  engine_id: string;
  name: string;
  description: string;
  enabled: boolean;
  priority: number;
}

const DecisionEngines: React.FC = () => {
  const [engines, setEngines] = useState<DecisionEngine[]>([]);

  useEffect(() => {
    fetchEngines();
  }, []);

  const fetchEngines = async () => {
    try {
      const response = await axios.get('/api/v1/decision-engines');
      setEngines(response.data.engines || []);
    } catch (error) {
      console.error('Failed to fetch decision engines:', error);
    }
  };

  const toggleEngine = async (engineId: string, enabled: boolean) => {
    try {
      await axios.patch(`/api/v1/decision-engines/${engineId}`, { enabled: !enabled });
      fetchEngines();
    } catch (error) {
      console.error('Failed to toggle engine:', error);
    }
  };

  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>Decision Engines</Typography>
      <Typography variant="body2" color="text.secondary" gutterBottom>
        Configure and manage decision-making engines
      </Typography>

      <Alert severity="info" sx={{ mt: 2, mb: 3 }}>
        Decision engines work in priority order to determine optimal instance placement and cost optimization strategies.
      </Alert>

      <Grid container spacing={2}>
        {engines.map((engine) => (
          <Grid item xs={12} md={6} key={engine.engine_id}>
            <Card>
              <CardContent>
                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Box>
                    <Typography variant="h6">{engine.name}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {engine.description}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Priority: {engine.priority}
                    </Typography>
                  </Box>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={engine.enabled}
                        onChange={() => toggleEngine(engine.engine_id, engine.enabled)}
                      />
                    }
                    label={engine.enabled ? 'On' : 'Off'}
                  />
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Paper>
  );
};

export default DecisionEngines;
