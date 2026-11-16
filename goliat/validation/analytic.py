"""License-free analytic reference solutions for RF dosimetry benchmarks.

Everything here is written from textbook physics and needs only NumPy/SciPy, so
solver output produced by GOLIAT/Sim4Life (or any FDTD code) can be checked
without a solver license.

Contents
--------
* Mie scattering by a homogeneous lossy sphere under plane-wave incidence
  (Bohren & Huffman 1983, ch. 4): cross-sections, absorbed power, whole-body
  SAR, internal E-field and local SAR at arbitrary points.
* Planar multilayer transfer (Airy/Parratt reflection recursion) for oblique
  TE/TM incidence on lossy layers over a half-space: R, T, per-layer
  absorption, depth profile of SAR, and APD (absorbed power density).
* Closed-form Fresnel half-space transmission, (1-|Gamma|^2).
* 4-pole Cole-Cole tissue model with Gabriel et al. (1996c) parameters.
* Peak spatial-average APD over a square on a planar grid, and cube
  mass-averaged SAR (simple variant, no IEC/IEEE 62704-1 air handling).

Conventions
-----------
* Inputs are real ``eps_r`` (relative permittivity) and ``sigma`` (total
  conductivity in S/m, dielectric losses included, as in the Gabriel tables).
* Internally the physics time convention exp(-i*omega*t) is used, i.e.
  eps_c = eps_r + i*sigma/(omega*eps0). Returned complex field phasors follow
  this convention; take the complex conjugate for exp(+j*omega*t). Magnitudes,
  powers and SAR are convention-independent.
* Field amplitudes are peak phasors: S_inc = |E0|^2 / (2*eta), and local SAR is
  sigma*|E|^2 / (2*rho).
* SI units throughout (m, Hz, S/m, kg/m^3, W/m^2, W/kg).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence, Tuple

import numpy as np
from scipy import special
from scipy.signal import fftconvolve

EPS0 = 8.8541878128e-12  # F/m (CODATA 2018)
MU0 = 1.25663706212e-6  # H/m (CODATA 2018)
C0 = 299792458.0  # m/s
ETA0 = math.sqrt(MU0 / EPS0)  # ~376.73 ohm

__all__ = [
    "EPS0",
    "MU0",
    "C0",
    "ETA0",
    # Mie
    "MieResult",
    "mie_sphere",
    "sphere_absorbed_power",
    "sphere_wb_sar",
    "sphere_internal_field",
    "sphere_local_sar",
    # planar
    "Layer",
    "MultilayerResult",
    "multilayer_response",
    "fresnel_halfspace",
    "halfspace_apd",
    # tissues
    "ColeColeParams",
    "GABRIEL_1996",
    "cole_cole",
    "tissue_properties",
    # averaging
    "SquareAverageResult",
    "peak_spatial_average_apd",
    "CubeAverageResult",
    "mass_averaged_sar",
]


def _eps_complex(eps_r: float, sigma: float, frequency: float) -> complex:
    """Complex relative permittivity, exp(-i omega t) convention (Im >= 0 for loss)."""
    omega = 2.0 * math.pi * frequency
    return complex(eps_r, sigma / (omega * EPS0))


# ---------------------------------------------------------------------------
# Mie scattering
# ---------------------------------------------------------------------------


@dataclass
class MieResult:
    """Mie solution for a homogeneous sphere in a lossless host.

    Cross-sections are in m^2, efficiencies Q = C / (pi a^2) are dimensionless.
    ``a_n``/``b_n`` are the Bohren-Huffman scattering coefficients; ``cs_n``/``ds_n``
    are the internal coefficients premultiplied by j_n(m x) (overflow-safe form).
    """

    radius: float
    frequency: float
    x: float  # size parameter k_host * a
    m: complex  # relative refractive index (sphere / host)
    n_terms: int
    q_ext: float
    q_sca: float
    q_abs: float
    a_n: np.ndarray = field(repr=False)
    b_n: np.ndarray = field(repr=False)
    cs_n: np.ndarray = field(repr=False)
    ds_n: np.ndarray = field(repr=False)

    @property
    def geometric_cross_section(self) -> float:
        return math.pi * self.radius**2

    @property
    def c_ext(self) -> float:
        return self.q_ext * self.geometric_cross_section

    @property
    def c_sca(self) -> float:
        return self.q_sca * self.geometric_cross_section

    @property
    def c_abs(self) -> float:
        return self.q_abs * self.geometric_cross_section


def _default_n_terms(x: float) -> int:
    # Wiscombe (1980) / Bohren-Huffman criterion.
    return int(round(x + 4.0 * x ** (1.0 / 3.0) + 2.0))


def _log_derivative(z: complex, n_terms: int) -> np.ndarray:
    """D_n(z) = psi_n'(z)/psi_n(z) for n = 0..n_terms, by downward recurrence (stable)."""
    n_start = int(max(n_terms, abs(z))) + 16
    d = np.zeros(n_start + 1, dtype=complex)
    for n in range(n_start, 0, -1):
        d[n - 1] = n / z - 1.0 / (d[n] + n / z)
    return d[: n_terms + 1]


