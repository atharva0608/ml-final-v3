import React from 'react';
import {
  Grid,
  Card,
  CardContent,
  Typography,
  Box,
  LinearProgress,
  Chip,
} from '@mui/material';
import {
  TrendingUp,
  Cloud,
  CheckCircle,
  Warning,
  AttachMoney,
  Speed,
} from '@mui/icons-material';
import { motion } from 'framer-motion';
import { LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import numeral from 'numeral';

// Mock data - replace with real API calls
const savingsData = [
  { month: 'Jan', savings: 4200, predicted: 4000 },
  { month: 'Feb', savings: 5100, predicted: 4800 },
  { month: 'Mar', savings: 6300, predicted: 5900 },
  { month: 'Apr', savings: 7500, predicted: 7000 },
  { month: 'May', savings: 8900, predicted: 8300 },
  { month: 'Jun', savings: 10200, predicted: 9600 },
];

const costBreakdown = [
  { name: 'Spot Instances', value: 3500, color: '#00C853' },
  { name: 'On-Demand', value: 2000, color: '#2196F3' },
  { name: 'Reserved', value: 1500, color: '#FFC107' },
];

// Animated stat card component
const StatCard = ({ title, value, subtitle, icon: Icon, color, trend }: any) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.5 }}
  >
    <Card
      sx={{
        background: `linear-gradient(135deg, ${color}22 0%, ${color}11 100%)`,
        border: `1px solid ${color}33`,
      }}
    >
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              {title}
            </Typography>
            <Typography variant="h3" sx={{ fontWeight: 700, color }}>
              {value}
            </Typography>
            {subtitle && (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                {subtitle}
              </Typography>
            )}
            {trend && (
              <Chip
                label={`${trend > 0 ? '+' : ''}${trend}% vs last month`}
                size="small"
                color={trend > 0 ? 'success' : 'error'}
                sx={{ mt: 1 }}
              />
            )}
          </Box>
          <Box
            sx={{
              bgcolor: `${color}22`,
              borderRadius: 2,
              p: 1.5,
            }}
          >
            <Icon sx={{ fontSize: 40, color }} />
          </Box>
        </Box>
      </CardContent>
    </Card>
  </motion.div>
);

export default function Dashboard() {
  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h3" gutterBottom sx={{ fontWeight: 700 }}>
          CloudOptim Dashboard
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Agentless Kubernetes Cost Optimization - Real-time monitoring and analytics
        </Typography>
      </Box>

      {/* Stats Grid */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard
            title="Monthly Savings"
            value="$10,234"
            subtitle="vs projected costs"
            icon={AttachMoney}
            color="#00C853"
            trend={14.5}
          />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard
            title="Clusters Monitored"
            value="8"
            subtitle="All clusters healthy"
            icon={Cloud}
            color="#2196F3"
          />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard
            title="Optimizations Today"
            value="23"
            subtitle="15 spot, 8 bin packing"
            icon={CheckCircle}
            color="#00E676"
          />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard
            title="Spot Warnings"
            value="2"
            subtitle="Handled automatically"
            icon={Warning}
            color="#FFC107"
          />
        </Grid>
      </Grid>

      {/* Charts */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        {/* Savings Trend */}
        <Grid item xs={12} lg={8}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Savings Trend vs Predictions
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Actual savings (green) vs ML predictions (blue)
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={savingsData}>
                  <defs>
                    <linearGradient id="colorSavings" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#00C853" stopOpacity={0.8} />
                      <stop offset="95%" stopColor="#00C853" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="colorPredicted" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#2196F3" stopOpacity={0.8} />
                      <stop offset="95%" stopColor="#2196F3" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                  <XAxis dataKey="month" stroke="#B0BEC5" />
                  <YAxis stroke="#B0BEC5" />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#132F4C', border: '1px solid #444' }}
                    formatter={(value: any) => `$${numeral(value).format('0,0')}`}
                  />
                  <Area type="monotone" dataKey="savings" stroke="#00C853" fillOpacity={1} fill="url(#colorSavings)" strokeWidth={2} />
                  <Area type="monotone" dataKey="predicted" stroke="#2196F3" fillOpacity={1} fill="url(#colorPredicted)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        {/* Cost Breakdown */}
        <Grid item xs={12} lg={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Cost Breakdown
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Current month spend by instance type
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={costBreakdown}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={5}
                    dataKey="value"
                    label={({ name, value }) => `${name}: $${numeral(value).format('0,0')}`}
                  >
                    {costBreakdown.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value: any) => `$${numeral(value).format('0,0')}`} />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Quick Actions */}
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Recent Optimization Activity
          </Typography>
          <Box sx={{ mt: 2 }}>
            {[
              { time: '2 min ago', action: 'Spot Optimization', cluster: 'prod-eks-1', savings: '$45/mo' },
              { time: '15 min ago', action: 'Bin Packing', cluster: 'staging-eks', savings: '$120/mo' },
              { time: '1 hour ago', action: 'Rightsizing', cluster: 'dev-eks', savings: '$35/mo' },
              { time: '2 hours ago', action: 'Spot Interruption Handled', cluster: 'prod-eks-2', savings: 'N/A' },
            ].map((item, index) => (
              <Box
                key={index}
                sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  py: 2,
                  borderBottom: index < 3 ? '1px solid #333' : 'none',
                }}
              >
                <Box>
                  <Typography variant="body1">{item.action}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {item.cluster} • {item.time}
                  </Typography>
                </Box>
                <Chip
                  label={item.savings}
                  color={item.savings !== 'N/A' ? 'success' : 'default'}
                  size="small"
                />
              </Box>
            ))}
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}
