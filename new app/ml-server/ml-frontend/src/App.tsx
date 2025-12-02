import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme, CssBaseline, Box } from '@mui/material';
import Navigation from './components/Navigation';
import Overview from './components/Dashboard/Overview';
import ModelList from './components/ModelManagement/ModelList';
import DataGapFiller from './components/DataGapFiller/DataGapFiller';
import PricingData from './components/PricingData/PricingData';
import ModelRefresh from './components/ModelRefresh/ModelRefresh';
import LivePredictions from './components/LivePredictions/LivePredictions';
import DecisionEngines from './components/DecisionEngines/DecisionEngines';

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
              <Route path="/models" element={<ModelList />} />
              <Route path="/data-gap-filler" element={<DataGapFiller />} />
              <Route path="/pricing-data" element={<PricingData />} />
              <Route path="/model-refresh" element={<ModelRefresh />} />
              <Route path="/live-predictions" element={<LivePredictions />} />
              <Route path="/decision-engines" element={<DecisionEngines />} />
            </Routes>
          </Box>
        </Box>
      </Router>
    </ThemeProvider>
  );
};

export default App;
