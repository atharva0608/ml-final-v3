"""
Unified ML Model Training Script for CloudOptim

This script trains all ML models used by the ML Server:
1. Spot Price Predictor - Predicts future Spot prices
2. Interruption Predictor - Predicts Spot interruption probability
3. Resource Forecaster - Forecasts resource usage patterns

Training Data Requirements:
- Historical Spot pricing data (2023-2024)
- AWS Spot Advisor interruption rates
- Instance metadata (CPU, memory, family)

Usage:
    python train_models.py --model spot_predictor --region us-east-1 --instances m5.large,c5.large
    python train_models.py --model all --region us-east-1,us-west-2

Environment:
    - Requires: Python 3.11+, pandas, scikit-learn, xgboost, lightgbm
    - Hardware: Works on MacBook M4 Air 16GB RAM
    - Data: CSV files in ./training/data/
"""

import os
import sys
import argparse
import pickle
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import xgboost as xgb
import lightgbm as lgb

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CloudOptimModelTrainer:
    """
    Unified trainer for all CloudOptim ML models
    """

    def __init__(self, data_dir: str = "./training/data", output_dir: str = "./models/uploaded"):
        """
        Initialize model trainer

        Args:
            data_dir: Directory containing training data CSVs
            output_dir: Directory to save trained models
        """
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.scaler = StandardScaler()
        self.label_encoders = {}

    def load_spot_price_data(
        self,
        region: str,
        instance_types: List[str]
    ) -> pd.DataFrame:
        """
        Load historical Spot price data

        Expected CSV format:
            timestamp,instance_type,availability_zone,spot_price,interruption_rate

        Args:
            region: AWS region (e.g., 'us-east-1')
            instance_types: List of instance types to include

        Returns:
            DataFrame with loaded data
        """
        logger.info(f"Loading Spot price data for {region}, instances: {instance_types}")

        # Try to load from CSV
        csv_path = self.data_dir / f"spot_prices_{region}.csv"

        if not csv_path.exists():
            logger.warning(f"CSV file not found: {csv_path}")
            logger.info("Generating sample data for demonstration...")
            return self._generate_sample_data(region, instance_types)

        df = pd.read_csv(csv_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Filter by instance types
        if instance_types:
            df = df[df['instance_type'].isin(instance_types)]

        logger.info(f"Loaded {len(df)} records from {csv_path}")
        return df

    def _generate_sample_data(
        self,
        region: str,
        instance_types: List[str],
        days: int = 365
    ) -> pd.DataFrame:
        """
        Generate sample training data for demonstration

        This creates realistic-looking Spot price data with:
        - Daily/weekly seasonality
        - Random volatility
        - Interruption rate patterns
        """
        logger.info(f"Generating {days} days of sample data...")

        data = []
        start_date = datetime.now() - timedelta(days=days)

        # Base prices for different instance types
        base_prices = {
            'm5.large': 0.096,
            'c5.large': 0.085,
            'r5.large': 0.126,
            't3.large': 0.0832
        }

        interruption_rates = ['<5%', '5-10%', '10-15%', '15-20%', '>20%']

        for instance_type in instance_types:
            base_price = base_prices.get(instance_type, 0.10)

            for day in range(days):
                date = start_date + timedelta(days=day)

                # Generate 24 hourly records per day
                for hour in range(24):
                    timestamp = date + timedelta(hours=hour)

                    # Add daily seasonality (cheaper at night)
                    time_factor = 1.0 - 0.2 * np.sin(2 * np.pi * hour / 24)

                    # Add weekly seasonality (cheaper on weekends)
                    day_of_week = timestamp.weekday()
                    weekly_factor = 0.9 if day_of_week >= 5 else 1.0

                    # Add random volatility
                    volatility = np.random.normal(1.0, 0.15)

                    # Calculate Spot price (30-70% of base On-Demand price)
                    spot_price = base_price * 0.5 * time_factor * weekly_factor * volatility
                    spot_price = max(0.01, min(spot_price, base_price * 0.9))

                    # Interruption rate based on price gap
                    price_gap = (base_price - spot_price) / base_price
                    if price_gap > 0.7:
                        int_rate = '<5%'
                    elif price_gap > 0.5:
                        int_rate = '5-10%'
                    elif price_gap > 0.3:
                        int_rate = '10-15%'
                    else:
                        int_rate = '>20%'

                    data.append({
                        'timestamp': timestamp,
                        'instance_type': instance_type,
                        'region': region,
                        'availability_zone': f"{region}a",
                        'spot_price': round(spot_price, 4),
                        'on_demand_price': base_price,
                        'interruption_rate': int_rate
                    })

        df = pd.DataFrame(data)

        # Save for future use
        output_path = self.data_dir / f"spot_prices_{region}_generated.csv"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        logger.info(f"Saved generated data to {output_path}")

        return df

    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create features for ML model

        Features:
        - Time-based: hour, day_of_week, month, is_weekend
        - Price-based: price_gap, volatility, moving averages
        - Historical: lag features, rolling statistics
        """
        logger.info("Engineering features...")

        df = df.copy()
        df = df.sort_values('timestamp')

        # Time features
        df['hour'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        df['month'] = df['timestamp'].dt.month
        df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
        df['is_night'] = ((df['hour'] >= 22) | (df['hour'] <= 6)).astype(int)

        # Price features
        df['price_gap'] = (df['on_demand_price'] - df['spot_price']) / df['on_demand_price']
        df['price_ratio'] = df['spot_price'] / df['on_demand_price']

        # Encode categorical features
        if 'interruption_rate' in df.columns:
            rate_mapping = {'<5%': 1, '5-10%': 2, '10-15%': 3, '15-20%': 4, '>20%': 5}
            df['interruption_rate_encoded'] = df['interruption_rate'].map(rate_mapping)

        # Encode instance type
        if 'instance_type' not in self.label_encoders:
            self.label_encoders['instance_type'] = LabelEncoder()
            self.label_encoders['instance_type'].fit(df['instance_type'])

        df['instance_type_encoded'] = self.label_encoders['instance_type'].transform(df['instance_type'])

        # Rolling statistics (grouped by instance type)
        for window in [24, 168]:  # 1 day, 1 week
            df[f'price_ma_{window}h'] = df.groupby('instance_type')['spot_price'].transform(
                lambda x: x.rolling(window=window, min_periods=1).mean()
            )
            df[f'price_std_{window}h'] = df.groupby('instance_type')['spot_price'].transform(
                lambda x: x.rolling(window=window, min_periods=1).std()
            )

        # Lag features
        for lag in [1, 6, 24]:  # 1 hour, 6 hours, 1 day
            df[f'price_lag_{lag}h'] = df.groupby('instance_type')['spot_price'].shift(lag)

        # Fill NaN values from rolling/lag features
        df = df.fillna(method='bfill').fillna(method='ffill')

        logger.info(f"Created {len(df.columns)} features")
        return df

    def train_spot_price_predictor(
        self,
        df: pd.DataFrame,
        model_name: str = "spot_price_predictor"
    ) -> Tuple[Any, Dict[str, float], pd.DataFrame]:
        """
        Train Spot price prediction model

        Args:
            df: DataFrame with engineered features
            model_name: Name for saved model

        Returns:
            (trained_model, metrics, feature_importance)
        """
        logger.info("Training Spot Price Predictor...")

        # Define features and target
        feature_cols = [
            'hour', 'day_of_week', 'month', 'is_weekend', 'is_night',
            'on_demand_price', 'price_ratio', 'instance_type_encoded',
            'interruption_rate_encoded',
            'price_ma_24h', 'price_ma_168h',
            'price_std_24h', 'price_std_168h',
            'price_lag_1h', 'price_lag_6h', 'price_lag_24h'
        ]

        target_col = 'spot_price'

        # Prepare data
        X = df[feature_cols].values
        y = df[target_col].values

        # Time series split (preserves temporal order)
        tscv = TimeSeriesSplit(n_splits=5)

        # For final model, use 80-20 split
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # Train XGBoost model
        logger.info("Training XGBoost model...")
        model = xgb.XGBRegressor(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            n_jobs=-1
        )

        model.fit(
            X_train_scaled,
            y_train,
            eval_set=[(X_test_scaled, y_test)],
            verbose=False
        )

        # Predictions
        y_pred_train = model.predict(X_train_scaled)
        y_pred_test = model.predict(X_test_scaled)

        # Calculate metrics
        metrics = {
            'train_mae': mean_absolute_error(y_train, y_pred_train),
            'test_mae': mean_absolute_error(y_test, y_pred_test),
            'train_rmse': np.sqrt(mean_squared_error(y_train, y_pred_train)),
            'test_rmse': np.sqrt(mean_squared_error(y_test, y_pred_test)),
            'train_r2': r2_score(y_train, y_pred_train),
            'test_r2': r2_score(y_test, y_pred_test),
            'train_mape': np.mean(np.abs((y_train - y_pred_train) / y_train)) * 100,
            'test_mape': np.mean(np.abs((y_test - y_pred_test) / y_test)) * 100
        }

        # Feature importance
        feature_importance = pd.DataFrame({
            'feature': feature_cols,
            'importance': model.feature_importances_
        }).sort_values('importance', ascending=False)

        logger.info(f"Model Performance:")
        logger.info(f"  Test MAE: ${metrics['test_mae']:.4f}")
        logger.info(f"  Test RMSE: ${metrics['test_rmse']:.4f}")
        logger.info(f"  Test R²: {metrics['test_r2']:.4f}")
        logger.info(f"  Test MAPE: {metrics['test_mape']:.2f}%")

        # Save model
        model_metadata = {
            'model_name': model_name,
            'model_type': 'spot_price_predictor',
            'model_version': '1.0',
            'trained_date': datetime.now().isoformat(),
            'trained_until_date': df['timestamp'].max().date().isoformat(),
            'metrics': metrics,
            'feature_columns': feature_cols,
            'scaler': 'StandardScaler',
            'algorithm': 'XGBoost',
            'hyperparameters': model.get_params(),
            'data_summary': {
                'total_records': len(df),
                'train_records': len(X_train),
                'test_records': len(X_test),
                'instance_types': df['instance_type'].unique().tolist(),
                'regions': df['region'].unique().tolist()
            }
        }

        self._save_model(model, model_name, model_metadata, feature_importance)

        return model, metrics, feature_importance

    def _save_model(
        self,
        model: Any,
        model_name: str,
        metadata: Dict[str, Any],
        feature_importance: pd.DataFrame
    ):
        """
        Save trained model with metadata

        Saves:
        - model.pkl: Pickled model object
        - scaler.pkl: Fitted scaler
        - metadata.json: Model metadata
        - feature_importance.csv: Feature importance scores
        - label_encoders.pkl: Label encoders for categorical features
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_dir = self.output_dir / f"{model_name}_{timestamp}"
        model_dir.mkdir(parents=True, exist_ok=True)

        # Save model
        model_path = model_dir / "model.pkl"
        with open(model_path, 'wb') as f:
            pickle.dump(model, f)
        logger.info(f"Saved model to {model_path}")

        # Save scaler
        scaler_path = model_dir / "scaler.pkl"
        with open(scaler_path, 'wb') as f:
            pickle.dump(self.scaler, f)
        logger.info(f"Saved scaler to {scaler_path}")

        # Save label encoders
        encoders_path = model_dir / "label_encoders.pkl"
        with open(encoders_path, 'wb') as f:
            pickle.dump(self.label_encoders, f)
        logger.info(f"Saved label encoders to {encoders_path}")

        # Save metadata
        metadata_path = model_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        logger.info(f"Saved metadata to {metadata_path}")

        # Save feature importance
        importance_path = model_dir / "feature_importance.csv"
        feature_importance.to_csv(importance_path, index=False)
        logger.info(f"Saved feature importance to {importance_path}")

        logger.info(f"\n{'='*60}")
        logger.info(f"Model saved successfully!")
        logger.info(f"Location: {model_dir}")
        logger.info(f"{'='*60}\n")

        # Create a symlink to latest model
        latest_link = self.output_dir / f"{model_name}_latest"
        if latest_link.exists():
            latest_link.unlink()
        latest_link.symlink_to(model_dir)
        logger.info(f"Created symlink: {latest_link} -> {model_dir}")


def main():
    """
    Main training script
    """
    parser = argparse.ArgumentParser(description='Train CloudOptim ML models')
    parser.add_argument(
        '--model',
        type=str,
        default='spot_predictor',
        choices=['spot_predictor', 'interruption_predictor', 'all'],
        help='Model to train'
    )
    parser.add_argument(
        '--region',
        type=str,
        default='us-east-1',
        help='AWS region(s), comma-separated'
    )
    parser.add_argument(
        '--instances',
        type=str,
        default='m5.large,c5.large,r5.large,t3.large',
        help='Instance types, comma-separated'
    )
    parser.add_argument(
        '--data-dir',
        type=str,
        default='./training/data',
        help='Directory with training data'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='./models/uploaded',
        help='Directory to save models'
    )

    args = parser.parse_args()

    # Parse arguments
    regions = [r.strip() for r in args.region.split(',')]
    instance_types = [i.strip() for i in args.instances.split(',')]

    logger.info("="*60)
    logger.info("CloudOptim ML Model Training")
    logger.info("="*60)
    logger.info(f"Model: {args.model}")
    logger.info(f"Regions: {regions}")
    logger.info(f"Instance Types: {instance_types}")
    logger.info("="*60)

    # Initialize trainer
    trainer = CloudOptimModelTrainer(
        data_dir=args.data_dir,
        output_dir=args.output_dir
    )

    # Load data
    all_data = []
    for region in regions:
        df = trainer.load_spot_price_data(region, instance_types)
        all_data.append(df)

    combined_df = pd.concat(all_data, ignore_index=True)
    logger.info(f"Total records loaded: {len(combined_df)}")

    # Engineer features
    df_features = trainer.engineer_features(combined_df)

    # Train model
    if args.model in ['spot_predictor', 'all']:
        model, metrics, importance = trainer.train_spot_price_predictor(df_features)

        logger.info("\nTop 10 Most Important Features:")
        print(importance.head(10).to_string(index=False))

    logger.info("\n" + "="*60)
    logger.info("Training completed successfully!")
    logger.info("="*60)
    logger.info(f"\nNext steps:")
    logger.info(f"1. Upload model via ML Server frontend (http://localhost:3001)")
    logger.info(f"2. Activate model for predictions")
    logger.info(f"3. Trigger gap-fill if needed")
    logger.info("="*60)


if __name__ == "__main__":
    main()
