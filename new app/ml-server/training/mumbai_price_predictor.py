"""
CloudOptim ML Training & Backtesting - Mumbai Region
=====================================================

Complete implementation of the CloudOptim ML strategy:
- Price forecasting (1 hour ahead)
- Risk & stability scoring (relative, cross-sectional)
- Capability grouping
- Backtesting on 2025 Mumbai data
- Extensive visualizations

Hardware: MacBook M4 Air 16GB RAM
Data: Mumbai region, 2023-2025, 10-minute intervals, 4 instance types
"""

# ============================================================================
# IMPORTS
# ============================================================================

import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# ML libraries
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, mean_absolute_percentage_error
import xgboost as xgb
import lightgbm as lgb

# Set visualization style
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")
plt.rcParams['figure.figsize'] = (14, 8)
plt.rcParams['font.size'] = 10

print("="*80)
print("CloudOptim ML Training - Mumbai Region")
print("="*80)
print(f"Start Time: {datetime.now()}")
print("="*80)

# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    # Data paths - YOUR ACTUAL FILE PATHS
    'training_data': '/Users/atharvapudale/Downloads/aws_2023_2024_complete_24months.csv',
    'test_q1': '/Users/atharvapudale/Downloads/mumbai_spot_data_sorted_asc(1-2-3-25).csv',
    'test_q2': '/Users/atharvapudale/Downloads/mumbai_spot_data_sorted_asc(4-5-6-25).csv',
    'test_q3': '/Users/atharvapudale/Downloads/mumbai_spot_data_sorted_asc(7-8-9-25).csv',
    'event_data': '/Users/atharvapudale/Downloads/aws_stress_events_2023_2025.csv',

    'output_dir': './training/outputs',
    'models_dir': './models/uploaded',

    # Data parameters
    'region': 'ap-south-1',  # Mumbai
    'instance_types': ['t3.medium', 't4g.medium', 'c5.large', 't4g.small'],  # Your 4 instances

    # Training parameters
    'train_end_date': '2024-12-31',  # Train on 2023-2024 data
    'test_start_date': '2025-01-01',  # Test on 2025 data

    # Feature engineering
    'lookback_periods': {
        '1h': 6,    # 10-min intervals
        '6h': 36,
        '24h': 144,
        '7d': 1008
    },

    # Forecasting
    'forecast_horizon': 6,  # 1 hour ahead (6 × 10 min)

    # Risk thresholds (for visualization only, not used in scoring)
    'risk_percentiles': {
        'safe': 0.20,      # Bottom 20% risk
        'medium': 0.70,    # Middle 50%
        'risky': 1.00      # Top 30%
    },

    # Use actual data (set to False to generate sample data)
    'use_actual_data': True
}

# Create output directories
Path(CONFIG['output_dir']).mkdir(parents=True, exist_ok=True)
Path(CONFIG['models_dir']).mkdir(parents=True, exist_ok=True)

print("\n📁 Configuration:")
for key, value in CONFIG.items():
    if not isinstance(value, dict):
        if isinstance(value, str) and '/' in value:
            # Show only filename for paths
            print(f"  {key}: {Path(value).name if Path(value).exists() else value}")
        else:
            print(f"  {key}: {value}")

# ============================================================================
# DATA LOADING & PREPARATION
# ============================================================================

print("\n" + "="*80)
print("1. DATA LOADING")
print("="*80)

def standardize_columns(df):
    """Standardize column names to expected format"""
    df.columns = df.columns.str.lower().str.strip()

    # Column mapping
    col_map = {}
    for col in df.columns:
        if 'time' in col or 'date' in col:
            col_map[col] = 'timestamp'
        elif 'spot' in col and 'price' in col:
            col_map[col] = 'spot_price'
        elif 'ondemand' in col or 'on_demand' in col or 'on-demand' in col:
            col_map[col] = 'on_demand_price'
        elif 'instance' in col and 'type' in col:
            col_map[col] = 'instance_type'
        elif col in ['az', 'availability_zone']:
            col_map[col] = 'availability_zone'
        elif col in ['region']:
            col_map[col] = 'region'

    df = df.rename(columns=col_map)

    # Parse timestamp
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')

    # Parse numeric columns
    df['spot_price'] = pd.to_numeric(df['spot_price'], errors='coerce')
    if 'on_demand_price' in df.columns:
        df['on_demand_price'] = pd.to_numeric(df['on_demand_price'], errors='coerce')

    # Infer region from AZ if missing
    if 'region' not in df.columns or df['region'].isna().all():
        if 'availability_zone' in df.columns:
            df['region'] = df['availability_zone'].str.extract(r'^([a-z]+-[a-z]+-\d+)')[0]

    # Drop rows with missing critical data
    df = df.dropna(subset=['spot_price', 'timestamp']).sort_values('timestamp')

    # Drop unnecessary columns that are not used in the model
    unnecessary_cols = ['sps', 'if', 'sourcefile', 't3', 't2']
    cols_to_drop = [col for col in unnecessary_cols if col in df.columns]
    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)

    # Calculate savings if not present
    if 'on_demand_price' in df.columns and 'savings' not in df.columns:
        df['savings'] = ((df['on_demand_price'] - df['spot_price']) / df['on_demand_price']) * 100

    if 'on_demand_price' in df.columns and 'discount' not in df.columns:
        df['discount'] = df['savings'] / 100

    return df

