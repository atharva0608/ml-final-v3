# ML Model Requirements & Training Guide

**CloudOptim ML Server - Model Specifications**

---

## 📋 Overview

This document describes requirements for ML models used by CloudOptim ML Server, including:
- **Input features** required for predictions
- **Output format** expected by decision engines
- **Performance metrics** for model validation
- **Training data** specifications
- **Deployment** requirements

---

## 🎯 Model Types

CloudOptim supports the following model types:

### 1. Spot Price Predictor
**Purpose**: Predict future AWS Spot instance prices

**Input Features** (17 features):
```python
{
    # Time-based features
    "hour": int,  # 0-23
    "day_of_week": int,  # 0-6 (Monday=0)
    "month": int,  # 1-12
    "is_weekend": int,  # 0 or 1
    "is_night": int,  # 0 or 1 (night: 22:00-06:00)

    # Price features
    "on_demand_price": float,  # Current On-Demand price
    "price_ratio": float,  # spot_price / on_demand_price

    # Instance features
    "instance_type_encoded": int,  # Label-encoded instance type
    "interruption_rate_encoded": int,  # 1-5 (from AWS Spot Advisor)

    # Historical features (rolling statistics)
    "price_ma_24h": float,  # 24-hour moving average
    "price_ma_168h": float,  # 1-week moving average
    "price_std_24h": float,  # 24-hour standard deviation
    "price_std_168h": float,  # 1-week standard deviation

    # Lag features
    "price_lag_1h": float,  # Price 1 hour ago
    "price_lag_6h": float,  # Price 6 hours ago
    "price_lag_24h": float,  # Price 24 hours ago
}
```

**Output**:
```python
{
    "predicted_price": float,  # Predicted Spot price (USD/hour)
    "confidence": float  # 0.0-1.0
}
```

**Performance Requirements**:
- **MAE** (Mean Absolute Error): < $0.01 (excellent), < $0.02 (acceptable)
- **MAPE** (Mean Absolute Percentage Error): < 10%
- **R²** (R-squared): > 0.85
- **Prediction Latency**: < 50ms per prediction

**Training Data Requirements**:
- **Minimum**: 30 days of hourly Spot price data
- **Recommended**: 90-365 days for better seasonality capture
- **Regions**: At least 1 region (us-east-1 recommended for start)
- **Instance Types**: Start with 4 types (m5.large, c5.large, r5.large, t3.large)
- **Data Format**: CSV with columns: `timestamp,instance_type,availability_zone,spot_price,on_demand_price,interruption_rate`

---

### 2. Interruption Predictor
**Purpose**: Predict Spot instance interruption probability

**Input Features**:
```python
{
    "instance_type": str,
    "region": str,
    "availability_zone": str,
    "current_spot_price": float,
    "on_demand_price": float,
    "interruption_rate": str,  # AWS Spot Advisor: "<5%", "5-10%", etc.
    "price_history": list[float],  # Last 7 days of prices
    "hour": int,
    "day_of_week": int
}
```

**Output**:
```python
{
    "interruption_probability": float,  # 0.0-1.0
    "confidence": float,  # 0.0-1.0
    "recommendation": str,  # "safe" | "moderate" | "risky"
    "reasoning": str  # Human-readable explanation
}
```

**Performance Requirements**:
- **Precision**: > 0.80 (minimize false positives)
- **Recall**: > 0.75 (catch most interruptions)
- **F1-Score**: > 0.77
- **Latency**: < 100ms

---

### 3. Resource Forecaster (Optional)
**Purpose**: Forecast future resource usage for capacity planning

**Input Features**:
```python
{
    "namespace": str,
    "deployment": str,
    "current_cpu_usage": float,
    "current_memory_usage": float,
    "historical_usage": list[float],  # Last 24 hours
    "time_features": dict  # hour, day_of_week, month
}
```

**Output**:
```python
{
    "forecasted_cpu": float,
    "forecasted_memory": float,
    "confidence": float
}
```

---

## 🛠️ Training Requirements

### Hardware Requirements

**Minimum** (works on MacBook M4 Air 16GB RAM):
- CPU: 4+ cores
- RAM: 8GB
- Disk: 10GB free space

**Recommended**:
- CPU: 8+ cores
- RAM: 16GB
- GPU: Not required (XGBoost is CPU-optimized)

### Software Requirements

```bash
# Core dependencies
Python >= 3.11
pandas >= 2.0.0
numpy >= 1.24.0
scikit-learn >= 1.3.0
xgboost >= 2.0.0
lightgbm >= 4.0.0
```

### Training Data Format

**CSV File Structure** (spot_prices_us-east-1.csv):
```csv
timestamp,instance_type,region,availability_zone,spot_price,on_demand_price,interruption_rate
2023-01-01 00:00:00,m5.large,us-east-1,us-east-1a,0.0456,0.096,<5%
2023-01-01 01:00:00,m5.large,us-east-1,us-east-1a,0.0461,0.096,<5%
...
```

