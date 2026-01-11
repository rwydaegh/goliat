"""Generate publication-quality plots for proxy scores and correlation analysis."""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for headless servers
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.stats import spearmanr

# Set up nice plotting style
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['font.size'] = 11
plt.rcParams['axes.labelsize'] = 12
plt.rcParams['axes.titlesize'] = 13
plt.rcParams['figure.facecolor'] = 'white'

# Use relative paths from script location
script_dir = Path(__file__).parent
base_dir = script_dir.parent
output_dir = base_dir / "results" / "analysis_plots"
output_dir.mkdir(parents=True, exist_ok=True)

# Load data - try multiple locations
proxy_csv = base_dir / "results" / "all_proxy_scores.csv"
if not proxy_csv.exists():
    # Try far_field subdirectory
    alt = list(base_dir.rglob("all_proxy_scores.csv"))
    if alt:
        proxy_csv = alt[0]

corr_csv = base_dir / "results" / "proxy_sapd_correlation.csv"
if not corr_csv.exists():
    alt = list(base_dir.rglob("proxy_sapd_correlation.csv"))
    if alt:
        corr_csv = alt[0]

print(f"Proxy CSV: {proxy_csv}")
print(f"Correlation CSV: {corr_csv}")

proxy_df = pd.read_csv(proxy_csv)
corr_df = pd.read_csv(corr_csv)

print(f"Loaded {len(proxy_df):,} proxy scores")
print(f"Loaded {len(corr_df)} correlation data points")

# ============================================================
# FIGURE 1: Proxy Score Distribution (4-panel)
# ============================================================
fig1, axes = plt.subplots(2, 2, figsize=(12, 10))

# 1a. Histogram
ax = axes[0, 0]
n, bins, patches = ax.hist(proxy_df['proxy_score'], bins=80, edgecolor='none', alpha=0.8, color='steelblue')
ax.axvline(proxy_df['proxy_score'].mean(), color='red', linestyle='--', linewidth=2, label=f"Mean: {proxy_df['proxy_score'].mean():.3f}")
ax.axvline(proxy_df['proxy_score'].quantile(0.95), color='orange', linestyle='--', linewidth=2, label=f"95th pct: {proxy_df['proxy_score'].quantile(0.95):.3f}")
ax.axvline(proxy_df['proxy_score'].max(), color='green', linestyle='-', linewidth=2, label=f"Max: {proxy_df['proxy_score'].max():.3f}")
ax.set_xlabel("Proxy Score (mean |E_combined|²)")
ax.set_ylabel("Count")
ax.set_title("(a) Proxy Score Distribution")
ax.legend(loc='upper right', fontsize=9)

# 1b. Log histogram
ax = axes[0, 1]
ax.hist(np.log10(proxy_df['proxy_score']), bins=80, edgecolor='none', alpha=0.8, color='darkgreen')
ax.set_xlabel("log₁₀(Proxy Score)")
ax.set_ylabel("Count")
ax.set_title("(b) Log-Scale Distribution")

# 1c. CDF
ax = axes[1, 0]
sorted_scores = np.sort(proxy_df['proxy_score'])
cdf = np.arange(1, len(sorted_scores) + 1) / len(sorted_scores)
ax.plot(sorted_scores, cdf * 100, linewidth=2, color='navy')
ax.axhline(95, color='red', linestyle='--', alpha=0.7, label='95th percentile')
ax.axvline(proxy_df['proxy_score'].quantile(0.95), color='red', linestyle='--', alpha=0.7)
ax.fill_between(sorted_scores[cdf >= 0.95], 0, cdf[cdf >= 0.95] * 100, alpha=0.3, color='red', label='Top 5%')
ax.set_xlabel("Proxy Score")
ax.set_ylabel("Cumulative Percentage (%)")
ax.set_title("(c) Cumulative Distribution")
ax.legend(loc='lower right')
ax.set_ylim(0, 100)

# 1d. Score vs Z position (body location)
ax = axes[1, 1]
scatter = ax.scatter(proxy_df['z_mm'], proxy_df['proxy_score'], 
                     c=proxy_df['proxy_score'], cmap='viridis', 
                     alpha=0.4, s=2, rasterized=True)
ax.set_xlabel("Z position (mm) — Head ← → Feet")
ax.set_ylabel("Proxy Score")
ax.set_title("(d) Score vs Body Position")
cbar = plt.colorbar(scatter, ax=ax)
cbar.set_label('Proxy Score')

# Mark top 10
top_10 = proxy_df.nlargest(10, 'proxy_score')
ax.scatter(top_10['z_mm'], top_10['proxy_score'], c='red', s=80, marker='*', 
           edgecolors='white', linewidths=0.5, label='Top 10 candidates', zorder=10)
ax.legend(loc='upper right')

plt.tight_layout()
fig1.savefig(output_dir / "fig1_proxy_distribution.png", dpi=200, bbox_inches='tight')
print(f"Saved: fig1_proxy_distribution.png")