def load_mumbai_spot_data():
    """
    Load Mumbai Spot price data from actual CSV files
    """
    if not CONFIG['use_actual_data']:
        print("\n⚠️  Using sample data mode...")
        print("Creating sample data for demonstration...")
        return generate_sample_mumbai_data()

    print("\n📂 Loading ACTUAL Mumbai Spot price data...")

    # Load training data (2023-2024)
    print(f"\n  Loading training data: {Path(CONFIG['training_data']).name}")
    df_train = pd.read_csv(CONFIG['training_data'])
    df_train = standardize_columns(df_train)

    # Load test data (Q1, Q2, Q3 2025)
    test_dfs = []
    for quarter, path in [('Q1', CONFIG['test_q1']), ('Q2', CONFIG['test_q2']), ('Q3', CONFIG['test_q3'])]:
        print(f"  Loading test {quarter} 2025: {Path(path).name}")
        df_q = pd.read_csv(path)
        df_q = standardize_columns(df_q)
        test_dfs.append(df_q)

    df_test = pd.concat(test_dfs, ignore_index=True)

    # Combine training and test
    df = pd.concat([df_train, df_test], ignore_index=True)

    # Filter for Mumbai region and selected instance types
    df = df[df['region'] == CONFIG['region']]
    df = df[df['instance_type'].isin(CONFIG['instance_types'])]

    # Sort by timestamp
    df = df.sort_values(['instance_type', 'availability_zone', 'timestamp'])

    print(f"\n✓ Loaded {len(df):,} records")
    print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"  Training period: {len(df[df['timestamp'] <= CONFIG['train_end_date']]):,} records")
    print(f"  Test period: {len(df[df['timestamp'] > CONFIG['train_end_date']]):,} records")
    print(f"  Instance types: {sorted(df['instance_type'].unique())}")
    print(f"  Availability zones: {sorted(df['availability_zone'].unique())}")
    print(f"  Pools (instance × AZ): {df.groupby(['instance_type', 'availability_zone']).ngroups}")

    return df

def load_event_data():
    """
    Load AWS stress event data (optional enhancement for feature engineering)
    """
    if not Path(CONFIG['event_data']).exists():
        print("\n⚠️  Event data file not found - skipping event features")
        return None

    print(f"\n📅 Loading event data: {Path(CONFIG['event_data']).name}")
    df_events = pd.read_csv(CONFIG['event_data'])

    # Standardize event columns
    df_events.columns = df_events.columns.str.lower().str.strip()
    date_col = next((c for c in df_events.columns if 'date' in c), None)
    name_col = next((c for c in df_events.columns if 'event' in c or 'name' in c), None)

    rename_map = {}
    if date_col:
        rename_map[date_col] = 'event_date'
    if name_col:
        rename_map[name_col] = 'event_name'

    df_events = df_events.rename(columns=rename_map)
    df_events['event_date'] = pd.to_datetime(df_events['event_date'], errors='coerce')
    df_events = df_events.dropna(subset=['event_date'])

    print(f"✓ Loaded {len(df_events)} events")
    return df_events