def mie_sphere(
    radius: float,
    frequency: float,
    eps_r: float,
    sigma: float,
    eps_r_host: float = 1.0,
    n_terms: Optional[int] = None,
) -> MieResult:
    """Solve plane-wave scattering by a homogeneous (lossy) sphere.

    Valid range: size parameter x = k a from ~1e-4 up to ~1e4 (cost O(x));
    |m| x up to a few thousand. Accuracy of q_abs = q_ext - q_sca degrades
    (absolute error ~1e-12 * q_ext) for nearly lossless spheres.
    """
    if radius <= 0 or frequency <= 0:
        raise ValueError("radius and frequency must be positive")
    k = 2.0 * math.pi * frequency * math.sqrt(eps_r_host) / C0
    x = k * radius
    m = np.sqrt(_eps_complex(eps_r, sigma, frequency) / eps_r_host)
    nmax = _default_n_terms(x) if n_terms is None else int(n_terms)
    n_all = np.arange(nmax + 1)
    # Riccati-Bessel functions of the real host argument.
    psi = x * special.spherical_jn(n_all, x)
    chi = x * special.spherical_yn(n_all, x)
    xi = psi + 1j * chi  # x h_n^(1)(x)
    d = _log_derivative(m * x, nmax)

    n = n_all[1:]
    psi_n, psi_m1 = psi[1:], psi[:-1]
    xi_n, xi_m1 = xi[1:], xi[:-1]
    dn = d[1:]
    ta = dn / m + n / x
    tb = m * dn + n / x
    a_n = (ta * psi_n - psi_m1) / (ta * xi_n - xi_m1)
    b_n = (tb * psi_n - psi_m1) / (tb * xi_n - xi_m1)
    # Internal coefficients times j_n(m x) (BH eq. 4.52-4.53 with Wronskian i/x).
    dxi = xi_m1 - n * xi_n / x  # xi_n'(x)
    cs_n = (1j / x) / (dxi - m * dn * xi_n)
    ds_n = (1j / x) / (m * dxi - dn * xi_n)

    w = 2 * n + 1
    q_ext = 2.0 / x**2 * float(np.sum(w * (a_n + b_n).real))
    q_sca = 2.0 / x**2 * float(np.sum(w * (np.abs(a_n) ** 2 + np.abs(b_n) ** 2)))
    q_abs = q_ext - q_sca
    if sigma == 0 and abs(q_abs) < 1e-10 * max(q_ext, 1e-300):
        q_abs = 0.0
    return MieResult(radius, frequency, x, complex(m), nmax, q_ext, q_sca, q_abs, a_n, b_n, cs_n, ds_n)


def sphere_absorbed_power(radius: float, frequency: float, eps_r: float, sigma: float, s_inc: float = 1.0, **kw) -> float:
    """Total absorbed power (W) for incident power density ``s_inc`` (W/m^2)."""
    return mie_sphere(radius, frequency, eps_r, sigma, **kw).c_abs * s_inc