# ============================================================
# FIGURE 2: Proxy vs SAPD Correlation
# ============================================================
fig2, axes = plt.subplots(1, 2, figsize=(12, 5))

# 2a. Scatter with labels
ax = axes[0]
sapd_mW = corr_df['sapd_w_m2'] * 1000  # Convert to mW/m²

ax.scatter(corr_df['proxy_score'], sapd_mW, s=150, c='steelblue', alpha=0.8, edgecolors='white', linewidth=1)

# Add candidate labels
for i, row in corr_df.iterrows():
    ax.annotate(f"#{int(row['candidate_idx'])}", 
               (row['proxy_score'], row['sapd_w_m2'] * 1000),
               textcoords="offset points", xytext=(8, 0), fontsize=10, fontweight='bold')

# Trend line
z = np.polyfit(corr_df['proxy_score'], sapd_mW, 1)
p = np.poly1d(z)
x_line = np.linspace(corr_df['proxy_score'].min() - 0.02, corr_df['proxy_score'].max() + 0.02, 100)
ax.plot(x_line, p(x_line), 'r--', alpha=0.5, linewidth=2, label=f'Linear fit')

# Stats
r = corr_df['proxy_score'].corr(corr_df['sapd_w_m2'])
rho, p_val = spearmanr(corr_df['proxy_score'], corr_df['sapd_w_m2'])

ax.set_xlabel("Proxy Score (mean |E_combined|²)")
ax.set_ylabel("Actual SAPD (mW/m²)")
ax.set_title(f"(a) Proxy vs Actual SAPD\nPearson R² = {r**2:.3f}, Spearman ρ = {rho:.3f}")
ax.legend()

# Highlight the winner
max_idx = corr_df['sapd_w_m2'].idxmax()
ax.scatter(corr_df.loc[max_idx, 'proxy_score'], sapd_mW[max_idx], 
           s=250, facecolors='none', edgecolors='red', linewidth=3, label='Worst case')

# 2b. Rank comparison
ax = axes[1]
proxy_rank = corr_df['proxy_score'].rank(ascending=False)
sapd_rank = corr_df['sapd_w_m2'].rank(ascending=False)

ax.scatter(proxy_rank, sapd_rank, s=150, c='darkorange', alpha=0.8, edgecolors='white', linewidth=1)
for i, row in corr_df.iterrows():
    ax.annotate(f"#{int(row['candidate_idx'])}", 
               (proxy_rank.iloc[i], sapd_rank.iloc[i]),
               textcoords="offset points", xytext=(8, 0), fontsize=10, fontweight='bold')

# Perfect correlation line
ax.plot([0.5, 10.5], [0.5, 10.5], 'g--', linewidth=2, alpha=0.5, label='Perfect rank match')
ax.set_xlabel("Rank by Proxy Score (1 = highest)")
ax.set_ylabel("Rank by Actual SAPD (1 = highest)")
ax.set_title(f"(b) Rank Comparison\n(diagonal = perfect prediction)")
ax.set_xlim(0.5, 10.5)
ax.set_ylim(0.5, 10.5)
ax.set_aspect('equal')
ax.legend(loc='lower right')
ax.invert_yaxis()
ax.invert_xaxis()

plt.tight_layout()
fig2.savefig(output_dir / "fig2_proxy_sapd_correlation.png", dpi=200, bbox_inches='tight')
print(f"Saved: fig2_proxy_sapd_correlation.png")

# ============================================================
# SUMMARY STATS
# ============================================================
print("\n" + "="*60)
print("SUMMARY STATISTICS")
print("="*60)
print(f"\nProxy Score Distribution (n={len(proxy_df):,}):")
print(f"  Mean:  {proxy_df['proxy_score'].mean():.4f}")
print(f"  Std:   {proxy_df['proxy_score'].std():.4f}")
print(f"  Min:   {proxy_df['proxy_score'].min():.4f}")
print(f"  Max:   {proxy_df['proxy_score'].max():.4f}")
print(f"  95th:  {proxy_df['proxy_score'].quantile(0.95):.4f}")

print(f"\nCorrelation Analysis (n={len(corr_df)}):")
print(f"  Pearson R:   {r:.4f}")
print(f"  R-squared:   {r**2:.4f}")
print(f"  Spearman ρ:  {rho:.4f}")
print(f"  p-value:     {p_val:.4f}")

print(f"\nSAPD Results:")
print(f"  Min SAPD:    {corr_df['sapd_w_m2'].min()*1000:.4f} mW/m²")
print(f"  Max SAPD:    {corr_df['sapd_w_m2'].max()*1000:.4f} mW/m²")
print(f"  Ratio:       {corr_df['sapd_w_m2'].max()/corr_df['sapd_w_m2'].min():.2f}x")

print(f"\nPlots saved to: {output_dir}")
plt.close('all')
print("Done!")