def generate_sample_mumbai_data():
    """
    Generate realistic sample data for Mumbai region (10-min intervals)
    """
    print("\n🔧 Generating sample Mumbai Spot price data...")

    # Date range: 2023-01-01 to 2025-03-31 (2+ years)
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2025, 3, 31)

    # 10-minute intervals
    timestamps = pd.date_range(start=start_date, end=end_date, freq='10T')

    # Instance specs (Mumbai pricing)
    instance_specs = {
        'm5.large': {'od_price': 0.096, 'vcpu': 2, 'memory': 8, 'volatility': 0.12},
        'c5.large': {'od_price': 0.085, 'vcpu': 2, 'memory': 4, 'volatility': 0.15},
        'r5.large': {'od_price': 0.126, 'vcpu': 2, 'memory': 16, 'volatility': 0.10},
        't3.large': {'od_price': 0.0832, 'vcpu': 2, 'memory': 8, 'volatility': 0.18}
    }

    azs = ['ap-south-1a', 'ap-south-1b', 'ap-south-1c']

    data = []

    for instance_type in CONFIG['instance_types']:
        specs = instance_specs[instance_type]
        od_price = specs['od_price']
        base_volatility = specs['volatility']

        for az in azs:
            # Base Spot price (50-70% of On-Demand)
            base_discount = np.random.uniform(0.50, 0.70)
            base_spot = od_price * (1 - base_discount)

            for ts in timestamps:
                # Time-based patterns
                hour = ts.hour
                day_of_week = ts.dayofweek
                month = ts.month

                # Daily pattern (cheaper at night)
                time_factor = 1.0 - 0.15 * np.sin(2 * np.pi * hour / 24)

                # Weekly pattern (cheaper on weekends)
                weekly_factor = 0.92 if day_of_week >= 5 else 1.0

                # Seasonal pattern (higher demand in Q4)
                seasonal_factor = 1.05 if month in [10, 11, 12] else 1.0

                # Random volatility
                volatility = np.random.normal(1.0, base_volatility)

                # Occasional spikes (capacity crunch)
                if np.random.random() < 0.02:  # 2% of time
                    spike = np.random.uniform(1.5, 2.5)
                else:
                    spike = 1.0

                # Calculate Spot price
                spot_price = base_spot * time_factor * weekly_factor * seasonal_factor * volatility * spike
                spot_price = np.clip(spot_price, 0.01, od_price * 0.95)  # Never exceed 95% of OD

                savings = ((od_price - spot_price) / od_price) * 100

                data.append({
                    'timestamp': ts,
                    'instance_type': instance_type,
                    'availability_zone': az,
                    'spot_price': round(spot_price, 6),
                    'on_demand_price': od_price,
                    'savings': round(savings, 2)
                })

    df = pd.DataFrame(data)

    # Save generated data
    output_path = Path(CONFIG['data_dir']) / f"spot_prices_{CONFIG['region']}_generated.csv"
    Path(CONFIG['data_dir']).mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    print(f"✓ Generated {len(df):,} records")
    print(f"✓ Saved to: {output_path}")

    return df

# Load spot price data
df_raw = load_mumbai_spot_data()

# Load event data (optional)
df_events = load_event_data() if CONFIG.get('use_actual_data', False) else None

# Display sample
print("\n📊 Sample data:")
print(df_raw.head(10))

# ============================================================================
# FEATURE ENGINEERING
# ============================================================================

print("\n" + "="*80)
print("2. FEATURE ENGINEERING")
print("="*80)

def engineer_features(df):
    """
    Create comprehensive features for price forecasting and risk scoring
    """
    print("\n🔧 Engineering features...")

    df = df.copy()
    df = df.sort_values(['instance_type', 'availability_zone', 'timestamp'])

    # ========================================================================
    # TIME FEATURES
    # ========================================================================
    df['hour'] = df['timestamp'].dt.hour
    df['day_of_week'] = df['timestamp'].dt.dayofweek
    df['month'] = df['timestamp'].dt.month
    df['day_of_month'] = df['timestamp'].dt.day
    df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
    df['is_peak_hour'] = ((df['hour'] >= 9) & (df['hour'] <= 17)).astype(int)
    df['is_night'] = ((df['hour'] >= 22) | (df['hour'] <= 6)).astype(int)

    # Quarter and season
    df['quarter'] = df['timestamp'].dt.quarter
    df['is_q4'] = (df['quarter'] == 4).astype(int)  # High demand quarter

    # ========================================================================
    # PRICE FEATURES
    # ========================================================================
    df['discount'] = 1 - (df['spot_price'] / df['on_demand_price'])
    df['price_ratio'] = df['spot_price'] / df['on_demand_price']
    df['savings_pct'] = df['savings'] / 100

    # ========================================================================
    # ROLLING STATISTICS (per instance_type + AZ)
    # ========================================================================
    print("  Computing rolling statistics...")

    groupby_cols = ['instance_type', 'availability_zone']

    for period_name, window in CONFIG['lookback_periods'].items():
        if window <= 0:
            continue

        # Price statistics
        df[f'price_mean_{period_name}'] = df.groupby(groupby_cols)['spot_price'].transform(
            lambda x: x.rolling(window=window, min_periods=1).mean()
        )
        df[f'price_std_{period_name}'] = df.groupby(groupby_cols)['spot_price'].transform(
            lambda x: x.rolling(window=window, min_periods=1).std()
        )
        df[f'price_min_{period_name}'] = df.groupby(groupby_cols)['spot_price'].transform(
            lambda x: x.rolling(window=window, min_periods=1).min()
        )
        df[f'price_max_{period_name}'] = df.groupby(groupby_cols)['spot_price'].transform(
            lambda x: x.rolling(window=window, min_periods=1).max()
        )

        # Discount statistics
        df[f'discount_mean_{period_name}'] = df.groupby(groupby_cols)['discount'].transform(
            lambda x: x.rolling(window=window, min_periods=1).mean()
        )
        df[f'discount_std_{period_name}'] = df.groupby(groupby_cols)['discount'].transform(
            lambda x: x.rolling(window=window, min_periods=1).std()
        )

    # Volatility ratio
    for period in ['1h', '24h', '7d']:
        if f'price_mean_{period}' in df.columns and f'price_std_{period}' in df.columns:
            df[f'volatility_ratio_{period}'] = df[f'price_std_{period}'] / (df[f'price_mean_{period}'] + 1e-6)

    # ========================================================================
    # SPIKE & CAPACITY CRUSH INDICATORS
    # ========================================================================
    print("  Computing spike and capacity crush indicators...")

    # Price spikes (price jumps > 20% from mean)
    for period in ['24h', '7d']:
        if f'price_mean_{period}' in df.columns:
            df[f'is_spike_{period}'] = (
                (df['spot_price'] > df[f'price_mean_{period}'] * 1.2).astype(int)
            )
            df[f'spike_count_{period}'] = df.groupby(groupby_cols)[f'is_spike_{period}'].transform(
                lambda x: x.rolling(window=CONFIG['lookback_periods'][period], min_periods=1).sum()
            )

    # Near On-Demand (capacity crush indicator)
    df['near_ondemand'] = (df['price_ratio'] > 0.90).astype(int)

    for period in ['24h', '7d']:
        window = CONFIG['lookback_periods'][period]
        df[f'near_od_count_{period}'] = df.groupby(groupby_cols)['near_ondemand'].transform(
            lambda x: x.rolling(window=window, min_periods=1).sum()
        )
        df[f'near_od_percent_{period}'] = df[f'near_od_count_{period}'] / window * 100

    # ========================================================================
    # LAG FEATURES
    # ========================================================================
    print("  Creating lag features...")

    for lag in [1, 6, 36, 144]:  # 10min, 1h, 6h, 24h
        df[f'price_lag_{lag}'] = df.groupby(groupby_cols)['spot_price'].shift(lag)
        df[f'discount_lag_{lag}'] = df.groupby(groupby_cols)['discount'].shift(lag)

    # Price change (momentum)
    df['price_change_1h'] = df['spot_price'] - df['price_lag_6']
    df['price_change_pct_1h'] = (df['price_change_1h'] / (df['price_lag_6'] + 1e-6)) * 100

    # ========================================================================
    # INSTANCE TYPE ENCODING
    # ========================================================================
    label_encoder = LabelEncoder()
    df['instance_type_encoded'] = label_encoder.fit_transform(df['instance_type'])
    df['az_encoded'] = label_encoder.fit_transform(df['availability_zone'])

    # ========================================================================
    # TARGET (1 HOUR AHEAD PRICE)
    # ========================================================================
    forecast_horizon = CONFIG['forecast_horizon']  # 6 steps = 1 hour
    df['target_price_1h'] = df.groupby(groupby_cols)['spot_price'].shift(-forecast_horizon)

    # Fill NaN values from rolling statistics
    df = df.fillna(method='bfill').fillna(method='ffill')

    # Drop rows with missing target
    df_clean = df.dropna(subset=['target_price_1h'])

    print(f"\n✓ Feature engineering complete")
    print(f"  Total features: {len(df_clean.columns)}")
    print(f"  Rows after cleaning: {len(df_clean):,}")

    return df_clean, label_encoder

