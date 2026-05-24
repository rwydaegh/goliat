"""Variance-component estimators for the env-FF mixed model.

Model (per metric):

    log Y_{p, f, d, pi}  =  mu  +  alpha_p  +  beta_f  +  (alpha*beta)_{p,f}
                              +  gamma_d  +  delta_pi  +  eps

For the balanced fully-crossed env-FF design (4 phantoms x 9 freqs x 6 dir x
2 pol, one observation per cell) the Type-I / method-of-moments estimator
from expected mean squares is the textbook REML solution: identical point
estimates, no iteration. We use it as the primary estimator.

A REML cross-check via :mod:`statsmodels.regression.mixed_linear_model` is
provided in :func:`decompose_reml`. For the balanced case it should match
:func:`decompose_balanced` to within optimiser tolerance; if it disagrees by
more than a few percent, the design is unbalanced (missing sims) and the
REML number is the one to trust.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class VarianceComponents:
    """Variance components (in log Y units) for one metric."""

    metric: str
    n_obs: int
    grand_mean_logY: float
    sigma2: dict[str, float] = field(default_factory=dict)  # component -> variance
    df: dict[str, int] = field(default_factory=dict)
    ms: dict[str, float] = field(default_factory=dict)
    method: str = "balanced-MoM"

    @property
    def sigma(self) -> dict[str, float]:
        return {k: float(np.sqrt(max(v, 0.0))) for k, v in self.sigma2.items()}

    @property
    def total_var(self) -> float:
        return float(sum(max(v, 0.0) for v in self.sigma2.values()))

    def cv_log(self) -> dict[str, float]:
        """CV in log-space: sigma_X (since log Y is dimensionless after log)."""
        return {f"CV_{k}": s for k, s in self.sigma.items()}

    def cv_multiplicative(self) -> dict[str, float]:
        """Multiplicative CV: exp(sigma_X) - 1 (the linear-scale spread)."""
        return {f"CV_{k}": float(np.expm1(s)) for k, s in self.sigma.items()}

    def fractions(self) -> dict[str, float]:
        tot = self.total_var
        if tot <= 0:
            return {k: 0.0 for k in self.sigma2}
        return {k: max(v, 0.0) / tot for k, v in self.sigma2.items()}

    def to_row(self) -> dict:
        out = {"metric": self.metric, "n_obs": self.n_obs, "logY_mean": self.grand_mean_logY, "method": self.method}
        for k, v in self.sigma2.items():
            out[f"var_{k}"] = v
        for k, v in self.sigma.items():
            out[f"sigma_{k}"] = v
        for k, v in self.fractions().items():
            out[f"frac_{k}"] = v
        return out


def decompose_balanced(df: pd.DataFrame, metric: str) -> VarianceComponents:
    """Closed-form variance components for the balanced env-FF design.

    Uses the standard EMS for a 4-way random-effects ANOVA with main
    effects on phantom (p), freq (f), direction (d), polarisation (pi) and
    the p x f interaction. Higher-order interactions and pure numerical
    noise are pooled into the residual.
    """
    sub = df[df["metric"] == metric].copy()
    if sub.empty:
        raise ValueError(f"No data for metric {metric}")

    levels = {
        "phantom": sorted(sub["phantom"].unique()),
        "freq": sorted(sub["freq_mhz"].unique()),
        "dir": sorted(sub["direction"].unique()),
        "pol": sorted(sub["polarization"].unique()),
    }
    n_p, n_f, n_d, n_pi = (len(levels[k]) for k in ("phantom", "freq", "dir", "pol"))
    n_expected = n_p * n_f * n_d * n_pi
    n_obs = len(sub)
    if n_obs != n_expected:
        raise ValueError(
            f"Design is unbalanced for metric={metric}: got {n_obs} obs, "
            f"expected {n_expected} ({n_p}x{n_f}x{n_d}x{n_pi}). "
            "Use decompose_reml() for unbalanced data."
        )

    y = sub["logY"].to_numpy()
    grand = float(y.mean())

    # Group means for each marginal.
    mean_p = sub.groupby("phantom")["logY"].mean()
    mean_f = sub.groupby("freq_mhz")["logY"].mean()
    mean_pf = sub.groupby(["phantom", "freq_mhz"])["logY"].mean()
    mean_d = sub.groupby("direction")["logY"].mean()
    mean_pi = sub.groupby("polarization")["logY"].mean()

    ss_p = n_f * n_d * n_pi * ((mean_p - grand) ** 2).sum()
    ss_f = n_p * n_d * n_pi * ((mean_f - grand) ** 2).sum()
    ss_d = n_p * n_f * n_pi * ((mean_d - grand) ** 2).sum()
    ss_pi = n_p * n_f * n_d * ((mean_pi - grand) ** 2).sum()

    # p x f interaction (after removing main effects):
    pf_devs = mean_pf.reset_index()
    pf_devs["mean_p"] = pf_devs["phantom"].map(mean_p)
    pf_devs["mean_f"] = pf_devs["freq_mhz"].map(mean_f)
    pf_devs["interaction"] = pf_devs["logY"] - pf_devs["mean_p"] - pf_devs["mean_f"] + grand
    ss_pf = n_d * n_pi * (pf_devs["interaction"] ** 2).sum()

    ss_total = ((y - grand) ** 2).sum()
    ss_resid = ss_total - (ss_p + ss_f + ss_pf + ss_d + ss_pi)

    df_p = n_p - 1
    df_f = n_f - 1
    df_pf = df_p * df_f
    df_d = n_d - 1
    df_pi = n_pi - 1
    df_total = n_obs - 1
    df_resid = df_total - (df_p + df_f + df_pf + df_d + df_pi)

    ms = {
        "phantom": ss_p / df_p,
        "freq": ss_f / df_f,
        "pf": ss_pf / df_pf,
        "dir": ss_d / df_d,
        "pol": ss_pi / df_pi,
        "resid": ss_resid / df_resid,
    }

    # EMS-based variance components (random-effects 4-way ANOVA with
    # additive main effects + p x f interaction).
    v_resid = ms["resid"]
    v_d = (ms["dir"] - v_resid) / (n_p * n_f * n_pi)
    v_pi = (ms["pol"] - v_resid) / (n_p * n_f * n_d)
    v_pf = (ms["pf"] - v_resid) / (n_d * n_pi)
    v_p = (ms["phantom"] - ms["pf"]) / (n_f * n_d * n_pi)
    v_f = (ms["freq"] - ms["pf"]) / (n_p * n_d * n_pi)

    sigma2 = {
        "phantom": float(v_p),
        "freq": float(v_f),
        "pf": float(v_pf),
        "dir": float(v_d),
        "pol": float(v_pi),
        "resid": float(v_resid),
    }
    return VarianceComponents(
        metric=metric,
        n_obs=n_obs,
        grand_mean_logY=grand,
        sigma2=sigma2,
        df={"phantom": df_p, "freq": df_f, "pf": df_pf, "dir": df_d, "pol": df_pi, "resid": df_resid},
        ms=ms,
        method="balanced-MoM",
    )


def decompose_reml(df: pd.DataFrame, metric: str) -> VarianceComponents:
    """REML fit via statsmodels MixedLM (variance components).

    For a *balanced* design this returns the same point estimates as
    :func:`decompose_balanced` (to optimiser tolerance) and is useful as a
    sanity check. For unbalanced designs it is the correct estimator.
    """
    try:
        import statsmodels.formula.api as smf
    except ImportError as exc:
        raise RuntimeError("statsmodels is required for decompose_reml(); install with `pip install statsmodels`") from exc

    sub = df[df["metric"] == metric].copy()
    if sub.empty:
        raise ValueError(f"No data for metric {metric}")

    sub["pf"] = sub["phantom"].astype(str) + ":" + sub["freq_mhz"].astype(str)
    sub["_grp"] = 0  # single dummy group; variance components below.

    vc_formula = {
        "phantom": "0 + C(phantom)",
        "freq": "0 + C(freq_mhz)",
        "pf": "0 + C(pf)",
        "dir": "0 + C(direction)",
        "pol": "0 + C(polarization)",
    }
    md = smf.mixedlm(
        "logY ~ 1",
        sub,
        groups=sub["_grp"],
        vc_formula=vc_formula,
        re_formula="0",
    )
    fit = md.fit(reml=True, method="lbfgs")

    sigma2 = {k: float(fit.vcomp[i]) for i, k in enumerate(vc_formula)}
    sigma2["resid"] = float(fit.scale)

    return VarianceComponents(
        metric=metric,
        n_obs=len(sub),
        grand_mean_logY=float(sub["logY"].mean()),
        sigma2=sigma2,
        df={},
        ms={},
        method="REML (statsmodels)",
    )