def sphere_wb_sar(radius: float, frequency: float, eps_r: float, sigma: float, density: float, s_inc: float = 1.0, **kw) -> float:
    """Whole-body average SAR (W/kg) = P_abs / (density * 4/3 pi a^3)."""
    mass = density * 4.0 / 3.0 * math.pi * radius**3
    return sphere_absorbed_power(radius, frequency, eps_r, sigma, s_inc, **kw) / mass


def _sph_jn_ratio(n: int, rho: np.ndarray, rho_ref: complex) -> np.ndarray:
    """j_n(rho) / j_n(rho_ref), computed with exponentially scaled Bessel functions."""
    num = special.jve(n + 0.5, rho)
    den = special.jve(n + 0.5, rho_ref)
    scale = np.exp(np.abs(rho.imag) - abs(rho_ref.imag))
    return np.sqrt(rho_ref / rho) * num / den * scale


def sphere_internal_field(
    radius: float,
    frequency: float,
    eps_r: float,
    sigma: float,
    points: np.ndarray,
    s_inc: float = 1.0,
    eps_r_host: float = 1.0,
    n_terms: Optional[int] = None,
) -> np.ndarray:
    """Internal electric field (complex peak phasors, V/m) at ``points`` (N, 3), in m.

    Geometry: sphere centred at the origin; incident wave E = E0 x_hat exp(i k z)
    (x-polarized, travelling +z), with |E0| = sqrt(2 eta_host s_inc), zero phase at
    the origin. Points must satisfy |r| <= radius. Returns Cartesian (N, 3).
    Suggested range: x <= ~200, |Im(m) x| arbitrary (scaled Bessel functions).
    """
    res = mie_sphere(radius, frequency, eps_r, sigma, eps_r_host, n_terms)
    pts = np.atleast_2d(np.asarray(points, dtype=float))
    r = np.linalg.norm(pts, axis=1)
    if np.any(r > radius * (1 + 1e-12)):
        raise ValueError("sphere_internal_field only evaluates points inside the sphere")
    r = np.maximum(r, 1e-9 * radius)
    cos_t = np.clip(pts[:, 2] / r, -1.0, 1.0)
    sin_t = np.sqrt(1.0 - cos_t**2)
    phi = np.arctan2(pts[:, 1], pts[:, 0])
    cos_p, sin_p = np.cos(phi), np.sin(phi)

    k = 2.0 * math.pi * frequency * math.sqrt(eps_r_host) / C0
    e0 = math.sqrt(2.0 * ETA0 / math.sqrt(eps_r_host) * s_inc)
    m = res.m
    rho = m * k * r
    rho_ref = m * res.x

    e_r = np.zeros(r.shape, complex)
    e_t = np.zeros(r.shape, complex)
    e_p = np.zeros(r.shape, complex)
    pi_prev = np.zeros_like(cos_t)  # pi_0
    pi_cur = np.ones_like(cos_t)  # pi_1
    for n in range(1, res.n_terms + 1):
        if n > 1:
            pi_prev, pi_cur = pi_cur, ((2 * n - 1) * cos_t * pi_cur - n * pi_prev) / (n - 1)
        tau = n * cos_t * pi_cur - (n + 1) * pi_prev
        z = _sph_jn_ratio(n, rho, rho_ref)  # j_n(rho)/j_n(mx)
        zm1 = _sph_jn_ratio(n - 1, rho, rho_ref) * (special.jve(n - 0.5, rho_ref) / special.jve(n + 0.5, rho_ref))
        dz = zm1 - n * z / rho  # [rho j_n(rho)]' / rho, normalized by j_n(mx)
        en = (1j**n) * e0 * (2 * n + 1) / (n * (n + 1))
        c, d = res.cs_n[n - 1], res.ds_n[n - 1]
        # E = sum En (c M_o1n - i d N_e1n)
        e_r += en * (-1j * d) * cos_p * n * (n + 1) * sin_t * pi_cur * z / rho
        e_t += en * (c * cos_p * pi_cur * z - 1j * d * cos_p * tau * dz)
        e_p += en * (-c * sin_p * tau * z + 1j * d * sin_p * pi_cur * dz)

    ex = e_r * sin_t * cos_p + e_t * cos_t * cos_p - e_p * sin_p
    ey = e_r * sin_t * sin_p + e_t * cos_t * sin_p + e_p * cos_p
    ez = e_r * cos_t - e_t * sin_t
    return np.stack([ex, ey, ez], axis=1)


