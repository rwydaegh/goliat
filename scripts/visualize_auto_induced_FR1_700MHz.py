"""
Quick visualization of auto_induced_FR1 results at 700 MHz.
Four phantoms: duke (adult male), ella (adult female),
               eartha (6y girl), thelonious (child boy).
"""

import json
import os
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy.stats import spearmanr

# ── paths ─────────────────────────────────────────────────────────────────────
BASE = r"c:\Users\rwydaegh\OneDrive - UGent\rwydaegh\GOLIAT code\goliat\results\auto_induced_FR1\extracted"
PHANTOMS = ["duke", "ella", "eartha", "thelonious"]
LABELS = {"duke": "Duke\n(adult ♂)", "ella": "Ella\n(adult ♀)", "eartha": "Eartha\n(child ♀, 6y)", "thelonious": "Thelonious\n(child ♂)"}
COLORS = {"duke": "#2166ac", "ella": "#4dac26", "eartha": "#d01c8b", "thelonious": "#f1a340"}
ADULTS = ["duke", "ella"]
CHILDREN = ["eartha", "thelonious"]

# ── load data ─────────────────────────────────────────────────────────────────
summaries = {}
proxy_dfs = {}

for ph in PHANTOMS:
    with open(os.path.join(BASE, ph, "auto_induced_summary.json")) as f:
        summaries[ph] = json.load(f)
    proxy_dfs[ph] = pd.read_csv(os.path.join(BASE, ph, "all_proxy_scores.csv"))


# ── derived tables ─────────────────────────────────────────────────────────────
def extraction_df(ph):
    ers = summaries[ph]["extraction_results"]
    rows = []
    for e in ers:
        rows.append(
            {
                "candidate_idx": e["candidate_idx"],
                "peak_sar_10g_mWkg": e["peak_sar_10g_W_kg"] * 1000,
                "wb_sar_uWkg": e["whole_body_sar_W_kg"] * 1e6,
            }
        )
    df = pd.DataFrame(rows)
    # merge hotspot scores from candidates list (first 20 sorted by score)
    cands = summaries[ph]["candidates"][:20]
    score_map = {i + 1: c["hotspot_score"] for i, c in enumerate(cands)}
    df["hotspot_score"] = df["candidate_idx"].map(score_map)
    df["z_mm"] = [cands[i]["voxel_idx"][2] for i in range(len(df))]
    return df


ext_dfs = {ph: extraction_df(ph) for ph in PHANTOMS}

# ── figure layout ──────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(18, 20))
fig.suptitle("Auto-Induced Exposure  –  FR1 / 700 MHz  (all 4 phantoms)", fontsize=16, fontweight="bold", y=0.99)

gs = gridspec.GridSpec(4, 4, figure=fig, hspace=0.55, wspace=0.42)

# ══════════════════════════════════════════════════════════════════════════════
# ROW 0  –  Hotspot-score distributions (10k samples, one panel per phantom)
# ══════════════════════════════════════════════════════════════════════════════
for col, ph in enumerate(PHANTOMS):
    ax = fig.add_subplot(gs[0, col])
    scores = proxy_dfs[ph]["proxy_score"]
    top20 = sorted([c["hotspot_score"] for c in summaries[ph]["candidates"][:20]], reverse=True)

    ax.hist(scores, bins=80, color=COLORS[ph], alpha=0.7, edgecolor="none")
    # mark the top-20 selected candidates
    for s in top20:
        ax.axvline(s, color="k", lw=0.6, alpha=0.5)
    ax.axvline(top20[0], color="red", lw=1.5, label=f"top-1 ({top20[0]:.2f})")

    ax.set_title(LABELS[ph], fontsize=10, fontweight="bold")
    ax.set_xlabel("Hotspot score (proxy)", fontsize=8)
    ax.set_ylabel("# samples" if col == 0 else "", fontsize=8)
    ax.set_xlim(left=0)
    ax.legend(fontsize=7, loc="upper right")
    ax.tick_params(labelsize=8)

    # small inset text
    pct = (scores > top20[-1]).mean() * 100
    ax.text(
        0.97,
        0.6,
        f"top-20 threshold\n= {top20[-1]:.2f}\n({pct:.1f}% of samples)",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=7,
        bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.8),
    )

# ══════════════════════════════════════════════════════════════════════════════
# ROW 1  –  Proxy score vs actual peak SAR 10g (rank scatter + Spearman r)
# ══════════════════════════════════════════════════════════════════════════════
for col, ph in enumerate(PHANTOMS):
    ax = fig.add_subplot(gs[1, col])
    df = ext_dfs[ph].dropna(subset=["hotspot_score"])
    xs = df["hotspot_score"]
    ys = df["peak_sar_10g_mWkg"]

    rho, pval = spearmanr(xs, ys)

    sc = ax.scatter(xs, ys, c=df["candidate_idx"], cmap="plasma", s=60, zorder=3)
    # annotate worst candidate
    wc = summaries[ph]["worst_case"]
    wc_row = df[df["candidate_idx"] == wc["candidate_idx"]]
    if not wc_row.empty:
        ax.scatter(wc_row["hotspot_score"], wc_row["peak_sar_10g_mWkg"], marker="*", s=250, color="red", zorder=5, label="worst case")

    ax.set_xlabel("Hotspot score (proxy)", fontsize=8)
    ax.set_ylabel("Peak SAR$_{10g}$ [mW/kg]" if col == 0 else "", fontsize=8)
    ax.set_title(f"{LABELS[ph]}\nSpearman ρ = {rho:.2f} (p={pval:.3f})", fontsize=9)
    ax.legend(fontsize=7)
    ax.tick_params(labelsize=8)
    plt.colorbar(sc, ax=ax, label="candidate #", pad=0.01).ax.tick_params(labelsize=7)

