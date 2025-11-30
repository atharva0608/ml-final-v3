# Mumbai Spot Price Predictor - Data Format & Configuration

## CSV Data Format

### Required Headers (Aligned with train_models.py)

```csv
timestamp,instance_type,availability_zone,spot_price,on_demand_price,savings
```

**Field Descriptions:**
- `timestamp` (datetime): ISO 8601 format (e.g., "2023-01-01 00:00:00")
- `instance_type` (string): EC2 instance type (e.g., "m5.large")
- `availability_zone` (string): AWS AZ (e.g., "ap-south-1a")
- `spot_price` (float): Current Spot price in USD/hour
- `on_demand_price` (float): On-Demand price in USD/hour
- `savings` (float): Percentage savings vs On-Demand (0-100)

**Optional Headers:**
- `interruption_rate` (string): AWS Spot Advisor rate ("<5%", "5-10%", etc.)

### File Paths

```
./training/data/spot_prices_ap-south-1.csv          # Expected input file
./training/data/spot_prices_ap-south-1_generated.csv # Auto-generated if missing
./training/outputs/                                   # Visualization outputs
./models/uploaded/                                    # Trained model outputs
```

## Mumbai Region Configuration

### Instance Types (4 total)

| Instance Type | vCPU | Memory (GB) | On-Demand Price ($/hr) | Base Volatility |
|--------------|------|-------------|------------------------|-----------------|
| m5.large     | 2    | 8           | $0.096                 | 0.12            |
| c5.large     | 2    | 4           | $0.085                 | 0.15            |
| r5.large     | 2    | 16          | $0.126                 | 0.10            |
| t3.large     | 2    | 8           | $0.0832                | 0.18            |

### Availability Zones (3 total)

- `ap-south-1a` (Mumbai Zone A)
- `ap-south-1b` (Mumbai Zone B)
- `ap-south-1c` (Mumbai Zone C)

### Total Pools: 12

**Calculation:** 4 instance types × 3 availability zones = 12 unique pools

Each pool is a unique combination of instance type and AZ:
```
m5.large + ap-south-1a
m5.large + ap-south-1b
m5.large + ap-south-1c
c5.large + ap-south-1a
c5.large + ap-south-1b
c5.large + ap-south-1c
r5.large + ap-south-1a
r5.large + ap-south-1b
r5.large + ap-south-1c
t3.large + ap-south-1a
t3.large + ap-south-1b
t3.large + ap-south-1c
```

## Training Configuration

### Data Split

```python
train_end_date: '2024-12-31'    # Train on 2023-2024 data
test_start_date: '2025-01-01'   # Test on 2025 data
```

### XGBoost Hyperparameters (Aligned with train_models.py)

```python
n_estimators: 200           # Number of boosting rounds
max_depth: 6                # Maximum tree depth
learning_rate: 0.05         # Step size shrinkage
subsample: 0.8              # Row sampling ratio
colsample_bytree: 0.8       # Column sampling ratio
random_state: 42            # Reproducibility
n_jobs: -1                  # Use all CPU cores
tree_method: 'hist'         # Histogram-based (fast on M4 Mac)
```

### Feature Engineering

**Time Features:**
- hour (0-23)
- day_of_week (0-6)
- month (1-12)
- is_weekend (0/1)
- is_night (0/1)
- is_peak_hour (0/1)

**Price Features:**
- price_mean_1h, 6h, 24h, 7d (rolling averages)
- price_std_1h, 6h, 24h, 7d (rolling volatility)
- price_min_24h, price_max_24h
- volatility_ratio_1h, 24h
- near_od_ratio (proximity to On-Demand price)

**Lag Features:**
- price_lag_6, 12, 36, 72, 144 (10-min intervals)

**Spike Detection:**
- spike_count_24h (capacity crush detection)
- time_since_spike

**Total Features:** 40+

## Risk Scoring (Relative, Cross-Sectional)

### Risk Components (Weighted)

```python
risk_score = (
    0.30 × near_od_rank_score +      # Capacity crush (30%)
    0.25 × volatility_rank_score +    # Price volatility (25%)
    0.15 × spike_rank_score +         # Spike frequency (15%)
    0.15 × discount_rank_score +      # Low discount = risky (15%)
    0.15 × pred_error_rank_score      # Prediction uncertainty (15%)
)
```

### Risk Categories

- **SAFE**: Bottom 20% risk (risk_score < 0.20 percentile)
- **MEDIUM**: Middle 50% risk (0.20 ≤ risk_score ≤ 0.70)
- **RISKY**: Top 30% risk (risk_score > 0.70 percentile)

### Stability Score

```python
stability_score = 1.0 - risk_score
```

## Sample Data Generation

### Parameters

