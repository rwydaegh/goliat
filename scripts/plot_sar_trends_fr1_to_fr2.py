"""
Plot SAR trends from FR1 through FR3 and FR2 for Thelonious (M, 6y).

Three curves:
  - Skin SAR:      FR1 x_neg (solid) + FR3/FR2 x_neg (dashed)  [black]
  - Eye SAR:       FR1 x_neg (solid) + FR3/FR2 x_neg (dashed)  [red]
  - WB-SAR:        FR1 12-dir avg (solid) + FR3/FR2 x_neg (dashed)  [dark blue]

All values normalized to 1 W/m² incident.
FR3/FR2 organ groups: bilateral ×½ correction applied.
psSAR10g: no bilateral correction.

Output: papers/pmb/source/figures/sar_trends_fr1_to_fr2.{png,pdf}
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

try:
    import scienceplots  # noqa: F401

    plt.style.use(["science", "ieee", "no-latex"])
except ImportError:
    print("Warning: scienceplots not available.")

plt.rcParams.update(
    {
        "font.size": 9,
        "axes.titlesize": 9,
        "axes.labelsize": 9,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
        "lines.markersize": 4,
        "lines.markeredgewidth": 0.6,
    }
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ETA0 = 376.73  # free-space impedance, Ω
SCALE_FULL = 2 * ETA0  # ×753.46: raw (W/kg at 1 V/m) → W/kg at 1 W/m²
SCALE_HALF = ETA0  # ×376.73: half-phantom bilateral-corrected organ groups
SCALE_HALF_PSSAR = 2 * ETA0  # no bilateral correction for psSAR10g
# Whole-body SAR mass correction for the half-phantom: Sim4Life divides the
# absorbed power by the mass of tissue *in the simulation* (the illuminated
# half). At FR3 the absent shadow half absorbs negligibly but is half of the
# real body's mass, so SAR_wb = P_abs/m_full = P_abs/(2 m_half) = half the
# half-phantom value. (Local/organ-group metrics on the lit side are
# unaffected; this is a whole-body averaging-mass correction only.)
SCALE_HALF_WB = ETA0 / 2  # ×188.37

REPO = Path(__file__).parent.parent
FR1_BASE = REPO / "results" / "far_field" / "thelonious"
FR3_BASE = REPO / "results" / "thelonious_FR3"
OUT_DIR = REPO / "papers" / "pmb" / "source" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FR1_FREQS_MHZ = [450, 700, 835, 1450, 2140, 2450, 3500, 5200, 5800]
FR3_FREQS_MHZ = [7000, 9000, 11000, 13000, 15000, 26000]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_fr1_xneg(freqs_mhz):
    """Load FR1 x_neg theta SAR values, normalized to 1 W/m²."""
    records = []
    for f_mhz in freqs_mhz:
        p = FR1_BASE / f"{f_mhz}MHz" / "environmental_x_neg_theta" / "sar_results.json"
        with open(p) as fh:
            d = json.load(fh)
        records.append(
            {
                "freq_ghz": f_mhz / 1000,
                "skin_mwkg": d["skin_group_weighted_avg_sar"] * SCALE_FULL * 1e3,
                "eyes_mwkg": d["eyes_group_weighted_avg_sar"] * SCALE_FULL * 1e3,
                "wb_mwkg": d["whole_body_sar"] * SCALE_FULL * 1e3,
                "pssar_mwkg": d["peak_sar_10g_W_kg"] * SCALE_FULL * 1e3,
            }
        )
    return pd.DataFrame(records)


def load_fr1_12diravg_wb():
    """Load FR1 12-direction isotropic average whole-body SAR, normalized to 1 W/m²."""
    plot_path = REPO / "plots" / "far_field" / "thelonious" / "line" / "sar_line_environmental.csv"
    if plot_path.exists():
        df = pd.read_csv(plot_path)
    else:
        raise FileNotFoundError(f"Cannot find sar_line_environmental.csv; tried {plot_path}")
    df["freq_ghz"] = df["frequency_mhz"] / 1000
    df = df.rename(columns={"SAR_whole_body": "wb_12dir_mwkg"})
    return df[["freq_ghz", "wb_12dir_mwkg"]]


def load_fr3_xneg(freqs_mhz):
    """Load FR3/FR2 x_neg theta SAR values, normalized to 1 W/m² with bilateral ×½."""
    records = []
    for f_mhz in freqs_mhz:
        p = FR3_BASE / f"{f_mhz}MHz" / "environmental_x_neg_theta" / "sar_results.json"
        with open(p) as fh:
            d = json.load(fh)
        records.append(
            {
                "freq_ghz": f_mhz / 1000,
                "skin_mwkg": d["skin_group_weighted_avg_sar"] * SCALE_HALF * 1e3,
                "eyes_mwkg": d["eyes_group_weighted_avg_sar"] * SCALE_HALF * 1e3,
                "wb_mwkg": d["whole_body_sar"] * SCALE_HALF_WB * 1e3,
                "pssar_mwkg": d["peak_sar_10g_W_kg"] * SCALE_HALF_PSSAR * 1e3,
            }
        )
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------


def make_plot(fr1_xneg, fr1_wb12, fr3):
    fig, ax = plt.subplots(figsize=(3.5, 2.8))

    # Color scheme: black, red, dark blue
    C_SKIN = "black"
    C_EYES = "red"
    C_WB = "#00008B"

    BOUNDARY_GHZ = 6.35  # geometric mean between 5.8 and 7.0 GHz
    MS_FR1 = 4
    MS_FR3 = 4
    LW = 1.5

    # ---- Shaded FR3/FR2 region ----
    ax.axvspan(BOUNDARY_GHZ, 30, color="gray", alpha=0.06, zorder=0)

    # ---- Skin SAR ----
    ax.plot(
        fr1_xneg["freq_ghz"],
        fr1_xneg["skin_mwkg"],
        color=C_SKIN,
        linestyle="solid",
        marker="o",
        markersize=MS_FR1,
        linewidth=LW,
        label="Skin SAR",
        markerfacecolor=C_SKIN,
    )
    ax.plot(
        fr3["freq_ghz"],
        fr3["skin_mwkg"],
        color=C_SKIN,
        linestyle="dashed",
        marker="o",
        markersize=MS_FR3,
        linewidth=LW,
        label="_nolegend_",
        markerfacecolor="white",
        markeredgecolor=C_SKIN,
    )

    # ---- Eye SAR ----
    ax.plot(
        fr1_xneg["freq_ghz"],
        fr1_xneg["eyes_mwkg"],
        color=C_EYES,
        linestyle="solid",
        marker="s",
        markersize=MS_FR1,
        linewidth=LW,
        label="Eye SAR",
        markerfacecolor=C_EYES,
    )
    ax.plot(
        fr3["freq_ghz"],
        fr3["eyes_mwkg"],
        color=C_EYES,
        linestyle="dashed",
        marker="s",
        markersize=MS_FR3,
        linewidth=LW,
        label="_nolegend_",
        markerfacecolor="white",
        markeredgecolor=C_EYES,
    )

    # ---- WB-SAR: FR1 = 12-dir avg (solid), FR3 = x_neg (dashed) ----
    ax.plot(
        fr1_wb12["freq_ghz"],
        fr1_wb12["wb_12dir_mwkg"],
        color=C_WB,
        linestyle="solid",
        marker="^",
        markersize=MS_FR1,
        linewidth=LW,
        label=r"SAR$_\mathrm{wb}$",
        markerfacecolor=C_WB,
    )
    ax.plot(
        fr3["freq_ghz"],
        fr3["wb_mwkg"],
        color=C_WB,
        linestyle="dashed",
        marker="^",
        markersize=MS_FR3,
        linewidth=LW,
        label="_nolegend_",
        markerfacecolor="white",
        markeredgecolor=C_WB,
    )

    # ---- Vertical boundary line ----
    ax.axvline(x=BOUNDARY_GHZ, color="gray", linestyle="-", linewidth=0.7, alpha=0.5)

    # ---- Band labels (blended axes/data transform) ----
    trans = ax.get_xaxis_transform()  # x in data coords, y in axes fraction
    ax.text(1.4, 0.97, "FR1", ha="center", va="top", fontsize=7, color="dimgray", transform=trans)
    # FR3/FR2 label: place at lower-right inside the shaded region, above WB line
    ax.text(13.5, 0.97, "FR3 / FR2", ha="center", va="top", fontsize=7, color="dimgray", transform=trans)

    # ---- Axes ----
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(0.4, 30)
    ax.set_ylim(0.03, 80)  # upper headroom above skin SAR at 26 GHz (39.8)

    # x-ticks: select key frequencies that matter for the story
    xticks = [0.45, 0.7, 1.45, 3.5, 5.8, 7, 10, 15, 26]
    ax.set_xticks(xticks)
    ax.set_xticklabels(
        ["0.45", "0.7", "1.45", "3.5", "5.8", "7", "10", "15", "26"],
        rotation=45,
        ha="right",
    )

    ax.set_xlabel("Frequency (GHz)")
    ax.set_ylabel(r"SAR (mW kg$^{-1}$ at 1 W m$^{-2}$)")

    ax.grid(True, which="both", ls="--", alpha=0.3)

    # ---- Legend (3 metrics only; solid/dashed explained in caption) ----
    legend = ax.legend(
        frameon=True,
        edgecolor="black",
        fancybox=False,
        framealpha=1.0,
        loc="lower left",
    )
    legend.get_frame().set_linewidth(1.0)

    plt.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    print("Loading FR1 x_neg theta data...")
    fr1_xneg = load_fr1_xneg(FR1_FREQS_MHZ)

    print("Loading FR1 12-direction average WB-SAR...")
    fr1_wb12 = load_fr1_12diravg_wb()

    print("Loading FR3/FR2 x_neg theta data...")
    fr3 = load_fr3_xneg(FR3_FREQS_MHZ)

    # Sanity-check against known values
    print("\nSanity check (expected values from thelonious_fr3_fr2_sar_summary.md):")
    print(f"  FR1 skin @ 5.8 GHz:  {fr1_xneg.loc[fr1_xneg.freq_ghz == 5.8, 'skin_mwkg'].values[0]:.2f}  (expect 18.6)")
    print(f"  FR1 eyes @ 5.8 GHz:  {fr1_xneg.loc[fr1_xneg.freq_ghz == 5.8, 'eyes_mwkg'].values[0]:.2f}  (expect 4.92)")
    print(f"  FR3 skin @ 7.0 GHz:  {fr3.loc[fr3.freq_ghz == 7.0, 'skin_mwkg'].values[0]:.2f}  (expect 21.5)")
    print(f"  FR3 eyes @ 7.0 GHz:  {fr3.loc[fr3.freq_ghz == 7.0, 'eyes_mwkg'].values[0]:.2f}  (expect 3.62)")
    print(f"  FR3 WB   @ 7.0 GHz:  {fr3.loc[fr3.freq_ghz == 7.0, 'wb_mwkg'].values[0]:.2f}  (expect 3.96, mass-corrected)")
    print(f"  FR3 skin @ 26 GHz:   {fr3.loc[fr3.freq_ghz == 26.0, 'skin_mwkg'].values[0]:.2f}  (expect 39.8)")
    print(f"  FR3 eyes @ 26 GHz:   {fr3.loc[fr3.freq_ghz == 26.0, 'eyes_mwkg'].values[0]:.4f}  (expect 0.047)")

    print("\nGenerating figure...")
    fig = make_plot(fr1_xneg, fr1_wb12, fr3)

    png_path = OUT_DIR / "sar_trends_fr1_to_fr2.png"
    pdf_path = OUT_DIR / "sar_trends_fr1_to_fr2.pdf"

    fig.savefig(png_path, dpi=300, bbox_inches="tight")
    print(f"Saved PNG: {png_path}")
    fig.savefig(pdf_path, bbox_inches="tight")
    print(f"Saved PDF: {pdf_path}")

    plt.show()


if __name__ == "__main__":
    main()
