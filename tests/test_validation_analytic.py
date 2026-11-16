"""Independent checks of goliat.validation.analytic (physics limits, conservation, closed forms)."""

import math

import numpy as np
import pytest

from goliat.validation import (
    C0,
    ETA0,
    Layer,
    fresnel_halfspace,
    halfspace_apd,
    mass_averaged_sar,
    mie_sphere,
    multilayer_response,
    peak_spatial_average_apd,
    sphere_absorbed_power,
    sphere_internal_field,
    sphere_wb_sar,
    tissue_properties,
)
from goliat.validation.analytic import EPS0

# ----------------------------------------------------------------- tissues


@pytest.mark.parametrize(
    "tissue,freq,eps_ref,sig_ref",
    [
        # IFAC-CNR tabulations of the Gabriel 1996c model (independent source of the numbers).
        ("muscle", 900e6, 55.03, 0.943),
        ("muscle", 2.45e9, 52.73, 1.739),
        ("muscle", 10e9, 42.76, 10.63),
        ("skin_dry", 900e6, 41.41, 0.867),
        ("skin_dry", 10e9, 31.29, 8.014),
        ("skin_dry", 60e9, 7.98, 36.40),
        ("skin_wet", 900e6, 46.08, 0.845),
        ("blood", 900e6, 61.36, 1.538),
        ("fat", 900e6, 5.462, 0.0510),
    ],
)
def test_cole_cole_matches_ifac(tissue, freq, eps_ref, sig_ref):
    eps, sig = tissue_properties(tissue, freq)
    assert eps == pytest.approx(eps_ref, rel=2e-3)
    assert sig == pytest.approx(sig_ref, rel=3e-3)


# ----------------------------------------------------------------- Mie


def test_lossless_sphere_absorbs_nothing():
    r = mie_sphere(0.05, 2e9, 4.0, 0.0)
    assert r.q_sca > 0.1
    assert abs(r.q_abs) < 1e-10
    assert r.q_ext == pytest.approx(r.q_sca, rel=1e-10)


def test_rayleigh_limit_absorption():
    # Moderate contrast so the magnetic-dipole (eddy-current) loss, O(x^2 |m|^2) relative, is negligible.
    eps, sig, f = 4.0, 0.05, 100e6
    a = 1e-3
    r = mie_sphere(a, f, eps, sig)
    assert r.x < 0.01
    ec = complex(eps, sig / (2 * math.pi * f * EPS0))
    # Quasi-static: Q_abs = 4 x Im((eps-1)/(eps+2)); internal field 3/(eps+2) E0.
    q_qs = 4 * r.x * ((ec - 1) / (ec + 2)).imag
    assert r.q_abs == pytest.approx(q_qs, rel=1e-3)
    # Independent route: P = sigma/2 |E_in|^2 V with uniform internal field.
    e0sq = 2 * ETA0 * 1.0
    p_qs = 0.5 * sig * abs(3 / (ec + 2)) ** 2 * e0sq * 4 / 3 * math.pi * a**3
    assert sphere_absorbed_power(a, f, eps, sig, 1.0) == pytest.approx(p_qs, rel=2e-3)


def _fresnel_avg_absorption(eps, sig, f):
    """Geometric-optics Q_abs of an opaque sphere: 2 * int (1-R(theta)) cos sin dtheta."""
    th = np.linspace(0, math.pi / 2, 2001)
    vals = []
    for t in th:
        t_te = fresnel_halfspace(eps, sig, f, math.degrees(t), "TE")[1]
        t_tm = fresnel_halfspace(eps, sig, f, math.degrees(t), "TM")[1]
        vals.append(0.5 * (t_te + t_tm) * math.cos(t) * math.sin(t))
    return 2 * np.trapz(vals, th)


