import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Box from '@mui/material/Box';
import { QueryClient, QueryClientProvider } from 'react-query';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

// Components
import Navigation from './components/Navigation';
import Dashboard from './components/Dashboard/Overview';
import ClusterList from './components/Clusters/ClusterList';
import ClusterDetails from './components/Clusters/ClusterDetails';
import CostMonitoring from './components/CostMonitoring/RealTimeCost';
import PredictionComparison from './components/CostMonitoring/PredictionComparison';
import OptimizationHistory from './components/Optimization/OptimizationHistory';
import LiveMonitoring from './components/LiveMonitoring/LiveDashboard';
import SpotWarnings from './components/LiveMonitoring/SpotWarnings';

// Enhanced dark theme for better UX
const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#00C853',  // Green for savings/success
      light: '#5EFC82',
      dark: '#009624',
    },
    secondary: {
      main: '#2196F3',  // Blue for actions
      light: '#6EC6FF',
      dark: '#0069C0',
    },
    error: {
      main: '#FF5252',
    },
    warning: {
      main: '#FFC107',
    },
    success: {
      main: '#00E676',
    },
    background: {
      default: '#0A1929',
      paper: '#132F4C',
    },
    text: {
      primary: '#FFFFFF',
      secondary: '#B0BEC5',
    },
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    h1: {
      fontSize: '2.5rem',
      fontWeight: 700,
    },
    h2: {
      fontSize: '2rem',
      fontWeight: 600,
    },
    h3: {
      fontSize: '1.75rem',
      fontWeight: 600,
    },
    h4: {
      fontSize: '1.5rem',
      fontWeight: 500,
    },
    h5: {
      fontSize: '1.25rem',
      fontWeight: 500,
    },
    h6: {
      fontSize: '1rem',
      fontWeight: 500,
    },
  },
  shape: {
    borderRadius: 12,
  },
  components: {
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          borderRadius: 16,
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 600,
          borderRadius: 8,
        },
      },
    },
  },
});

// React Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30000,  // 30 seconds
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Box sx={{ display: 'flex', minHeight: '100vh' }}>
          <Navigation />
          <Box component="main" sx={{ flexGrow: 1, p: 3, mt: 8, width: '100%' }}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/clusters" element={<ClusterList />} />
              <Route path="/clusters/:id" element={<ClusterDetails />} />
              <Route path="/cost" element={<CostMonitoring />} />
              <Route path="/predictions" element={<PredictionComparison />} />
              <Route path="/optimization" element={<OptimizationHistory />} />
              <Route path="/live" element={<LiveMonitoring />} />
              <Route path="/spot-warnings" element={<SpotWarnings />} />
            </Routes>
          </Box>
        </Box>
        <ToastContainer
          position="top-right"
          autoClose={5000}
          hideProgressBar={false}
          newestOnTop
          closeOnClick
          rtl={false}
          pauseOnFocusLoss
          draggable
          pauseOnHover
          theme="dark"
        />
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
