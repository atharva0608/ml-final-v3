/**
 * TypeScript Type Definitions for ML Server Frontend
 */

export interface MLModel {
  model_id: string;
  model_name: string;
  model_version: string;
  model_type: 'spot_predictor' | 'resource_forecaster';
  trained_until_date: string;
  upload_date: string;
  active: boolean;
  model_file_path: string;
  model_metadata?: Record<string, any>;
  performance_metrics?: Record<string, any>;
}

export interface DecisionEngine {
  engine_id: string;
  engine_name: string;
  engine_version: string;
  engine_type: string;
  upload_date: string;
  active: boolean;
  config?: Record<string, any>;
}

export interface GapAnalysis {
  trained_until: string;
  current_date: string;
  gap_days: number;
  required_data_types: string[];
  estimated_records: number;
}

export interface GapFillStatus {
  gap_id: string;
  status: 'pending' | 'filling' | 'completed' | 'failed';
  percent_complete: number;
  records_filled: number;
  records_expected: number;
  eta_seconds?: number;
  started_at: string;
  completed_at?: string;
  error_message?: string;
}

export interface SpotPrice {
  instance_type: string;
  availability_zone: string;
  region: string;
  spot_price: number;
  timestamp: string;
  product_description?: string;
}

export interface HealthStatus {
  status: string;
  service: string;
  version: string;
  components: Record<string, string>;
}