# ══════════════════════════════════════════════════════════════════════════════
# ROW 2  –  Spatial distribution of top-20 candidates (x-z view, body height)
# ══════════════════════════════════════════════════════════════════════════════
for col, ph in enumerate(PHANTOMS):
    ax = fig.add_subplot(gs[2, col])
    cands = summaries[ph]["candidates"][:20]
    xs = [c["voxel_idx"][0] for c in cands]  # voxel x
    zs = [float(c["voxel_idx"][2]) for c in cands]  # voxel z (height)
    sc_vals = [c["hotspot_score"] for c in cands]

    sc = ax.scatter(xs, zs, c=sc_vals, cmap="YlOrRd", s=80, edgecolors="k", lw=0.4, vmin=0, vmax=max(sc_vals))

    # mark actual worst case
    wc_ci = summaries[ph]["worst_case"]["candidate_idx"] - 1  # 0-indexed
    if wc_ci < len(cands):
        ax.scatter(xs[wc_ci], zs[wc_ci], marker="*", s=250, color="red", zorder=5, label=f"worst SAR (cand {wc_ci + 1})")

    plt.colorbar(sc, ax=ax, label="hotspot score").ax.tick_params(labelsize=7)
    ax.set_title(f"{LABELS[ph]}", fontsize=10, fontweight="bold")
    ax.set_xlabel("Voxel x", fontsize=8)
    ax.set_ylabel("Voxel z (height)" if col == 0 else "", fontsize=8)
    ax.legend(fontsize=7)
    ax.tick_params(labelsize=8)

# ══════════════════════════════════════════════════════════════════════════════
# ROW 3  –  Summary bars: worst-case peak SAR and whole-body SAR across phantoms
# ══════════════════════════════════════════════════════════════════════════════
ax_peak = fig.add_subplot(gs[3, :2])
ax_wb = fig.add_subplot(gs[3, 2:])

peak_vals = []
wb_vals = []
bar_colors = []
bar_labels = []

for ph in PHANTOMS:
    wc = summaries[ph]["worst_case"]
    peak_vals.append(wc["peak_sar_10g_W_kg"] * 1000)
    wb_vals.append(wc["whole_body_sar_W_kg"] * 1e6)
    bar_colors.append(COLORS[ph])
    bar_labels.append(LABELS[ph].replace("\n", " "))

x = np.arange(len(PHANTOMS))
width = 0.5

bars1 = ax_peak.bar(x, peak_vals, width, color=bar_colors, edgecolor="k", lw=0.7, alpha=0.85)
ax_peak.set_xticks(x)
ax_peak.set_xticklabels(bar_labels, fontsize=9)
ax_peak.set_ylabel("Worst-case peak SAR$_{10g}$ [mW/kg]", fontsize=9)
ax_peak.set_title("Worst-case Peak SAR$_{10g}$ (per phantom)", fontsize=10, fontweight="bold")
ax_peak.tick_params(labelsize=8)
for b, v in zip(bars1, peak_vals):
    ax_peak.text(b.get_x() + b.get_width() / 2, v + 0.003, f"{v:.3f}", ha="center", va="bottom", fontsize=8)

# children vs adults ratio
child_mean = np.mean([peak_vals[PHANTOMS.index(ph)] for ph in CHILDREN])
adult_mean = np.mean([peak_vals[PHANTOMS.index(ph)] for ph in ADULTS])
ax_peak.text(
    0.97,
    0.97,
    f"Child / Adult\npeak SAR ratio:\n{child_mean / adult_mean:.2f}×",
    transform=ax_peak.transAxes,
    ha="right",
    va="top",
    fontsize=9,
    bbox=dict(boxstyle="round,pad=0.4", fc="#fff9c4", ec="orange", lw=1.2),
)

bars2 = ax_wb.bar(x, wb_vals, width, color=bar_colors, edgecolor="k", lw=0.7, alpha=0.85)
ax_wb.set_xticks(x)
ax_wb.set_xticklabels(bar_labels, fontsize=9)
ax_wb.set_ylabel("Worst-case whole-body SAR [µW/kg]", fontsize=9)
ax_wb.set_title("Worst-case Whole-Body SAR (per phantom)", fontsize=10, fontweight="bold")
ax_wb.tick_params(labelsize=8)
for b, v in zip(bars2, wb_vals):
    ax_wb.text(b.get_x() + b.get_width() / 2, v + 0.05, f"{v:.2f}", ha="center", va="bottom", fontsize=8)

child_mean_wb = np.mean([wb_vals[PHANTOMS.index(ph)] for ph in CHILDREN])
adult_mean_wb = np.mean([wb_vals[PHANTOMS.index(ph)] for ph in ADULTS])
ax_wb.text(
    0.97,
    0.97,
    f"Child / Adult\nWB-SAR ratio:\n{child_mean_wb / adult_mean_wb:.2f}×",
    transform=ax_wb.transAxes,
    ha="right",
    va="top",
    fontsize=9,
    bbox=dict(boxstyle="round,pad=0.4", fc="#fff9c4", ec="orange", lw=1.2),
)

# ── save ───────────────────────────────────────────────────────────────────────
out = os.path.join(BASE, "..", "FR1_700MHz_overview.png")
plt.savefig(out, dpi=150, bbox_inches="tight")
print(f"Saved: {os.path.abspath(out)}")
