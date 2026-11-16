"""Tests for goliat.postprocessing.multiport_apd (synthetic fields, no Sim4Life)."""

import itertools

import h5py
import numpy as np
import pytest

from goliat.postprocessing import multiport_apd as mp


def _rand_fields(rng, N, M, smooth_shape=None):
    E = rng.standard_normal((N, M, 3)) + 1j * rng.standard_normal((N, M, 3))
    H = rng.standard_normal((N, M, 3)) + 1j * rng.standard_normal((N, M, 3))
    if smooth_shape is not None:
        # spatially smooth patterns so hotspots exist (more realistic)
        nx, ny = smooth_shape
        x, y = np.meshgrid(np.linspace(0, 1, nx), np.linspace(0, 1, ny), indexing="ij")
        for i in range(N):
            env = np.exp(-((x - rng.random()) ** 2 + (y - rng.random()) ** 2) / 0.05).ravel()
            E[i] *= env[:, None]
            H[i] *= env[:, None]
    return E, H


def _grid_setup(rng, N=3, nx=24, ny=20, dx=1e-3, area=25e-6):
    x = np.arange(nx) * dx
    y = np.arange(ny) * dx
    M = nx * ny
    E, H = _rand_fields(rng, N, M, (nx, ny))
    normals = np.tile([0.0, 0.0, 1.0], (M, 1))
    Qp = mp.point_matrices_surface(E, H, normals)
    am = mp.area_matrices_grid(Qp.reshape(nx, ny, N, N), x, y, area_m2=area)
    return E, H, normals, Qp, am, x, y


def _grid_average_map(apd, nx, ny, x, y, area):
    """Reference sAPD map from a scalar APD map via the N=1 matrix path."""
    am1 = mp.area_matrices_grid(apd.reshape(nx, ny, 1, 1).astype(complex), x, y, area_m2=area)
    return np.real(am1.Q[:, 0, 0])


# ---------------------------------------------------------------------------
# Point matrices / linearity
# ---------------------------------------------------------------------------


def test_point_matrices_hermitian_and_match_combined_field():
    rng = np.random.default_rng(0)
    N, M = 4, 50
    E, H = _rand_fields(rng, N, M)
    n = rng.standard_normal((M, 3))
    n /= np.linalg.norm(n, axis=1, keepdims=True)
    Q = mp.point_matrices_surface(E, H, n, chunk_size=7)
    assert np.allclose(Q, np.conj(np.swapaxes(Q, 1, 2)))
    for _ in range(5):
        a = rng.standard_normal(N) + 1j * rng.standard_normal(N)
        Ec = np.tensordot(a, E, axes=1)
        Hc = np.tensordot(a, H, axes=1)
        ref = mp.apd_surface(Ec, Hc, n)
        got = np.real(np.einsum("i,mij,j->m", np.conj(a), Q, a))
        assert np.allclose(got, ref, rtol=1e-12, atol=1e-12)


def test_volumetric_matrices_linearity():
    rng = np.random.default_rng(1)
    N, M, D = 3, 40, 6
    E = rng.standard_normal((N, M, D, 3)) + 1j * rng.standard_normal((N, M, D, 3))
    sigma = rng.random((M, D)) * 30
    sigma[:, -1] = 0.0  # beyond zmax
    dz = 0.2e-3
    Q = mp.point_matrices_volumetric(E, sigma, dz, chunk_size=9)
    assert np.all(np.linalg.eigvalsh(Q) > -1e-9)  # PSD
    a = rng.standard_normal(N) + 1j * rng.standard_normal(N)
    ref = mp.apd_volumetric(np.tensordot(a, E, axes=1), sigma, dz)
    got = np.real(np.einsum("i,mij,j->m", np.conj(a), Q, a))
    assert np.allclose(got, ref)