def test_large_sphere_geometric_optics_limit():
    f = 10e9
    eps, sig = map(float, tissue_properties("muscle", f))
    q_go = _fresnel_avg_absorption(eps, sig, f)
    # Opaque sphere (skin depth ~3 mm << a): Q_abs -> Fresnel-averaged GO value with an
    # O(x^-2/3) edge correction, Q_ext -> 2 (extinction paradox).
    errs = []
    for a in (0.5, 2.0, 8.0):
        r = mie_sphere(a, f, eps, sig)
        errs.append(r.q_abs - q_go)
    assert r.x > 1600
    assert r.q_ext == pytest.approx(2.0, rel=0.01)
    assert r.q_abs == pytest.approx(q_go, rel=0.02)
    assert errs[0] > errs[1] > errs[2] > 0
    assert errs[1] / errs[0] == pytest.approx(4 ** (-2 / 3), rel=0.15)
    # Normal-incidence (1-|Gamma|^2) is only a rough estimate (TM pseudo-Brewster raises the average).
    assert r.q_abs == pytest.approx(fresnel_halfspace(eps, sig, f)[1], rel=0.1)


def test_mie_against_published_reference_values():
    # Cross-checked against miepython 3.3 (independent implementation), agreement < 1e-9.
    eps, sig = map(float, tissue_properties("muscle", 900e6))
    r = mie_sphere(0.1, 900e6, eps, sig)
    assert r.q_ext == pytest.approx(2.64289533, rel=1e-7)
    assert r.q_sca == pytest.approx(1.79096646, rel=1e-7)


def test_internal_field_m_equal_one_is_incident_wave():
    f, a = 1e9, 0.2
    rng = np.random.default_rng(0)
    pts = rng.uniform(-1, 1, (200, 3))
    pts = pts[np.linalg.norm(pts, axis=1) < 1] * a
    e = sphere_internal_field(a, f, 1.0, 0.0, pts, s_inc=1.0, n_terms=40)
    k = 2 * math.pi * f / C0
    e0 = math.sqrt(2 * ETA0)
    ref = np.zeros_like(e)
    ref[:, 0] = e0 * np.exp(1j * k * pts[:, 2])
    assert np.max(np.abs(e - ref)) < 1e-8 * e0


def test_internal_field_small_sphere_quasistatic():
    # Low contrast and tiny |m| k a: induced (eddy) field is negligible against 3/(eps+2) E0.
    eps, sig, f, a = 4.0, 0.05, 50e6, 1e-4
    e = sphere_internal_field(a, f, eps, sig, np.array([[0, 0, 0.0], [0.3e-4, -0.2e-4, 0.4e-4]]))
    ec = complex(eps, sig / (2 * math.pi * f * EPS0))
    ref = abs(3 / (ec + 2)) * math.sqrt(2 * ETA0)
    assert np.abs(e[:, 0]) == pytest.approx([ref, ref], rel=3e-4)  # first-order retardation error ~ |m| k r
    assert np.all(np.abs(e[:, 1:]) < 1e-3 * ref)


def test_volume_integral_of_internal_field_matches_c_abs():
    # Gauss-Legendre quadrature of sigma/2 |E|^2 over the sphere must reproduce C_abs * S_inc.
    eps, sig, f, a = 55.0, 0.94, 900e6, 0.05
    nr, nt, npf = 40, 40, 16
    xr, wr = np.polynomial.legendre.leggauss(nr)
    xt, wt = np.polynomial.legendre.leggauss(nt)
    r = 0.5 * a * (xr + 1)
    wr = 0.5 * a * wr
    mu = xt
    phi = np.arange(npf) * 2 * math.pi / npf
    R, MU, PHI = np.meshgrid(r, mu, phi, indexing="ij")
    W = (wr[:, None, None] * R**2) * wt[None, :, None] * (2 * math.pi / npf)
    st = np.sqrt(1 - MU**2)
    pts = np.stack([R * st * np.cos(PHI), R * st * np.sin(PHI), R * MU], axis=-1).reshape(-1, 3)
    e = sphere_internal_field(a, f, eps, sig, pts)
    p_vol = float(np.sum(0.5 * sig * np.sum(np.abs(e) ** 2, axis=1) * W.ravel()))
    assert p_vol == pytest.approx(sphere_absorbed_power(a, f, eps, sig), rel=1e-6)


def test_wb_sar_definition():
    p = sphere_absorbed_power(0.1, 900e6, 55.0, 0.94, 10.0)
    sar = sphere_wb_sar(0.1, 900e6, 55.0, 0.94, 1090.0, 10.0)
    assert sar == pytest.approx(p / (1090 * 4 / 3 * math.pi * 0.1**3))