def sphere_local_sar(radius, frequency, eps_r, sigma, density, points, s_inc=1.0, **kw) -> np.ndarray:
    """Local (point) SAR in W/kg inside the sphere: sigma |E|^2 / (2 rho)."""
    e = sphere_internal_field(radius, frequency, eps_r, sigma, points, s_inc, **kw)
    return sigma * np.sum(np.abs(e) ** 2, axis=1) / (2.0 * density)


# ---------------------------------------------------------------------------
# Planar multilayer
# ---------------------------------------------------------------------------


@dataclass
class Layer:
    """Homogeneous planar layer. ``thickness`` is ignored for the terminating half-space."""

    thickness: float
    eps_r: float
    sigma: float
    density: float = 1000.0
    name: str = ""


@dataclass
class MultilayerResult:
    """Response of a layered half-space to an oblique plane wave.

    Power fractions (``reflectance``, ``transmittance``, ``absorbed``) are relative to
    the incident flux through the surface, S_inc cos(theta), and sum to 1.
    ``apd`` (W/m^2) is the power density entering the first layer (the body
    surface); ``transmittance`` is the fraction entering the terminating half-space.
    ``interface_flux`` (W/m^2) is S_z at the top of each layer and at the top of the
    half-space (len = n_layers + 1). Depth z is measured from the body surface.
    """

    frequency: float
    angle_deg: float
    polarization: str
    s_inc: float
    reflection: complex
    reflectance: float
    transmittance: float
    absorbed: np.ndarray
    interface_flux: np.ndarray
    apd: float
    _layers: list = field(repr=False, default_factory=list)
    _amp: np.ndarray = field(repr=False, default=None)
    _rho: np.ndarray = field(repr=False, default=None)
    _kz: np.ndarray = field(repr=False, default=None)
    _eps: np.ndarray = field(repr=False, default=None)
    _kx: float = 0.0
    _z_top: np.ndarray = field(repr=False, default=None)

    def e_field_sq(self, z: np.ndarray) -> np.ndarray:
        """|E|^2 (peak, V^2/m^2) at depths z >= 0 inside the stack."""
        z = np.atleast_1d(np.asarray(z, dtype=float))
        if np.any(z < 0):
            raise ValueError("depth must be >= 0")
        omega = 2.0 * math.pi * self.frequency
        idx = np.searchsorted(self._z_top, z, side="right") - 1
        out = np.empty(z.shape)
        for j in np.unique(idx):
            sel = idx == j
            s = z[sel] - self._z_top[j]
            kz, a, rho = self._kz[j], self._amp[j], self._rho[j]
            d = self._layers[j].thickness if j < len(self._layers) - 1 else 0.0
            fwd = a * np.exp(1j * kz * s)
            bwd = a * rho * np.exp(1j * kz * (2 * d - s)) if j < len(self._layers) - 1 else 0.0 * fwd
            psi, psi_m = fwd + bwd, fwd - bwd
            if self.polarization == "TE":
                out[sel] = np.abs(psi) ** 2
            else:
                eps = self._eps[j]
                ex = kz * psi_m / (omega * EPS0 * eps)
                ez = self._kx * psi / (omega * EPS0 * eps)
                out[sel] = np.abs(ex) ** 2 + np.abs(ez) ** 2
        return out

    def power_density(self, z) -> np.ndarray:
        """Dissipated power density sigma |E|^2 / 2 (W/m^3) at depth z."""
        z = np.atleast_1d(np.asarray(z, dtype=float))
        idx = np.searchsorted(self._z_top, z, side="right") - 1
        sig = np.array([self._layers[j].sigma for j in idx])
        return 0.5 * sig * self.e_field_sq(z)

    def sar_profile(self, z) -> np.ndarray:
        """Local SAR (W/kg) at depth z, using each layer's ``density``."""
        z = np.atleast_1d(np.asarray(z, dtype=float))
        idx = np.searchsorted(self._z_top, z, side="right") - 1
        rho = np.array([self._layers[j].density for j in idx])
        return self.power_density(z) / rho