def test_coherent_superposition_area_average():
    """sAPD from Q_A equals averaging the APD of the superposed fields."""
    rng = np.random.default_rng(2)
    nx, ny, area = 24, 20, 25e-6
    E, H, n, _, am, x, y = _grid_setup(rng, nx=nx, ny=ny, area=area)
    for _ in range(4):
        a = rng.standard_normal(3) + 1j * rng.standard_normal(3)
        apd = mp.apd_surface(np.tensordot(a, E, axes=1), np.tensordot(a, H, axes=1), n)
        ref = _grid_average_map(apd, nx, ny, x, y, area)
        assert np.allclose(mp.spatial_average_apd(am, a, chunk_size=13), ref)
        # linearity in the matrices: scaling a by s scales sAPD by |s|^2
        assert np.allclose(mp.spatial_average_apd(am, 2j * a), 4 * ref)


# ---------------------------------------------------------------------------
# Area averaging geometry
# ---------------------------------------------------------------------------


def test_grid_box_filter_fractional_weights_exact():
    # constant field -> average equals the constant; linear ramp -> centre value
    nx, ny, dx = 30, 30, 1e-3
    x = np.arange(nx) * dx
    y = np.arange(ny) * dx
    ramp = (x[:, None] + 0 * y[None, :]).astype(complex)
    for area in (4e-6 * 4.7, 1e-4, 16e-6):  # non-integer and integer side lengths
        am = mp.area_matrices_grid(ramp[..., None, None], x, y, area_m2=area)
        assert np.allclose(np.real(am.Q[:, 0, 0]), am.centers[:, 0])


def test_surface_square_matches_grid_on_plane():
    rng = np.random.default_rng(3)
    nx, ny, dx = 21, 19, 1e-3
    area = (5 * dx) ** 2  # odd number of cells -> identical membership
    _, _, _, Qp, am_g, x, y = _grid_setup(rng, nx=nx, ny=ny, dx=dx, area=area)
    X, Y = np.meshgrid(x, y, indexing="ij")
    pts = np.stack([X.ravel(), Y.ravel(), np.zeros(X.size)], axis=1)
    normals = np.tile([0.0, 0.0, 1.0], (len(pts), 1))
    areas = np.full(len(pts), dx * dx)
    gi = am_g.meta["grid_index"]
    centers = gi[:, 0] * ny + gi[:, 1]
    am_s = mp.area_matrices_surface(
        Qp,
        pts,
        normals,
        areas,
        area_m2=area,
        shape="square",
        center_indices=centers,
        ref_dir=(1, 0, 0),
        chunk_size=17,
    )
    assert am_s.n_areas == am_g.n_areas
    assert np.allclose(am_s.Q, am_g.Q)
    assert np.allclose(am_s.coverage, 1.0)


def test_surface_disc_on_sphere_coverage_and_normals():
    # icosphere-like sampling via a UV sphere mesh
    R = 0.08
    nt, nph = 360, 720  # ~0.7 mm spacing at the equator
    th = np.linspace(0, np.pi, nt)
    ph = np.linspace(0, 2 * np.pi, nph, endpoint=False)
    T, P = np.meshgrid(th, ph, indexing="ij")
    verts = R * np.stack([np.sin(T) * np.cos(P), np.sin(T) * np.sin(P), np.cos(T)], -1).reshape(-1, 3)
    i, j = np.meshgrid(np.arange(nt - 1), np.arange(nph), indexing="ij")
    a = (i * nph + j).ravel()
    b = (i * nph + (j + 1) % nph).ravel()
    c, d = a + nph, b + nph
    faces = np.concatenate([np.stack([a, c, b], 1), np.stack([b, c, d], 1)])
    pts, nrm, areas = mp.surface_from_mesh(verts, faces, interior_point=(0, 0, 0))
    eq = np.where(np.abs(pts[:, 2]) < 2e-3)[0][:10]
    assert np.all(np.sum(nrm[eq] * pts[eq], axis=1) < 0)  # inward
    Q1 = np.ones((len(pts), 1, 1), dtype=complex)
    am = mp.area_matrices_surface(Q1, pts, nrm, areas, area_m2=4e-4, shape="disc", center_indices=eq, min_coverage=0.5)
    # Euclidean disc of radius r on a sphere covers 2*pi*R*h, h = r^2/(2R) -> exactly pi r^2
    assert np.allclose(am.coverage, 1.0, atol=0.03)
    assert np.allclose(np.real(am.Q[:, 0, 0]), 1.0)


