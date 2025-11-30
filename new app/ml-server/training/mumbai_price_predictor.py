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
    # Data paths (ADJUST TO YOUR LOCAL PATHS)
    'data_dir': './training/data',  # Change this to your data directory
    'output_dir': './training/outputs',
    'models_dir': './models/uploaded',

    # Data parameters
    'region': 'ap-south-1',  # Mumbai
    'instance_types': ['m5.large', 'c5.large', 'r5.large', 't3.large'],  # Your 4 instances

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
    }
}

# Create output directories
Path(CONFIG['output_dir']).mkdir(parents=True, exist_ok=True)
Path(CONFIG['models_dir']).mkdir(parents=True, exist_ok=True)

print("\n📁 Configuration:")
for key, value in CONFIG.items():
    if not isinstance(value, dict):
        print(f"  {key}: {value}")

# ============================================================================
# DATA LOADING & PREPARATION
# ============================================================================

print("\n" + "="*80)
print("1. DATA LOADING")
print("="*80)

def load_mumbai_spot_data():
    """
    Load Mumbai Spot price data

    Expected CSV format:
    timestamp,instance_type,availability_zone,spot_price,on_demand_price,savings

    If you have different column names, adjust the mapping below.
    """
    data_path = Path(CONFIG['data_dir']) / f"spot_prices_{CONFIG['region']}.csv"

    if not data_path.exists():
        print(f"\n⚠️  Data file not found: {data_path}")
        print("Creating sample data for demonstration...")
        return generate_sample_mumbai_data()

    print(f"\n📂 Loading data from: {data_path}")
    df = pd.read_csv(data_path)

    # Parse timestamp
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # Filter for Mumbai region and selected instance types
    df = df[df['instance_type'].isin(CONFIG['instance_types'])]

    # Sort by timestamp
    df = df.sort_values(['instance_type', 'availability_zone', 'timestamp'])

    print(f"✓ Loaded {len(df):,} records")
    print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"  Instance types: {df['instance_type'].nunique()}")
    print(f"  Availability zones: {df['availability_zone'].nunique()}")

    return df

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

# Load data
df_raw = load_mumbai_spot_data()

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

    # Aggregate by pool
    savings_by_pool = df_analysis.groupby(['instance_type', 'availability_zone', 'risk_category']).agg({
        'hourly_savings': 'mean',
        'monthly_savings': 'mean',
        'annual_savings': 'mean',
        'discount': 'mean',
        'spot_price': 'mean',
        'on_demand_price': 'first'
    }).reset_index()

    savings_by_pool = savings_by_pool.sort_values('annual_savings', ascending=False)

    print("\n📊 Savings by Pool (sorted by annual savings):")
    print(savings_by_pool.to_string(index=False))

    return df_analysis, savings_by_pool

df_test_analysis, savings_by_pool = calculate_savings_analysis(df_test, pool_risk_scores)

# ============================================================================
# VISUALIZATION - COMPREHENSIVE GRAPHS
# ============================================================================

print("\n" + "="*80)
print("7. GENERATING VISUALIZATIONS")
print("="*80)

# Figure 1: Predicted vs Actual Prices (All Pools)
print("\n📈 1. Predicted vs Actual Prices...")

fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle('Predicted vs Actual Spot Prices - All Instance Types (Mumbai 2025)', fontsize=16, fontweight='bold')