df_features, label_encoder = engineer_features(df_raw)

# Display feature summary
print("\n📊 Feature columns:")
feature_cols = [col for col in df_features.columns if col not in [
    'timestamp', 'instance_type', 'availability_zone', 'spot_price',
    'on_demand_price', 'savings', 'target_price_1h'
]]
print(f"  {len(feature_cols)} features created")

# ============================================================================
# TRAIN/TEST SPLIT
# ============================================================================

print("\n" + "="*80)
print("3. TRAIN/TEST SPLIT")
print("="*80)

# Split by date
train_mask = df_features['timestamp'] <= pd.to_datetime(CONFIG['train_end_date'])
test_mask = df_features['timestamp'] >= pd.to_datetime(CONFIG['test_start_date'])

df_train = df_features[train_mask].copy()
df_test = df_features[test_mask].copy()

print(f"\n✓ Train set: {len(df_train):,} records")
print(f"  Date range: {df_train['timestamp'].min()} to {df_train['timestamp'].max()}")
print(f"\n✓ Test set: {len(df_test):,} records")
print(f"  Date range: {df_test['timestamp'].min()} to {df_test['timestamp'].max()}")

# ============================================================================
# MODEL TRAINING - PRICE FORECASTING
# ============================================================================

print("\n" + "="*80)
print("4. PRICE FORECASTING MODEL TRAINING")
print("="*80)

# Select features for modeling
feature_cols_model = [
    # Time features
    'hour', 'day_of_week', 'month', 'is_weekend', 'is_peak_hour', 'is_night', 'is_q4',
    # Price features
    'on_demand_price', 'price_ratio', 'discount',
    # Instance encoding
    'instance_type_encoded', 'az_encoded',
    # Rolling statistics
    'price_mean_1h', 'price_std_1h', 'price_mean_6h', 'price_std_6h',
    'price_mean_24h', 'price_std_24h', 'price_min_24h', 'price_max_24h',
    'price_mean_7d', 'price_std_7d',
    'discount_mean_24h', 'discount_std_24h',
    'volatility_ratio_1h', 'volatility_ratio_24h', 'volatility_ratio_7d',
    # Spikes & capacity crush
    'spike_count_24h', 'spike_count_7d',
    'near_od_percent_24h', 'near_od_percent_7d',
    # Lags
    'price_lag_1', 'price_lag_6', 'price_lag_36', 'price_lag_144',
    'discount_lag_1', 'discount_lag_6',
    'price_change_1h', 'price_change_pct_1h'
]

