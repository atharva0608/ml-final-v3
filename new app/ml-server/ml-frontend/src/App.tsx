import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Box from '@mui/material/Box';

// Components
import Navigation from './components/Navigation';
import Dashboard from './components/Dashboard/Overview';
import ModelManagement from './components/ModelManagement/ModelList';
import DataGapFiller from './components/DataGapFiller/GapAnalyzer';
import PricingDataViewer from './components/PricingData/SpotPriceViewer';
import ModelRefresh from './components/ModelRefresh/RefreshTrigger';
import LivePredictions from './components/LivePredictions/PredictionChart';
import DecisionEngines from './components/DecisionEngines/EngineList';

// Theme
const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
  },
});

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ display: 'flex' }}>
        <Navigation />
        <Box component="main" sx={{ flexGrow: 1, p: 3, mt: 8 }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/models" element={<ModelManagement />} />
            <Route path="/gap-filler" element={<DataGapFiller />} />
            <Route path="/pricing" element={<PricingDataViewer />} />
            <Route path="/refresh" element={<ModelRefresh />} />
            <Route path="/predictions" element={<LivePredictions />} />
            <Route path="/engines" element={<DecisionEngines />} />
          </Routes>
        </Box>
      </Box>
    </ThemeProvider>
  );
}

export default App;
