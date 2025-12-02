import React from 'react';
import {
  Box, ToggleButton, ToggleButtonGroup, Paper, Typography, Chip
} from '@mui/material';
import { Science, CloudQueue } from '@mui/icons-material';

export type AppMode = 'testing' | 'production';

interface ModeToggleProps {
  mode: AppMode;
  onModeChange: (mode: AppMode) => void;
}

const ModeToggle: React.FC<ModeToggleProps> = ({ mode, onModeChange }) => {
  const handleChange = (event: React.MouseEvent<HTMLElement>, newMode: AppMode | null) => {
    if (newMode !== null) {
      onModeChange(newMode);
    }
  };

  return (
    <Paper
      elevation={3}
      sx={{
        p: 2,
        mb: 3,
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        color: 'white'
      }}
    >
      <Box display="flex" justifyContent="space-between" alignItems="center">
        <Box>
          <Typography variant="h6">
            ML Server Mode
          </Typography>
          <Typography variant="body2" sx={{ opacity: 0.9 }}>
            {mode === 'testing'
              ? 'Standalone testing environment for model evaluation'
              : 'Production mode connected to Core Platform'}
          </Typography>
        </Box>

        <ToggleButtonGroup
          value={mode}
          exclusive
          onChange={handleChange}
          sx={{
            bgcolor: 'white',
            '& .MuiToggleButton-root': {
              px: 3,
              py: 1,
              border: 'none',
              '&.Mui-selected': {
                bgcolor: 'primary.main',
                color: 'white',
                '&:hover': {
                  bgcolor: 'primary.dark',
                },
              },
            },
          }}
        >
          <ToggleButton value="testing">
            <Science sx={{ mr: 1 }} />
            Testing Mode
          </ToggleButton>
          <ToggleButton value="production">
            <CloudQueue sx={{ mr: 1 }} />
            Production Mode
          </ToggleButton>
        </ToggleButtonGroup>
      </Box>

      <Box mt={2} display="flex" gap={1}>
        {mode === 'testing' && (
          <>
            <Chip
              label="Independent"
              size="small"
              sx={{ bgcolor: 'rgba(255,255,255,0.2)', color: 'white' }}
            />
            <Chip
              label="Model Upload"
              size="small"
              sx={{ bgcolor: 'rgba(255,255,255,0.2)', color: 'white' }}
            />
            <Chip
              label="Live Predictions"
              size="small"
              sx={{ bgcolor: 'rgba(255,255,255,0.2)', color: 'white' }}
            />
          </>
        )}
        {mode === 'production' && (
          <>
            <Chip
              label="Connected"
              size="small"
              sx={{ bgcolor: 'rgba(255,255,255,0.2)', color: 'white' }}
            />
            <Chip
              label="Core Platform Integration"
              size="small"
              sx={{ bgcolor: 'rgba(255,255,255,0.2)', color: 'white' }}
            />
            <Chip
              label="Customer Feedback Loop"
              size="small"
              sx={{ bgcolor: 'rgba(255,255,255,0.2)', color: 'white' }}
            />
          </>
        )}
      </Box>
    </Paper>
  );
};

export default ModeToggle;
