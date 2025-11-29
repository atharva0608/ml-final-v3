/**
 * API Service for Core Platform Backend
 *
 * Provides typed API client for all Core Platform endpoints
 */

import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Clusters API
export const clustersAPI = {
  list: () => apiClient.get('/admin/clusters'),
  
  get: (clusterId: string) => apiClient.get(`/admin/clusters/${clusterId}`),
  
  register: (data: any) => apiClient.post('/admin/clusters', data),
  
  update: (clusterId: string, data: any) => apiClient.put(`/admin/clusters/${clusterId}`, data),
  
  delete: (clusterId: string) => apiClient.delete(`/admin/clusters/${clusterId}`),
  
  getSavings: () => apiClient.get('/admin/savings'),
};

// Optimization API
export const optimizationAPI = {
  trigger: (clusterId: string, type: string) =>
    apiClient.post('/optimization/trigger', { cluster_id: clusterId, optimization_type: type }),
  
  getHistory: (params?: any) => apiClient.get('/optimization/history', { params }),
  
  getStatus: (optimizationId: string) =>
    apiClient.get(`/optimization/status/${optimizationId}`),
};

// Events API (Spot Warnings)
export const eventsAPI = {
  getSpotWarnings: (params?: any) =>
    apiClient.get('/events/spot-warnings', { params }),
  
  getHistory: (params?: any) => apiClient.get('/events/history', { params }),
};

// Remote K8s API
export const k8sAPI = {
  getNodes: (clusterId: string) => apiClient.get(`/k8s/${clusterId}/nodes`),
  
  getPods: (clusterId: string) => apiClient.get(`/k8s/${clusterId}/pods`),
  
  getMetrics: (clusterId: string) => apiClient.get(`/k8s/${clusterId}/metrics`),
  
  drainNode: (clusterId: string, nodeName: string) =>
    apiClient.post(`/k8s/${clusterId}/nodes/drain`, { node_name: nodeName }),
};

// Health API
export const healthAPI = {
  check: () => apiClient.get('/health'),
  
  getMetrics: () => apiClient.get('/metrics'),
};

export default apiClient;
