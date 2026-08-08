"""
Key question: is the top hotspot-score focus voxel close to where peak SAR actually occurs?
Shows focus z vs peak z, and focus-to-peak distance vs SAR, for all 4 phantoms at 700 MHz.
"""

import json
import os
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
from collections import Counter

import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt

BASE = Path(__file__).resolve().parents[1] / "results" / "auto_induced_FR1" / "extracted"
PHANTOMS = ["duke", "ella", "eartha", "thelonious"]
LABELS = {"duke": "Duke (adult ♂)", "ella": "Ella (adult ♀)", "eartha": "Eartha (child ♀)", "thelonious": "Thelonious (child ♂)"}
COLORS = {"duke": "#2166ac", "ella": "#4dac26", "eartha": "#d01c8b", "thelonious": "#f1a340"}


# ── load ──────────────────────────────────────────────────────────────────────
def load_phantom(ph):
    with open(os.path.join(BASE, ph, "auto_induced_summary.json")) as f:
        s = json.load(f)
    cands = s["candidates"][:20]
    rows = []
    for i, cand in enumerate(cands):
        sar_file = os.path.join(BASE, ph, f"candidate_{i + 1:02d}", "sar_results.json")
        if not os.path.exists(sar_file):
            continue
        with open(sar_file) as f:
            sr = json.load(f)
        focus = np.array([int(v) for v in cand["voxel_idx"]])
        peak = np.array(sr["peak_sar_details"]["PeakCell"])
        rows.append(
            {
                "cand_idx": i + 1,
                "hotspot": cand["hotspot_score"],
                "focus_z": focus[2],
                "peak_z": peak[2],
                "focus": focus,
                "peak": peak,
                "dist": float(np.linalg.norm(focus - peak)),
                "sar_mWkg": sr["peak_sar_10g_W_kg"] * 1000,
                "wb_sar": sr["whole_body_sar"] * 1e6,
                "is_worst": (i + 1) == s["worst_case"]["candidate_idx"],
            }
        )
    return rows, s


data = {ph: load_phantom(ph) for ph in PHANTOMS}

# ── figure ─────────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(18, 15))
fig.suptitle(
    "Focus Voxel vs Peak SAR Location  –  FR1 / 700 MHz\nDo we actually focus where the SAR peaks?", fontsize=14, fontweight="bold", y=0.99
)
gs = gridspec.GridSpec(3, 4, figure=fig, hspace=0.55, wspace=0.45)

# ══════════════════════════════════════════════════════════════════════════════
# ROW 0  –  Focus z vs Peak z scatter (if proxy worked: points on diagonal)
# ══════════════════════════════════════════════════════════════════════════════
for col, ph in enumerate(PHANTOMS):
    ax = fig.add_subplot(gs[0, col])
    rows, s = data[ph]

    focus_zs = [r["focus_z"] for r in rows]
    peak_zs = [r["peak_z"] for r in rows]
    scores = [r["hotspot"] for r in rows]
    sars = [r["sar_mWkg"] for r in rows]

    sc = ax.scatter(focus_zs, peak_zs, c=sars, cmap="YlOrRd", s=70, edgecolors="k", lw=0.5, zorder=3, vmin=min(sars), vmax=max(sars))

    # perfect agreement line
    all_z = focus_zs + peak_zs
    zmin, zmax = min(all_z), max(all_z)
    ax.plot([zmin, zmax], [zmin, zmax], "k--", lw=1, alpha=0.4, label="focus = peak")

    # mark worst case
    worst = next(r for r in rows if r["is_worst"])
    ax.scatter(worst["focus_z"], worst["peak_z"], marker="*", s=260, color="red", zorder=5, label=f"worst SAR\n(cand {worst['cand_idx']})")

    plt.colorbar(sc, ax=ax, label="Peak SAR [mW/kg]").ax.tick_params(labelsize=7)
    ax.set_xlabel("Focus voxel z", fontsize=8)
    ax.set_ylabel("Peak SAR cell z" if col == 0 else "", fontsize=8)
    ax.set_title(LABELS[ph], fontsize=9, fontweight="bold")
    ax.legend(fontsize=7)
    ax.tick_params(labelsize=8)

    # count how many unique peak cells
    unique_peaks = len(set(tuple(r["peak"]) for r in rows))
    ax.text(
        0.02,
        0.98,
        f"{unique_peaks} unique\npeak locations\n(out of {len(rows)})",
        transform=ax.transAxes,
        va="top",
        fontsize=7.5,
        bbox=dict(boxstyle="round,pad=0.3", fc="lightyellow", ec="orange", alpha=0.9),
    )