def test_very_lossy_large_sphere_is_finite():
    eps, sig = tissue_properties("skin_dry", 60e9)
    r = mie_sphere(0.05, 60e9, float(eps), float(sig))  # x ~ 63, |Im m x| ~ 2.5e2
    assert np.isfinite(r.q_abs) and 0 < r.q_abs < 1
    e = sphere_internal_field(0.05, 60e9, float(eps), float(sig), np.array([[0, 0, -0.0499], [0, 0, 0.0]]))
    assert np.all(np.isfinite(e))
    assert np.abs(e[1, 0]) < 1e-20  # deep interior is shielded


# ----------------------------------------------------------------- planar


@pytest.mark.parametrize("pol", ["TE", "TM"])
@pytest.mark.parametrize("angle", [0.0, 35.0, 70.0])
def test_single_interface_matches_fresnel(pol, angle):
    eps, sig = tissue_properties("skin_dry", 30e9)
    res = multilayer_response([], Layer(0, float(eps), float(sig)), 30e9, angle, pol)
    g, t = fresnel_halfspace(float(eps), float(sig), 30e9, angle, pol)
    assert res.reflectance == pytest.approx(abs(g) ** 2, rel=1e-12)
    assert res.transmittance == pytest.approx(t, rel=1e-10)
    assert res.apd == pytest.approx(halfspace_apd(float(eps), float(sig), 30e9, 1.0, angle, pol), rel=1e-10)


def test_brewster_angle_lossless_tm():
    eps = 4.0
    th = math.degrees(math.atan(math.sqrt(eps)))
    res = multilayer_response([], Layer(0, eps, 0.0), 1e9, th, "TM")
    assert res.reflectance < 1e-20
    te = multilayer_response([], Layer(0, eps, 0.0), 1e9, th, "TE")
    assert te.reflectance > 0.1


def test_quarter_wave_antireflection():
    f, eps_sub = 10e9, 9.0
    n1 = math.sqrt(math.sqrt(eps_sub))
    d = C0 / f / (4 * n1)
    res = multilayer_response([Layer(d, n1**2, 0.0)], Layer(0, eps_sub, 0.0), f)
    assert res.reflectance < 1e-20
    assert res.transmittance == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize("pol", ["TE", "TM"])
@pytest.mark.parametrize("f", [0.9e9, 10e9, 60e9])
def test_energy_conservation_skin_fat_muscle(pol, f):
    layers = [Layer(1.5e-3, *map(float, tissue_properties("skin_dry", f))), Layer(4e-3, *map(float, tissue_properties("fat", f)))]
    sub = Layer(0, *map(float, tissue_properties("muscle", f)))
    res = multilayer_response(layers, sub, f, 40.0, pol)
    assert res.reflectance + res.transmittance + res.absorbed.sum() == pytest.approx(1.0, abs=1e-12)
    assert np.all(res.absorbed > 0)
    assert res.apd == pytest.approx((1 - res.reflectance) * math.cos(math.radians(40)), rel=1e-12)


@pytest.mark.parametrize("pol", ["TE", "TM"])
def test_depth_integral_of_loss_matches_layer_absorption(pol):
    f = 10e9
    layers = [Layer(1e-3, *map(float, tissue_properties("skin_dry", f))), Layer(3e-3, *map(float, tissue_properties("fat", f)))]
    sub = Layer(0, *map(float, tissue_properties("muscle", f)))
    res = multilayer_response(layers, sub, f, 30.0, pol, s_inc=10.0)
    s_norm = 10.0 * math.cos(math.radians(30))
    edges = [0.0, 1e-3, 4e-3, 4e-3 + 0.05]
    for j in range(3):
        x, w = np.polynomial.legendre.leggauss(200)
        z = 0.5 * (edges[j + 1] - edges[j]) * (x + 1) + edges[j]
        p = np.sum(res.power_density(z) * w) * 0.5 * (edges[j + 1] - edges[j])
        ref = res.absorbed[j] * s_norm if j < 2 else res.interface_flux[-1]
        assert p == pytest.approx(ref, rel=1e-6)
    # SAR at the surface = sigma |E(0)|^2 / (2 rho)
    assert res.sar_profile(0.0)[0] == pytest.approx(res.power_density(0.0)[0] / layers[0].density)


