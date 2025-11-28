/**
 * API Service for ML Server Backend
 *
 * Provides typed API client for all ML Server endpoints
 */

import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8001/api/v1/ml';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Models API
export const modelsAPI = {
  list: (params?: { active?: boolean; limit?: number; offset?: number }) =>
    apiClient.get('/models/list', { params }),

  upload: (formData: FormData) =>
    apiClient.post('/models/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),

  activate: (modelId: string, version: string) =>
    apiClient.post('/models/activate', { model_id: modelId, version }),

  delete: (modelId: string) =>
    apiClient.delete(`/models/${modelId}`),

  getDetails: (modelId: string) =>
    apiClient.get(`/models/${modelId}/details`),
};

// Gap Filler API
export const gapFillerAPI = {
  analyze: (modelId: string, lookbackDays: number = 15) =>
    apiClient.post('/gap-filler/analyze', { model_id: modelId, required_lookback_days: lookbackDays }),

  fill: (data: {
    model_id: string;
    instance_types: string[];
    regions: string[];
    gap_start_date: string;
    gap_end_date: string;
  }) =>
    apiClient.post('/gap-filler/fill', data),

  getStatus: (gapId: string) =>
    apiClient.get(`/gap-filler/status/${gapId}`),

  getHistory: (params?: { limit?: number; offset?: number }) =>
    apiClient.get('/gap-filler/history', { params }),
};

// Pricing Data API
export const pricingAPI = {
  getSpotPrices: (params: {
    instance_type: string;
    region: string;
    start_date?: string;
    end_date?: string;
    limit?: number;
  }) =>
    apiClient.get('/pricing/spot', { params }),

  getOnDemandPrices: (params?: { instance_type?: string; region?: string }) =>
    apiClient.get('/pricing/on-demand', { params }),

  getSpotAdvisor: (params?: { instance_type?: string; region?: string }) =>
    apiClient.get('/pricing/spot-advisor', { params }),

  getStats: () =>
    apiClient.get('/pricing/stats'),
};

// Health API
export const healthAPI = {
  check: () =>
    apiClient.get('/health'),

  getMetrics: () =>
    apiClient.get('/metrics'),
};

export default apiClient;