# ══════════════════════════════════════════════════════════════════════════════
# ROW 1  –  Distance focus→peak vs Peak SAR (does farther = less SAR or more?)
# ══════════════════════════════════════════════════════════════════════════════
for col, ph in enumerate(PHANTOMS):
    ax = fig.add_subplot(gs[1, col])
    rows, s = data[ph]

    dists = [r["dist"] for r in rows]
    sars = [r["sar_mWkg"] for r in rows]
    scores = [r["hotspot"] for r in rows]

    sc = ax.scatter(dists, sars, c=scores, cmap="plasma", s=70, edgecolors="k", lw=0.5, zorder=3)

    worst = next(r for r in rows if r["is_worst"])
    ax.scatter(worst["dist"], worst["sar_mWkg"], marker="*", s=260, color="red", zorder=5, label=f"worst SAR\nd={worst['dist']:.0f} vox")

    top1 = rows[0]  # highest hotspot score
    ax.scatter(top1["dist"], top1["sar_mWkg"], marker="^", s=160, color="blue", zorder=5, label=f"top hotspot\nd={top1['dist']:.0f} vox")

    plt.colorbar(sc, ax=ax, label="hotspot score").ax.tick_params(labelsize=7)
    ax.set_xlabel("Distance focus → peak SAR cell [voxels]", fontsize=8)
    ax.set_ylabel("Peak SAR$_{10g}$ [mW/kg]" if col == 0 else "", fontsize=8)
    ax.set_title(LABELS[ph], fontsize=9, fontweight="bold")
    ax.legend(fontsize=7)
    ax.tick_params(labelsize=8)

# ══════════════════════════════════════════════════════════════════════════════
# ROW 2  –  Dominant peak SAR locations (how many candidates end up at same spot)
#           + arrow diagram concept: focus arrows vs peak concentration
# ══════════════════════════════════════════════════════════════════════════════
for col, ph in enumerate(PHANTOMS):
    ax = fig.add_subplot(gs[2, col])
    rows, s = data[ph]

    # Show focus_z distribution vs peak_z distribution as stacked bar or lines
    focus_zs = [r["focus_z"] for r in rows]
    peak_zs = [r["peak_z"] for r in rows]
    sars = [r["sar_mWkg"] for r in rows]

    # sort by hotspot score (they already are, row 0 = best)
    cand_nums = [r["cand_idx"] for r in rows]

    # horizontal: candidate rank; lines connect focus z (circle) to peak z (square)
    for i, r in enumerate(rows):
        rank = i + 1
        col_val = plt.cm.YlOrRd((r["sar_mWkg"] - min(sars)) / (max(sars) - min(sars)))
        ax.plot([rank, rank], [r["focus_z"], r["peak_z"]], color="gray", lw=0.8, zorder=1)
        ax.scatter(rank, r["focus_z"], marker="o", s=30, color=COLORS[ph], zorder=3, alpha=0.7)
        ax.scatter(rank, r["peak_z"], marker="s", s=50, c=[col_val], edgecolors="k", lw=0.3, zorder=4)
        if r["is_worst"]:
            ax.annotate(
                "★ worst\nSAR",
                xy=(rank, r["peak_z"]),
                xytext=(rank + 1.5, r["peak_z"] + 20),
                fontsize=6.5,
                color="red",
                arrowprops=dict(arrowstyle="->", color="red", lw=0.8),
            )

    # dummy legend entries
    ax.scatter([], [], marker="o", color=COLORS[ph], s=30, label="focus voxel z")
    ax.scatter([], [], marker="s", color="orange", s=50, edgecolors="k", lw=0.3, label="peak SAR cell z")

    ax.set_xlabel("Candidate rank (by hotspot score)", fontsize=8)
    ax.set_ylabel("Voxel z (body height)" if col == 0 else "", fontsize=8)
    ax.set_title(f"{LABELS[ph]}\ncircle=focus, square=peak SAR", fontsize=9, fontweight="bold")
    ax.legend(fontsize=7, loc="upper right")
    ax.tick_params(labelsize=8)

    # annotation: how many peak at same z
    z_counts = Counter(peak_zs)
    top_z, top_n = z_counts.most_common(1)[0]
    ax.axhline(top_z, color="orange", lw=1.5, ls="--", alpha=0.6)
    ax.text(
        0.02,
        0.02,
        f"Most common peak z={top_z}\n({top_n}/{len(rows)} candidates land here)",
        transform=ax.transAxes,
        va="bottom",
        fontsize=7.5,
        bbox=dict(boxstyle="round,pad=0.3", fc="lightyellow", ec="orange", alpha=0.9),
    )

# ── save ──────────────────────────────────────────────────────────────────────
out = os.path.join(BASE, "..", "FR1_700MHz_focus_vs_peak_location.png")
plt.savefig(out, dpi=150, bbox_inches="tight")
print(f"Saved: {os.path.abspath(out)}")