def test_thick_lossy_layer_converges_to_halfspace():
    f = 10e9
    eps, sig = map(float, tissue_properties("muscle", f))
    half = multilayer_response([], Layer(0, eps, sig), f, 20.0, "TM")
    thick = multilayer_response([Layer(0.5, eps, sig)], Layer(0, 1.0, 0.0), f, 20.0, "TM")  # 0.5 m >> skin depth
    assert thick.reflectance == pytest.approx(half.reflectance, rel=1e-12)
    assert thick.absorbed[0] == pytest.approx(half.transmittance, rel=1e-12)
    assert thick.transmittance < 1e-100


def test_skin_halfspace_normal_incidence_closed_form():
    # Derived by hand: n = sqrt(eps_c), T = 4 Re(n) / |1+n|^2 at normal incidence.
    for f in (10e9, 30e9):
        eps, sig = map(float, tissue_properties("skin_dry", f))
        n = np.sqrt(complex(eps, sig / (2 * math.pi * f * EPS0)))
        t_ref = 4 * n.real / abs(1 + n) ** 2
        assert fresnel_halfspace(eps, sig, f)[1] == pytest.approx(t_ref, rel=1e-12)
        assert 0.45 < t_ref < 0.6


# ----------------------------------------------------------------- averaging


def test_psapd_uniform_and_gaussian():
    dx = 0.5e-3
    grid = np.full((100, 100), 7.0)
    assert peak_spatial_average_apd(grid, dx, area=4e-4).peak == pytest.approx(7.0)
    assert peak_spatial_average_apd(grid, 0.3e-3, area=1e-4).peak == pytest.approx(7.0)  # fractional cells
    # Narrow Gaussian spot: whole power captured by the 4 cm^2 window.
    x = (np.arange(200) - 99.5) * dx
    X, Y = np.meshgrid(x, x, indexing="ij")
    s = 1e-3
    apd = np.exp(-(X**2 + Y**2) / (2 * s**2)) / (2 * math.pi * s**2)  # 1 W total
    res = peak_spatial_average_apd(apd, dx, area=4e-4)
    assert res.peak == pytest.approx(1.0 / 4e-4, rel=1e-6)


def test_mass_averaged_sar_uniform_and_point_source():
    vox = (1e-3, 1e-3, 1e-3)
    rho = np.full((40, 40, 40), 1000.0)
    res = mass_averaged_sar(np.full(rho.shape, 2.0), rho, vox, mass=0.01)
    assert np.nanmax(np.abs(res.averaged - 2.0)) < 1e-9
    centre = res.side[20, 20, 20]
    assert centre == pytest.approx((0.01 / 1000) ** (1 / 3), rel=1e-6)  # 21.54 mm
    # Single hot voxel holding power P: every cube that fully contains it averages to P / 10 g.
    sar = np.zeros(rho.shape)
    sar[20, 20, 20] = 5.0  # W/kg in a 1 mg voxel -> 5e-6 W
    res = mass_averaged_sar(sar, rho, vox, mass=0.01)
    assert res.peak == pytest.approx(5e-6 / 0.01, rel=1e-9)
    # Linear gradient: symmetric cube average equals the centre value.
    lin = np.broadcast_to(np.arange(40.0)[:, None, None], rho.shape).copy()
    res = mass_averaged_sar(lin, rho, vox, mass=0.001)
    assert res.averaged[20, 20, 20] == pytest.approx(20.0, rel=1e-9)


def test_mass_averaged_sar_anisotropic_and_air():
    vox = (1e-3, 2e-3, 0.5e-3)
    rho = np.full((30, 20, 60), 1050.0)
    rho[:, :, :10] = 0.0  # air layer
    res = mass_averaged_sar(np.where(rho > 0, 3.0, 0.0), rho, vox, mass=0.001)
    assert np.all(np.isnan(res.averaged[:, :, :10]))
    assert np.nanmax(np.abs(res.averaged - 3.0)) < 1e-9
    assert res.side[15, 10, 40] == pytest.approx((0.001 / 1050) ** (1 / 3), rel=1e-6)
