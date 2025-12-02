import React, { useState, useEffect } from 'react';
import {
  Typography, Paper, Box, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Chip, Button
} from '@mui/material';
import axios from 'axios';

const ClusterList: React.FC = () => {
  const [clusters, setClusters] = useState<any[]>([]);

  useEffect(() => {
    fetchClusters();
  }, []);

  const fetchClusters = async () => {
    try {
      const response = await axios.get('/api/v1/clusters');
      setClusters(response.data.clusters || []);
    } catch (error) {
      console.error('Failed to fetch clusters:', error);
    }
  };

  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>Cluster Management</Typography>
      <TableContainer>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Cluster Name</TableCell>
              <TableCell>Region</TableCell>
              <TableCell>Nodes</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Cost/Month</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {clusters.map((cluster) => (
              <TableRow key={cluster.cluster_id}>
                <TableCell>{cluster.cluster_name}</TableCell>
                <TableCell>{cluster.region}</TableCell>
                <TableCell>{cluster.node_count}</TableCell>
                <TableCell>
                  <Chip label={cluster.status} color="success" size="small" />
                </TableCell>
                <TableCell>${cluster.monthly_cost?.toLocaleString() || 0}</TableCell>
                <TableCell>
                  <Button size="small">View Details</Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  );
};

export default ClusterList;
