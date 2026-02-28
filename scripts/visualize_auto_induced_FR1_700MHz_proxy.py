"""
Deeper dive: proxy score quality and spatial analysis for FR1 700 MHz.
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

BASE = r"c:\Users\rwydaegh\OneDrive - UGent\rwydaegh\GOLIAT code\goliat\results\auto_induced_FR1\extracted"
PHANTOMS = ["duke", "ella", "eartha", "thelonious"]
LABELS = {"duke": "Duke (adult ♂)", "ella": "Ella (adult ♀)", "eartha": "Eartha (child ♀)", "thelonious": "Thelonious (child ♂)"}
COLORS = {"duke": "#2166ac", "ella": "#4dac26", "eartha": "#d01c8b", "thelonious": "#f1a340"}

summaries = {}
proxy_dfs = {}
for ph in PHANTOMS:
    with open(os.path.join(BASE, ph, "auto_induced_summary.json")) as f:
        summaries[ph] = json.load(f)
    proxy_dfs[ph] = pd.read_csv(os.path.join(BASE, ph, "all_proxy_scores.csv"))


def get_ext_df(ph):
    ers = summaries[ph]["extraction_results"]
    cands = summaries[ph]["candidates"][:20]
    rows = []
    for i, e in enumerate(ers):
        c = cands[i] if i < len(cands) else {}
        rows.append(
            {
                "candidate_idx": e["candidate_idx"],
                "hotspot_score": c.get("hotspot_score", np.nan),
                "peak_sar_mWkg": e["peak_sar_10g_W_kg"] * 1000,
                "wb_sar_uWkg": e["whole_body_sar_W_kg"] * 1e6,
                "voxel_x": int(c["voxel_idx"][0]) if c else np.nan,
                "voxel_y": int(c["voxel_idx"][1]) if c else np.nan,
                "voxel_z": float(c["voxel_idx"][2]) if c else np.nan,
                "dist_mm": c.get("distance_to_skin_mm", np.nan),
                "z_mm": float(c["voxel_idx"][2]) if c else np.nan,
            }
        )
    df = pd.DataFrame(rows)
    df["proxy_rank"] = df["hotspot_score"].rank(ascending=False).astype(int)
    df["sar_rank"] = df["peak_sar_mWkg"].rank(ascending=False).astype(int)
    return df


ext_dfs = {ph: get_ext_df(ph) for ph in PHANTOMS}

# ─── figure ───────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(16, 14))
fig.suptitle("Proxy Score Quality & Spatial Analysis  –  FR1 / 700 MHz", fontsize=15, fontweight="bold", y=0.99)
gs = gridspec.GridSpec(3, 4, figure=fig, hspace=0.55, wspace=0.45)

# ══════════════════════════════════════════════════════════════════════════════
# ROW 0  –  Proxy rank vs SAR rank (rank-rank plot; perfect = diagonal)
# ══════════════════════════════════════════════════════════════════════════════
for col, ph in enumerate(PHANTOMS):
    ax = fig.add_subplot(gs[0, col])
    df = ext_dfs[ph]
    rho, _ = spearmanr(df["proxy_rank"], df["sar_rank"])

    sc = ax.scatter(df["proxy_rank"], df["sar_rank"], c=df["peak_sar_mWkg"], cmap="YlOrRd", s=70, edgecolors="k", lw=0.5, zorder=3)
    ax.plot([1, 20], [1, 20], "k--", lw=1, alpha=0.4, label="perfect proxy")

    # mark actual best and worst by SAR
    best = df.loc[df["sar_rank"].idxmin()]
    worst_row = df.loc[df["sar_rank"].idxmax()]
    ax.scatter(
        best["proxy_rank"], best["sar_rank"], marker="*", s=220, color="red", zorder=5, label=f"best SAR (cand {int(best.candidate_idx)})"
    )

    plt.colorbar(sc, ax=ax, label="Peak SAR [mW/kg]", pad=0.01).ax.tick_params(labelsize=7)
    ax.set_xlabel("Proxy rank (1=best)", fontsize=8)
    ax.set_ylabel("SAR rank (1=best)" if col == 0 else "", fontsize=8)
    ax.set_title(f"{LABELS[ph]}\nSpearman ρ = {rho:.2f}", fontsize=9, fontweight="bold")
    ax.set_xlim(0.5, 20.5)
    ax.set_ylim(0.5, 20.5)
    ax.legend(fontsize=6, loc="lower right")
    ax.tick_params(labelsize=8)

# ══════════════════════════════════════════════════════════════════════════════
# ROW 1  –  Height (z_mm) of candidates vs SAR, coloured by hotspot score
# Visualises where on the body the beamforming focuses and what z gives max SAR
# ══════════════════════════════════════════════════════════════════════════════
for col, ph in enumerate(PHANTOMS):
    ax = fig.add_subplot(gs[1, col])
    df = ext_dfs[ph]

    sc = ax.scatter(df["voxel_z"], df["peak_sar_mWkg"], c=df["hotspot_score"], cmap="plasma", s=70, edgecolors="k", lw=0.4, zorder=3)

    # best SAR
    best = df.loc[df["peak_sar_mWkg"].idxmax()]
    ax.scatter(
        best["voxel_z"],
        best["peak_sar_mWkg"],
        marker="*",
        s=230,
        color="red",
        zorder=5,
        label=f"max SAR\n(z={best.voxel_z:.0f}, cand {int(best.candidate_idx)})",
    )

    plt.colorbar(sc, ax=ax, label="hotspot score").ax.tick_params(labelsize=7)
    ax.set_xlabel("Voxel z  (height)", fontsize=8)
    ax.set_ylabel("Peak SAR$_{10g}$ [mW/kg]" if col == 0 else "", fontsize=8)
    ax.set_title(f"{LABELS[ph]}", fontsize=9, fontweight="bold")
    ax.legend(fontsize=7)
    ax.tick_params(labelsize=8)

# ══════════════════════════════════════════════════════════════════════════════
# ROW 2  –  Proxy score distribution comparison: adults vs children (overlay)
# + summary table of key metrics
# ══════════════════════════════════════════════════════════════════════════════
ax_dist = fig.add_subplot(gs[2, :2])

bins = np.linspace(0, 3.2, 60)
for ph in PHANTOMS:
    scores = proxy_dfs[ph]["proxy_score"]
    ls = "-" if ph in ["duke", "ella"] else "--"
    ax_dist.hist(scores, bins=bins, alpha=0.35, color=COLORS[ph], label=LABELS[ph], density=True, edgecolor="none")
    ax_dist.axvline(max(c["hotspot_score"] for c in summaries[ph]["candidates"][:20]), color=COLORS[ph], lw=2, ls=ls)

ax_dist.set_xlabel("Hotspot score (proxy)", fontsize=9)
ax_dist.set_ylabel("Density", fontsize=9)
ax_dist.set_title(
    "Hotspot Score Distributions — adults (solid) vs children (dashed)\nvertical lines = top-1 score per phantom",
    fontsize=9,
    fontweight="bold",
)
ax_dist.legend(fontsize=8, loc="upper right")
ax_dist.set_xlim(0, 3.5)

# ── Summary metrics table ─────────────────────────────────────────────────────
ax_tbl = fig.add_subplot(gs[2, 2:])
ax_tbl.axis("off")

col_labels = ["Phantom", "Top-1\nproxy", "Worst-case\ncand #", "Peak SAR\n[mW/kg]", "WB-SAR\n[µW/kg]", "ρ(proxy, SAR)"]
rows_data = []
for ph in PHANTOMS:
    df = ext_dfs[ph]
    wc = summaries[ph]["worst_case"]
    top1 = summaries[ph]["candidates"][0]["hotspot_score"]
    rho, pval = spearmanr(df["proxy_rank"], df["sar_rank"])
    sig = "**" if pval < 0.01 else ("*" if pval < 0.05 else "n.s.")
    rows_data.append(
        [
            LABELS[ph].replace("\n", " "),
            f"{top1:.2f}",
            str(wc["candidate_idx"]),
            f"{wc['peak_sar_10g_W_kg'] * 1000:.3f}",
            f"{wc['whole_body_sar_W_kg'] * 1e6:.2f}",
            f"{rho:.2f} ({sig})",
        ]
    )

tbl = ax_tbl.table(cellText=rows_data, colLabels=col_labels, loc="center", cellLoc="center")
tbl.auto_set_font_size(False)
tbl.set_fontsize(8.5)
tbl.scale(1.05, 1.8)
# colour header
for j in range(len(col_labels)):
    tbl[(0, j)].set_facecolor("#cce5ff")
    tbl[(0, j)].set_text_props(fontweight="bold")
# colour child rows
for i in range(1, 5):
    if "child" in rows_data[i - 1][0]:
        for j in range(len(col_labels)):
            tbl[(i, j)].set_facecolor("#fff3cd")

ax_tbl.set_title("Summary: 700 MHz auto-induced (raw sim values, no normalisation)", fontsize=9, fontweight="bold", pad=8)

# ── save ──────────────────────────────────────────────────────────────────────
out = os.path.join(BASE, "..", "FR1_700MHz_proxy_analysis.png")
plt.savefig(out, dpi=150, bbox_inches="tight")
print(f"Saved: {os.path.abspath(out)}")
