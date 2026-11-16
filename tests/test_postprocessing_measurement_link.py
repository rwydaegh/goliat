"""Physics tests for goliat.postprocessing.measurement_link.

Reference fields are computed independently from closed-form solutions
(Hertzian dipole, plane waves) and never through the module under test.
"""

import numpy as np
import pytest

from goliat.postprocessing import measurement_link as ml

C0 = 299_792_458.0
MU0 = 4e-7 * np.pi
ETA0 = MU0 * C0
F = 30e9
LAM = C0 / F
K = 2 * np.pi / LAM


def dipole_fields(X, Y, Z, u=(1.0, 0.0, 0.0), il=1e-3, k=K, src=(0.0, 0.0, 0.0)):
    """Exact Hertzian-dipole E and H (peak phasors, exp(+jwt)) at points X,Y,Z."""
    u = np.asarray(u, float) / np.linalg.norm(u)
    R = np.stack([X - src[0], Y - src[1], Z - src[2]], axis=-1)
    r = np.linalg.norm(R, axis=-1)[..., None]
    rh = R / r
    ur = np.sum(rh * u, axis=-1)[..., None]
    g = np.exp(-1j * k * r) * il / (4 * np.pi)
    E = ETA0 * g * ((1j * k / r) * (rh * ur - u) + (1 / r**2 + 1 / (1j * k * r**3)) * (3 * rh * ur - u))
    H = g * (1j * k / r + 1 / r**2) * np.cross(u, rh)
    return E, H


def dipole_plane(z, half=0.1, step=LAM / 10, **kw):
    x = np.arange(-half, half + step / 2, step)
    y = x.copy()
    X, Y = np.meshgrid(x, y, indexing="ij")
    E, H = dipole_fields(X, Y, np.full_like(X, z), **kw)
    return ml.PlanarField(x=x, y=y, z=z, frequency_hz=F, E=E, H=H)


def rel_err(a, b):
    return np.linalg.norm(a - b) / np.linalg.norm(b)


def central(fld, half):
    return fld.crop((-half, half), (-half, half))


# ---------------------------------------------------------------- PWS physics


def _pws_dipole_errors(half, z1=0.5 * LAM, z2=2.0 * LAM, step=LAM / 10, centre=0.03):
    meas = dipole_plane(z1, half=half, step=step)
    tangential_only = ml.PlanarField(x=meas.x, y=meas.y, z=z1, frequency_hz=F, E=meas.E[..., :2])
    prop = ml.propagate(tangential_only, z2, pad_factor=2)
    ref = dipole_plane(z2, half=half, step=step)
    p, r = central(prop, centre), central(ref, centre)
    return rel_err(p.E, r.E), rel_err(p.E[..., 2], r.E[..., 2]), rel_err(p.H, r.H)


def test_dipole_pws_propagation_matches_exact_fields():
    # 30 GHz x-dipole, tangential E sampled at z1 = lambda/2 (5 mm) with lambda/10
    # steps, propagated to z2 = 2 lambda (20 mm); error on the central 6x6 cm.
    e_err, ez_err, h_err = _pws_dipole_errors(half=0.25)
    print(f"dipole PWS 5mm->20mm, 50 cm aperture: E {e_err:.2e}, Ez {ez_err:.2e}, H {h_err:.2e}")
    assert e_err < 0.015
    assert ez_err < 0.02
    assert h_err < 0.015
    # the residual is aperture truncation: it shrinks as the scan grows
    e_small, _, _ = _pws_dipole_errors(half=0.15)
    e_large, _, _ = _pws_dipole_errors(half=0.4)
    print(f"aperture convergence: 30 cm {e_small:.2e} > 50 cm {e_err:.2e} > 80 cm {e_large:.2e}")
    assert e_small > e_err > e_large


def test_reconstruct_full_fields_on_same_plane():
    fld = dipole_plane(LAM, half=0.25)
    rec = ml.reconstruct_fields(ml.PlanarField(x=fld.x, y=fld.y, z=fld.z, frequency_hz=F, E=fld.E[..., :2]))
    p, r = central(rec, 0.03), central(fld, 0.03)
    print(f"same-plane reconstruction at z=lambda: E {rel_err(p.E, r.E):.2e}, H {rel_err(p.H, r.H):.2e}")
    assert rel_err(p.E, r.E) < 0.015
    assert rel_err(p.H, r.H) < 0.015
    # psPD from PWS-reconstructed H agrees with psPD from the exact H
    for area in (1e-4, 4e-4):
        pd_rec = ml.spatial_average_pd(central(rec, 0.05), area).pspdn
        pd_ref = ml.spatial_average_pd(central(fld, 0.05), area).pspdn
        print(f"psPDn({area * 1e4:.0f} cm2) PWS {pd_rec:.4e} vs exact {pd_ref:.4e} W/m2")
        assert abs(pd_rec / pd_ref - 1) < 0.01


