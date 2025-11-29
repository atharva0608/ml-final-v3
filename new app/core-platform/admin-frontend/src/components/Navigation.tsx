import React from 'react';
import { Link as RouterLink, useLocation } from 'react-router-dom';
import {
  AppBar,
  Toolbar,
  Typography,
  Box,
  Button,
  Chip,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  Dashboard,
  Cloud,
  AttachMoney,
  Timeline,
  Speed,
  Warning,
  Notifications,
} from '@mui/icons-material';

const navItems = [
  { label: 'Dashboard', path: '/', icon: Dashboard },
  { label: 'Clusters', path: '/clusters', icon: Cloud },
  { label: 'Cost Monitor', path: '/cost', icon: AttachMoney },
  { label: 'Optimization', path: '/optimization', icon: Timeline },
  { label: 'Live', path: '/live', icon: Speed },
  { label: 'Spot Warnings', path: '/spot-warnings', icon: Warning },
];

export default function Navigation() {
  const location = useLocation();

  return (
    <AppBar position="fixed" sx={{ zIndex: (theme) => theme.zIndex.drawer + 1 }}>
      <Toolbar>
        <Box sx={{ display: 'flex', alignItems: 'center', flexGrow: 1 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, mr: 4 }}>
            CloudOptim
          </Typography>
          <Chip label="Agentless" size="small" color="success" sx={{ mr: 2 }} />
          <Box sx={{ display: 'flex', gap: 1 }}>
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <Button
                  key={item.path}
                  component={RouterLink}
                  to={item.path}
                  startIcon={<Icon />}
                  sx={{
                    color: isActive ? 'primary.main' : 'text.primary',
                    bgcolor: isActive ? 'primary.dark' : 'transparent',
                    '&:hover': {
                      bgcolor: 'primary.dark',
                    },
                  }}
                >
                  {item.label}
                </Button>
              );
            })}
          </Box>
        </Box>
        <Tooltip title="Notifications">
          <IconButton color="inherit">
            <Notifications />
          </IconButton>
        </Tooltip>
      </Toolbar>
    </AppBar>
  );
}