**Required Columns**:
- `timestamp`: ISO 8601 format (YYYY-MM-DD HH:MM:SS)
- `instance_type`: EC2 instance type (e.g., "m5.large")
- `region`: AWS region (e.g., "us-east-1")
- `availability_zone`: AWS AZ (e.g., "us-east-1a")
- `spot_price`: Spot price in USD (e.g., 0.0456)
- `on_demand_price`: On-Demand price in USD (e.g., 0.096)
- `interruption_rate`: AWS Spot Advisor rate ("<5%", "5-10%", "10-15%", "15-20%", ">20%")

**Data Sources**:
1. **AWS EC2 API**:
   ```python
   import boto3
   ec2 = boto3.client('ec2', region_name='us-east-1')
   response = ec2.describe_spot_price_history(
       StartTime=start_date,
       EndTime=end_date,
       InstanceTypes=['m5.large'],
       ProductDescriptions=['Linux/UNIX']
   )
   ```

2. **AWS Spot Advisor** (public data):
   ```bash
   curl https://spot-bid-advisor.s3.amazonaws.com/spot-advisor-data.json
   ```

---

## 📊 Model Performance Metrics

### How to Interpret Metrics

**Mean Absolute Error (MAE)**:
- Measures average prediction error in original units (USD)
- Example: MAE = $0.015 means predictions are off by 1.5 cents on average
- **Target**: < $0.01 (excellent), < $0.02 (acceptable), < $0.05 (needs improvement)

**Mean Absolute Percentage Error (MAPE)**:
- Measures error as percentage of actual value
- Example: MAPE = 8.5% means 8.5% average error
- **Target**: < 10% (excellent), < 15% (acceptable), < 25% (needs improvement)

**R² (R-squared)**:
- Measures how well model explains variance (0-1)
- Example: R² = 0.92 means model explains 92% of price variance
- **Target**: > 0.85 (excellent), > 0.75 (acceptable), > 0.60 (needs improvement)

**RMSE (Root Mean Squared Error)**:
- Similar to MAE but penalizes large errors more
- Use alongside MAE to detect outliers
- **Target**: < $0.02 (excellent), < $0.04 (acceptable)

### Example Training Output

```
Model Performance:
  Test MAE: $0.0087       ✅ Excellent
  Test RMSE: $0.0124      ✅ Excellent
  Test R²: 0.9234         ✅ Excellent
  Test MAPE: 7.82%        ✅ Excellent

Top Features:
  1. price_ma_168h        (importance: 0.245)
  2. price_ratio          (importance: 0.189)
  3. on_demand_price      (importance: 0.143)
  4. hour                 (importance: 0.112)
  5. price_lag_24h        (importance: 0.098)
```

---

## 🎓 Training Guide

### Step-by-Step Training Process

#### 1. Prepare Training Data

```bash
# Create data directory
mkdir -p /home/user/ml-final-v3/new\ app/ml-server/training/data

# Option A: Use sample data (for testing)
python training/train_models.py --region us-east-1 --instances m5.large,c5.large

# Option B: Fetch real data from AWS (recommended)
python scripts/fetch_spot_prices.py --region us-east-1 --days 90
```

#### 2. Train Model

```bash
cd "/home/user/ml-final-v3/new app/ml-server"

# Train Spot Price Predictor
python training/train_models.py \
    --model spot_predictor \
    --region us-east-1 \
    --instances m5.large,c5.large,r5.large,t3.large \
    --data-dir ./training/data \
    --output-dir ./models/uploaded

# Expected output:
# - models/uploaded/spot_price_predictor_20250130_143025/model.pkl
# - models/uploaded/spot_price_predictor_20250130_143025/metadata.json
# - models/uploaded/spot_price_predictor_20250130_143025/scaler.pkl
# - models/uploaded/spot_price_predictor_20250130_143025/feature_importance.csv
```

#### 3. Validate Model

```python
# Load trained model
import pickle
with open('models/uploaded/spot_price_predictor_latest/model.pkl', 'rb') as f:
    model = pickle.load(f)

# Check metadata
import json
with open('models/uploaded/spot_price_predictor_latest/metadata.json', 'r') as f:
    metadata = json.load(f)
    print(f"Test MAE: ${metadata['metrics']['test_mae']:.4f}")
    print(f"Test R²: {metadata['metrics']['test_r2']:.4f}")
```

#### 4. Upload to ML Server

