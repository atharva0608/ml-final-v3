import React, { useState, useEffect } from 'react';
import {
  Typography, Paper, Box, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Chip
} from '@mui/material';
import axios from 'axios';

interface Engine {
  name: string;
  type: string;
  status: string;
  description: string;
}

const EngineList: React.FC = () => {
  const [engines, setEngines] = useState<Engine[]>([
    { name: 'Spot Optimizer', type: 'spot_optimizer', status: 'active', description: 'Adaptive risk scoring with feedback loop' },
    { name: 'Bin Packing', type: 'bin_packing', status: 'active', description: 'Tetris-style workload consolidation' },
    { name: 'Rightsizing', type: 'rightsizing', status: 'active', description: 'Hybrid Day Zero + ML sizing' },
    { name: 'Office Hours', type: 'office_hours', status: 'active', description: 'Auto-scale dev/staging environments' },
    { name: 'Ghost Probe', type: 'ghost_probe', status: 'active', description: 'Detect zombie EC2 instances' },
    { name: 'Zombie Volume', type: 'zombie_volume', status: 'active', description: 'Cleanup unattached EBS volumes' },
    { name: 'Network Optimizer', type: 'network_optimizer', status: 'active', description: 'Cross-AZ traffic optimization' },
    { name: 'OOMKilled Remediation', type: 'oomkilled', status: 'active', description: 'Auto-fix OOMKilled pods' },
  ]);

  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>Decision Engines</Typography>
      <Typography paragraph>
        8 Pluggable decision engines for comprehensive optimization
      </Typography>
      <TableContainer>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Engine Name</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Description</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {engines.map((engine) => (
              <TableRow key={engine.type}>
                <TableCell>{engine.name}</TableCell>
                <TableCell><Chip label={engine.type} size="small" /></TableCell>
                <TableCell>
                  <Chip label={engine.status} color="success" size="small" />
                </TableCell>
                <TableCell>{engine.description}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  );
};

export default EngineList;