# Ensure all feature columns exist
feature_cols_model = [col for col in feature_cols_model if col in df_train.columns]

print(f"\n📋 Using {len(feature_cols_model)} features for modeling")

# Prepare data
X_train = df_train[feature_cols_model].values
y_train = df_train['target_price_1h'].values

X_test = df_test[feature_cols_model].values
y_test = df_test['target_price_1h'].values

print(f"\n✓ Training set: {X_train.shape}")
print(f"✓ Test set: {X_test.shape}")

# Scale features
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# Train XGBoost model
print("\n🤖 Training XGBoost Price Forecasting Model...")

model_price = xgb.XGBRegressor(
    n_estimators=200,  # Aligned with train_models.py
    max_depth=6,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42,
    n_jobs=-1,
    tree_method='hist'  # Faster on M4 Mac
)

model_price.fit(
    X_train_scaled,
    y_train,
    eval_set=[(X_test_scaled, y_test)],
    verbose=False
)

# Predictions
y_pred_train = model_price.predict(X_train_scaled)
y_pred_test = model_price.predict(X_test_scaled)

# Calculate metrics
metrics = {
    'train_mae': mean_absolute_error(y_train, y_pred_train),
    'test_mae': mean_absolute_error(y_test, y_pred_test),
    'train_rmse': np.sqrt(mean_squared_error(y_train, y_pred_train)),
    'test_rmse': np.sqrt(mean_squared_error(y_test, y_pred_test)),
    'train_r2': r2_score(y_train, y_pred_train),
    'test_r2': r2_score(y_test, y_pred_test),
    'train_mape': mean_absolute_percentage_error(y_train, y_pred_train) * 100,
    'test_mape': mean_absolute_percentage_error(y_test, y_pred_test) * 100
}

print("\n" + "="*80)
print("MODEL PERFORMANCE METRICS")
print("="*80)
for metric, value in metrics.items():
    if 'mae' in metric or 'rmse' in metric:
        print(f"  {metric:20s}: ${value:.6f}")
    elif 'mape' in metric:
        print(f"  {metric:20s}: {value:.2f}%")
    else:
        print(f"  {metric:20s}: {value:.4f}")

# Add predictions to test dataframe
df_test['predicted_price_1h'] = y_pred_test
df_test['prediction_error'] = df_test['predicted_price_1h'] - df_test['target_price_1h']
df_test['prediction_error_pct'] = (df_test['prediction_error'] / df_test['target_price_1h']) * 100

# Feature importance
feature_importance = pd.DataFrame({
    'feature': feature_cols_model,
    'importance': model_price.feature_importances_
}).sort_values('importance', ascending=False)

print("\n📊 Top 15 Most Important Features:")
print(feature_importance.head(15).to_string(index=False))

# ============================================================================
# RISK & STABILITY SCORING (RELATIVE, CROSS-SECTIONAL)
# ============================================================================

print("\n" + "="*80)
print("5. RISK & STABILITY SCORING")
print("="*80)

def calculate_relative_risk_scores(df):
    """
    Calculate relative risk scores using cross-sectional ranking
    (no absolute thresholds)
    """
    print("\n🎯 Calculating relative risk scores...")

    df = df.copy()

    # For each instance_type + AZ combination, calculate risk ingredients
    groupby_cols = ['instance_type', 'availability_zone']

    # Aggregate metrics per pool over test period
    pool_metrics = df.groupby(groupby_cols).agg({
        'volatility_ratio_7d': 'mean',
        'spike_count_7d': 'mean',
        'near_od_percent_7d': 'mean',
        'discount': 'mean',
        'spot_price': 'mean',
        'prediction_error_pct': lambda x: np.abs(x).mean()
    }).reset_index()

    pool_metrics.columns = [
        'instance_type', 'availability_zone',
        'avg_volatility_7d', 'avg_spike_count_7d', 'avg_near_od_pct_7d',
        'avg_discount', 'avg_spot_price', 'avg_pred_error_pct'
    ]

    # Calculate relative ranks (0 to 1)
    N = len(pool_metrics)

    # Higher value = higher risk
    pool_metrics['volatility_rank_score'] = pool_metrics['avg_volatility_7d'].rank() / N
    pool_metrics['spike_rank_score'] = pool_metrics['avg_spike_count_7d'].rank() / N
    pool_metrics['near_od_rank_score'] = pool_metrics['avg_near_od_pct_7d'].rank() / N

    # Lower discount = higher risk
    pool_metrics['discount_rank_score'] = (N - pool_metrics['avg_discount'].rank()) / N

    # Higher prediction error = higher risk
    pool_metrics['pred_error_rank_score'] = pool_metrics['avg_pred_error_pct'].rank() / N

    # Combined risk score (weighted average)
    pool_metrics['risk_score'] = (
        0.30 * pool_metrics['near_od_rank_score'] +      # Capacity crush (most important)
        0.25 * pool_metrics['volatility_rank_score'] +    # Price volatility
        0.15 * pool_metrics['spike_rank_score'] +         # Spike frequency
        0.15 * pool_metrics['discount_rank_score'] +      # Low discount = risky
        0.15 * pool_metrics['pred_error_rank_score']      # Prediction uncertainty
    )

    # Categorize by risk (relative percentiles)
    pool_metrics['risk_category'] = pd.cut(
        pool_metrics['risk_score'],
        bins=[0, 0.20, 0.70, 1.0],
        labels=['SAFE', 'MEDIUM', 'RISKY']
    )

    # Stability score (inverse of risk)
    pool_metrics['stability_score'] = 1 - pool_metrics['risk_score']

    print(f"\n✓ Calculated risk scores for {len(pool_metrics)} pools")

    return pool_metrics