**Via Frontend** (http://localhost:3001):
1. Go to "Models" page
2. Click "Upload Model"
3. Select model directory: `models/uploaded/spot_price_predictor_20250130_143025/`
4. Click "Upload"
5. Wait for upload to complete
6. Click "Activate" to use for predictions

**Via API**:
```bash
curl -X POST http://localhost:8001/api/v1/ml/models/upload \
  -F "model=@models/uploaded/spot_price_predictor_latest/model.pkl" \
  -F "metadata=@models/uploaded/spot_price_predictor_latest/metadata.json"
```

#### 5. Test Predictions

```bash
curl -X POST http://localhost:8001/api/v1/ml/predict/spot-price \
  -H "Content-Type: application/json" \
  -d '{
    "instance_type": "m5.large",
    "region": "us-east-1",
    "availability_zone": "us-east-1a"
  }'
```

---

## 📦 Model File Structure

Each trained model must include these files:

```
spot_price_predictor_20250130_143025/
├── model.pkl                    # Pickled model object (XGBoost/LightGBM)
├── scaler.pkl                   # Fitted StandardScaler
├── label_encoders.pkl           # Label encoders for categorical features
├── metadata.json                # Model metadata (see below)
└── feature_importance.csv       # Feature importance scores
```

### metadata.json Structure

```json
{
  "model_name": "spot_price_predictor",
  "model_type": "spot_price_predictor",
  "model_version": "1.0",
  "trained_date": "2025-01-30T14:30:25",
  "trained_until_date": "2025-01-30",
  "metrics": {
    "train_mae": 0.0065,
    "test_mae": 0.0087,
    "train_rmse": 0.0095,
    "test_rmse": 0.0124,
    "train_r2": 0.9456,
    "test_r2": 0.9234,
    "train_mape": 6.12,
    "test_mape": 7.82
  },
  "feature_columns": [
    "hour", "day_of_week", "month", "is_weekend", "is_night",
    "on_demand_price", "price_ratio", "instance_type_encoded",
    "interruption_rate_encoded",
    "price_ma_24h", "price_ma_168h",
    "price_std_24h", "price_std_168h",
    "price_lag_1h", "price_lag_6h", "price_lag_24h"
  ],
  "scaler": "StandardScaler",
  "algorithm": "XGBoost",
  "hyperparameters": {
    "n_estimators": 200,
    "max_depth": 6,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8
  },
  "data_summary": {
    "total_records": 87600,
    "train_records": 70080,
    "test_records": 17520,
    "instance_types": ["m5.large", "c5.large", "r5.large", "t3.large"],
    "regions": ["us-east-1"]
  }
}
```

---

## 🚀 Deployment & Integration

### Model Deployment Checklist

- [ ] Model achieves performance targets (MAE < $0.02, R² > 0.85)
- [ ] Metadata.json is complete and accurate
- [ ] `trained_until_date` is set correctly
- [ ] Feature columns match training script exactly
- [ ] Scaler and label encoders are included
- [ ] Test predictions locally before upload
- [ ] Upload via frontend or API
- [ ] Activate model in ML Server
- [ ] Trigger gap-fill if needed (if trained_until_date < today)
- [ ] Monitor predictions for first 24 hours

### Risk Scoring Integration

The Spot Optimizer Engine uses model predictions in its risk scoring formula:

```python
Risk Score = (0.60 × Public_Rate_Score) +    # AWS Spot Advisor data
             (0.25 × Volatility_Score) +      # From historical prices
             (0.10 × Gap_Score) +             # Current vs OD price
             (0.05 × Time_Score)              # Time of day

# Model prediction used for Volatility_Score:
# - Predict next 24 hours of prices
# - Calculate standard deviation
# - Normalize to 0-1 range
```

**Expected Behavior**:
- Model predicts stable prices → Volatility_Score = 0.9 → Higher risk score (safer)
- Model predicts volatile prices → Volatility_Score = 0.3 → Lower risk score (risky)

---

## 🔧 Troubleshooting

### Common Training Issues

**Issue**: "MAE is too high (> $0.05)"
- **Cause**: Insufficient training data or feature engineering
- **Solution**:
  - Increase training data to 90+ days
  - Check for data quality issues (outliers, missing values)
  - Tune hyperparameters (increase n_estimators to 300-500)

**Issue**: "Model overfitting (train R² >> test R²)"
- **Cause**: Model too complex for data
- **Solution**:
  - Reduce max_depth to 4-5
  - Increase regularization (higher subsample, lower learning_rate)
  - Add more training data

**Issue**: "Feature importance shows one feature dominates"
- **Cause**: Other features not engineered well
- **Solution**:
  - Review feature engineering in train_models.py
  - Add more rolling statistics (7-day, 14-day)
  - Include external features (day of month, holidays)

**Issue**: "Predictions are all similar (low variance)"
- **Cause**: Model not learning patterns
- **Solution**:
  - Check feature scaling (StandardScaler should be fitted)
  - Verify feature columns match exactly between training and inference
  - Increase model complexity (more trees, deeper trees)

---

## 📚 References

- **XGBoost Documentation**: https://xgboost.readthedocs.io/
- **AWS Spot Advisor**: https://aws.amazon.com/ec2/spot/instance-advisor/
- **AWS EC2 Pricing API**: https://docs.aws.amazon.com/AWSEC2/latest/APIReference/
- **Time Series Forecasting**: https://otexts.com/fpp3/

---

**Last Updated**: 2025-01-30
**Version**: 1.0
**Maintained By**: CloudOptim ML Team
