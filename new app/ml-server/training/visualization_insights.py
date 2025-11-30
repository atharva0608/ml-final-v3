"""
Enhanced Visualization Module for Mumbai Spot Price Predictor
Provides clear, insightful graphs with statistical annotations and actionable insights
"""

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D

# Set style for professional visualizations
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")
plt.rcParams['figure.figsize'] = (16, 10)
plt.rcParams['font.size'] = 10
plt.rcParams['axes.titlesize'] = 12
plt.rcParams['axes.labelsize'] = 11
plt.rcParams['xtick.labelsize'] = 9
plt.rcParams['ytick.labelsize'] = 9
plt.rcParams['legend.fontsize'] = 9


def create_price_prediction_comparison(df_test, pool_risk_scores):
    """
    Create a clear comparison of predicted vs actual prices with insights
    """
    fig, axes = plt.subplots(2, 2, figsize=(18, 12))
    fig.suptitle('Mumbai Spot Price Analysis - Key Insights (2025)', fontsize=16, fontweight='bold')

    # Get top 4 pools by combined score
    top_pools = pool_risk_scores.nsmallest(4, 'risk_score')[['instance_type', 'availability_zone']]

    for idx, (ax, (_, pool)) in enumerate(zip(axes.flatten(), top_pools.iterrows())):
        # Filter data for this pool
        pool_data = df_test[
            (df_test['instance_type'] == pool['instance_type']) &
            (df_test['availability_zone'] == pool['availability_zone'])
        ].copy()

        if len(pool_data) == 0:
            continue

        # Sample for visualization (every 144 points = daily)
        pool_data_sample = pool_data.iloc[::144].copy()

        # Plot actual vs predicted
        ax.plot(pool_data_sample['timestamp'], pool_data_sample['target_price_1h'],
                label='Actual Price', color='#2E86AB', linewidth=2, alpha=0.8)
        ax.plot(pool_data_sample['timestamp'], pool_data_sample['predicted_price_1h'],
                label='Predicted Price', color='#A23B72', linewidth=1.5, linestyle='--', alpha=0.8)

        # Calculate and show statistics
        mae = np.mean(np.abs(pool_data['prediction_error']))
        mape = np.mean(np.abs(pool_data['prediction_error_pct']))
        avg_price = pool_data['target_price_1h'].mean()
        price_std = pool_data['target_price_1h'].std()

        # Add horizontal lines for avg price
        ax.axhline(y=avg_price, color='green', linestyle=':', alpha=0.5, linewidth=1)

        # Add shaded region for ±1 std dev
        ax.fill_between(pool_data_sample['timestamp'],
                        avg_price - price_std, avg_price + price_std,
                        alpha=0.1, color='gray', label='±1 Std Dev')

        # Title with insights
        pool_name = f"{pool['instance_type']} ({pool['availability_zone']})"
        ax.set_title(f'{pool_name}\n' +
                    f'Avg: ${avg_price:.4f}/hr | MAE: ${mae:.4f} | MAPE: {mape:.1f}% | Volatility: ${price_std:.4f}',
                    fontsize=11, fontweight='bold')

        ax.set_xlabel('Date', fontsize=10)
        ax.set_ylabel('Spot Price (USD/hour)', fontsize=10)
        ax.legend(loc='upper left', framealpha=0.9)
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis='x', rotation=45)

    plt.tight_layout()
    return fig