for idx, instance_type in enumerate(CONFIG['instance_types']):
    ax = axes[idx // 2, idx % 2]

    # Filter data for this instance type
    df_inst = df_test_analysis[df_test_analysis['instance_type'] == instance_type]

    # Sample data for visualization (every 60th point = every 10 hours)
    df_sample = df_inst.iloc[::60]

    # Plot
    ax.plot(df_sample['timestamp'], df_sample['target_price_1h'],
            label='Actual Price', linewidth=2, alpha=0.8)
    ax.plot(df_sample['timestamp'], df_sample['predicted_price_1h'],
            label='Predicted Price (1h ahead)', linewidth=2, alpha=0.8, linestyle='--')

    ax.set_title(f'{instance_type}', fontsize=14, fontweight='bold')
    ax.set_xlabel('Date')
    ax.set_ylabel('Spot Price (USD/hour)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.tick_params(axis='x', rotation=45)

plt.tight_layout()
plt.show()
print("  ✓ Displayed")

# Figure 2: Risk Scores and Stability
print("\n📈 2. Risk Scores and Stability...")

fig, axes = plt.subplots(1, 2, figsize=(16, 6))

# Risk score distribution
ax1 = axes[0]
for risk_cat in ['SAFE', 'MEDIUM', 'RISKY']:
    data = pool_risk_scores[pool_risk_scores['risk_category'] == risk_cat]
    ax1.scatter(data['avg_spot_price'], data['risk_score'],
               label=risk_cat, s=200, alpha=0.7)

ax1.set_xlabel('Average Spot Price (USD/hour)', fontsize=12)
ax1.set_ylabel('Risk Score (0=safe, 1=risky)', fontsize=12)
ax1.set_title('Risk Score vs Spot Price', fontsize=14, fontweight='bold')
ax1.legend()
ax1.grid(True, alpha=0.3)

# Stability score by instance type
ax2 = axes[1]
pool_risk_scores_sorted = pool_risk_scores.sort_values('stability_score', ascending=False)
x_pos = np.arange(len(pool_risk_scores_sorted))
colors = pool_risk_scores_sorted['risk_category'].map({'SAFE': 'green', 'MEDIUM': 'orange', 'RISKY': 'red'})

ax2.barh(x_pos, pool_risk_scores_sorted['stability_score'], color=colors, alpha=0.7)
ax2.set_yticks(x_pos)
ax2.set_yticklabels([f"{row['instance_type']} ({row['availability_zone']})"
                      for _, row in pool_risk_scores_sorted.iterrows()], fontsize=9)
ax2.set_xlabel('Stability Score (0=unstable, 1=stable)', fontsize=12)
ax2.set_title('Pool Stability Ranking', fontsize=14, fontweight='bold')
ax2.grid(True, alpha=0.3, axis='x')

plt.tight_layout()
plt.show()
print("  ✓ Displayed")

# Figure 3: Savings Analysis
print("\n📈 3. Savings Analysis...")

fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle('Savings Analysis - Mumbai 2025', fontsize=16, fontweight='bold')

# 3a: Annual savings by pool
ax1 = axes[0, 0]
savings_sorted = savings_by_pool.sort_values('annual_savings', ascending=False)
x_pos = np.arange(len(savings_sorted))
colors_risk = savings_sorted['risk_category'].map({'SAFE': 'green', 'MEDIUM': 'orange', 'RISKY': 'red'})

ax1.barh(x_pos, savings_sorted['annual_savings'], color=colors_risk, alpha=0.7)
ax1.set_yticks(x_pos)
ax1.set_yticklabels([f"{row['instance_type']} ({row['availability_zone']})"
                      for _, row in savings_sorted.iterrows()], fontsize=9)
ax1.set_xlabel('Annual Savings (USD)', fontsize=11)
ax1.set_title('Annual Savings by Pool', fontsize=12, fontweight='bold')
ax1.grid(True, alpha=0.3, axis='x')

# 3b: Discount percentage vs risk
ax2 = axes[0, 1]
for risk_cat in ['SAFE', 'MEDIUM', 'RISKY']:
    data = savings_by_pool[savings_by_pool['risk_category'] == risk_cat]
    ax2.scatter(data['discount'] * 100, data['annual_savings'],
               label=risk_cat, s=200, alpha=0.7)

ax2.set_xlabel('Average Discount (%)', fontsize=11)
ax2.set_ylabel('Annual Savings (USD)', fontsize=11)
ax2.set_title('Discount vs Savings by Risk Category', fontsize=12, fontweight='bold')
ax2.legend()
ax2.grid(True, alpha=0.3)

# 3c: Savings over time (monthly)
ax3 = axes[1, 0]
df_test_analysis['year_month'] = df_test_analysis['timestamp'].dt.to_period('M')
monthly_savings = df_test_analysis.groupby(['year_month', 'instance_type']).agg({
    'monthly_savings': 'mean'
}).reset_index()

for instance_type in CONFIG['instance_types']:
    data = monthly_savings[monthly_savings['instance_type'] == instance_type]
    ax3.plot(data['year_month'].astype(str), data['monthly_savings'],
            label=instance_type, marker='o', linewidth=2)

ax3.set_xlabel('Month', fontsize=11)
ax3.set_ylabel('Average Monthly Savings (USD)', fontsize=11)
ax3.set_title('Monthly Savings Trend', fontsize=12, fontweight='bold')
ax3.legend()
ax3.grid(True, alpha=0.3)
ax3.tick_params(axis='x', rotation=45)

# 3d: Risk vs Savings trade-off
ax4 = axes[1, 1]

# Merge on all three keys including risk_category to get matching rows
merged_risk_savings = pool_risk_scores.merge(
    savings_by_pool,
    on=['instance_type', 'availability_zone', 'risk_category'],
    how='inner'  # Only keep rows that match
)

# Plot risk vs savings
scatter = ax4.scatter(
    merged_risk_savings['risk_score'],
    merged_risk_savings['annual_savings'],
    c=merged_risk_savings['avg_volatility_7d'],
    s=200,
    alpha=0.7,
    cmap='RdYlGn_r',
    edgecolors='black',
    linewidth=0.5
)

ax4.set_xlabel('Risk Score (0=safe, 1=risky)', fontsize=11)
ax4.set_ylabel('Annual Savings (USD)', fontsize=11)
ax4.set_title('Risk vs Savings Trade-off', fontsize=12, fontweight='bold')
ax4.grid(True, alpha=0.3)
cbar = plt.colorbar(scatter, ax=ax4)
cbar.set_label('Volatility (7d)', fontsize=10)

plt.tight_layout()
plt.show()
print("  ✓ Displayed")

# Figure 4: Model Performance
print("\n📈 4. Model Performance Analysis...")

fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle('Price Forecasting Model Performance', fontsize=16, fontweight='bold')

# 4a: Actual vs Predicted scatter
ax1 = axes[0, 0]
sample_size = min(5000, len(y_test))
indices = np.random.choice(len(y_test), sample_size, replace=False)

ax1.scatter(y_test[indices], y_pred_test[indices], alpha=0.5, s=10)
ax1.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()],
         'r--', linewidth=2, label='Perfect Prediction')