# ---------------------------------------------------------------------------
# Optimisers
# ---------------------------------------------------------------------------


def test_total_power_eigen_upper_bounds_random_excitations():
    rng = np.random.default_rng(4)
    _, _, _, _, am, _, _ = _grid_setup(rng, N=4)
    P = 2.5
    res = mp.worst_case_total_power(am, power=P, chunk_size=11)
    assert np.isclose(np.sum(np.abs(res.excitation) ** 2), P)
    # eigenvector attains the value
    assert np.isclose(mp.spatial_average_apd(am, res.excitation)[res.area_index], res.value)
    # brute force over random excitations never exceeds, and gets close
    A = rng.standard_normal((20000, 4)) + 1j * rng.standard_normal((20000, 4))
    A *= np.sqrt(P) / np.linalg.norm(A, axis=1, keepdims=True)
    cb = mp.evaluate_codebook(am, A, return_map=False)
    assert cb.value <= res.value * (1 + 1e-10)
    assert cb.value >= 0.9 * res.value
    # per-area map is the per-area max eigenvalue
    assert np.isclose(res.per_area.max(), res.value)


def test_phase_only_bounds_and_codebook_dominance():
    rng = np.random.default_rng(5)
    _, _, _, _, am, _, _ = _grid_setup(rng, N=4)
    P = 1.0
    tp = mp.worst_case_total_power(am, power=P)
    cbk = mp.phase_codebook(4, n_levels=4, power=P)
    rand_cb = np.sqrt(P / 4) * np.exp(2j * np.pi * rng.random((50, 4)))
    codebook = np.vstack([cbk, rand_cb])
    cb = mp.evaluate_codebook(am, codebook)
    po = mp.worst_case_phase_only(am, power=P, init_excitations=codebook, n_starts=4)
    assert np.allclose(np.abs(po.excitation) ** 2, P / 4)
    assert po.value <= tp.value * (1 + 1e-10)
    assert po.value >= cb.per_beam_peak.max() - 1e-12
    assert np.all(po.value >= cb.per_beam_map.max(axis=1) - 1e-12)
    # reported value is reproducible from the excitation
    assert np.isclose(mp.spatial_average_apd(am, po.excitation)[po.area_index], po.value)
    # without codebook seeding, multistart still matches/exceeds the 2-bit exhaustive optimum here
    po2 = mp.worst_case_phase_only(am, power=P, n_starts=16)
    ex = mp.worst_case_phase_exhaustive(am, power=P, n_levels=4)
    assert po2.value >= ex.value - 1e-12
    assert ex.value <= po2.value <= tp.value * (1 + 1e-10)


def test_phase_only_pruning_is_exact():
    rng = np.random.default_rng(6)
    _, _, _, _, am, _, _ = _grid_setup(rng, N=3)
    a = mp.worst_case_phase_only(am, prune=True, chunk_size=5)
    b = mp.worst_case_phase_only(am, prune=False, return_map=True, chunk_size=1000)
    assert np.isclose(a.value, b.value)
    assert np.isclose(np.nanmax(b.per_area), b.value)
    assert a.info["n_areas_optimized"] <= am.n_areas


def test_exhaustive_matches_explicit_loop():
    rng = np.random.default_rng(7)
    _, _, _, _, am, _, _ = _grid_setup(rng, N=3)
    ex = mp.worst_case_phase_exhaustive(am, power=1.0, n_levels=4)
    best = -np.inf
    for k1, k2 in itertools.product(range(4), repeat=2):
        a = np.exp(1j * np.pi / 2 * np.array([0, k1, k2])) / np.sqrt(3)
        best = max(best, mp.spatial_average_apd(am, a).max())
    assert np.isclose(ex.value, best)


