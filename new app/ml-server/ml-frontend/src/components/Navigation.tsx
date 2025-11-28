import React from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { AppBar, Toolbar, Typography, Box, Button } from '@mui/material';

export default function Navigation() {
  return (
    <AppBar position="fixed">
      <Toolbar>
        <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
          ML Server - CloudOptim
        </Typography>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button color="inherit" component={RouterLink} to="/">Dashboard</Button>
          <Button color="inherit" component={RouterLink} to="/models">Models</Button>
          <Button color="inherit" component={RouterLink} to="/gap-filler">Gap Filler</Button>
          <Button color="inherit" component={RouterLink} to="/pricing">Pricing Data</Button>
          <Button color="inherit" component={RouterLink} to="/refresh">Refresh</Button>
          <Button color="inherit" component={RouterLink} to="/predictions">Predictions</Button>
          <Button color="inherit" component={RouterLink} to="/engines">Engines</Button>
        </Box>
      </Toolbar>
    </AppBar>
  );
}