ax1.set_xlabel('Actual Price (USD)', fontsize=11)
ax1.set_ylabel('Predicted Price (USD)', fontsize=11)
ax1.set_title(f'Actual vs Predicted (R²={metrics["test_r2"]:.4f})', fontsize=12, fontweight='bold')
ax1.legend()
ax1.grid(True, alpha=0.3)

# 4b: Prediction error distribution
ax2 = axes[0, 1]
errors = df_test_analysis['prediction_error_pct'].dropna()
ax2.hist(errors, bins=50, alpha=0.7, edgecolor='black')
ax2.axvline(x=0, color='r', linestyle='--', linewidth=2, label='Zero Error')
ax2.axvline(x=errors.median(), color='g', linestyle='--', linewidth=2, label=f'Median: {errors.median():.2f}%')
ax2.set_xlabel('Prediction Error (%)', fontsize=11)
ax2.set_ylabel('Frequency', fontsize=11)
ax2.set_title(f'Prediction Error Distribution (MAPE={metrics["test_mape"]:.2f}%)', fontsize=12, fontweight='bold')
ax2.legend()
ax2.grid(True, alpha=0.3)

# 4c: Error by instance type
ax3 = axes[1, 0]
error_by_type = df_test_analysis.groupby('instance_type')['prediction_error_pct'].apply(
    lambda x: np.abs(x).mean()
)
ax3.bar(error_by_type.index, error_by_type.values, alpha=0.7, edgecolor='black')
ax3.set_xlabel('Instance Type', fontsize=11)
ax3.set_ylabel('Mean Absolute Error (%)', fontsize=11)
ax3.set_title('Prediction Error by Instance Type', fontsize=12, fontweight='bold')
ax3.grid(True, alpha=0.3, axis='y')