def create_risk_stability_dashboard(pool_risk_scores, savings_by_pool):
    """
    Create a comprehensive risk & stability dashboard
    """
    fig, axes = plt.subplots(2, 2, figsize=(18, 12))
    fig.suptitle('Pool Risk & Stability Analysis - Investment Decision Matrix', fontsize=16, fontweight='bold')

    # Merge data
    merged = pool_risk_scores.merge(savings_by_pool, on=['instance_type', 'availability_zone'])

    # 1. Risk Score vs Savings Scatter (Investment Matrix)
    ax1 = axes[0, 0]
    scatter = ax1.scatter(merged['risk_score'], merged['annual_savings'],
                         c=merged['avg_volatility_7d'], s=300, alpha=0.7,
                         cmap='RdYlGn_r', edgecolors='black', linewidth=1.5)

    # Add labels for each point
    for _, row in merged.iterrows():
        ax1.annotate(f"{row['instance_type'][:2]}\n{row['availability_zone'][-1]}",
                    (row['risk_score'], row['annual_savings']),
                    fontsize=8, ha='center', va='center', fontweight='bold')

    # Add quadrant lines
    median_risk = merged['risk_score'].median()
    median_savings = merged['annual_savings'].median()
    ax1.axvline(x=median_risk, color='gray', linestyle='--', alpha=0.5)
    ax1.axhline(y=median_savings, color='gray', linestyle='--', alpha=0.5)

    # Label quadrants
    ax1.text(0.1, merged['annual_savings'].max() * 0.95, 'BEST\n(Low Risk, High Savings)',
             fontsize=10, fontweight='bold', color='green', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    ax1.text(merged['risk_score'].max() * 0.85, merged['annual_savings'].max() * 0.95, 'HIGH REWARD\n(High Risk, High Savings)',
             fontsize=10, fontweight='bold', color='orange', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    ax1.set_xlabel('Risk Score (0=safe, 1=risky)', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Annual Savings (USD)', fontsize=11, fontweight='bold')
    ax1.set_title('Investment Matrix: Risk vs Reward\n(Color = Volatility, Size = Pool)', fontsize=12, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    cbar = plt.colorbar(scatter, ax=ax1)
    cbar.set_label('Price Volatility (7d)', fontsize=9)

    # 2. Stability Score Ranking
    ax2 = axes[0, 1]
    sorted_pools = merged.sort_values('stability_score', ascending=True)
    colors = ['red' if x < 0.33 else 'orange' if x < 0.67 else 'green' for x in sorted_pools['stability_score']]

    y_pos = np.arange(len(sorted_pools))
    ax2.barh(y_pos, sorted_pools['stability_score'], color=colors, alpha=0.7, edgecolor='black')
    ax2.set_yticks(y_pos)
    ax2.set_yticklabels([f"{row['instance_type']} ({row['availability_zone']})"
                         for _, row in sorted_pools.iterrows()], fontsize=9)
    ax2.set_xlabel('Stability Score (1.0 = Most Stable)', fontsize=11, fontweight='bold')
    ax2.set_title('Pool Stability Ranking\n(Green = Stable, Orange = Moderate, Red = Unstable)',
                  fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='x')
    ax2.axvline(x=0.5, color='gray', linestyle='--', alpha=0.5, label='Medium Threshold')

    # Add value labels
    for i, v in enumerate(sorted_pools['stability_score']):
        ax2.text(v + 0.01, i, f'{v:.3f}', va='center', fontsize=8)

    # 3. Discount % by Instance Type
    ax3 = axes[1, 0]
    discount_data = merged.groupby('instance_type').agg({
        'discount': ['mean', 'min', 'max']
    }).reset_index()
    discount_data.columns = ['instance_type', 'avg_discount', 'min_discount', 'max_discount']
    discount_data = discount_data.sort_values('avg_discount', ascending=False)

    x_pos = np.arange(len(discount_data))
    bars = ax3.bar(x_pos, discount_data['avg_discount'] * 100,
                   color='#2E86AB', alpha=0.7, edgecolor='black', linewidth=1.5)

    # Add error bars for min/max
    ax3.errorbar(x_pos, discount_data['avg_discount'] * 100,
                yerr=[discount_data['avg_discount'] * 100 - discount_data['min_discount'] * 100,
                      discount_data['max_discount'] * 100 - discount_data['avg_discount'] * 100],
                fmt='none', color='black', capsize=5, capthick=2)

    ax3.set_xticks(x_pos)
    ax3.set_xticklabels(discount_data['instance_type'], fontsize=10, fontweight='bold')
    ax3.set_ylabel('Average Discount (%)', fontsize=11, fontweight='bold')
    ax3.set_title('Spot Discount by Instance Type\n(Error bars = min/max across AZs)',
                  fontsize=12, fontweight='bold')
    ax3.grid(True, alpha=0.3, axis='y')

    # Add value labels on bars
    for bar, val in zip(bars, discount_data['avg_discount'] * 100):
        height = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2., height + 1,
                f'{val:.1f}%', ha='center', va='bottom', fontsize=9, fontweight='bold')

    # 4. Total Savings Potential
    ax4 = axes[1, 1]
    savings_sorted = merged.sort_values('annual_savings', ascending=False)

    bars = ax4.barh(range(len(savings_sorted)), savings_sorted['annual_savings'],
                    color=['green' if r < 0.4 else 'orange' if r < 0.6 else 'red'
                          for r in savings_sorted['risk_score']],
                    alpha=0.7, edgecolor='black', linewidth=1)

    ax4.set_yticks(range(len(savings_sorted)))
    ax4.set_yticklabels([f"{row['instance_type']} ({row['availability_zone']})"
                         for _, row in savings_sorted.iterrows()], fontsize=9)
    ax4.set_xlabel('Annual Savings (USD)', fontsize=11, fontweight='bold')
    ax4.set_title('Annual Savings Potential\n(Color = Risk Level)', fontsize=12, fontweight='bold')
    ax4.grid(True, alpha=0.3, axis='x')

    # Add value labels
    for i, v in enumerate(savings_sorted['annual_savings']):
        ax4.text(v + 10, i, f'${v:.0f}', va='center', fontsize=8)

    # Add legend for risk colors
    legend_elements = [Line2D([0], [0], color='green', lw=4, label='Low Risk (<0.4)'),
                      Line2D([0], [0], color='orange', lw=4, label='Medium Risk (0.4-0.6)'),
                      Line2D([0], [0], color='red', lw=4, label='High Risk (>0.6)')]
    ax4.legend(handles=legend_elements, loc='lower right', framealpha=0.9)

    plt.tight_layout()
    return fig


def create_price_trend_analysis(df_test):
    """
    Create price trend and volatility analysis over time
    """
    fig, axes = plt.subplots(2, 2, figsize=(18, 12))
    fig.suptitle('Price Trend & Volatility Analysis - Temporal Patterns', fontsize=16, fontweight='bold')

    # Group by instance type for analysis
    for idx, instance_type in enumerate(['m5.large', 'c5.large', 'r5.large', 't3.large']):
        ax = axes.flatten()[idx]

        # Filter data
        instance_data = df_test[df_test['instance_type'] == instance_type].copy()

        # Calculate monthly averages
        instance_data['year_month'] = instance_data['timestamp'].dt.to_period('M')
        monthly_stats = instance_data.groupby('year_month').agg({
            'spot_price': ['mean', 'min', 'max', 'std']
        }).reset_index()
        monthly_stats.columns = ['month', 'avg_price', 'min_price', 'max_price', 'volatility']
        monthly_stats['month'] = monthly_stats['month'].dt.to_timestamp()

        # Plot average price with range
        ax.plot(monthly_stats['month'], monthly_stats['avg_price'],
                label='Avg Price', color='#2E86AB', linewidth=2.5, marker='o', markersize=6)
        ax.fill_between(monthly_stats['month'],
                        monthly_stats['min_price'], monthly_stats['max_price'],
                        alpha=0.2, color='#2E86AB', label='Price Range (Min-Max)')

        # Add trend line
        z = np.polyfit(range(len(monthly_stats)), monthly_stats['avg_price'], 1)
        p = np.poly1d(z)
        trend_label = 'Upward Trend' if z[0] > 0 else 'Downward Trend'
        ax.plot(monthly_stats['month'], p(range(len(monthly_stats))),
                "--", color='red', linewidth=2, alpha=0.7, label=trend_label)

        # Calculate trend percentage
        trend_pct = (monthly_stats['avg_price'].iloc[-1] - monthly_stats['avg_price'].iloc[0]) / monthly_stats['avg_price'].iloc[0] * 100

        # Title with insights
        ax.set_title(f'{instance_type}\n' +
                    f'Avg: ${monthly_stats["avg_price"].mean():.4f}/hr | ' +
                    f'Volatility: ${monthly_stats["volatility"].mean():.4f} | ' +
                    f'Trend: {trend_pct:+.1f}%',
                    fontsize=11, fontweight='bold')

        ax.set_xlabel('Month', fontsize=10)
        ax.set_ylabel('Spot Price (USD/hour)', fontsize=10)
        ax.legend(loc='best', framealpha=0.9)
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis='x', rotation=45)

    plt.tight_layout()
    return fig


def create_model_performance_dashboard(metrics, feature_importance, df_test):
    """
    Create model performance and insights dashboard
    """
    fig = plt.figure(figsize=(18, 12))
    gs = fig.add_gridspec(3, 2, hspace=0.3, wspace=0.3)
    fig.suptitle('Model Performance & Feature Analysis - Diagnostic Dashboard', fontsize=16, fontweight='bold')

    # 1. Feature Importance (Top 15)
    ax1 = fig.add_subplot(gs[0, :])
    top_features = feature_importance.head(15)
    colors = plt.cm.viridis(np.linspace(0.3, 0.9, len(top_features)))

    bars = ax1.barh(range(len(top_features)), top_features['importance'],
                    color=colors, edgecolor='black', linewidth=1)
    ax1.set_yticks(range(len(top_features)))
    ax1.set_yticklabels(top_features['feature'], fontsize=10)
    ax1.set_xlabel('Importance Score', fontsize=11, fontweight='bold')
    ax1.set_title('Top 15 Most Important Features for Price Prediction\n(Higher = More Influential)',
                  fontsize=12, fontweight='bold')
    ax1.grid(True, alpha=0.3, axis='x')

    # Add value labels
    for i, (bar, val) in enumerate(zip(bars, top_features['importance'])):
        width = bar.get_width()
        ax1.text(width + 0.002, i, f'{val:.3f}', va='center', fontsize=8)

    # 2. Prediction Error Distribution
    ax2 = fig.add_subplot(gs[1, 0])
    errors = df_test['prediction_error'].dropna()
    ax2.hist(errors, bins=50, color='#A23B72', alpha=0.7, edgecolor='black')
    ax2.axvline(x=0, color='red', linestyle='--', linewidth=2, label='Perfect Prediction')
    ax2.axvline(x=errors.mean(), color='green', linestyle='--', linewidth=2,
                label=f'Mean Error: ${errors.mean():.4f}')

    ax2.set_xlabel('Prediction Error (USD)', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Frequency', fontsize=11, fontweight='bold')
    ax2.set_title(f'Prediction Error Distribution\nStd Dev: ${errors.std():.4f} | Median: ${errors.median():.4f}',
                  fontsize=12, fontweight='bold')
    ax2.legend(loc='upper right', framealpha=0.9)
    ax2.grid(True, alpha=0.3)

    # 3. Model Metrics Comparison
    ax3 = fig.add_subplot(gs[1, 1])
    metric_names = ['Train MAE', 'Test MAE', 'Train RMSE', 'Test RMSE']
    metric_values = [metrics['train_mae'], metrics['test_mae'],
                    metrics['train_rmse'], metrics['test_rmse']]
    colors_metrics = ['green', 'orange', 'green', 'orange']

    bars = ax3.bar(range(len(metric_names)), metric_values,
                   color=colors_metrics, alpha=0.7, edgecolor='black', linewidth=1.5)
    ax3.set_xticks(range(len(metric_names)))
    ax3.set_xticklabels(metric_names, fontsize=10, rotation=15)
    ax3.set_ylabel('Error (USD)', fontsize=11, fontweight='bold')
    ax3.set_title('Model Error Metrics\n(Lower = Better, Green = Train, Orange = Test)',
                  fontsize=12, fontweight='bold')
    ax3.grid(True, alpha=0.3, axis='y')

    # Add value labels
    for bar, val in zip(bars, metric_values):
        height = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2., height + 0.0001,
                f'${val:.4f}', ha='center', va='bottom', fontsize=9, fontweight='bold')

    # 4. R² Score Visualization
    ax4 = fig.add_subplot(gs[2, 0])
    r2_labels = ['Train R²', 'Test R²']
    r2_values = [metrics['train_r2'], metrics['test_r2']]
    r2_target = [0.85, 0.85]  # Target performance

    x = np.arange(len(r2_labels))
    width = 0.35

    bars1 = ax4.bar(x - width/2, r2_values, width, label='Actual',
                    color=['green' if v >= 0.6 else 'orange' if v >= 0.4 else 'red' for v in r2_values],
                    alpha=0.7, edgecolor='black', linewidth=1.5)
    bars2 = ax4.bar(x + width/2, r2_target, width, label='Target',
                    color='gray', alpha=0.3, edgecolor='black', linewidth=1.5)

    ax4.set_ylabel('R² Score', fontsize=11, fontweight='bold')
    ax4.set_title('R² Score: Variance Explained\n(1.0 = Perfect, >0.6 = Good, <0.4 = Poor)',
                  fontsize=12, fontweight='bold')
    ax4.set_xticks(x)
    ax4.set_xticklabels(r2_labels, fontsize=10)
    ax4.legend(loc='upper right', framealpha=0.9)
    ax4.grid(True, alpha=0.3, axis='y')
    ax4.set_ylim(0, 1.0)

    # Add value labels
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax4.text(bar.get_x() + bar.get_width()/2., height + 0.02,
                    f'{height:.3f}', ha='center', va='bottom', fontsize=9, fontweight='bold')

    # 5. MAPE Comparison
    ax5 = fig.add_subplot(gs[2, 1])
    mape_labels = ['Train MAPE', 'Test MAPE']
    mape_values = [metrics['train_mape'], metrics['test_mape']]

    bars = ax5.bar(range(len(mape_labels)), mape_values,
                   color=['green' if v < 10 else 'orange' if v < 20 else 'red' for v in mape_values],
                   alpha=0.7, edgecolor='black', linewidth=1.5)
    ax5.set_xticks(range(len(mape_labels)))
    ax5.set_xticklabels(mape_labels, fontsize=10)
    ax5.set_ylabel('MAPE (%)', fontsize=11, fontweight='bold')
    ax5.set_title('Mean Absolute Percentage Error\n(<10% = Excellent, <20% = Good, >20% = Poor)',
                  fontsize=12, fontweight='bold')
    ax5.grid(True, alpha=0.3, axis='y')

    # Add threshold line
    ax5.axhline(y=15, color='orange', linestyle='--', alpha=0.5, label='Target (15%)')
    ax5.legend(loc='upper right', framealpha=0.9)

    # Add value labels
    for bar, val in zip(bars, mape_values):
        height = bar.get_height()
        ax5.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                f'{val:.2f}%', ha='center', va='bottom', fontsize=9, fontweight='bold')

    return fig


def create_summary_insights(pool_risk_scores, savings_by_pool, metrics):
    """
    Create a summary dashboard with key insights and recommendations
    """
    fig = plt.figure(figsize=(18, 10))
    gs = fig.add_gridspec(2, 3, hspace=0.3, wspace=0.3)
    fig.suptitle('Executive Summary - Key Insights & Recommendations', fontsize=16, fontweight='bold')

    # Merge data
    merged = pool_risk_scores.merge(savings_by_pool, on=['instance_type', 'availability_zone'])

    # 1. Best Pool Recommendation
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.axis('off')

    best_pool = merged.nsmallest(1, 'risk_score').iloc[0]

    recommendation_text = f"""
    🏆 RECOMMENDED POOL

    Instance: {best_pool['instance_type']}
    Zone: {best_pool['availability_zone']}

    💰 Annual Savings: ${best_pool['annual_savings']:.2f}
    📊 Discount: {best_pool['discount']*100:.1f}%
    🛡️ Stability: {best_pool['stability_score']:.3f}/1.0
    ⚠️ Risk: {best_pool['risk_score']:.3f}/1.0

    💡 Why This Pool?
    - {('Highest stability score' if best_pool['stability_score'] == merged['stability_score'].max() else 'Good stability')}
    - {('Best discount rate' if best_pool['discount'] == merged['discount'].max() else 'Competitive discount')}
    - ${best_pool['avg_spot_price']:.4f}/hr avg price
    """

    ax1.text(0.1, 0.95, recommendation_text, transform=ax1.transAxes,
            fontsize=11, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.8),
            family='monospace')

    # 2. Risk Distribution
    ax2 = fig.add_subplot(gs[0, 1])
    risk_bins = pd.cut(merged['risk_score'], bins=[0, 0.3, 0.6, 1.0], labels=['Low', 'Medium', 'High'])
    risk_counts = risk_bins.value_counts()

    colors_risk = ['green', 'orange', 'red']
    wedges, texts, autotexts = ax2.pie(risk_counts, labels=risk_counts.index, autopct='%1.0f%%',
                                       colors=colors_risk, startangle=90,
                                       textprops={'fontsize': 11, 'fontweight': 'bold'})
    ax2.set_title('Risk Distribution Across Pools\n(Lower Risk = Safer Investment)',
                  fontsize=12, fontweight='bold')

    # 3. Total Savings Potential
    ax3 = fig.add_subplot(gs[0, 2])
    ax3.axis('off')

    total_savings = merged['annual_savings'].sum()
    avg_discount = merged['discount'].mean() * 100
    max_savings_pool = merged.nlargest(1, 'annual_savings').iloc[0]

    savings_text = f"""
    💵 TOTAL SAVINGS POTENTIAL

    All Pools Combined: ${total_savings:,.2f}/year
    Average Discount: {avg_discount:.1f}%

    Top Saver:
    {max_savings_pool['instance_type']} ({max_savings_pool['availability_zone']})
    ${max_savings_pool['annual_savings']:.2f}/year

    📈 Savings Range:
    Min: ${merged['annual_savings'].min():.2f}
    Max: ${merged['annual_savings'].max():.2f}
    """

    ax3.text(0.1, 0.95, savings_text, transform=ax3.transAxes,
            fontsize=11, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8),
            family='monospace')

    # 4. Model Performance Summary
    ax4 = fig.add_subplot(gs[1, 0])
    ax4.axis('off')

    performance_text = f"""
    🤖 MODEL PERFORMANCE

    Test R²: {metrics['test_r2']:.3f}
    Test MAE: ${metrics['test_mae']:.4f}
    Test MAPE: {metrics['test_mape']:.2f}%

    Interpretation:
    - R² = {metrics['test_r2']:.1%} variance explained
    - {'✅ Good' if metrics['test_r2'] > 0.6 else '⚠️ Moderate' if metrics['test_r2'] > 0.4 else '❌ Needs improvement'}
    - MAPE: {'Excellent' if metrics['test_mape'] < 10 else 'Good' if metrics['test_mape'] < 20 else 'Acceptable'} accuracy
    """

    ax4.text(0.1, 0.95, performance_text, transform=ax4.transAxes,
            fontsize=11, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8),
            family='monospace')

    # 5. Instance Type Comparison
    ax5 = fig.add_subplot(gs[1, 1:])

    instance_summary = merged.groupby('instance_type').agg({
        'annual_savings': 'mean',
        'discount': 'mean',
        'stability_score': 'mean',
        'risk_score': 'mean'
    }).reset_index()
    instance_summary = instance_summary.sort_values('stability_score', ascending=False)

    x = np.arange(len(instance_summary))
    width = 0.2

    ax5.bar(x - 1.5*width, instance_summary['annual_savings']/100, width,
            label='Savings ($100s)', color='green', alpha=0.7)
    ax5.bar(x - 0.5*width, instance_summary['discount']*100, width,
            label='Discount (%)', color='blue', alpha=0.7)
    ax5.bar(x + 0.5*width, instance_summary['stability_score']*100, width,
            label='Stability (%)', color='purple', alpha=0.7)
    ax5.bar(x + 1.5*width, (1-instance_summary['risk_score'])*100, width,
            label='Safety (%)', color='orange', alpha=0.7)

    ax5.set_xlabel('Instance Type', fontsize=11, fontweight='bold')
    ax5.set_ylabel('Score / Value', fontsize=11, fontweight='bold')
    ax5.set_title('Instance Type Comparison (All Metrics Normalized to 0-100 scale)',
                  fontsize=12, fontweight='bold')
    ax5.set_xticks(x)
    ax5.set_xticklabels(instance_summary['instance_type'], fontsize=10, fontweight='bold')
    ax5.legend(loc='upper right', framealpha=0.9)
    ax5.grid(True, alpha=0.3, axis='y')

    return fig
