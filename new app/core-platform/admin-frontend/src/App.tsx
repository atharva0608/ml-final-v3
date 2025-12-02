import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme, CssBaseline, Box } from '@mui/material';
import Navigation from './components/Navigation';
import Overview from './components/Dashboard/Overview';
import ClusterList from './components/Clusters/ClusterList';
import LiveDashboard from './components/LiveMonitoring/LiveDashboard';
import RealTimeCost from './components/CostMonitoring/RealTimeCost';
import OptimizationHistory from './components/Optimization/OptimizationHistory';

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
    success: {
      main: '#2e7d32',
      dark: '#1b5e20',
    },
  },
});

const App: React.FC = () => {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <Box sx={{ display: 'flex' }}>
          <Navigation />
          <Box component="main" sx={{ flexGrow: 1, p: 3, mt: 8 }}>
            <Routes>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<Overview />} />
              <Route path="/clusters" element={<ClusterList />} />
              <Route path="/live-monitoring" element={<LiveDashboard />} />
              <Route path="/cost-monitoring" element={<RealTimeCost />} />
              <Route path="/optimization-history" element={<OptimizationHistory />} />
            </Routes>
          </Box>
        </Box>
      </Router>
    </ThemeProvider>
  );
};

export default App;