pool_risk_scores = calculate_relative_risk_scores(df_test)

print("\n📊 Pool Risk Scores:")
print(pool_risk_scores.sort_values('risk_score')[
    ['instance_type', 'availability_zone', 'risk_score', 'stability_score', 'risk_category',
     'avg_spot_price', 'avg_discount']
].to_string(index=False))

# ============================================================================
# SAVINGS CALCULATION
# ============================================================================

print("\n" + "="*80)
print("6. SAVINGS ANALYSIS")
print("="*80)

def calculate_savings_analysis(df, pool_scores):
    """
    Calculate actual savings achieved and compare to baseline
    """
    print("\n💰 Calculating savings...")

    # Merge pool scores with test data
    df_analysis = df.merge(
        pool_scores[['instance_type', 'availability_zone', 'risk_score', 'risk_category', 'stability_score']],
        on=['instance_type', 'availability_zone'],
        how='left'
    )

    # Calculate hourly savings per pool
    df_analysis['hourly_savings'] = df_analysis['on_demand_price'] - df_analysis['spot_price']
    df_analysis['monthly_savings'] = df_analysis['hourly_savings'] * 730  # hours/month
    df_analysis['annual_savings'] = df_analysis['monthly_savings'] * 12

    # Aggregate by pool (risk_category is preserved since it's constant per pool)
    savings_by_pool = df_analysis.groupby(['instance_type', 'availability_zone']).agg({
        'hourly_savings': 'mean',
        'monthly_savings': 'mean',
        'annual_savings': 'mean',
        'discount': 'mean',
        'spot_price': 'mean',
        'on_demand_price': 'first',
        'risk_category': 'first',  # All rows for a pool have the same risk_category
        'risk_score': 'first',
        'stability_score': 'first'
    }).reset_index()

    savings_by_pool = savings_by_pool.sort_values('annual_savings', ascending=False)

    print("\n📊 Savings by Pool (sorted by annual savings):")
    print(savings_by_pool.to_string(index=False))

    return df_analysis, savings_by_pool

df_test_analysis, savings_by_pool = calculate_savings_analysis(df_test, pool_risk_scores)

# ============================================================================
# VISUALIZATION - COMPREHENSIVE GRAPHS WITH CLEAR INSIGHTS
# ============================================================================

print("\n" + "="*80)
print("7. GENERATING ENHANCED VISUALIZATIONS")
print("="*80)

# Import enhanced visualization module
# Add the training directory to Python path to ensure visualization_insights can be imported
import os

# Method 1: Try to get the script/notebook directory
try:
    if '__file__' in globals():
        # Running as a script
        script_dir = Path(__file__).parent.resolve()
    else:
        # Running in Jupyter notebook - try to get the notebook's directory
        # Use os.getcwd() which should be the notebook's working directory
        script_dir = Path(os.getcwd()).resolve()
except:
    script_dir = Path.cwd().resolve()

# Add multiple potential paths to ensure the module is found
paths_to_add = [
    str(script_dir),  # Current directory
    str(script_dir / 'training'),  # In case we're in parent directory
    str(script_dir.parent / 'training'),  # In case we're in a subdirectory
]

for path in paths_to_add:
    if os.path.exists(path) and path not in sys.path:
        sys.path.insert(0, path)

# Now import the visualization module
try:
    from visualization_insights import (
        create_price_prediction_comparison,
        create_risk_stability_dashboard,
        create_price_trend_analysis,
        create_model_performance_dashboard,
        create_summary_insights
    )
    print("✓ Successfully imported visualization_insights module")
except ImportError as e:
    print(f"❌ Failed to import visualization_insights: {e}")
    print(f"Current directory: {os.getcwd()}")
    print(f"Script directory: {script_dir}")
    print(f"sys.path: {sys.path[:3]}")
    print("\nPlease ensure visualization_insights.py is in the same directory as this script.")
    raise

