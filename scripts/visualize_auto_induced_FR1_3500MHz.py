"""
Analysis of 3500 MHz auto-induced results: new config (top_n=40, percentile=80,
min_dist=100mm, padding=100mm) across all four phantoms (duke, eartha, ella,
thelonious).

Outputs
-------
results/auto_induced_FR1/new_config/3500MHz/panels/{phantom}/   -- 9 per-phantom panels
results/auto_induced_FR1/new_config/3500MHz/panels/combined/    -- cross-phantom panels
"""

import glob
import json
import os

import matplotlib
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = r"c:\Users\rwydaegh\OneDrive - UGent\rwydaegh\GOLIAT code\goliat\results\auto_induced_FR1"
NEW_ROOT = os.path.join(ROOT, "new_config", "3500MHz")
PANEL_ROOT = os.path.join(NEW_ROOT, "panels")

PHANTOMS = ["duke", "eartha", "ella", "thelonious"]
COLORS = {"duke": "#2166ac", "eartha": "#d6604d", "ella": "#4dac26", "thelonious": "#8e44ad"}
MARKERS = {"duke": "o", "eartha": "s", "ella": "^", "thelonious": "D"}
FREQ_LABEL = "3500 MHz"


def save(fig, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def load_phantom_data(phantom):
    new_dir = os.path.join(NEW_ROOT, phantom)

    with open(os.path.join(new_dir, "auto_induced_summary.json")) as f:
        summary = json.load(f)

    df_proxy = pd.read_csv(os.path.join(new_dir, "all_proxy_scores.csv"))

    cand_rows = []
    for cdir in sorted(glob.glob(os.path.join(new_dir, "candidate_*/"))):
        sar_path = os.path.join(cdir, "sar_results.json")
        if not os.path.exists(sar_path):
            continue
        with open(sar_path) as f:
            sr = json.load(f)
        cnum = int(os.path.basename(cdir.rstrip("/\\")).replace("candidate_", ""))
        peak = sr.get("peak_sar_10g_W_kg")
        if peak is None:
            continue
        loc = sr.get("peak_sar_details", {}).get("PeakLocation", [None, None, None])
        cand_rows.append(
            {
                "candidate": cnum,
                "peak_sar_mW_kg": peak * 1000,
                "wb_sar_uW_kg": sr.get("whole_body_sar", 0) * 1e6,
                "skin_peak_mW_kg": sr.get("skin_group_peak_sar", 0) * 1000,
                "peak_x_mm": loc[0] * 1000 if loc[0] is not None else None,
                "peak_y_mm": loc[1] * 1000 if loc[1] is not None else None,
                "peak_z_mm": loc[2] * 1000 if loc[2] is not None else None,
            }
        )
    df_sar = pd.DataFrame(cand_rows)

    cands = summary["candidates"]
    df_cands = pd.DataFrame(
        [
            {
                "candidate": i + 1,
                "proxy_score": c["hotspot_score"],
                "vox_z": float(c["voxel_idx"][2]),
                "distance_mm": c.get("distance_to_skin_mm"),
            }
            for i, c in enumerate(cands)
        ]
    )

    df_merged = df_sar.merge(
        df_cands[["candidate", "proxy_score", "vox_z"]], on="candidate", how="left"
    )

    return df_merged, df_cands, df_proxy, summary


def make_per_phantom_panels(phantom, df_merged, df_cands, df_proxy):
    panel_dir = os.path.join(PANEL_ROOT, phantom)
    os.makedirs(panel_dir, exist_ok=True)

    def sp(name):
        return os.path.join(panel_dir, f"{name}.png")

    rho, pval = spearmanr(df_merged["proxy_score"], df_merged["peak_sar_mW_kg"])
    wc_row = df_merged.loc[df_merged["peak_sar_mW_kg"].idxmax()]
    worst_sar = df_merged["peak_sar_mW_kg"].max()
    worst_cand = int(wc_row["candidate"])
    worst_z = float(wc_row["peak_z_mm"])
    worst_proxy = float(wc_row["proxy_score"])
    proxy_rank = int((df_cands["proxy_score"] > worst_proxy).sum()) + 1
    n_total = len(df_cands)
    label = f"{phantom.capitalize()} {FREQ_LABEL}"

    # Panel A
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(df_proxy["proxy_score"], bins=100, color=COLORS[phantom], alpha=0.6,
            label="all 10k samples")
    for s in sorted(df_cands["proxy_score"], reverse=True):
        ax.axvline(s, color="orange", lw=0.5, alpha=0.7)
    ax.axvline(df_cands["proxy_score"].max(), color="red", lw=1.8,
               label=f"top score ({df_cands['proxy_score'].max():.3f})")
    ax.axvline(df_cands["proxy_score"].min(), color="darkred", lw=1.2, ls="--",
               label=f"cut-off ({df_cands['proxy_score'].min():.3f})")
    nonzero_pct = (df_proxy["proxy_score"] > df_cands["proxy_score"].min()).mean() * 100
    ax.text(0.97, 0.65,
            f"Top {n_total} from 10k\ncut-off = {df_cands['proxy_score'].min():.3f}\n({nonzero_pct:.1f}% above)",
            transform=ax.transAxes, ha="right", va="top", fontsize=9,
            bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.9))
    ax.set_xlabel("Hotspot score (proxy)", fontsize=11)
    ax.set_ylabel("# samples", fontsize=11)
    ax.set_title(f"A  Proxy score distribution - {label} (new config)", fontsize=12, fontweight="bold")
    ax.set_xlim(left=0)
    ax.legend(fontsize=9)
    save(fig, sp("A_proxy_histogram"))

    # Panel B
    fig, ax = plt.subplots(figsize=(7, 6))
    sc = ax.scatter(df_merged["proxy_score"], df_merged["peak_sar_mW_kg"],
                    c=df_merged["candidate"], cmap="plasma", s=80, zorder=3)
    ax.scatter(wc_row["proxy_score"], wc_row["peak_sar_mW_kg"],
               marker="*", s=350, color="red", zorder=5, label=f"worst (C{worst_cand})")
    ax.set_xlabel("Hotspot score (proxy)", fontsize=11)
    ax.set_ylabel("Peak SAR$_{10g}$ [mW/kg]", fontsize=11)
    ax.set_title(
        f"B  Proxy vs actual SAR - {label}\nSpearman rho = {rho:.2f}  (p = {pval:.3f},  n = {len(df_merged)})",
        fontsize=12, fontweight="bold")
    ax.legend(fontsize=9)
    plt.colorbar(sc, ax=ax, label="candidate #")
    save(fig, sp("B_proxy_vs_SAR"))

    # Panel C
    fig, ax = plt.subplots(figsize=(9, 5))
    df_ranked = df_merged.sort_values("peak_sar_mW_kg", ascending=False).reset_index(drop=True)
    colors_c = ["#d73027" if i == 0 else COLORS[phantom] for i in range(len(df_ranked))]
    ax.bar(range(len(df_ranked)), df_ranked["peak_sar_mW_kg"], color=colors_c, edgecolor="k", lw=0.5)
    ax.set_xticks(range(len(df_ranked)))
    ax.set_xticklabels([f"C{int(r)}" for r in df_ranked["candidate"]], rotation=90, fontsize=7)
    ax.set_ylabel("Peak SAR$_{10g}$ [mW/kg]", fontsize=11)
    ax.set_title(f"C  Ranked SAR - {label} - worst: C{worst_cand} = {worst_sar:.4f} mW/kg",
                 fontsize=12, fontweight="bold")
    save(fig, sp("C_ranked_SAR"))

    # Panel D
    fig, ax = plt.subplots(figsize=(10, 5))
    sc_d = ax.scatter(df_cands["candidate"], df_cands["vox_z"],
                      c=df_cands["proxy_score"], cmap="YlOrRd", s=100,
                      edgecolors="k", lw=0.5, zorder=2, label=f"all {n_total} (proxy score)")
    ax.scatter(df_merged["candidate"], df_merged["vox_z"],
               s=(df_merged["peak_sar_mW_kg"] / df_merged["peak_sar_mW_kg"].max()) * 400 + 40,
               marker="D", facecolors="none", edgecolors="blue", lw=1.5, zorder=3,
               label="SAR extracted (size prop SAR)")
    ax.scatter(worst_cand, wc_row["vox_z"],
               marker="*", s=450, color="red", zorder=5, label=f"worst-case (C{worst_cand})")
    plt.colorbar(sc_d, ax=ax, label="proxy score")
    ax.set_xlabel("Candidate #", fontsize=11)
    ax.set_ylabel("Focus voxel Z (height index)", fontsize=11)
    ax.set_title(f"D  Spatial Z-coverage of all {n_total} candidates - {label}",
                 fontsize=12, fontweight="bold")
    ax.legend(fontsize=9)
    save(fig, sp("D_spatial_Z_coverage"))

    # Panel E (no old config for 3500 MHz, just new)
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.hist(df_cands["vox_z"], bins=20, color=COLORS[phantom], alpha=0.7,
            label=f"new config (n={n_total})")
    ax.set_xlabel("Focus voxel Z (height index)", fontsize=11)
    ax.set_ylabel("# candidates", fontsize=11)
    ax.set_title(f"E  Body-height coverage - {label}", fontsize=12, fontweight="bold")
    ax.legend(fontsize=10)
    save(fig, sp("E_Z_coverage"))

    # Panel F
    fig, ax = plt.subplots(figsize=(7, 6))
    sc_f = ax.scatter(df_merged["proxy_score"], df_merged["peak_z_mm"],
                      c=df_merged["peak_sar_mW_kg"], cmap="hot_r", s=90,
                      edgecolors="k", lw=0.4)
    ax.scatter(wc_row["proxy_score"], wc_row["peak_z_mm"],
               marker="*", s=350, color="red", zorder=5, label=f"worst (C{worst_cand})")
    plt.colorbar(sc_f, ax=ax, label="peak SAR$_{10g}$ [mW/kg]")
    ax.set_xlabel("Hotspot score (proxy)", fontsize=11)
    ax.set_ylabel("Peak SAR location Z [mm]", fontsize=11)
    ax.set_title(f"F  Where in the body does the SAR peak land? - {label}",
                 fontsize=12, fontweight="bold")
    ax.legend(fontsize=9)
    save(fig, sp("F_SAR_peak_location"))

    # Panel G
    fig, ax = plt.subplots(figsize=(7, 5))
    rho_wb, _ = spearmanr(df_merged["proxy_score"], df_merged["wb_sar_uW_kg"])
    ax.scatter(df_merged["proxy_score"], df_merged["wb_sar_uW_kg"],
               c=COLORS[phantom], s=70, alpha=0.85)
    ax.set_xlabel("Hotspot score (proxy)", fontsize=11)
    ax.set_ylabel("Whole-body SAR [uW/kg]", fontsize=11)
    ax.set_title(f"G  Proxy vs whole-body SAR (rho = {rho_wb:.2f}) - {label}",
                 fontsize=12, fontweight="bold")
    save(fig, sp("G_proxy_vs_WB_SAR"))

    # Panel H
    fig, ax = plt.subplots(figsize=(7, 6))
    sc_h = ax.scatter(df_merged["vox_z"], df_merged["peak_z_mm"],
                      c=df_merged["peak_sar_mW_kg"], cmap="hot_r", s=90,
                      edgecolors="k", lw=0.4)
    ax.set_xlabel("Focus voxel Z (height index)", fontsize=11)
    ax.set_ylabel("Actual SAR peak Z [mm]", fontsize=11)
    ax.set_title(f"H  Focus height vs actual SAR peak height - {label}",
                 fontsize=12, fontweight="bold")
    plt.colorbar(sc_h, ax=ax, label="peak SAR$_{10g}$ [mW/kg]")
    save(fig, sp("H_focus_vs_SAR_peak_Z"))

    # Panel I
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.axis("off")
    lines = [
        f"SUMMARY - {label}, new config",
        f"Candidates done: {len(df_merged)} / {n_total}",
        "",
        f"Worst case:  C#{worst_cand}",
        f"  psSAR10g  = {worst_sar:.4f} mW/kg",
        f"  peak at Z = {worst_z:.0f} mm",
        f"  proxy rank = #{proxy_rank} / {n_total}",
        "",
        f"Spearman rho (proxy/SAR) = {rho:.2f}",
    ]
    ax.text(0.05, 0.95, "\n".join(lines), transform=ax.transAxes,
            va="top", ha="left", fontsize=11, fontfamily="monospace",
            bbox=dict(boxstyle="round,pad=0.7", fc="#f0f4ff", ec=COLORS[phantom], lw=2))
    save(fig, sp("I_summary"))

    return {
        "phantom": phantom,
        "n_cands": n_total,
        "n_done": len(df_merged),
        "worst_cand": worst_cand,
        "worst_sar_mW_kg": worst_sar,
        "worst_z_mm": worst_z,
        "proxy_rank": proxy_rank,
        "rho": rho,
        "pval": pval,
        "df_merged": df_merged,
        "df_cands": df_cands,
    }


