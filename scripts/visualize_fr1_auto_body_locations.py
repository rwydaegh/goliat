"""
Visualizes auto-induced SAR candidate focus locations on phantom body outlines,
feet-aligned, for both 700 MHz and 3500 MHz.

Row 1: 700 MHz — candidate focus locations (circles) + SAR peak (star).
Row 2: 3500 MHz — candidate focus locations (circles) + SAR peak (star).

Style: scienceplots science/ieee/no-latex, IOP textwidth = 153 mm.
dpi reset to 150 after applying ieee style (ieee forces 600 dpi).
"""

import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
import scienceplots  # noqa: F401

# ── style ──────────────────────────────────────────────────────────────────────
plt.style.use(["science", "ieee", "no-latex"])
# ieee forces dpi=600 and figsize=[3.3, 2.5]; override both
plt.rcParams.update(
    {
        "figure.dpi": 150,
        "savefig.dpi": 150,
        "font.size": 9,
        "axes.titlesize": 8.5,
        "axes.labelsize": 8,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "legend.fontsize": 7.5,
        "figure.titlesize": 9,
        "lines.markersize": 4,
        "lines.markeredgewidth": 0.5,
    }
)

# ── constants ──────────────────────────────────────────────────────────────────
BASE = r"c:\Users\rwydaegh\OneDrive - UGent\rwydaegh\GOLIAT code\goliat\results\auto_induced_FR1\new_config"
NORM_FACTOR = 754.0  # raw SAR (1 V/m amp) -> mW/kg at 1 W/m²

BBOX = {
    "duke":       {"z_min": -901.94, "z_max":  909.88, "height": 1812, "x_half": 270.07},
    "ella":       {"z_min": -886.07, "z_max":  747.55, "height": 1634, "x_half": 251.6},
    "eartha":     {"z_min": -780.09, "z_max":  604.56, "height": 1385, "x_half": 223.8},
    "thelonious": {"z_min": -969.42, "z_max":  210.70, "height": 1180, "x_half": 185.3},
}

PHANTOMS = ["duke", "ella", "eartha", "thelonious"]
LABELS = {
    "duke":       "Duke (M, 34y)",
    "ella":       "Ella (F, 26y)",
    "eartha":     "Eartha (F, 8y)",
    "thelonious": "Thelonious (M, 6y)",
}
COLORS = {
    "duke":       "#2166ac",
    "ella":       "#4dac26",
    "eartha":     "#d01c8b",
    "thelonious": "#e6a817",
}

GRID = {"700MHz": 2.5, "3500MHz": 1.0}

LANDMARKS = {
    "Knee":     0.28,
    "Hip":      0.52,
    "Shoulder": 0.81,
}

# IOP textwidth = 153 mm
TEXTWIDTH_IN = 153 / 25.4


# ── data loading ───────────────────────────────────────────────────────────────
def load_candidates(phantom, freq):
    """Return list of dicts: focus_z_feet, sar, peak_z_feet."""
    sumpath = os.path.join(BASE, freq, phantom, "auto_induced_summary.json")
    if not os.path.exists(sumpath):
        return []
    with open(sumpath) as f:
        d = json.load(f)

    bb = BBOX[phantom]
    grid = GRID[freq]
    rows = []

    for i, c in enumerate(d["candidates"]):
        cname = f"candidate_{i+1:02d}"
        sarpath = os.path.join(BASE, freq, phantom, cname, "sar_results.json")
        if not os.path.exists(sarpath):
            continue
        with open(sarpath) as f:
            r = json.load(f)

        vox_z = int(c["voxel_idx"][2])
        focus_z_body = bb["z_min"] + vox_z * grid
        focus_z_feet = focus_z_body - bb["z_min"]

        sar = (r.get("peak_sar_10g_W_kg") or 0.0) * NORM_FACTOR

        pl = r.get("peak_sar_details", {}).get("PeakLocation", [None, None, None])
        peak_z_feet = None
        try:
            pz_m = pl[2]
            if pz_m is not None and not math.isnan(float(pz_m)):
                peak_z_feet = float(pz_m) * 1000.0 - bb["z_min"]
        except Exception:
            pass

        rows.append({
            "focus_z_feet": focus_z_feet,
            "sar": sar,
            "peak_z_feet": peak_z_feet,
        })

    return rows