def test_back_propagation_requires_filter_and_recovers_propagating_band():
    z1, z2 = 3 * LAM, 1.5 * LAM
    fld = dipole_plane(z1, half=0.25)
    with pytest.raises(ValueError):
        ml.propagate(fld, z2)
    back = ml.propagate(fld, z2, k_max_factor=1.0, taper=0.05)
    # reference: exact field at z2 restricted to the same (propagating) band
    ref = ml.reconstruct_fields(dipole_plane(z2, half=0.25), k_max_factor=1.0, taper=0.05)
    err_t = rel_err(central(back, 0.03).E[..., :2], central(ref, 0.03).E[..., :2])
    err = rel_err(central(back, 0.03).E, central(ref, 0.03).E)
    print(f"back-propagation 3λ->1.5λ vs band-limited exact: Et {err_t:.2e}, E {err:.2e}")
    assert err_t < 0.01
    assert err < 0.01


def test_plane_wave_power_density():
    # Oblique TE/TM mix chosen on an FFT bin so that the periodic model is exact.
    n, step = 64, LAM / 8
    x = np.arange(n) * step
    y = np.arange(n) * step
    kx = 2 * np.pi * 5 / (n * step)
    ky = 2 * np.pi * 3 / (n * step)
    kz = np.sqrt(K**2 - kx**2 - ky**2)
    kvec = np.array([kx, ky, kz])
    e0 = np.cross(kvec, [0.3, -1.0, 0.2])
    e0 = (e0 / np.linalg.norm(e0)) * (12.0 * np.exp(0.4j))  # |E| = 12 V/m, transverse to k
    X, Y = np.meshgrid(x, y, indexing="ij")
    phase = np.exp(-1j * (kx * X + ky * Y + kz * 0.0))[..., None]
    E = e0 * phase
    H = np.cross(kvec, e0) / (K * ETA0) * phase
    fld = ml.PlanarField(x=x, y=y, z=0.0, frequency_hz=F, E=E, H=H)
    S = ml.poynting(fld)
    expected_mag = 12.0**2 / (2 * ETA0)
    np.testing.assert_allclose(np.linalg.norm(S, axis=-1), expected_mag, rtol=1e-10)
    np.testing.assert_allclose(S[..., 2], expected_mag * kz / K, rtol=1e-10)
    # Same values when H and Ez come from PWS reconstruction of tangential E only
    rec = ml.reconstruct_fields(ml.PlanarField(x=x, y=y, z=0.0, frequency_hz=F, E=E[..., :2]), pad_factor=1)
    np.testing.assert_allclose(rec.E, E, rtol=1e-9, atol=1e-9 * 12)
    np.testing.assert_allclose(rec.H, H, rtol=1e-9, atol=1e-9 * 12 / ETA0)
    avg = ml.spatial_average_pd(rec, area_m2=1e-4)
    assert avg.pspdn == pytest.approx(expected_mag * kz / K, rel=1e-9)
    assert avg.pspdtot == pytest.approx(expected_mag, rel=1e-9)
    # normal incidence plane wave: PD = |E|^2 / (2 eta)
    En = np.zeros((n, n, 3), complex)
    En[..., 0] = 10.0
    pw = ml.reconstruct_fields(ml.PlanarField(x=x, y=y, z=0.0, frequency_hz=F, E=En[..., :2]), pad_factor=1)
    np.testing.assert_allclose(ml.poynting(pw)[..., 2], 100 / (2 * ETA0), rtol=1e-12)
    np.testing.assert_allclose(ml.plane_wave_pd(pw), 100 / (2 * ETA0), rtol=1e-12)


def test_power_conservation_between_planes():
    z1, z2 = 0.5 * LAM, 3.0 * LAM
    il = 1e-3
    fld = dipole_plane(z1, half=0.25)
    et = ml.PlanarField(x=fld.x, y=fld.y, z=z1, frequency_hz=F, E=fld.E[..., :2])
    spec = ml.angular_spectrum(et, pad_factor=2)
    p1, p2 = spec.plane_power(0.0), spec.plane_power(z2 - z1)
    # spatial Poynting integral of the PWS fields (full padded grid at z2)
    s1 = ml.total_power(ml.reconstruct_fields(et))
    s2 = ml.total_power(ml.propagate(et, z2, keep_padding=True))
    # independent: exact dipole fields integrated over the same scan aperture
    exact1 = ml.total_power(fld)
    # analytic: half the radiated power of an x-dipole crosses any infinite z>0 plane
    prad_half = 0.5 * ETA0 * (K * il) ** 2 / (12 * np.pi)
    print(
        f"power [W]: PWS z1 {s1:.5e}, PWS z2 {s2:.5e}, spectral {p1:.5e}/{p2:.5e}, "
        f"exact on aperture {exact1:.5e}, analytic infinite plane {prad_half:.5e}"
    )
    assert p2 == pytest.approx(p1, rel=1e-10)  # only propagating waves carry real power
    assert s2 == pytest.approx(s1, rel=1e-3)
    assert s1 == pytest.approx(exact1, rel=5e-3)
    # the finite 50 cm aperture captures most, but not all, of the half-space power
    assert 0.9 * prad_half < exact1 < prad_half