def make_combined_panels(all_stats):
    comb_dir = os.path.join(PANEL_ROOT, "combined")
    os.makedirs(comb_dir, exist_ok=True)

    def sp(name):
        return os.path.join(comb_dir, f"{name}.png")

    phantoms = [s["phantom"] for s in all_stats]
    worst_sars = [s["worst_sar_mW_kg"] for s in all_stats]

    # Z1: worst-case SAR per phantom
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(phantoms, worst_sars,
                  color=[COLORS[p] for p in phantoms], edgecolor="k", lw=0.8, alpha=0.85)
    for bar, val in zip(bars, worst_sars):
        ax.text(bar.get_x() + bar.get_width() / 2, val * 1.02,
                f"{val:.4f}", ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_ylabel("Worst-case peak SAR$_{10g}$ [mW/kg]", fontsize=11)
    ax.set_title(f"Z1  Worst-case SAR comparison across phantoms\n{FREQ_LABEL}, new config, 1 mW input",
                 fontsize=12, fontweight="bold")
    ax.set_ylim(0, max(worst_sars) * 1.2)
    save(fig, sp("Z1_worst_case_comparison"))

    # Z2: proxy vs SAR all phantoms
    fig, ax = plt.subplots(figsize=(8, 6))
    for s in all_stats:
        dm = s["df_merged"]
        ax.scatter(dm["proxy_score"], dm["peak_sar_mW_kg"],
                   color=COLORS[s["phantom"]], marker=MARKERS[s["phantom"]],
                   s=60, alpha=0.75, label=f"{s['phantom'].capitalize()} (rho={s['rho']:.2f})",
                   zorder=3)
        wrow = dm.loc[dm["peak_sar_mW_kg"].idxmax()]
        ax.scatter(wrow["proxy_score"], wrow["peak_sar_mW_kg"],
                   color=COLORS[s["phantom"]], marker="*", s=300, zorder=5,
                   edgecolors="k", lw=0.6)
    ax.set_xlabel("Hotspot score (proxy)", fontsize=11)
    ax.set_ylabel("Peak SAR$_{10g}$ [mW/kg]", fontsize=11)
    ax.set_title(f"Z2  Proxy vs actual SAR - all phantoms ({FREQ_LABEL})\n(* = worst-case per phantom)",
                 fontsize=12, fontweight="bold")
    ax.legend(fontsize=10)
    save(fig, sp("Z2_proxy_vs_SAR_all_phantoms"))

    # Z3: ranked SAR 4 subplots
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    axes = axes.flatten()
    for ax, s in zip(axes, all_stats):
        dm = s["df_merged"]
        df_ranked = dm.sort_values("peak_sar_mW_kg", ascending=False).reset_index(drop=True)
        clrs = ["#d73027" if i == 0 else COLORS[s["phantom"]] for i in range(len(df_ranked))]
        ax.bar(range(len(df_ranked)), df_ranked["peak_sar_mW_kg"],
               color=clrs, edgecolor="k", lw=0.4)
        ax.set_xticks(range(len(df_ranked)))
        ax.set_xticklabels([f"C{int(r)}" for r in df_ranked["candidate"]],
                           rotation=90, fontsize=6)
        ax.set_ylabel("SAR$_{10g}$ [mW/kg]", fontsize=9)
        ax.set_title(
            f"{s['phantom'].capitalize()}  -  worst C{s['worst_cand']} = {s['worst_sar_mW_kg']:.4f} mW/kg",
            fontsize=10, fontweight="bold")
    fig.suptitle(f"Z3  Ranked SAR for all phantoms - {FREQ_LABEL}, new config",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    save(fig, sp("Z3_ranked_SAR_all_phantoms"))

    # Z4: Spearman rho + candidate count
    fig, axes = plt.subplots(1, 2, figsize=(10, 5))
    ax = axes[0]
    rhos = [s["rho"] for s in all_stats]
    bars_r = ax.bar(phantoms, rhos,
                    color=[COLORS[p] for p in phantoms], edgecolor="k", lw=0.8, alpha=0.85)
    for bar, val in zip(bars_r, rhos):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.01,
                f"{val:.2f}", ha="center", va="bottom", fontsize=11, fontweight="bold")
    ax.set_ylim(0, 1.15)
    ax.set_ylabel("Spearman rho", fontsize=11)
    ax.set_title("Proxy-SAR correlation (Spearman rho)", fontsize=11, fontweight="bold")
    ax.axhline(0.7, color="gray", ls="--", lw=1, label="rho = 0.70")
    ax.legend(fontsize=9)

    ax = axes[1]
    n_dones = [s["n_done"] for s in all_stats]
    n_totals = [s["n_cands"] for s in all_stats]
    x = np.arange(len(phantoms))
    ax.bar(x - 0.2, n_totals, 0.35, color="lightgray", edgecolor="k", lw=0.6,
           label="total candidates")
    ax.bar(x + 0.2, n_dones, 0.35,
           color=[COLORS[p] for p in phantoms], edgecolor="k", lw=0.6,
           alpha=0.85, label="extracted")
    ax.set_xticks(x)
    ax.set_xticklabels(phantoms)
    ax.set_ylabel("# candidates", fontsize=11)
    ax.set_title("Candidates per phantom", fontsize=11, fontweight="bold")
    ax.legend(fontsize=9)

    fig.suptitle(f"Z4  Correlation & coverage - all phantoms ({FREQ_LABEL})",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    save(fig, sp("Z4_correlation_and_coverage"))

    # Z5: SAR peak body height
    fig, ax = plt.subplots(figsize=(8, 6))
    for s in all_stats:
        dm = s["df_merged"].dropna(subset=["peak_z_mm"])
        ax.scatter(dm["peak_z_mm"], dm["peak_sar_mW_kg"],
                   color=COLORS[s["phantom"]], marker=MARKERS[s["phantom"]],
                   s=60, alpha=0.7, label=s["phantom"].capitalize(), zorder=3)
        wrow = dm.loc[dm["peak_sar_mW_kg"].idxmax()]
        ax.scatter(wrow["peak_z_mm"], wrow["peak_sar_mW_kg"],
                   color=COLORS[s["phantom"]], marker="*", s=300,
                   edgecolors="k", lw=0.6, zorder=5)
    ax.set_xlabel("SAR peak location Z [mm]", fontsize=11)
    ax.set_ylabel("Peak SAR$_{10g}$ [mW/kg]", fontsize=11)
    ax.set_title(f"Z5  SAR peak body height across all phantoms ({FREQ_LABEL})\n(* = worst-case per phantom)",
                 fontsize=12, fontweight="bold")
    ax.legend(fontsize=10)
    save(fig, sp("Z5_SAR_peak_height_all_phantoms"))

    # Z6: summary table
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.axis("off")
    header = f"{'Phantom':<12} {'N':>4} {'Worst C':>8} {'SAR [mW/kg]':>12} {'Z [mm]':>8} {'Proxy #':>8} {'rho':>6}"
    lines = [f"SUMMARY - all phantoms, {FREQ_LABEL}, new config",
             "=" * len(header), header, "-" * len(header)]
    for s in all_stats:
        lines.append(
            f"{s['phantom'].capitalize():<12} {s['n_done']:>4} "
            f"C{s['worst_cand']:>6} {s['worst_sar_mW_kg']:>12.4f} "
            f"{s['worst_z_mm']:>8.0f} {s['proxy_rank']:>8} {s['rho']:>6.2f}"
        )
    ax.text(0.03, 0.97, "\n".join(lines), transform=ax.transAxes,
            va="top", ha="left", fontsize=9.5, fontfamily="monospace",
            bbox=dict(boxstyle="round,pad=0.7", fc="#f0f4ff", ec="#333", lw=1.5))
    save(fig, sp("Z6_summary_table"))


# main
all_stats = []
for phantom in PHANTOMS:
    print(f"\n{'='*50}\nProcessing {phantom} ...\n{'='*50}")
    df_merged, df_cands, df_proxy, summary = load_phantom_data(phantom)
    stats = make_per_phantom_panels(phantom, df_merged, df_cands, df_proxy)
    all_stats.append(stats)

print("\n" + "=" * 50)
print("Generating combined panels ...")
make_combined_panels(all_stats)
print("\nAll panels saved.")