```python
start_date: 2023-01-01
end_date: 2025-03-31
frequency: 10-minute intervals
total_records: ~1.4M (4 instances × 3 AZs × 118,584 timestamps)
```

### Price Patterns

**Daily Seasonality:**
- Cheaper at night (22:00 - 06:00)
- Higher demand during business hours (09:00 - 18:00)

**Weekly Seasonality:**
- 8% discount on weekends (Saturday-Sunday)

**Seasonal Trends:**
- 5% higher demand in Q4 (Oct-Dec)

**Volatility:**
- Instance-specific base volatility (10-18%)
- Random normal distribution around base

**Spikes:**
- 2% probability of capacity crush (1.5-2.5× price spike)
- Simulates real-world capacity shortages

## Model Outputs

### Saved Files

```
./models/uploaded/spot_price_predictor_ap-south-1.pkl    # Trained XGBoost model
./models/uploaded/scaler_ap-south-1.pkl                  # Feature scaler
./models/uploaded/metadata_ap-south-1.json               # Model metadata
./training/outputs/predictions_vs_actual.png             # Visualization 1
./training/outputs/risk_scores.png                       # Visualization 2
./training/outputs/savings_analysis.png                  # Visualization 3
./training/outputs/model_performance.png                 # Visualization 4
./training/outputs/recommendations.png                   # Visualization 5
```

### Model Metadata

```json
{
  "model_type": "XGBoost Price Predictor",
  "region": "ap-south-1",
  "instance_types": ["m5.large", "c5.large", "r5.large", "t3.large"],
  "training_period": "2023-01-01 to 2024-12-31",
  "test_period": "2025-01-01 to 2025-03-31",
  "features_count": 39,
  "test_mae": "<computed>",
  "test_rmse": "<computed>",
  "test_r2": "<computed>",
  "test_mape": "<computed>",
  "best_pool": "<computed>",
  "created_at": "<timestamp>"
}
```

## Performance Metrics

### Expected Results

- **Test MAE**: < $0.005 (sub-cent accuracy)
- **Test RMSE**: < $0.008
- **Test R²**: > 0.60 (60% variance explained)
- **Test MAPE**: < 15% (mean absolute percentage error)

### Best Pool Criteria

1. **Lowest risk score** (highest stability)
2. **Highest annual savings**
3. **Lowest prediction error**

## Alignment Status ✓

| Component                | Reference (train_models.py) | Mumbai Predictor | Status |
|--------------------------|----------------------------|------------------|--------|
| CSV Headers              | ✓ Compatible               | ✓ Compatible     | ✅      |
| On-Demand Prices         | ✓ Correct                  | ✓ Correct        | ✅      |
| Instance Types           | 4 types                    | 4 types          | ✅      |
| Availability Zones       | 1 AZ (basic)               | 3 AZs (Mumbai)   | ✅      |
| Total Pools              | 4                          | 12               | ✅      |
| XGBoost n_estimators     | 200                        | 200              | ✅      |
| XGBoost max_depth        | 6                          | 6                | ✅      |
| XGBoost learning_rate    | 0.05                       | 0.05             | ✅      |
| XGBoost subsample        | 0.8                        | 0.8              | ✅      |
| XGBoost colsample_bytree | 0.8                        | 0.8              | ✅      |
| XGBoost random_state     | 42                         | 42               | ✅      |
| XGBoost n_jobs           | -1                         | -1               | ✅      |
| tree_method              | Not specified              | 'hist' (M4 opt)  | ✅      |
| File Paths               | ./models/uploaded          | ./models/uploaded| ✅      |

## Usage

### Running the Training Script

```bash
cd "/home/user/ml-final-v3/new app/ml-server/training"
jupyter lab
# Open mumbai_price_predictor.py
# Run all cells
```

### Expected Runtime

- **With CSV file**: 2-3 minutes
- **With sample data generation**: 5-7 minutes
- **Total cells**: 10 sections + visualizations
- **Output**: 13 plots across 5 figures

### Troubleshooting

**Issue**: ValueError in scatter plot
**Solution**: Fixed in commit 6941c14 (merge on all 3 keys)

**Issue**: SyntaxError in dictionary
**Solution**: Fixed in commit 73e5175 (added values to empty keys)

**Issue**: Out of memory
**Solution**: Reduce date range or use sample_frac() on DataFrame

## References

- **Reference Model**: `/home/user/ml-final-v3/new app/ml-server/training/train_models.py`
- **Inference Model**: `/home/user/ml-final-v3/new app/ml-server/models/spot_predictor.py`
- **Configuration**: `/home/user/ml-final-v3/new app/ml-server/config/ml_config.yaml`
- **Documentation**: `/home/user/ml-final-v3/new app/ml-server/docs/MODEL_REQUIREMENTS.md`
