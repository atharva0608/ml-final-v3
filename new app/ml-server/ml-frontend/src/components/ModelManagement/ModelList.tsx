import React, { useState, useEffect } from 'react';
import {
  Typography, Paper, Box, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Button, Chip, IconButton,
  Dialog, DialogTitle, DialogContent, DialogActions, TextField
} from '@mui/material';
import { CloudUpload, CheckCircle, Cancel } from '@mui/icons-material';
import axios from 'axios';

interface Model {
  model_id: string;
  model_name: string;
  model_type: string;
  version: string;
  status: 'active' | 'inactive';
  accuracy?: number;
  mae?: number;
  rmse?: number;
  created_at: string;
}

const ModelList: React.FC = () => {
  const [models, setModels] = useState<Model[]>([]);
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [modelName, setModelName] = useState('');

  useEffect(() => {
    fetchModels();
  }, []);

  const fetchModels = async () => {
    try {
      const response = await axios.get('/api/v1/models');
      setModels(response.data.models || []);
    } catch (error) {
      console.error('Failed to fetch models:', error);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile || !modelName) return;

    const formData = new FormData();
    formData.append('model_file', selectedFile);
    formData.append('model_name', modelName);

    try {
      await axios.post('/api/v1/models/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setUploadDialogOpen(false);
      setSelectedFile(null);
      setModelName('');
      fetchModels();
    } catch (error) {
      console.error('Failed to upload model:', error);
    }
  };

  const toggleModelStatus = async (modelId: string, currentStatus: string) => {
    try {
      const newStatus = currentStatus === 'active' ? 'inactive' : 'active';
      await axios.patch(`/api/v1/models/${modelId}/status`, { status: newStatus });
      fetchModels();
    } catch (error) {
      console.error('Failed to update model status:', error);
    }
  };

  return (
    <Paper sx={{ p: 3 }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h5">Model Management</Typography>
        <Button
          variant="contained"
          startIcon={<CloudUpload />}
          onClick={() => setUploadDialogOpen(true)}
        >
          Upload Model
        </Button>
      </Box>

      <TableContainer>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Model Name</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Version</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Accuracy</TableCell>
              <TableCell>MAE</TableCell>
              <TableCell>RMSE</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {models.map((model) => (
              <TableRow key={model.model_id}>
                <TableCell>{model.model_name}</TableCell>
                <TableCell>{model.model_type}</TableCell>
                <TableCell>{model.version}</TableCell>
                <TableCell>
                  <Chip
                    label={model.status}
                    color={model.status === 'active' ? 'success' : 'default'}
                    size="small"
                  />
                </TableCell>
                <TableCell>{model.accuracy ? `${(model.accuracy * 100).toFixed(2)}%` : '-'}</TableCell>
                <TableCell>{model.mae?.toFixed(4) || '-'}</TableCell>
                <TableCell>{model.rmse?.toFixed(4) || '-'}</TableCell>
                <TableCell>
                  <IconButton
                    size="small"
                    onClick={() => toggleModelStatus(model.model_id, model.status)}
                    color={model.status === 'active' ? 'error' : 'success'}
                  >
                    {model.status === 'active' ? <Cancel /> : <CheckCircle />}
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={uploadDialogOpen} onClose={() => setUploadDialogOpen(false)}>
        <DialogTitle>Upload New Model</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="Model Name"
            value={modelName}
            onChange={(e) => setModelName(e.target.value)}
            margin="normal"
          />
          <Button
            variant="outlined"
            component="label"
            fullWidth
            sx={{ mt: 2 }}
          >
            Select Model File (.pkl)
            <input
              type="file"
              hidden
              accept=".pkl"
              onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
            />
          </Button>
          {selectedFile && (
            <Typography variant="body2" sx={{ mt: 1 }}>
              Selected: {selectedFile.name}
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setUploadDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleUpload} variant="contained" disabled={!selectedFile || !modelName}>
            Upload
          </Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
};

export default ModelList;
