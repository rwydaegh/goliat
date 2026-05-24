"""Per-metric reporting for the env-FF variance-component decomposition."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .reml_anova import VarianceComponents

# Components whose spread is configurational uncertainty (sT1.5.4 deliverable).
CONFIGURATIONAL = ("dir", "pol", "resid")
# Components corresponding to "findings already reported" in the FF paper.
FINDINGS = ("phantom", "freq", "pf")
ALL_COMPONENTS = FINDINGS + ("dir", "pol", "resid")


def _sigma_or_nan(sig: dict[str, float], key: str) -> float:
    """Sigma for a component, or NaN if the component is absent."""
    v = sig.get(key)
    return v if v is not None else float("nan")


def _row(vc: VarianceComponents) -> dict:
    sig = vc.sigma
    frac = vc.fractions()
    row = {
        "metric": vc.metric,
        "n_obs": vc.n_obs,
        "method": vc.method,
        "logY_mean": vc.grand_mean_logY,
    }
    for c in ALL_COMPONENTS:
        row[f"sigma_{c}"] = sig.get(c, np.nan)
        row[f"frac_{c}"] = frac.get(c, np.nan)
    # Headline configurational CVs (log-space sigmas).
    row["CV_dir"] = sig.get("dir", np.nan)
    row["CV_pol"] = sig.get("pol", np.nan)
    row["CV_resid"] = sig.get("resid", np.nan)
    # Cross-check verdict: resid much smaller than phantom and freq.
    sig_resid = _sigma_or_nan(sig, "resid")
    sig_phantom = _sigma_or_nan(sig, "phantom")
    sig_freq = _sigma_or_nan(sig, "freq")
    if np.isfinite(sig_resid) and np.isfinite(sig_phantom) and np.isfinite(sig_freq):
        denom = max(min(sig_phantom, sig_freq), 1e-12)
        ratio = sig_resid / denom
        row["resid_over_min_pf"] = ratio
        row["robust"] = bool(ratio < 0.2)  # noise floor < 20% of the smaller of the two physical effects
    else:
        row["resid_over_min_pf"] = np.nan
        row["robust"] = False
    return row


def build_report(components: list[VarianceComponents]) -> pd.DataFrame:
    """Stack per-metric VarianceComponents into a tidy summary table."""
    return pd.DataFrame([_row(c) for c in components])


def format_console_table(report: pd.DataFrame) -> str:
    """Compact human-readable table for the terminal."""
    cols = [
        "metric",
        "sigma_phantom",
        "sigma_freq",
        "sigma_pf",
        "sigma_dir",
        "sigma_pol",
        "sigma_resid",
        "resid_over_min_pf",
        "robust",
    ]
    fmt = report[cols].copy()
    for c in cols:
        if c.startswith("sigma_") or c == "resid_over_min_pf":
            fmt[c] = fmt[c].map(lambda v: f"{v:.3f}" if pd.notna(v) else "—")
    return fmt.to_string(index=False)


def write_outputs(
    report: pd.DataFrame,
    components: list[VarianceComponents],
    out_dir: Path | str,
) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    report.to_csv(out / "variance_components_summary.csv", index=False)

    long_rows = []
    for vc in components:
        sig = vc.sigma
        frac = vc.fractions()
        for c in ALL_COMPONENTS:
            long_rows.append(
                {
                    "metric": vc.metric,
                    "component": c,
                    "sigma2": vc.sigma2.get(c, np.nan),
                    "sigma": sig.get(c, np.nan),
                    "fraction": frac.get(c, np.nan),
                    "method": vc.method,
                }
            )
    pd.DataFrame(long_rows).to_csv(out / "variance_components_long.csv", index=False)