def multilayer_response(
    layers: Sequence[Layer],
    substrate: Layer,
    frequency: float,
    angle_deg: float = 0.0,
    polarization: str = "TE",
    eps_r_incident: float = 1.0,
    s_inc: float = 1.0,
) -> MultilayerResult:
    """Plane wave from a lossless medium onto ``layers`` (top to bottom) over ``substrate``.

    Uses the reflection-coefficient (Airy/Parratt) recursion, which only involves
    decaying exponentials, so arbitrarily thick lossy layers are handled.
    TE = E perpendicular to the plane of incidence (s); TM = H perpendicular (p).
    """
    pol = polarization.upper()
    if pol not in ("TE", "TM"):
        raise ValueError("polarization must be 'TE' or 'TM'")
    stack = list(layers) + [substrate]
    omega = 2.0 * math.pi * frequency
    k0 = omega / C0
    theta = math.radians(angle_deg)
    kx = k0 * math.sqrt(eps_r_incident) * math.sin(theta)
    eps = np.array([complex(eps_r_incident, 0.0)] + [_eps_complex(L.eps_r, L.sigma, frequency) for L in stack])
    kz = np.sqrt(eps * k0**2 - kx**2 + 0j)
    kz = np.where(kz.imag < 0, -kz, kz)
    q = kz if pol == "TE" else kz / eps
    n_med = len(eps)  # incident medium + layers + substrate
    thick = np.array([0.0] + [L.thickness for L in layers] + [0.0])

    # gamma[j]: B/A at the top of medium j; rho[j]: reflection seen at the bottom of medium j.
    gamma = np.zeros(n_med, complex)
    rho = np.zeros(n_med, complex)
    for j in range(n_med - 2, -1, -1):
        r = (q[j] - q[j + 1]) / (q[j] + q[j + 1])
        rho[j] = (r + gamma[j + 1]) / (1.0 + r * gamma[j + 1])
        gamma[j] = rho[j] * np.exp(2j * kz[j] * thick[j])

    eta_inc = ETA0 / math.sqrt(eps_r_incident)
    e0 = math.sqrt(2.0 * eta_inc * s_inc)
    amp = np.zeros(n_med, complex)
    amp[0] = e0 if pol == "TE" else e0 / eta_inc
    for j in range(n_med - 1):
        amp[j + 1] = amp[j] * np.exp(1j * kz[j] * thick[j]) * (1.0 + rho[j]) / (1.0 + gamma[j + 1])

    const = omega * MU0 if pol == "TE" else omega * EPS0
    # S_z at the top of each medium 1..N (body surface downwards).
    flux = np.array([0.5 * (q[j] * (1.0 - gamma[j]) * np.conj(1.0 + gamma[j])).real * abs(amp[j]) ** 2 / const for j in range(1, n_med)])
    s_norm = s_inc * math.cos(theta)
    absorbed = (flux[:-1] - flux[1:]) / s_norm
    trans = flux[-1] / s_norm
    refl = abs(gamma[0]) ** 2
    z_top = np.concatenate([[0.0], np.cumsum([L.thickness for L in layers])])
    return MultilayerResult(
        frequency=frequency,
        angle_deg=angle_deg,
        polarization=pol,
        s_inc=s_inc,
        reflection=complex(gamma[0]),
        reflectance=float(refl),
        transmittance=float(trans),
        absorbed=absorbed,
        interface_flux=flux,
        apd=float(flux[0]),
        _layers=stack,
        _amp=amp[1:],
        _rho=rho[1:],
        _kz=kz[1:],
        _eps=eps[1:],
        _kx=kx,
        _z_top=z_top,
    )