def test_single_port_reduces_to_ordinary_psapd():
    rng = np.random.default_rng(8)
    nx, ny, area = 24, 20, 25e-6
    E, H, n, _, am, x, y = _grid_setup(rng, N=1, nx=nx, ny=ny, area=area)
    ref = _grid_average_map(mp.apd_surface(E[0], H[0], n), nx, ny, x, y, area).max()
    P = 3.0
    assert np.isclose(mp.worst_case_total_power(am, power=P).value, P * ref)
    assert np.isclose(mp.worst_case_phase_only(am, power=P).value, P * ref)
    assert np.isclose(mp.worst_case_power_caps(am, power=P, port_caps=P).value, P * ref)
    assert np.isclose(mp.evaluate_codebook(am, [[np.sqrt(P)]]).value, P * ref)


def test_two_port_analytic_optimum():
    """Q = [[q1, c], [c*, q2]] -> phase-only optimum phi2 - phi1 = -arg c,
    value P/2 (q1 + q2 + 2|c|); total power = P * lambda_max."""
    rng = np.random.default_rng(9)
    _, _, _, _, am, _, _ = _grid_setup(rng, N=2)
    P = 1.0
    po = mp.worst_case_phase_only(am, power=P, prune=False, return_map=True)
    q1 = np.real(am.Q[:, 0, 0])
    q2 = np.real(am.Q[:, 1, 1])
    c = am.Q[:, 0, 1]
    closed = 0.5 * P * (q1 + q2 + 2 * np.abs(c))
    assert np.allclose(po.per_area, closed)
    a = po.excitation
    k = po.area_index
    dphi = np.angle(a[1] / a[0])
    assert np.isclose(np.angle(np.exp(1j * (dphi + np.angle(c[k])))), 0.0, atol=1e-6)
    lam = 0.5 * (q1 + q2) + np.sqrt(0.25 * (q1 - q2) ** 2 + np.abs(c) ** 2)
    assert np.isclose(mp.worst_case_total_power(am, power=P).value, P * lam.max())


def test_two_port_physical_phase_shifted_copy():
    """Port 2 radiates the same pattern as port 1 with a phase offset theta:
    optimum is phi2 = -theta and sAPD = 2 P * sAPD_1 (coherent gain 2 at P/2 each)."""
    rng = np.random.default_rng(10)
    nx, ny, area = 24, 20, 25e-6
    E1, H1 = _rand_fields(rng, 1, nx * ny, (nx, ny))
    theta = 1.1
    E = np.concatenate([E1, E1 * np.exp(1j * theta)])
    H = np.concatenate([H1, H1 * np.exp(1j * theta)])
    n = np.tile([0.0, 0.0, 1.0], (nx * ny, 1))
    x = np.arange(nx) * 1e-3
    y = np.arange(ny) * 1e-3
    am = mp.area_matrices_grid(mp.point_matrices_surface(E, H, n).reshape(nx, ny, 2, 2), x, y, area)
    s1 = _grid_average_map(mp.apd_surface(E1[0], H1[0], n), nx, ny, x, y, area).max()
    po = mp.worst_case_phase_only(am, power=1.0)
    assert np.isclose(po.value, 2 * s1)
    assert np.isclose(np.angle(po.excitation[1] / po.excitation[0]), -theta, atol=1e-6)
    assert np.isclose(mp.worst_case_total_power(am, power=1.0).value, 2 * s1)


def test_power_caps_limits_and_feasibility():
    rng = np.random.default_rng(11)
    _, _, _, _, am, _, _ = _grid_setup(rng, N=4)
    P = 10e-3  # 10 mW total, as in Wu et al. (2024) Fig. 5
    tp = mp.worst_case_total_power(am, power=P)
    loose = mp.worst_case_power_caps(am, power=P, port_caps=P)
    assert np.isclose(loose.value, tp.value, rtol=1e-6)
    capped = mp.worst_case_power_caps(am, power=P, port_caps=5e-3, n_starts=8)
    p = np.abs(capped.excitation) ** 2
    assert np.isclose(p.sum(), P) and np.all(p <= 5e-3 * (1 + 1e-9))
    assert capped.value <= tp.value * (1 + 1e-10)
    # dominates random feasible excitations
    A = np.sqrt(P / 4) * np.exp(2j * np.pi * rng.random((3000, 4)))  # equal split is feasible
    assert capped.value >= mp.evaluate_codebook(am, A, return_map=False).value - 1e-15
    # caps = P/N is the phase-only problem
    eq = mp.worst_case_power_caps(am, power=P, port_caps=P / 4, n_starts=8)
    po = mp.worst_case_phase_only(am, power=P, n_starts=8)
    assert np.isclose(eq.value, po.value, rtol=1e-6)
    with pytest.raises(ValueError):
        mp.worst_case_power_caps(am, power=P, port_caps=1e-3)


