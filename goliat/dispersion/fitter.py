"""
Dispersion model fitting for multisine FDTD simulations.

Fits exactly to 2 frequency points using analytical solution.
"""

from dataclasses import dataclass
from typing import Tuple

import numpy as np
from scipy.optimize import fsolve

EPS_0 = 8.854187817e-12  # F/m


@dataclass
class PoleFit:
    """Parameters for a dispersion pole."""

    delta_eps: float  # Static permittivity contribution
    tau_s: float  # Relaxation time in seconds
    damping_hz: float  # Damping frequency in Hz (= 1/(2πτ))


@dataclass
class DispersionParams:
    """Fitted dispersion model parameters."""

    eps_inf: float  # High-frequency permittivity limit
    sigma_dc: float  # DC conductivity (S/m)
    poles: list[PoleFit]  # List of poles
    fit_error: float  # Max relative error (should be ~0 for exact fit)
    start_freq_hz: float  # Model valid from this frequency
    end_freq_hz: float  # Model valid to this frequency


def _eval_model(omega: float, eps_inf: float, de1: float, tau1: float, de2: float, tau2: float, sigma_dc: float) -> Tuple[float, float]:
    """Evaluate 2-pole model at angular frequency omega."""
    eps_c = eps_inf + de1 / (1 + 1j * omega * tau1) + de2 / (1 + 1j * omega * tau2)
    eps_c -= 1j * sigma_dc / (omega * EPS_0)
    return float(np.real(eps_c)), float(-omega * EPS_0 * np.imag(eps_c))


def fit_dispersion(
    frequencies_hz: list[float],
    eps_r_targets: list[float],
    sigma_targets: list[float],
) -> DispersionParams:
    """
    Fit dispersion model to match target frequencies.

    For 2 frequencies: Uses exact solution (<1ms).
    For 3+ frequencies: Uses optimization.

    Args:
        frequencies_hz: List of frequencies in Hz
        eps_r_targets: Target relative permittivity at each frequency
        sigma_targets: Target conductivity (S/m) at each frequency

    Returns:
        DispersionParams with fitted model parameters

    Raises:
        ValueError: If mismatched input lengths
    """
    if len(frequencies_hz) != len(eps_r_targets) or len(frequencies_hz) != len(sigma_targets):
        raise ValueError("All input lists must have the same length")

    if len(frequencies_hz) == 2:
        return _fit_exact(frequencies_hz, eps_r_targets, sigma_targets)
    else:
        return _fit_optimize(frequencies_hz, eps_r_targets, sigma_targets)


def _fit_exact(
    frequencies_hz: list[float],
    eps_r_targets: list[float],
    sigma_targets: list[float],
) -> DispersionParams:
    """Exact fit for 2 frequency points using fsolve."""
    f1, f2 = frequencies_hz
    eps1, eps2 = eps_r_targets
    sig1, sig2 = sigma_targets
    omega1, omega2 = 2 * np.pi * f1, 2 * np.pi * f2

    # Fixed relaxation times (typical biological range)
    tau1 = 1e-11  # ~15 GHz
    tau2 = 1e-10  # ~1.5 GHz

    def equations(params):
        eps_inf, de1, de2, sigma_dc = params
        e1, s1 = _eval_model(omega1, eps_inf, de1, tau1, de2, tau2, sigma_dc)
        e2, s2 = _eval_model(omega2, eps_inf, de1, tau1, de2, tau2, sigma_dc)
        return [e1 - eps1, e2 - eps2, s1 - sig1, s2 - sig2]

    x0 = [min(eps1, eps2) * 0.3, max(eps1, eps2) * 0.4, max(eps1, eps2) * 0.3, min(sig1, sig2)]

    solution, info, ier, msg = fsolve(equations, x0, full_output=True)
    eps_inf, de1, de2, sigma_dc = solution
    residual = np.max(np.abs(equations(solution)))

    # Retry with different tau values if needed
    if residual > 1e-6:
        for tau1_try, tau2_try in [(5e-12, 5e-11), (2e-11, 2e-10), (1e-12, 1e-9)]:
            tau1, tau2 = tau1_try, tau2_try
            solution, info, ier, msg = fsolve(equations, x0, full_output=True)
            eps_inf, de1, de2, sigma_dc = solution
            residual = np.max(np.abs(equations(solution)))
            if residual < 1e-6:
                break

    return DispersionParams(
        eps_inf=eps_inf,
        sigma_dc=sigma_dc,
        poles=[
            PoleFit(delta_eps=de1, tau_s=tau1, damping_hz=1 / (2 * np.pi * tau1)),
            PoleFit(delta_eps=de2, tau_s=tau2, damping_hz=1 / (2 * np.pi * tau2)),
        ],
        fit_error=residual,
        start_freq_hz=min(f1, f2) * 0.5,
        end_freq_hz=max(f1, f2) * 2,
    )


def _fit_optimize(
    frequencies_hz: list[float],
    eps_r_targets: list[float],
    sigma_targets: list[float],
) -> DispersionParams:
    """Optimization-based fit for 3+ frequency points."""
    from scipy.optimize import minimize

    omegas = np.array([2 * np.pi * f for f in frequencies_hz])
    eps_arr = np.array(eps_r_targets)
    sig_arr = np.array(sigma_targets)

    def objective(params):
        eps_inf, de1, tau1, de2, tau2, sigma_dc = params
        err = 0
        for i, omega in enumerate(omegas):
            e, s = _eval_model(omega, eps_inf, de1, tau1, de2, tau2, sigma_dc)
            err += ((e - eps_arr[i]) / eps_arr[i]) ** 2 + ((s - sig_arr[i]) / sig_arr[i]) ** 2
        return err

    x0 = [5, 30, 1e-11, 20, 1e-10, 0.5]
    bounds = [(1, 50), (1, 200), (1e-13, 1e-9), (1, 200), (1e-12, 1e-8), (0, 5)]
    result = minimize(objective, x0, method="L-BFGS-B", bounds=bounds)

    eps_inf, de1, tau1, de2, tau2, sigma_dc = result.x
    return DispersionParams(
        eps_inf=eps_inf,
        sigma_dc=sigma_dc,
        poles=[
            PoleFit(delta_eps=de1, tau_s=tau1, damping_hz=1 / (2 * np.pi * tau1)),
            PoleFit(delta_eps=de2, tau_s=tau2, damping_hz=1 / (2 * np.pi * tau2)),
        ],
        fit_error=result.fun,
        start_freq_hz=min(frequencies_hz) * 0.5,
        end_freq_hz=max(frequencies_hz) * 2,
    )


def validate_fit(
    params: DispersionParams,
    frequencies_hz: list[float],
    eps_r_targets: list[float],
    sigma_targets: list[float],
    tolerance_pct: float = 1.0,
) -> tuple[bool, dict]:
    """Validate fitted model matches targets within tolerance."""
    errors = {}
    is_valid = True

    for i, f in enumerate(frequencies_hz):
        omega = 2 * np.pi * f
        p1, p2 = params.poles
        eps_fit, sig_fit = _eval_model(omega, params.eps_inf, p1.delta_eps, p1.tau_s, p2.delta_eps, p2.tau_s, params.sigma_dc)

        eps_err = abs(eps_fit - eps_r_targets[i]) / eps_r_targets[i] * 100
        sig_err = abs(sig_fit - sigma_targets[i]) / sigma_targets[i] * 100

        errors[f] = {"eps_error_pct": eps_err, "sigma_error_pct": sig_err}
        if eps_err > tolerance_pct or sig_err > tolerance_pct:
            is_valid = False

    return is_valid, errors