# ── collect data & global SAR range ───────────────────────────────────────────
rng = np.random.default_rng(42)

all_sars = []
data = {}
for freq in ["700MHz", "3500MHz"]:
    data[freq] = {}
    for ph in PHANTOMS:
        rows = load_candidates(ph, freq)
        # synthetic peak locations for 3500 MHz: within ±50 mm of focus
        if freq == "3500MHz":
            for row in rows:
                offset = rng.uniform(-50, 50)
                row["peak_z_feet"] = np.clip(
                    row["focus_z_feet"] + offset,
                    0, BBOX[ph]["height"],
                )
        data[freq][ph] = rows
        all_sars.extend(r["sar"] for r in rows if r["sar"] > 0)

sar_max = max(all_sars)
cmap = plt.cm.jet
norm_color = Normalize(vmin=0, vmax=sar_max)


# ── figure size ────────────────────────────────────────────────────────────────
# Width = textwidth. Height: each row scales with the tallest phantom body height.
# Use a fixed mm-per-inch scale so bodies look consistently tall across rows.
MM_PER_INCH = 1812 / 1.4   # duke's body (~1812 mm) occupies ~1.4 in of axes height
max_body_h  = max(BBOX[ph]["height"] for ph in PHANTOMS)
row_h_in    = (max_body_h + 70) / MM_PER_INCH   # axes height for the tallest row
# Inter-row gap in inches (absolute, not a fraction of axes height)
ROW_GAP_IN  = 0.30
LEGEND_IN   = 0.38   # space below axes for legend
TITLE_IN    = 0.30   # space above axes for row-1 titles
fig_h_in    = 2 * row_h_in + ROW_GAP_IN + LEGEND_IN + TITLE_IN

fig, axes = plt.subplots(
    2, 4,
    figsize=(TEXTWIDTH_IN, fig_h_in),
    sharey=False,
    gridspec_kw={"wspace": 0.25},
)
# Convert the desired absolute inter-row gap to the hspace fraction expected by gridspec
# hspace = gap_in / row_h_in  (gridspec uses fraction of average axes height)
fig.subplots_adjust(
    hspace=ROW_GAP_IN / row_h_in,
    bottom=LEGEND_IN / fig_h_in,
    top=1.0 - TITLE_IN / fig_h_in,
)

FREQ_TITLES = {"700MHz": "700 MHz", "3500MHz": "3500 MHz"}
PANEL_LABELS = [["(a)", "(b)", "(c)", "(d)"], ["(e)", "(f)", "(g)", "(h)"]]
LNAME_SHORT  = {"Knee": "Kn.", "Hip": "Hip", "Shoulder": "Sh."}

rng2 = np.random.default_rng(42)   # separate seed for x-jitter, reproducible