def test_chunking_invariance():
    rng = np.random.default_rng(12)
    _, _, _, _, am, _, _ = _grid_setup(rng, N=3)
    cb = mp.phase_codebook(3, 4)
    r1 = mp.evaluate_codebook(am, cb, chunk_size=7, beam_chunk=3)
    r2 = mp.evaluate_codebook(am, cb)
    assert np.allclose(r1.per_beam_map, r2.per_beam_map)
    assert np.array_equal(r1.per_beam_area_index, r2.per_beam_area_index)
    assert np.isclose(mp.worst_case_total_power(am, chunk_size=5).value, mp.worst_case_total_power(am).value)


def test_sample_port_fields_from_fake_h5(tmp_path):
    """Reuses GOLIAT's field_reader on a minimal _Output.h5 with the S4L layout."""
    nx, ny, nz = 5, 4, 3
    ax = [np.linspace(0, 4e-3, nx), np.linspace(0, 3e-3, ny), np.linspace(0, 2e-3, nz)]
    rng = np.random.default_rng(13)
    paths, truth = [], []
    for port in range(2):
        p = tmp_path / f"port{port}_Output.h5"
        comps = {}
        with h5py.File(p, "w") as f:
            m = f.create_group("Meshes/m0")
            for d, nm in enumerate("xyz"):
                m["axis_" + nm] = ax[d]
            obj = f.create_group("FieldGroups/0/_Object")
            obj.attrs["name"] = b"Overall Field"
            for ft in ("E", "H"):
                g = f.create_group(f"FieldGroups/0/AllFields/EM {ft}(x,y,z,f0)/_Object/Snapshots/0")
                for c in range(3):
                    shp = [nx - 1, ny - 1, nz - 1]
                    data = rng.standard_normal(shp + [2])
                    g[f"comp{c}"] = data
                    comps[(ft, c)] = data[..., 0] + 1j * data[..., 1]
        paths.append(p)
        truth.append(comps)
    pts = np.array([[0.5e-3, 0.5e-3, 0.5e-3], [3.9e-3, 2.9e-3, 1.9e-3]])
    out = mp.sample_port_fields_at_points(paths, pts)
    assert out["E"].shape == (2, 2, 3)
    assert np.isclose(out["H"][1, 1, 2], truth[1][("H", 2)][3, 2, 1])
    assert np.isclose(out["E"][0, 0, 0], truth[0][("E", 0)][0, 0, 0])


def test_linear_max_caps_matches_brute_force():
    """The per-step subproblem: exact water-filling vs. a fine 2-D grid search."""
    rng = np.random.default_rng(14)
    P = 1.0
    caps = np.array([0.6, 0.3, 0.5])
    g = rng.standard_normal((50, 3)) + 1j * rng.standard_normal((50, 3))
    a = mp._linear_max_caps(g, P, caps)
    p = np.abs(a) ** 2
    assert np.allclose(p.sum(-1), P) and np.all(p <= caps * (1 + 1e-9))
    val = np.real(np.sum(np.conj(a) * g, -1))
    # brute force over feasible amplitude pairs (r0, r1), r2 from the budget
    r0, r1 = np.meshgrid(np.linspace(0, np.sqrt(0.6), 400), np.linspace(0, np.sqrt(0.3), 400))
    r2sq = P - r0**2 - r1**2
    ok = (r2sq >= 0) & (r2sq <= 0.5)
    r2 = np.sqrt(np.clip(r2sq, 0, None))
    for i in range(len(g)):
        m = np.abs(g[i])
        best = np.max(np.where(ok, r0 * m[0] + r1 * m[1] + r2 * m[2], -np.inf))
        assert val[i] >= best - 1e-9
        assert val[i] <= best * (1 + 5e-3)