def fresnel_halfspace(
    eps_r: float, sigma: float, frequency: float, angle_deg: float = 0.0, polarization: str = "TE", eps_r_incident: float = 1.0
) -> Tuple[complex, float]:
    """Closed-form Fresnel reflection coefficient and transmitted power fraction 1-|Gamma|^2."""
    e1 = complex(eps_r_incident, 0.0)
    e2 = _eps_complex(eps_r, sigma, frequency)
    s = math.sin(math.radians(angle_deg))
    c1 = math.cos(math.radians(angle_deg))
    c2 = np.sqrt(1.0 - e1 * s**2 / e2 + 0j)  # complex cos(theta_t)
    n1, n2 = np.sqrt(e1), np.sqrt(e2)
    if polarization.upper() == "TE":
        g = (n1 * c1 - n2 * c2) / (n1 * c1 + n2 * c2)
    else:
        g = (n2 * c1 - n1 * c2) / (n2 * c1 + n1 * c2)
    return complex(g), float(1.0 - abs(g) ** 2)


def halfspace_apd(eps_r, sigma, frequency, s_inc=1.0, angle_deg=0.0, polarization="TE") -> float:
    """APD (W/m^2) for a homogeneous half-space: (1 - |Gamma|^2) S_inc cos(theta)."""
    _, t = fresnel_halfspace(eps_r, sigma, frequency, angle_deg, polarization)
    return t * s_inc * math.cos(math.radians(angle_deg))


# ---------------------------------------------------------------------------
# Tissue dielectric properties (Cole-Cole)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ColeColeParams:
    """4-pole Cole-Cole parameters (Gabriel et al. 1996c, Phys. Med. Biol. 41:2271, Table 1).

    eps(w) = eps_inf + sum_n delta_n / (1 + (j w tau_n)^(1-alpha_n)) + sigma_i / (j w eps0)
    """

    eps_inf: float
    delta: Tuple[float, float, float, float]
    tau: Tuple[float, float, float, float]  # seconds
    alpha: Tuple[float, float, float, float]
    sigma_ionic: float
    source: str = "Gabriel, Lau & Gabriel 1996c, Phys. Med. Biol. 41:2271-2293, Table 1"


_PS, _NS, _US, _MS = 1e-12, 1e-9, 1e-6, 1e-3

#: Parameter sets transcribed from Gabriel et al. 1996c Table 1 (same values as the
#: IFAC-CNR "Dielectric properties of body tissues" database). Spot-checked in the
#: test suite against published IFAC values (e.g. muscle 900 MHz: 55.03, 0.943 S/m).
GABRIEL_1996: Dict[str, ColeColeParams] = {
    "skin_dry": ColeColeParams(
        4.0, (32.0, 1100.0, 0.0, 0.0), (7.234 * _PS, 32.481 * _NS, 159.155 * _US, 15.915 * _MS), (0.0, 0.20, 0.20, 0.20), 0.0002
    ),
    "skin_wet": ColeColeParams(
        4.0, (39.0, 280.0, 3.0e4, 3.0e4), (7.958 * _PS, 79.577 * _NS, 1.592 * _US, 1.592 * _MS), (0.1, 0.0, 0.16, 0.2), 0.0004
    ),
    "muscle": ColeColeParams(
        4.0, (50.0, 7000.0, 1.2e6, 2.5e7), (7.234 * _PS, 353.678 * _NS, 318.310 * _US, 2.274 * _MS), (0.1, 0.1, 0.1, 0.0), 0.2
    ),
    "fat": ColeColeParams(  # "Fat (not infiltrated)"
        2.5, (3.0, 15.0, 3.3e4, 1.0e7), (7.958 * _PS, 15.915 * _NS, 159.155 * _US, 7.958 * _MS), (0.2, 0.1, 0.05, 0.01), 0.01
    ),
    "blood": ColeColeParams(
        4.0, (56.0, 5200.0, 0.0, 0.0), (8.377 * _PS, 132.629 * _NS, 159.155 * _US, 15.915 * _MS), (0.1, 0.1, 0.2, 0.0), 0.7
    ),
}


def cole_cole(params: ColeColeParams, frequency) -> Tuple[np.ndarray, np.ndarray]:
    """Return (eps_r, sigma [S/m]) for scalar or array ``frequency`` (Hz).

    Gabriel's fits are intended for 10 Hz - 20 GHz; above 20 GHz (up to ~100 GHz)
    they are the common extrapolation used in mmWave dosimetry but carry larger
    uncertainty.
    """
    f = np.asarray(frequency, dtype=float)
    jw = 1j * 2.0 * np.pi * f
    eps = params.eps_inf + params.sigma_ionic / (jw * EPS0) + 0j
    for de, tau, al in zip(params.delta, params.tau, params.alpha):
        if de:
            eps = eps + de / (1.0 + (jw * tau) ** (1.0 - al))
    eps_r = eps.real
    sigma = -eps.imag * 2.0 * np.pi * f * EPS0
    return eps_r, sigma