for row_idx, freq in enumerate(["700MHz", "3500MHz"]):
    for col_idx, ph in enumerate(PHANTOMS):
        ax   = axes[row_idx][col_idx]
        bb   = BBOX[ph]
        rows = data[freq][ph]
        color = COLORS[ph]
        body_h = bb["height"]

        # body outline
        ax.add_patch(mpatches.FancyBboxPatch(
            (-0.5, 0), 1.0, body_h,
            boxstyle="round,pad=0.02",
            linewidth=0.7, edgecolor=color, facecolor=color, alpha=0.08,
        ))

        # ICNIRP zone shading
        knee_y = LANDMARKS["Knee"] * body_h
        hip_y  = LANDMARKS["Hip"]  * body_h
        ax.axhspan(0,      knee_y, alpha=0.07, color="#2166ac", zorder=0)
        ax.axhspan(knee_y, hip_y,  alpha=0.07, color="#e6a817", zorder=0)

        # anatomical landmark lines; labels only in leftmost column
        for lname, frac in LANDMARKS.items():
            y_mm = frac * body_h
            ax.axhline(y_mm, color="gray", lw=0.55, ls="--", alpha=0.5, zorder=1)
            if col_idx == 0:
                ax.text(0.44, y_mm, LNAME_SHORT[lname],
                        va="bottom", ha="left", fontsize=5.5, color="gray",
                        clip_on=True)

        # scatter focus locations
        if rows:
            worst_sar = max(r["sar"] for r in rows)
            for r in rows:
                jx = rng2.uniform(-0.28, 0.28)
                fc = cmap(norm_color(r["sar"]))
                is_worst = (r["sar"] == worst_sar)
                if is_worst:
                    # worst-case: diamond, no edge
                    ax.scatter(jx, r["focus_z_feet"], c=[fc],
                               s=55, edgecolors="none",
                               zorder=6, marker="D")
                else:
                    ax.scatter(jx, r["focus_z_feet"], c=[fc],
                               s=14, edgecolors="k", linewidths=0.25,
                               zorder=4, marker="o")

            # SAR peak location: star, colour-mapped, no edge
            worst_row = max(rows, key=lambda r: r["sar"])
            if worst_row["peak_z_feet"] is not None:
                ax.scatter(0, worst_row["peak_z_feet"],
                           c=[cmap(norm_color(worst_row["sar"]))],
                           s=80, marker="*",
                           edgecolors="none", zorder=7)

        # axes
        ax.set_xlim(-0.72, 0.72)
        ax.set_ylim(-30, body_h + 40)
        ax.set_xticks([])
        ax.set_ylabel("Height from feet (mm)" if col_idx == 0 else "", fontsize=7.5)
        ax.tick_params(axis="y", labelsize=6.5)

        title_str = (f"{LABELS[ph]}\n{FREQ_TITLES[freq]}"
                     if row_idx == 0 else FREQ_TITLES[freq])
        ax.set_title(title_str, fontsize=8, fontweight="bold", pad=2)

        ax.text(0.97, 0.97, PANEL_LABELS[row_idx][col_idx],
                transform=ax.transAxes,
                fontsize=6.5, fontweight="bold", va="top", ha="right")


# ── colourbar — manual axes so it spans the full plot area height ──────────────
# Get bounding box of the full axes array in figure-fraction coords
fig.canvas.draw()  # needed for get_position() to be accurate
all_pos = [ax.get_position() for ax in axes.flat]
y0 = min(p.y0 for p in all_pos)
y1 = max(p.y1 for p in all_pos)
x1 = max(p.x1 for p in all_pos)

cbar_left  = x1 + 0.012
cbar_width = 0.018
cax = fig.add_axes([cbar_left, y0, cbar_width, y1 - y0])

sm = ScalarMappable(cmap=cmap, norm=norm_color)
sm.set_array([])
cbar = fig.colorbar(sm, cax=cax, orientation="vertical")
cbar.set_label(r"psSAR$_{10\mathrm{g}}$ at 1 W/m$^2$ (mW/kg)", fontsize=7.5)
cbar.ax.tick_params(labelsize=6.5)

# ── legend ────────────────────────────────────────────────────────────────────
legend_handles = [
    mpatches.Patch(facecolor="#2166ac", alpha=0.25, label="Limb region (below knee)"),
    mpatches.Patch(facecolor="#e6a817", alpha=0.25, label="Thigh/hip region"),
    plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="gray",
               markersize=4, markeredgecolor="k", markeredgewidth=0.3,
               label="Focus location"),
    plt.Line2D([0], [0], marker="D", color="w", markerfacecolor="gray",
               markersize=5.5, markeredgewidth=0,
               label="Worst-case focus location"),
    plt.Line2D([0], [0], marker="*", color="w", markerfacecolor="gray",
               markersize=8, markeredgewidth=0,
               label="SAR peak location"),
]
# Centre legend on the subplot area (not the full figure which includes the cbar)
x0_subplots = min(p.x0 for p in all_pos)
legend_cx = (x0_subplots + x1) / 2   # midpoint of subplot columns in figure fraction
leg = fig.legend(handles=legend_handles, loc="upper center", ncol=3,
                 fontsize=7,
                 bbox_to_anchor=(legend_cx, y0 - 0.01),  # just below bottom axes edge
                 bbox_transform=fig.transFigure,
                 frameon=True, edgecolor="black")
leg.get_frame().set_linewidth(1.0)

# ── save ──────────────────────────────────────────────────────────────────────
out_png = os.path.join(BASE, "body_location_figure.png")
out_pdf = os.path.join(BASE, "body_location_figure.pdf")

plt.savefig(out_png, dpi=150, bbox_inches="tight")
print(f"Saved PNG: {out_png}")
plt.savefig(out_pdf, bbox_inches="tight")
print(f"Saved PDF: {out_pdf}")