# Figure 1: Price Prediction Comparison with Insights
print("\n📈 1. Price Prediction Analysis (Top 4 Pools)...")
fig1 = create_price_prediction_comparison(df_test_analysis, pool_risk_scores)
output_path = Path(CONFIG['output_dir']) / 'price_prediction_comparison.png'
fig1.savefig(output_path, dpi=300, bbox_inches='tight')
plt.show()
print(f"  ✓ Displayed and saved to: {output_path}")

# Figure 2: Risk & Stability Dashboard
print("\n📈 2. Risk & Stability Investment Matrix...")
fig2 = create_risk_stability_dashboard(pool_risk_scores, savings_by_pool)
output_path = Path(CONFIG['output_dir']) / 'risk_stability_dashboard.png'
fig2.savefig(output_path, dpi=300, bbox_inches='tight')
plt.show()
print(f"  ✓ Displayed and saved to: {output_path}")

# Figure 3: Price Trend Analysis
print("\n📈 3. Price Trends & Volatility Patterns...")
fig3 = create_price_trend_analysis(df_test_analysis)
output_path = Path(CONFIG['output_dir']) / 'price_trend_analysis.png'
fig3.savefig(output_path, dpi=300, bbox_inches='tight')
plt.show()
print(f"  ✓ Displayed and saved to: {output_path}")

# Figure 4: Model Performance Dashboard
print("\n📈 4. Model Performance & Diagnostics...")
fig4 = create_model_performance_dashboard(metrics, feature_importance, df_test_analysis)
output_path = Path(CONFIG['output_dir']) / 'model_performance_dashboard.png'
fig4.savefig(output_path, dpi=300, bbox_inches='tight')
plt.show()
print(f"  ✓ Displayed and saved to: {output_path}")

# Figure 5: Executive Summary
print("\n📈 5. Executive Summary - Key Insights & Recommendations...")
fig5 = create_summary_insights(pool_risk_scores, savings_by_pool, metrics)
output_path = Path(CONFIG['output_dir']) / 'executive_summary.png'
fig5.savefig(output_path, dpi=300, bbox_inches='tight')
plt.show()
print(f"  ✓ Displayed and saved to: {output_path}")

print("\n✅ All visualizations generated successfully!")
print(f"   Saved to: {CONFIG['output_dir']}/")

# ============================================================================
# FINAL RECOMMENDATIONS
# ============================================================================

print("\n" + "="*80)
print("8. FINAL RECOMMENDATIONS - CHEAPEST & MOST STABLE POOLS")
print("="*80)

# Combine all metrics for final ranking
final_recommendations = pool_risk_scores.merge(
    savings_by_pool[['instance_type', 'availability_zone', 'annual_savings', 'discount']],
    on=['instance_type', 'availability_zone']
)

# Calculate combined score (balance of stability and savings)
# Normalize scores
final_recommendations['stability_norm'] = (
    final_recommendations['stability_score'] - final_recommendations['stability_score'].min()
) / (final_recommendations['stability_score'].max() - final_recommendations['stability_score'].min())

final_recommendations['savings_norm'] = (
    final_recommendations['annual_savings'] - final_recommendations['annual_savings'].min()
) / (final_recommendations['annual_savings'].max() - final_recommendations['annual_savings'].min())

# Combined score: 60% stability, 40% savings
final_recommendations['combined_score'] = (
    0.60 * final_recommendations['stability_norm'] +
    0.40 * final_recommendations['savings_norm']
)

# Sort by combined score
final_recommendations = final_recommendations.sort_values('combined_score', ascending=False)

print("\n🏆 TOP RECOMMENDATIONS (Ranked by Stability + Savings):")
print("="*80)

for idx, row in final_recommendations.iterrows():
    print(f"\n#{final_recommendations.index.get_loc(idx) + 1}. {row['instance_type']} in {row['availability_zone']}")
    print(f"  Risk Category: {row['risk_category']}")
    print(f"  Stability Score: {row['stability_score']:.4f} (0=unstable, 1=stable)")
    print(f"  Risk Score: {row['risk_score']:.4f} (0=safe, 1=risky)")
    print(f"  Average Spot Price: ${row['avg_spot_price']:.6f}/hour")
    print(f"  Average Discount: {row['avg_discount']*100:.2f}%")
    print(f"  Annual Savings: ${row['annual_savings']:.2f}")
    print(f"  Volatility (7d): {row['avg_volatility_7d']:.4f}")
    print(f"  Capacity Crush %: {row['avg_near_od_pct_7d']:.2f}%")
    print(f"  Combined Score: {row['combined_score']:.4f}")

# ============================================================================
# SUMMARY STATISTICS
# ============================================================================

print("\n" + "="*80)
print("9. SUMMARY STATISTICS")
print("="*80)