def tissue_properties(name: str, frequency) -> Tuple[np.ndarray, np.ndarray]:
    """Cole-Cole (eps_r, sigma) for a tissue key of :data:`GABRIEL_1996`."""
    try:
        params = GABRIEL_1996[name]
    except KeyError:
        raise KeyError(f"unknown tissue {name!r}; available: {sorted(GABRIEL_1996)}") from None
    return cole_cole(params, frequency)


# ---------------------------------------------------------------------------
# Spatial averaging helpers
# ---------------------------------------------------------------------------


def _edge_weights(length_cells: float) -> np.ndarray:
    """1-D kernel for a window spanning ``length_cells`` cells, aligned to a cell edge."""
    n_full = int(math.floor(length_cells + 1e-9))
    frac = length_cells - n_full
    w = np.ones(n_full + (1 if frac > 1e-9 else 0))
    if frac > 1e-9:
        w[-1] = frac
    return w


@dataclass
class SquareAverageResult:
    peak: float
    peak_index: Tuple[int, int]  # (i, j) of the window's first cell
    averaged: np.ndarray  # average for every valid window position
    side: float


def peak_spatial_average_apd(apd: np.ndarray, dx: float, dy: Optional[float] = None, area: float = 4e-4) -> SquareAverageResult:
    """Peak spatial-average APD over a square of ``area`` (m^2) on a planar grid.

    ``apd[i, j]`` holds cell-averaged APD (W/m^2) of a uniform grid with spacing
    ``dx`` (axis 0) and ``dy`` (axis 1). The square is axis-aligned, starts on a
    cell edge, and partially covered cells at the far edge get fractional
    weights. Windows must lie fully on the grid (no extrapolation). Limitations:
    planar surfaces only (no conformal/curved surface averaging as in IEC/IEEE
    63195-2), no rotated squares.
    """
    dy = dx if dy is None else dy
    side = math.sqrt(area)
    wx, wy = _edge_weights(side / dx), _edge_weights(side / dy)
    if len(wx) > apd.shape[0] or len(wy) > apd.shape[1]:
        raise ValueError("averaging square larger than the grid")
    kernel = np.outer(wx, wy)
    avg = fftconvolve(np.asarray(apd, float), kernel[::-1, ::-1], mode="valid") * (dx * dy) / area
    i, j = np.unravel_index(int(np.argmax(avg)), avg.shape)
    return SquareAverageResult(float(avg[i, j]), (int(i), int(j)), avg, side)


@dataclass
class CubeAverageResult:
    peak: float
    peak_index: Tuple[int, int, int]
    averaged: np.ndarray  # NaN where the centre voxel has zero density or the grid lacks mass
    side: np.ndarray  # cube side (m) per voxel


def _box_sum(sat: np.ndarray, centers: Tuple[np.ndarray, ...], half: Tuple[np.ndarray, ...]) -> np.ndarray:
    """Sum over the box [c-h, c+h] (inclusive, clipped) using a padded summed-volume table."""
    lo, hi = [], []
    for ax in range(3):
        nmax = sat.shape[ax] - 1
        lo.append(np.clip(centers[ax] - half[ax], 0, nmax))
        hi.append(np.clip(centers[ax] + half[ax] + 1, 0, nmax))
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    return (
        sat[x1, y1, z1]
        - sat[x0, y1, z1]
        - sat[x1, y0, z1]
        - sat[x1, y1, z0]
        + sat[x0, y0, z1]
        + sat[x0, y1, z0]
        + sat[x1, y0, z0]
        - sat[x0, y0, z0]
    )


def _sat(a: np.ndarray) -> np.ndarray:
    s = np.zeros(tuple(n + 1 for n in a.shape))
    s[1:, 1:, 1:] = a.cumsum(0).cumsum(1).cumsum(2)
    return s


