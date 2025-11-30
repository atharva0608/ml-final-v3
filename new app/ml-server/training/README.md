# CloudOptim ML Model Training

Train ML models for CloudOptim ML Server on your MacBook M4 Air 16GB RAM.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Train model (uses sample data if no CSV found)
python train_models.py --region us-east-1 --instances m5.large,c5.large,r5.large,t3.large

# 3. Model saved to: ../models/uploaded/spot_price_predictor_<timestamp>/
```

## Output

After training, you'll get:
- `model.pkl` - Trained XGBoost model
- `metadata.json` - Performance metrics & config
- `scaler.pkl` - Feature scaler
- `label_encoders.pkl` - Category encoders
- `feature_importance.csv` - Feature rankings

## Performance Targets

- **MAE**: < $0.02 (mean absolute error)
- **R²**: > 0.85 (variance explained)
- **MAPE**: < 10% (percentage error)

## Using Real Data

Place your CSV in `./data/spot_prices_us-east-1.csv`:

```csv
timestamp,instance_type,region,availability_zone,spot_price,on_demand_price,interruption_rate
2023-01-01 00:00:00,m5.large,us-east-1,us-east-1a,0.0456,0.096,<5%
```

Fetch from AWS:
```bash
# TODO: Add AWS data fetcher script
```

## Next Steps

1. Upload model via ML Server frontend: http://localhost:3001
2. Activate model for predictions
3. Test: `curl http://localhost:8001/api/v1/ml/predict/spot-price`

See: `../docs/MODEL_REQUIREMENTS.md` for complete guide.