def test_spatial_average_box_is_exact_for_fractional_windows():
    x = np.arange(0, 0.04, 1e-3)
    y = np.arange(0, 0.03, 1e-3)
    X, Y = np.meshgrid(x, y, indexing="ij")
    S = np.zeros(X.shape + (3,))
    S[..., 2] = 1.0 + 100 * X  # linear ramp: window average = value at centre
    fld = ml.PlanarField(x=x, y=y, z=0, frequency_hz=F, E=np.zeros(X.shape + (3,)))
    avg = ml.spatial_average_pd(fld, area_m2=(0.0105) ** 2, S=S)  # 10.5 cells
    Xc, _ = np.meshgrid(avg.xc, avg.yc, indexing="ij")
    np.testing.assert_allclose(avg.spdn, 1 + 100 * Xc, rtol=1e-12)
    assert avg.pspdn_location[0] == pytest.approx(avg.xc.max())


def test_spectral_upsample_reproduces_finer_sampling():
    coarse = dipole_plane(2 * LAM, half=0.12, step=LAM / 4)
    fine = ml.spectral_upsample(coarse, 4, pad_factor=2)
    X, Y = np.meshgrid(fine.x, fine.y, indexing="ij")
    E_ref, _ = dipole_fields(X, Y, np.full_like(X, 2 * LAM))
    ref = ml.PlanarField(x=fine.x, y=fine.y, z=fine.z, frequency_hz=F, E=E_ref)
    err = rel_err(central(fine, 0.03).E, central(ref, 0.03).E)
    print(f"spectral upsample λ/4 -> λ/16 at z=2λ: rel err {err:.2e}")
    assert err < 0.02


# ------------------------------------------------------- comparison metrics


def test_registration_recovers_known_shift():
    sim = dipole_plane(LAM, half=0.06, step=0.5e-3, u=(1, 0.3, 0))
    for shift in [(3e-3, -2e-3), (1.25e-3, 0.7e-3)]:
        X, Y = np.meshgrid(sim.x, sim.y, indexing="ij")
        E, H = dipole_fields(X, Y, np.full_like(X, LAM), u=(1, 0.3, 0), src=(shift[0], shift[1], 0.0))
        meas = ml.PlanarField(x=sim.x, y=sim.y, z=LAM, frequency_hz=F, E=E, H=H)
        est = ml.register_translation(sim, meas)
        print(f"shift {shift} -> estimated {est}")
        assert est[0] == pytest.approx(shift[0], abs=0.1e-3)
        assert est[1] == pytest.approx(shift[1], abs=0.1e-3)


def test_calibration_recovers_known_scale_and_compare_fields():
    sim = dipole_plane(LAM, half=0.05, step=0.5e-3)
    rng = np.random.default_rng(0)
    a = 0.73 * np.exp(0.4j)
    noise = 0.002 * np.max(np.abs(sim.E)) * (rng.standard_normal(sim.E.shape) + 1j * rng.standard_normal(sim.E.shape))
    meas = ml.PlanarField(x=sim.x, y=sim.y, z=sim.z, frequency_hz=F, E=(a * sim.E + noise)[..., :2])
    cal = ml.calibration_factor(meas, sim, mode="complex")
    assert cal.field_factor == pytest.approx(a, rel=5e-3)
    assert cal.power_factor == pytest.approx(0.73**2, rel=1e-2)
    mag = ml.calibration_factor(
        ml.PlanarField(x=sim.x, y=sim.y, z=sim.z, frequency_hz=F, E=np.abs(a * sim.E), phase_valid=False), sim, mode="magnitude"
    )
    assert mag.field_factor.real == pytest.approx(0.73, rel=1e-6)

    res = ml.compare_fields(meas, sim, register=True, calibrate=True)
    print("compare_fields:", res.as_dict())
    assert abs(res.shift_m[0]) < 0.1e-3 and abs(res.shift_m[1]) < 0.1e-3
    assert res.mre < 0.05
    assert res.phase_rms_deg < 3.0
    for area in (1e-4, 4e-4):
        assert abs(res.pspd_rel_error[area]) < 0.02
    raw = ml.compare_fields(meas, sim, register=False, calibrate=False)
    assert raw.pspd_rel_error[1e-4] == pytest.approx(1 / 0.73**2 - 1, rel=0.03)