summary_stats = {
    'Total Test Records': f"{len(df_test):,}",
    'Test Period': f"{df_test['timestamp'].min()} to {df_test['timestamp'].max()}",
    'Instance Types Analyzed': len(CONFIG['instance_types']),
    'Total Pools (Instance+AZ)': len(pool_risk_scores),
    '': '',
    'Model Performance': '',
    '  Test MAE': f"${metrics['test_mae']:.6f}",
    '  Test RMSE': f"${metrics['test_rmse']:.6f}",
    '  Test R²': f"{metrics['test_r2']:.4f}",
    '  Test MAPE': f"{metrics['test_mape']:.2f}%",
    ' ': '',
    'Risk Distribution': '',
    '  SAFE pools': f"{len(pool_risk_scores[pool_risk_scores['risk_category']=='SAFE'])}",
    '  MEDIUM pools': f"{len(pool_risk_scores[pool_risk_scores['risk_category']=='MEDIUM'])}",
    '  RISKY pools': f"{len(pool_risk_scores[pool_risk_scores['risk_category']=='RISKY'])}",
    '  ': '',
    'Best Pool': '',
    '  Instance Type': final_recommendations.iloc[0]['instance_type'],
    '  Availability Zone': final_recommendations.iloc[0]['availability_zone'],
    '  Risk Category': final_recommendations.iloc[0]['risk_category'],
    '  Stability Score': f"{final_recommendations.iloc[0]['stability_score']:.4f}",
    '  Annual Savings': f"${final_recommendations.iloc[0]['annual_savings']:.2f}",
    '  Discount': f"{final_recommendations.iloc[0]['avg_discount']*100:.2f}%"
}

for key, value in summary_stats.items():
    if key.startswith(' '):
        print(f"  {value}")
    elif key == '':
        print()
    else:
        print(f"{key}: {value}")

# ============================================================================
# SAVE OUTPUTS
# ============================================================================

print("\n" + "="*80)
print("10. SAVING OUTPUTS")
print("="*80)

# Save model
import pickle

output_dir = Path(CONFIG['models_dir'])
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
model_dir = output_dir / f"mumbai_price_predictor_{timestamp}"
model_dir.mkdir(parents=True, exist_ok=True)

# Save model
with open(model_dir / "model.pkl", 'wb') as f:
    pickle.dump(model_price, f)

# Save scaler
with open(model_dir / "scaler.pkl", 'wb') as f:
    pickle.dump(scaler, f)

# Save label encoder
with open(model_dir / "label_encoder.pkl", 'wb') as f:
    pickle.dump(label_encoder, f)

# Save metadata
metadata = {
    'model_name': 'mumbai_price_predictor',
    'model_type': 'spot_price_predictor',
    'model_version': '1.0',
    'trained_date': datetime.now().isoformat(),
    'train_period': f"{df_train['timestamp'].min()} to {df_train['timestamp'].max()}",
    'test_period': f"{df_test['timestamp'].min()} to {df_test['timestamp'].max()}",
    'region': CONFIG['region'],
    'instance_types': CONFIG['instance_types'],
    'metrics': metrics,
    'feature_columns': feature_cols_model,
    'forecast_horizon': CONFIG['forecast_horizon'],
    'algorithm': 'XGBoost',
    'hyperparameters': model_price.get_params(),
    'data_summary': {
        'total_train_records': len(df_train),
        'total_test_records': len(df_test),
        'pools_analyzed': len(pool_risk_scores)
    }
}

import json
with open(model_dir / "metadata.json", 'w') as f:
    json.dump(metadata, f, indent=2, default=str)

# Save feature importance
feature_importance.to_csv(model_dir / "feature_importance.csv", index=False)

# Save pool recommendations
final_recommendations.to_csv(model_dir / "pool_recommendations.csv", index=False)

# Save risk scores
pool_risk_scores.to_csv(model_dir / "pool_risk_scores.csv", index=False)

print(f"\n✓ Model saved to: {model_dir}")
print(f"  - model.pkl")
print(f"  - scaler.pkl")
print(f"  - label_encoder.pkl")
print(f"  - metadata.json")
print(f"  - feature_importance.csv")
print(f"  - pool_recommendations.csv")
print(f"  - pool_risk_scores.csv")

# ============================================================================
# COMPLETION
# ============================================================================

print("\n" + "="*80)
print("✅ TRAINING COMPLETE!")
print("="*80)
print(f"End Time: {datetime.now()}")
print("="*80)

print("\n📊 Quick Summary:")
print(f"  Best Pool: {final_recommendations.iloc[0]['instance_type']} in {final_recommendations.iloc[0]['availability_zone']}")
print(f"  Risk Level: {final_recommendations.iloc[0]['risk_category']}")
print(f"  Annual Savings: ${final_recommendations.iloc[0]['annual_savings']:.2f}")
print(f"  Model Accuracy: R²={metrics['test_r2']:.4f}, MAPE={metrics['test_mape']:.2f}%")

print("\n🎯 Next Steps:")
print("  1. Review the visualizations above")
print("  2. Check saved outputs in:", model_dir)
print("  3. Upload model to ML Server frontend")
print("  4. Activate model for predictions")

print("\n" + "="*80)