# 4d: Feature importance (top 20)
ax4 = axes[1, 1]
top_features = feature_importance.head(20)
y_pos = np.arange(len(top_features))
ax4.barh(y_pos, top_features['importance'], alpha=0.7, edgecolor='black')
ax4.set_yticks(y_pos)
ax4.set_yticklabels(top_features['feature'], fontsize=9)
ax4.set_xlabel('Importance Score', fontsize=11)
ax4.set_title('Top 20 Feature Importance', fontsize=12, fontweight='bold')
ax4.grid(True, alpha=0.3, axis='x')

plt.tight_layout()
plt.show()
print("  ✓ Displayed")

# Figure 5: Volatility and Capacity Crush Analysis
print("\n📈 5. Volatility and Capacity Crush Analysis...")

fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle('Volatility and Capacity Indicators - Mumbai 2025', fontsize=16, fontweight='bold')

# 5a: Volatility over time
ax1 = axes[0, 0]
for instance_type in CONFIG['instance_types']:
    df_inst = df_test_analysis[df_test_analysis['instance_type'] == instance_type]
    df_sample = df_inst.iloc[::144]  # Daily samples
    ax1.plot(df_sample['timestamp'], df_sample['volatility_ratio_24h'],
            label=instance_type, linewidth=2, alpha=0.8)

ax1.set_xlabel('Date', fontsize=11)
ax1.set_ylabel('Volatility Ratio (24h)', fontsize=11)
ax1.set_title('Price Volatility Over Time', fontsize=12, fontweight='bold')
ax1.legend()
ax1.grid(True, alpha=0.3)
ax1.tick_params(axis='x', rotation=45)

# 5b: Capacity crush events (near On-Demand)
ax2 = axes[0, 1]
for instance_type in CONFIG['instance_types']:
    df_inst = df_test_analysis[df_test_analysis['instance_type'] == instance_type]
    df_sample = df_inst.iloc[::144]  # Daily samples
    ax2.plot(df_sample['timestamp'], df_sample['near_od_percent_7d'],
            label=instance_type, linewidth=2, alpha=0.8)

ax2.set_xlabel('Date', fontsize=11)
ax2.set_ylabel('Near On-Demand % (7d)', fontsize=11)
ax2.set_title('Capacity Crush Indicator', fontsize=12, fontweight='bold')
ax2.legend()
ax2.grid(True, alpha=0.3)
ax2.tick_params(axis='x', rotation=45)

# 5c: Spike frequency by pool
ax3 = axes[1, 0]
spike_by_pool = pool_risk_scores.sort_values('avg_spike_count_7d', ascending=False)
x_pos = np.arange(len(spike_by_pool))
ax3.barh(x_pos, spike_by_pool['avg_spike_count_7d'], alpha=0.7, edgecolor='black')
ax3.set_yticks(x_pos)
ax3.set_yticklabels([f"{row['instance_type']} ({row['availability_zone']})"
                      for _, row in spike_by_pool.iterrows()], fontsize=9)
ax3.set_xlabel('Average Spike Count (7d)', fontsize=11)
ax3.set_title('Price Spike Frequency by Pool', fontsize=12, fontweight='bold')
ax3.grid(True, alpha=0.3, axis='x')

# 5d: Volatility vs Discount
ax4 = axes[1, 1]
for risk_cat in ['SAFE', 'MEDIUM', 'RISKY']:
    data = pool_risk_scores[pool_risk_scores['risk_category'] == risk_cat]
    ax4.scatter(data['avg_volatility_7d'], data['avg_discount'] * 100,
               label=risk_cat, s=200, alpha=0.7)

ax4.set_xlabel('Average Volatility (7d)', fontsize=11)
ax4.set_ylabel('Average Discount (%)', fontsize=11)
ax4.set_title('Volatility vs Discount Trade-off', fontsize=12, fontweight='bold')
ax4.legend()
ax4.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()
print("  ✓ Displayed")

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