# ------------------------------------------------------------------ file I/O


@pytest.mark.parametrize("ext", [".csv", ".npz", ".h5"])
def test_roundtrip_formats(tmp_path, ext):
    fld = dipole_plane(LAM, half=0.01, step=1e-3)
    path = tmp_path / f"map{ext}"
    {".csv": ml.save_csv, ".npz": ml.save_npz, ".h5": ml.save_hdf5}[ext](fld, path)
    back = ml.load_field_map(path)
    np.testing.assert_allclose(back.x, fld.x)
    np.testing.assert_allclose(back.E, fld.E, rtol=1e-12)
    np.testing.assert_allclose(back.H, fld.H, rtol=1e-12)
    assert back.frequency_hz == F and back.z == pytest.approx(fld.z)


def test_csv_in_mm_with_tangential_only(tmp_path):
    path = tmp_path / "probe.csv"
    rows = ["# frequency_hz = 3e10", "# z = 5", "# length_unit = mm", "x,y,Ex_re,Ex_im,Ey_re,Ey_im"]
    for xv in (2.0, 0.0, 1.0):
        for yv in (0.0, 1.0):
            rows.append(f"{xv},{yv},{xv},{yv},0,1")
    path.write_text("\n".join(rows) + "\n")
    fld = ml.load_csv(path)
    np.testing.assert_allclose(fld.x, [0, 1e-3, 2e-3])
    assert fld.z == pytest.approx(5e-3)
    assert not fld.has_ez
    assert fld.E[2, 1, 0] == pytest.approx(2 + 1j)


def test_sim4life_output_adapter(tmp_path):
    h5py = pytest.importorskip("h5py")
    ax = np.linspace(-0.01, 0.01, 11)
    ay = np.linspace(-0.01, 0.01, 9)
    az = np.linspace(0.0, 0.004, 5)
    path = tmp_path / "x_Output.h5"
    with h5py.File(path, "w") as f:
        f["Meshes/m0/axis_x"], f["Meshes/m0/axis_y"], f["Meshes/m0/axis_z"] = ax, ay, az
        f["FieldGroups/0/_Object"] = np.zeros(1)
        f["FieldGroups/0/_Object"].attrs["name"] = "Overall Field"
        for ft, val in (("E", (1 + 2j, 3j, 4.0)), ("H", (0.1, 0.2, 0.3j))):
            base = f"FieldGroups/0/AllFields/EM {ft}(x,y,z,f0)/_Object/Snapshots/0"
            for c, shp in enumerate([(10, 9, 5), (11, 8, 5), (11, 9, 4)]):
                d = np.zeros(shp + (2,))
                d[..., 0], d[..., 1] = np.real(val[c]), np.imag(val[c])
                f[f"{base}/comp{c}"] = d
    fld = ml.from_sim4life_output(path, z=0.0021, frequency_hz=F)
    assert fld.z == pytest.approx(0.002)
    assert fld.shape == (10, 8)
    np.testing.assert_allclose(fld.E[0, 0], [1 + 2j, 3j, 4.0])
    np.testing.assert_allclose(fld.H[0, 0], [0.1, 0.2, 0.3j])


def test_time_convention_and_magnitude_only_maps():
    fld = dipole_plane(LAM, half=0.06, step=0.5e-3)
    et = ml.PlanarField(x=fld.x, y=fld.y, z=fld.z, frequency_hz=F, E=fld.E[..., :2])
    fwd = ml.propagate(et, 2 * LAM)
    conj_in = ml.PlanarField(x=fld.x, y=fld.y, z=fld.z, frequency_hz=F, E=np.conj(fld.E[..., :2]), time_convention="-jwt")
    np.testing.assert_allclose(ml.propagate(conj_in, 2 * LAM).E, np.conj(fwd.E), atol=1e-9 * np.abs(fwd.E).max())

    # magnitude-only map (e.g. an image-based super-resolution output): no PWS,
    # PD falls back to the plane-wave estimate on both sides of the comparison
    mag = ml.PlanarField(x=fld.x, y=fld.y, z=fld.z, frequency_hz=F, E=np.abs(fld.E) * 0.9, phase_valid=False)
    with pytest.raises(ValueError):
        ml.propagate(mag, 2 * LAM)
    res = ml.compare_fields(mag, fld, register=True, calibrate=False)
    assert res.phase_rms_deg is None and res.complex_rel_l2 is None
    assert res.calibration.field_factor.real == pytest.approx(0.9, rel=1e-6)
    assert res.pspd_rel_error[1e-4] == pytest.approx(1 / 0.81 - 1, rel=1e-3)