def mass_averaged_sar(
    sar: np.ndarray,
    density: np.ndarray,
    voxel_size: Sequence[float],
    mass: float = 0.01,
    n_iter: int = 50,
) -> CubeAverageResult:
    """Cube mass-averaged SAR (e.g. ``mass=0.001`` for 1 g, ``0.01`` for 10 g, in kg).

    For every voxel with non-zero density a cube centred on the voxel centre is
    grown (bisection on its side) until the enclosed mass equals ``mass``;
    voxels cut by the cube faces contribute by their volume fraction. The result
    is (sum of absorbed power in cube) / mass.

    Limitations (simple variant, NOT the full IEC/IEEE 62704-1 algorithm):
    no limit on the air fraction in the cube and no re-centring/shifting of
    cubes near the surface; air (density 0) and space beyond the grid simply add
    volume but no mass, so near-surface cubes grow larger than a tissue-filled
    cube. Cubes are axis-aligned. Cost is O(N * n_iter); intended for small
    benchmark grids (<~1e6 voxels).
    """
    sar = np.asarray(sar, float)
    rho = np.asarray(density, float) * np.ones_like(sar)
    dv = float(np.prod(voxel_size))
    vs = np.asarray(voxel_size, float)
    sat_m = _sat(rho * dv)
    sat_p = _sat(sar * rho * dv)
    total_mass = sat_m[-1, -1, -1]

    idx = np.nonzero(rho > 0)
    centers = tuple(np.asarray(i) for i in idx)

    def sums(side: np.ndarray):
        # Per axis: weight (1-f) on |j|<=k, f extends to |j|<=k+1, where side/2 = (k+0.5+f)*d.
        hcells = [side / 2.0 / vs[a] - 0.5 for a in range(3)]
        ks = [np.floor(h).astype(int) for h in hcells]
        # Sub-voxel cube (k = -1): the centre voxel is covered by fraction side/d = 2*(h+0.5).
        fs = [np.where(k < 0, 2.0 * (h + 0.5), h - k) for h, k in zip(hcells, ks)]
        m_tot = np.zeros(side.shape)
        p_tot = np.zeros(side.shape)
        for cx in (0, 1):
            for cy in (0, 1):
                for cz in (0, 1):
                    coef = np.ones(side.shape)
                    half = []
                    for a, c in enumerate((cx, cy, cz)):
                        coef = coef * (fs[a] if c else (1.0 - fs[a]))
                        half.append(ks[a] + c)
                    # k = -1 means empty box
                    empty = np.any([h < 0 for h in half], axis=0)
                    hh = tuple(np.maximum(h, 0) for h in half)
                    mb = np.where(empty, 0.0, _box_sum(sat_m, centers, hh))
                    pb = np.where(empty, 0.0, _box_sum(sat_p, centers, hh))
                    m_tot += coef * mb
                    p_tot += coef * pb
        return m_tot, p_tot

    lo = np.zeros(len(idx[0]))
    hi_side = float(np.max(np.asarray(sar.shape) * vs)) * 2.0 + float(vs.max())
    hi = np.full(len(idx[0]), hi_side)
    for _ in range(n_iter):
        mid = 0.5 * (lo + hi)
        m_mid, _ = sums(mid)
        below = m_mid < mass
        lo = np.where(below, mid, lo)
        hi = np.where(below, hi, mid)
    side = 0.5 * (lo + hi)
    m_fin, p_fin = sums(side)

    averaged = np.full(sar.shape, np.nan)
    sides = np.full(sar.shape, np.nan)
    ok = total_mass >= mass * (1 - 1e-12)
    averaged[idx] = p_fin / m_fin if ok else np.nan
    sides[idx] = side if ok else np.nan
    if not np.any(np.isfinite(averaged)):
        raise ValueError("grid holds less mass than the averaging mass")
    pk = np.unravel_index(int(np.nanargmax(averaged)), averaged.shape)
    return CubeAverageResult(float(averaged[pk]), (int(pk[0]), int(pk[1]), int(pk[2])), averaged, sides)
