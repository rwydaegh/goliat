"""Worst-case (maximized) peak spatial-average APD for multi-port antennas.

Reviewer context: multi-antenna user equipment (MAUE) exposure is assessed
with the *maximized* peak spatial-average absorbed power density (mpsAPD),
i.e. the largest area-averaged APD over all averaging-area positions *and*
all admissible port excitations (Wu, Chen & Li, IEEE AWPL 23(12), 2024,
doi:10.1109/LAWP.2024.3421367).

Theory
------
Let ``E_i(r), H_i(r)`` be the complex fields produced by port ``i`` driven
alone with unit excitation (others terminated in matched loads), and let
``a`` (shape ``(N,)``) be the complex excitation vector. By superposition
``E = sum_i a_i E_i`` and ``H = sum_i a_i H_i``, so every APD definition that
is quadratic in the fields is a Hermitian form ``a^H Q(r) a``:

* Surface (Poynting) definition, ICNIRP/IEC 63195-2 eq. (2) of the paper::

      APD(r) = 1/2 Re[(E x H*) . n]          (n = unit normal INTO the body)
      Q(r)   = (G + G^H) / 4,   G_kl = (E_l x H_k*) . n

  which is the paper's ``T = 1/A int 1/4 [P1 + P2*] ds`` (their eq. 8).

* Volumetric definition, eq. (1) of the paper::

      APD(r) = int_0^zmax sigma |E|^2 / 2 dz  ( = int SAR * rho dz )
      Q_ij(r) = sum_d sigma_d dz_d / 2 * conj(E_i,d) . E_j,d

Area averaging is linear, so the spatial-average APD over area ``A`` centred
at ``c`` is ``a^H Q_A(c) a`` with ``Q_A(c) = (1/|A|) int_A Q(r) dS``. The
worst case is then a per-position quadratic maximisation followed by a max
over positions:

* total power ``||a||^2 = P``: ``P * lambda_max(Q_A)`` (Rayleigh quotient),
  exact; the eigenvector is the worst excitation;
* per-port power caps ``|a_i|^2 <= c_i`` with ``||a||^2 = P`` (the paper's
  SDR constraint set): non-convex QCQP, solved here by a monotone
  generalized power method with multi-start (lower bound) and bounded above
  by the total-power value;
* equal-amplitude phase-only (``|a_i|^2 = P/N``): coordinate ascent on the
  phases (closed-form per coordinate) with multi-start, plus exhaustive
  search over a quantized phase codebook for small ``N``;
* a user codebook: direct evaluation of every beam at every position.

All batch work is vectorised NumPy, chunked over surface points and
averaging-area positions. No Sim4Life dependency.
"""

from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Sequence, Union

import numpy as np

logger = logging.getLogger(__name__)

__all__ = [
    "AreaMatrices",
    "WorstCaseResult",
    "CodebookResult",
    "point_matrices_surface",
    "point_matrices_volumetric",
    "apd_surface",
    "apd_volumetric",
    "surface_from_mesh",
    "sample_port_fields_at_points",
    "area_matrices_grid",
    "area_matrices_surface",
    "spatial_average_apd",
    "worst_case_total_power",
    "worst_case_power_caps",
    "worst_case_phase_only",
    "worst_case_phase_exhaustive",
    "phase_codebook",
    "evaluate_codebook",
]


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class AreaMatrices:
    """Per-averaging-area Hermitian matrices ``Q_A`` (one per candidate area).

    Attributes:
        Q: ``(C, N, N)`` complex Hermitian matrices; ``a^H Q[c] a`` is the
            spatial-average APD of area ``c`` for excitation ``a``.
        centers: ``(C, 3)`` centre coordinates (m). For grids, z = 0.
        coverage: ``(C,)`` covered area / nominal area (1 for grid squares).
        area_m2: Nominal averaging area (m^2).
        shape: ``"grid_square"``, ``"square"`` or ``"disc"``.
        map_shape: Shape to reshape per-area vectors into (grids), else None.
        meta: Free-form extra info (e.g. ``center_index``, ``orientation_rad``).
    """

    Q: np.ndarray
    centers: np.ndarray
    coverage: np.ndarray
    area_m2: float
    shape: str
    map_shape: Optional[tuple] = None
    meta: Dict[str, np.ndarray] = field(default_factory=dict)

    @property
    def n_ports(self) -> int:
        return int(self.Q.shape[-1])

    @property
    def n_areas(self) -> int:
        return int(self.Q.shape[0])


@dataclass
class WorstCaseResult:
    """Worst-case psAPD over area positions and excitations.

    Attributes:
        value: Maximised psAPD (same units as the APD, scaled to ``power``).
        excitation: ``(N,)`` complex excitation achieving ``value``.
        area_index: Index of the worst averaging area.
        center: ``(3,)`` centre of the worst averaging area.
        method: Name of the optimiser.
        per_area: ``(C,)`` per-area maxima (NaN for pruned areas) or None.
        upper_bound: ``P * max lambda_max`` (total-power bound).
        info: Extra diagnostics.
    """

    value: float
    excitation: np.ndarray
    area_index: int
    center: np.ndarray
    method: str
    per_area: Optional[np.ndarray] = None
    upper_bound: Optional[float] = None
    info: dict = field(default_factory=dict)


@dataclass
class CodebookResult:
    """Codebook evaluation result.

    Attributes:
        value: Max over beams and areas.
        beam_index: Index of the worst beam.
        area_index: Index of the worst area.
        excitation: The worst beam's excitation vector.
        per_beam_peak: ``(K,)`` psAPD for each beam (max over areas).
        per_beam_area_index: ``(K,)`` argmax area for each beam.
        per_beam_map: ``(K, C)`` spatial-average APD map, or None.
    """

    value: float
    beam_index: int
    area_index: int
    excitation: np.ndarray
    per_beam_peak: np.ndarray
    per_beam_area_index: np.ndarray
    per_beam_map: Optional[np.ndarray] = None


# ---------------------------------------------------------------------------
# Point-wise Hermitian matrices and plain APD
# ---------------------------------------------------------------------------


def _hermitize(Q: np.ndarray) -> np.ndarray:
    return 0.5 * (Q + np.conj(np.swapaxes(Q, -1, -2)))


def point_matrices_surface(
    E: np.ndarray,
    H: np.ndarray,
    normals: np.ndarray,
    chunk_size: int = 20000,
    dtype=np.complex128,
) -> np.ndarray:
    """Per-point matrices for the surface (Poynting) APD definition.

    Args:
        E, H: ``(N, M, 3)`` per-port complex fields at M surface points.
        normals: ``(M, 3)`` unit normals pointing INTO the body.
        chunk_size: Points processed per chunk.
        dtype: Output dtype.

    Returns:
        ``(M, N, N)`` Hermitian matrices with ``APD = a^H Q a``.
    """
    E = np.asarray(E)
    H = np.asarray(H)
    n = np.asarray(normals, dtype=float)
    if E.shape != H.shape or E.ndim != 3 or E.shape[2] != 3:
        raise ValueError(f"E and H must both be (N, M, 3); got {E.shape}, {H.shape}")
    N, M, _ = E.shape
    out = np.empty((M, N, N), dtype=dtype)
    for s in range(0, M, chunk_size):
        e = slice(s, min(s + chunk_size, M))
        nxE = np.cross(n[None, e, :], E[:, e, :])  # (N, m, 3): n x E_l
        # (E_l x H_k*) . n = H_k* . (n x E_l)
        G = np.einsum("kmc,lmc->mkl", np.conj(H[:, e, :]), nxE, optimize=True)
        out[e] = 0.25 * (G + np.conj(np.swapaxes(G, -1, -2)))
    return out


def point_matrices_volumetric(
    E_columns: np.ndarray,
    sigma: np.ndarray,
    dz: Union[float, np.ndarray],
    chunk_size: int = 5000,
    dtype=np.complex128,
) -> np.ndarray:
    """Per-point matrices for the volumetric APD definition (int sigma|E|^2/2 dz).

    Each surface point owns a column of D depth samples along the inward
    normal (or a voxel column for planar phantoms). Samples outside tissue or
    beyond ``zmax`` should carry ``sigma = 0``.

    Args:
        E_columns: ``(N, M, D, 3)`` per-port E-fields along each column.
        sigma: ``(M, D)`` conductivity (S/m).
        dz: Depth step(s): scalar or ``(M, D)`` (m).

    Returns:
        ``(M, N, N)`` Hermitian PSD matrices.
    """
    E = np.asarray(E_columns)
    if E.ndim != 4 or E.shape[3] != 3:
        raise ValueError(f"E_columns must be (N, M, D, 3); got {E.shape}")
    N, M, D, _ = E.shape
    w = 0.5 * np.asarray(sigma, dtype=float) * np.broadcast_to(np.asarray(dz, dtype=float), (M, D))
    if np.any(w < 0):
        raise ValueError("sigma*dz must be non-negative")
    sw = np.sqrt(w)
    out = np.empty((M, N, N), dtype=dtype)
    for s in range(0, M, chunk_size):
        e = slice(s, min(s + chunk_size, M))
        Es = E[:, e] * sw[None, e, :, None]
        out[e] = np.einsum("imdc,jmdc->mij", np.conj(Es), Es, optimize=True)
    return out


def apd_surface(E: np.ndarray, H: np.ndarray, normals: np.ndarray) -> np.ndarray:
    """Plain APD map ``1/2 Re[(E x H*) . n]`` for a single combined field (M, 3)."""
    return 0.5 * np.real(np.sum(np.cross(E, np.conj(H)) * normals, axis=-1))


def apd_volumetric(E_columns: np.ndarray, sigma: np.ndarray, dz) -> np.ndarray:
    """Plain volumetric APD ``sum sigma |E|^2 / 2 dz`` for one field (M, D, 3)."""
    M, D = np.shape(sigma)
    return np.sum(0.5 * sigma * np.broadcast_to(dz, (M, D)) * np.sum(np.abs(E_columns) ** 2, axis=-1), axis=-1)


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def surface_from_mesh(
    vertices: np.ndarray,
    faces: np.ndarray,
    interior_point: Optional[Sequence[float]] = None,
    flip: bool = False,
):
    """Vertex normals and vertex areas for a triangle mesh (e.g. ``skin_apd.npz``).

    Vertex area = 1/3 of the adjacent triangle areas; vertex normal = area-
    weighted average of face normals. Normals follow the face winding; pass
    ``interior_point`` (e.g. head centre) to orient each normal towards it
    (inward), or ``flip=True`` to invert globally.

    Returns:
        ``(points (V,3), normals (V,3), areas (V,))``.
    """
    v = np.asarray(vertices, dtype=float)
    f = np.asarray(faces, dtype=np.int64)
    cr = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])  # 2*area*normal
    tri_area = 0.5 * np.linalg.norm(cr, axis=1)
    normals = np.zeros_like(v)
    areas = np.zeros(len(v))
    for k in range(3):
        np.add.at(normals, f[:, k], cr)
        np.add.at(areas, f[:, k], tri_area / 3.0)
    nn = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = np.divide(normals, nn, out=np.zeros_like(normals), where=nn > 0)
    if flip:
        normals = -normals
    if interior_point is not None:
        to_in = np.asarray(interior_point, dtype=float)[None, :] - v
        sign = np.where(np.sum(to_in * normals, axis=1) < 0, -1.0, 1.0)
        normals = normals * sign[:, None]
    return v, normals, areas


def _read_mesh_axes(h5_path: Union[str, Path]):
    import h5py

    with h5py.File(h5_path, "r") as f:
        for key in f["Meshes"].keys():
            mesh = f[f"Meshes/{key}"]
            if "axis_x" in mesh:
                return mesh["axis_x"][:], mesh["axis_y"][:], mesh["axis_z"][:]
    raise ValueError(f"No mesh with axes found in {h5_path}")


def sample_port_fields_at_points(
    h5_paths: Sequence[Union[str, Path]],
    points_m: np.ndarray,
    field_types: Sequence[str] = ("E", "H"),
) -> Dict[str, np.ndarray]:
    """Sample per-port fields from Sim4Life ``_Output.h5`` files at points.

    Maps each point to the voxel (cell) that contains it using the mesh node
    axes and reuses :func:`goliat.extraction.field_reader.read_field_at_indices`
    (voxel-centre approximation of the Yee components). This is a
    nearest-voxel sample: for surface APD prefer evaluating on points just
    inside the skin, and note that normal E is discontinuous at interfaces.

    Returns:
        ``{"E": (N, M, 3), "H": (N, M, 3)}`` complex128 arrays.
    """
    from goliat.extraction.field_reader import read_field_at_indices

    pts = np.asarray(points_m, dtype=float)
    ax = _read_mesh_axes(h5_paths[0])
    idx = np.empty((len(pts), 3), dtype=np.int64)
    for d in range(3):
        a = ax[d]
        idx[:, d] = np.clip(np.searchsorted(a, pts[:, d], side="right") - 1, 0, max(len(a) - 2, 0))
    out = {}
    for ft in field_types:
        out[ft] = np.stack([read_field_at_indices(p, idx, field_type=ft).astype(np.complex128) for p in h5_paths])
    return out


# ---------------------------------------------------------------------------
# Area averaging
# ---------------------------------------------------------------------------


def _box_kernel(half_width_cells: float) -> np.ndarray:
    """Overlap of cells [k-1/2, k+1/2] with [-h, h]; sums to 2h."""
    h = half_width_cells
    K = int(np.ceil(h - 0.5 - 1e-9))
    k = np.arange(-K, K + 1)
    return np.clip(np.minimum(k + 0.5, h) - np.maximum(k - 0.5, -h), 0.0, None)


def area_matrices_grid(
    Q_grid: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    area_m2: float = 4e-4,
) -> AreaMatrices:
    """Square-area averages on a planar, uniform 2-D grid (separable box filter).

    Each sample represents a ``dx x dy`` cell. The square of side
    ``L = sqrt(area_m2)`` is axis-aligned and centred on a sample; partially
    covered edge cells get fractional weights, so the average is exact for
    piecewise-constant data. Only centres whose square lies entirely inside
    the grid are kept ("valid" mode).

    Args:
        Q_grid: ``(nx, ny, N, N)`` point matrices on the grid.
        x, y: Uniform sample coordinates (m).
        area_m2: Averaging area (4e-4 = 4 cm^2, 1e-4 = 1 cm^2).
    """
    Q_grid = np.asarray(Q_grid)
    nx, ny, N, _ = Q_grid.shape
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    dx = float(np.mean(np.diff(x)))
    dy = float(np.mean(np.diff(y)))
    if not (np.allclose(np.diff(x), dx, rtol=1e-6) and np.allclose(np.diff(y), dy, rtol=1e-6)):
        raise ValueError("area_matrices_grid requires a uniform grid; use area_matrices_surface otherwise")
    L = float(np.sqrt(area_m2))
    kx = _box_kernel(L / (2 * dx)) * dx
    ky = _box_kernel(L / (2 * dy)) * dy
    Kx, Ky = len(kx) // 2, len(ky) // 2
    cx, cy = nx - 2 * Kx, ny - 2 * Ky
    if cx <= 0 or cy <= 0:
        raise ValueError(f"Grid ({nx}x{ny}) too small for a {area_m2 * 1e4:g} cm^2 square")
    tmp = np.zeros((cx, ny, N, N), dtype=Q_grid.dtype)
    for t, w in enumerate(kx):
        tmp += w * Q_grid[t : t + cx]
    Q = np.zeros((cx, cy, N, N), dtype=Q_grid.dtype)
    for t, w in enumerate(ky):
        Q += w * tmp[:, t : t + cy]
    Q /= kx.sum() * ky.sum()  # == L^2 when the square fits the cells
    X, Y = np.meshgrid(x[Kx : Kx + cx], y[Ky : Ky + cy], indexing="ij")
    centers = np.stack([X.ravel(), Y.ravel(), np.zeros(X.size)], axis=1)
    ix, iy = np.meshgrid(np.arange(Kx, Kx + cx), np.arange(Ky, Ky + cy), indexing="ij")
    return AreaMatrices(
        Q=_hermitize(Q.reshape(cx * cy, N, N)),
        centers=centers,
        coverage=np.ones(cx * cy),
        area_m2=area_m2,
        shape="grid_square",
        map_shape=(cx, cy),
        meta={"grid_index": np.stack([ix.ravel(), iy.ravel()], axis=1)},
    )


def _tangent_frame(n: np.ndarray, ref: np.ndarray):
    t1 = ref[None, :] - np.sum(ref[None, :] * n, axis=1, keepdims=True) * n
    bad = np.linalg.norm(t1, axis=1) < 1e-6
    if np.any(bad):
        alt = np.array([1.0, 0.0, 0.0]) if abs(ref[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        t1[bad] = alt - np.sum(alt * n[bad], axis=1, keepdims=True) * n[bad]
    t1 /= np.linalg.norm(t1, axis=1, keepdims=True)
    t2 = np.cross(n, t1)
    return t1, t2


def area_matrices_surface(
    Q_points: np.ndarray,
    points: np.ndarray,
    normals: np.ndarray,
    areas: np.ndarray,
    area_m2: float = 4e-4,
    shape: str = "square",
    center_indices: Optional[np.ndarray] = None,
    n_orientations: int = 1,
    ref_dir: Sequence[float] = (0.0, 0.0, 1.0),
    depth_tol: Optional[float] = None,
    min_normal_cos: float = 0.0,
    min_coverage: float = 0.9,
    normalize: str = "region",
    chunk_size: int = 2000,
) -> AreaMatrices:
    """Area averages on an arbitrary (curved) sampled surface.

    Region membership for a centre ``c`` with normal ``n_c`` (Euclidean, no
    geodesics):

    * ``"disc"``: ``|r - c| <= R``, ``R = sqrt(A/pi)``;
    * ``"square"``: projection onto the tangent plane at ``c`` satisfies
      ``|u|, |v| <= L/2`` (``L = sqrt(A)``) and ``|w| <= depth_tol``
      (default ``L/2``). The in-plane axes come from ``ref_dir`` projected on
      the tangent plane, rotated by ``k*pi/(2*n_orientations)``; every
      orientation is a separate candidate area.

    Both also require ``n . n_c >= min_normal_cos`` (rejects the far side of
    thin structures such as the pinna). The average is
    ``sum_m w_m Q_m / norm`` with ``w`` the point areas and ``norm`` either the
    covered area (``"region"``, a true mean) or ``area_m2`` (``"nominal"``).
    Areas whose covered area is below ``min_coverage * A`` (mesh borders) are
    dropped.

    Args:
        Q_points: ``(M, N, N)`` point matrices.
        points, normals, areas: ``(M, 3)``, ``(M, 3)`` inward unit, ``(M,)`` m^2.
        center_indices: Subset of points used as centres (default: all).
    """
    from scipy.sparse import csr_matrix
    from scipy.spatial import cKDTree

    if shape not in ("square", "disc"):
        raise ValueError("shape must be 'square' or 'disc'")
    if normalize not in ("region", "nominal"):
        raise ValueError("normalize must be 'region' or 'nominal'")
    Q_points = np.asarray(Q_points)
    M, N, _ = Q_points.shape
    pts = np.asarray(points, dtype=float)
    nrm = np.asarray(normals, dtype=float)
    w_all = np.asarray(areas, dtype=float)
    cidx = np.arange(M) if center_indices is None else np.asarray(center_indices, dtype=np.int64)
    L = float(np.sqrt(area_m2))
    depth = 0.0
    if shape == "disc":
        n_orientations = 1
        r_search = np.sqrt(area_m2 / np.pi)
    else:
        depth = 0.5 * L if depth_tol is None else float(depth_tol)
        r_search = float(np.sqrt(0.5 * L**2 + depth**2))
    tree = cKDTree(pts)
    Qflat = Q_points.reshape(M, N * N)
    ref = np.asarray(ref_dir, dtype=float)
    angles = np.arange(n_orientations) * (0.5 * np.pi / n_orientations)

    Q_out, cen_out, cov_out, ci_out, ang_out = [], [], [], [], []
    for s in range(0, len(cidx), chunk_size):
        cc = cidx[s : s + chunk_size]
        c_pts, c_n = pts[cc], nrm[cc]
        t1, t2 = _tangent_frame(c_n, ref)
        neigh = tree.query_ball_point(c_pts, r_search + 1e-12)
        for ang in angles:
            ua = np.cos(ang) * t1 + np.sin(ang) * t2
            va = -np.sin(ang) * t1 + np.cos(ang) * t2
            rows, cols, vals = [], [], []
            for j, nb in enumerate(neigh):
                nb = np.asarray(nb, dtype=np.int64)
                d = pts[nb] - c_pts[j]
                keep = (nrm[nb] @ c_n[j]) >= min_normal_cos
                if shape == "disc":
                    keep &= np.einsum("ij,ij->i", d, d) <= r_search**2 * (1 + 1e-12)
                else:
                    eps = 1e-9 * L
                    keep &= np.abs(d @ ua[j]) <= 0.5 * L + eps
                    keep &= np.abs(d @ va[j]) <= 0.5 * L + eps
                    keep &= np.abs(d @ c_n[j]) <= depth + eps
                nb = nb[keep]
                rows.append(np.full(len(nb), j))
                cols.append(nb)
                vals.append(w_all[nb])
            rows_a = np.concatenate(rows) if rows else np.zeros(0, int)
            W = csr_matrix((np.concatenate(vals), (rows_a, np.concatenate(cols))), shape=(len(cc), M))
            covered = np.asarray(W.sum(axis=1)).ravel()
            ok = covered >= min_coverage * area_m2
            if not np.any(ok):
                continue
            norm = covered[ok] if normalize == "region" else np.full(ok.sum(), area_m2)
            Qc = (W[ok] @ Qflat) / norm[:, None]
            Q_out.append(np.asarray(Qc).reshape(-1, N, N))
            cen_out.append(c_pts[ok])
            cov_out.append(covered[ok] / area_m2)
            ci_out.append(cc[ok])
            ang_out.append(np.full(ok.sum(), ang))
    if not Q_out:
        raise ValueError("No averaging area met min_coverage; check units (m, m^2) and normals")
    return AreaMatrices(
        Q=_hermitize(np.concatenate(Q_out)),
        centers=np.concatenate(cen_out),
        coverage=np.concatenate(cov_out),
        area_m2=area_m2,
        shape=shape,
        meta={"center_index": np.concatenate(ci_out), "orientation_rad": np.concatenate(ang_out)},
    )


# ---------------------------------------------------------------------------
# Evaluation and optimisation
# ---------------------------------------------------------------------------


def _quad(Q: np.ndarray, A: np.ndarray) -> np.ndarray:
    """``(K, C)`` values of ``a_k^H Q_c a_k`` for ``Q (C,N,N)``, ``A (K,N)``."""
    T = Q @ A.T  # (C, N, K)
    return np.real(np.einsum("nk,cnk->kc", np.conj(A.T), T, optimize=True))


def spatial_average_apd(am: AreaMatrices, excitation: np.ndarray, chunk_size: int = 100000) -> np.ndarray:
    """Spatial-average APD ``a^H Q_A a`` at every area for one excitation."""
    a = np.asarray(excitation, dtype=complex).reshape(1, -1)
    out = np.empty(am.n_areas)
    for s in range(0, am.n_areas, chunk_size):
        out[s : s + chunk_size] = _quad(am.Q[s : s + chunk_size], a)[0]
    return out


def _canonical_phase(a: np.ndarray) -> np.ndarray:
    """Remove the irrelevant global phase: largest |a_i| made real-positive."""
    a = np.asarray(a, dtype=complex)
    k = int(np.argmax(np.abs(a)))
    return a * np.exp(-1j * np.angle(a[k])) if abs(a[k]) > 0 else a


def _max_eig(am: AreaMatrices, chunk_size: int):
    lam = np.empty(am.n_areas)
    for s in range(0, am.n_areas, chunk_size):
        lam[s : s + chunk_size] = np.linalg.eigvalsh(am.Q[s : s + chunk_size])[:, -1]
    return lam


def _result(am, value, a, c, method, per_area, ub, **info) -> WorstCaseResult:
    return WorstCaseResult(
        value=float(value),
        excitation=_canonical_phase(a),
        area_index=int(c),
        center=am.centers[c],
        method=method,
        per_area=per_area,
        upper_bound=ub,
        info=info,
    )


def worst_case_total_power(am: AreaMatrices, power: float = 1.0, chunk_size: int = 20000) -> WorstCaseResult:
    """Exact mpsAPD under ``||a||^2 = power``: ``power * max_c lambda_max(Q_A[c])``."""
    lam = _max_eig(am, chunk_size)
    c = int(np.argmax(lam))
    _, V = np.linalg.eigh(am.Q[c])
    a = np.sqrt(power) * V[:, -1]
    return _result(am, power * lam[c], a, c, "total_power_eig", power * lam, float(power * lam[c]))


def _linear_max_caps(g: np.ndarray, power: float, caps: np.ndarray) -> np.ndarray:
    """argmax Re(a^H g) s.t. sum|a|^2 = power, |a_i|^2 <= caps_i (batched over rows).

    Exact KKT solution: phases align with ``g``; amplitudes
    ``r_i = min(t |g_i|, sqrt(c_i))`` with ``t`` such that ``sum r_i^2 = power``.
    ``t`` is found in closed form by sorting the cap ratios ``sqrt(c_i)/|g_i|``
    (water-filling), fully vectorised.
    """
    mag = np.abs(g)
    N = mag.shape[-1]
    caps_b = np.broadcast_to(caps, mag.shape)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(mag > 0, np.sqrt(caps_b) / np.where(mag > 0, mag, 1.0), np.inf)
    order = np.argsort(ratio, axis=-1)
    rs = np.take_along_axis(ratio, order, -1)
    cs = np.take_along_axis(caps_b, order, -1)
    m2 = np.take_along_axis(mag, order, -1) ** 2
    zeros = np.zeros(mag.shape[:-1] + (1,))
    cap_pref = np.concatenate([zeros, np.cumsum(cs, -1)], -1)[..., :N]  # sum caps of first k (capped)
    m2_rem = np.sum(m2, -1, keepdims=True) - np.concatenate([zeros, np.cumsum(m2, -1)], -1)[..., :N]
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.sqrt(np.maximum(power - cap_pref, 0.0) / m2_rem)  # candidate t with k capped entries
    lower = np.concatenate([zeros, rs[..., :-1]], -1)
    valid = (m2_rem > 0) & (t <= rs * (1 + 1e-12)) & (t >= lower * (1 - 1e-12))
    k = np.argmax(valid, axis=-1)
    has = np.any(valid, axis=-1)
    t_sel = np.where(has, np.take_along_axis(t, k[..., None], -1)[..., 0], np.inf)
    with np.errstate(invalid="ignore"):
        r = np.where(mag > 0, np.minimum(t_sel[..., None] * mag, np.sqrt(caps_b)), 0.0)
    # If every port with g_i != 0 is capped, give the deficit to the g_i == 0
    # ports in proportion to their caps (does not change Re(a^H g)).
    deficit = np.maximum(power - np.sum(r**2, axis=-1, keepdims=True), 0.0)
    zero = mag == 0
    zcap = np.sum(np.where(zero, caps_b, 0.0), axis=-1, keepdims=True)
    fill = np.where(zero, np.sqrt(caps_b * np.minimum(deficit / np.maximum(zcap, 1e-300), 1.0)), 0.0)
    return (r + fill) * np.exp(1j * np.angle(g))


def _optimize_chunk(Q, power, caps, n_starts, rng, max_iter, tol, init, mode):
    """Monotone ascent for a chunk of areas. Returns (best_val (C,), best_a (C,N))."""
    C, N, _ = Q.shape
    amp = np.sqrt(power / N)
    # starts: eigenvector, user inits, random
    _, V = np.linalg.eigh(Q)
    starts = [V[:, :, -1] * np.sqrt(power)]
    if init is not None:
        for a0 in init:
            starts.append(np.broadcast_to(a0, (C, N)))
    for _ in range(max(n_starts - len(starts), 0)):
        if mode == "phase":
            starts.append(np.exp(2j * np.pi * rng.random((C, N))))
        else:
            z = rng.standard_normal((C, N)) + 1j * rng.standard_normal((C, N))
            starts.append(z)
    a = np.stack(starts, axis=1)  # (C, S, N)
    if mode == "phase":
        ph = np.angle(a)
        ph[np.abs(a) == 0] = 0.0
        a = amp * np.exp(1j * ph)
    else:
        a = _linear_max_caps(a, power, caps)
    f = np.real(np.einsum("csn,cnm,csm->cs", np.conj(a), Q, a, optimize=True))
    Qs = Q
    it = -1
    if mode == "caps":
        # shift so the surrogate is convex (objective unchanged on ||a||^2 = P)
        lam_min = np.linalg.eigvalsh(Q)[:, 0]
        Qs = Q - np.minimum(lam_min, 0.0)[:, None, None] * np.eye(N)[None]
    for it in range(max_iter):
        if mode == "phase":
            for k in range(N):
                s_k = np.einsum("cj,csj->cs", Q[:, k, :], a) - Q[:, k, k][:, None] * a[:, :, k]
                nz = np.abs(s_k) > 0
                a[:, :, k] = np.where(nz, amp * np.exp(1j * np.angle(s_k)), a[:, :, k])
        else:
            g = np.einsum("cnm,csm->csn", Qs, a)
            a = _linear_max_caps(g, power, caps)
        f_new = np.real(np.einsum("csn,cnm,csm->cs", np.conj(a), Q, a, optimize=True))
        gain = np.max(f_new - f)
        f = f_new
        if gain <= tol * max(np.max(np.abs(f)), 1e-300):
            break
    best = np.argmax(f, axis=1)
    return f[np.arange(C), best], a[np.arange(C), best], it + 1


def _search(am, power, caps, n_starts, seed, max_iter, tol, init, prune, return_map, chunk_size, mode, method):
    rng = np.random.default_rng(seed)
    lam = _max_eig(am, chunk_size)
    ub = power * lam
    order = np.argsort(-ub) if prune and not return_map else np.arange(am.n_areas)
    per_area = np.full(am.n_areas, np.nan)
    best_v, best_a, best_c = -np.inf, None, -1
    n_eval = 0
    for s in range(0, am.n_areas, chunk_size):
        idx = order[s : s + chunk_size]
        if prune and not return_map:
            idx = idx[ub[idx] > best_v]
            if len(idx) == 0:
                break
        v, a, _ = _optimize_chunk(am.Q[idx], power, caps, n_starts, rng, max_iter, tol, init, mode)
        per_area[idx] = v
        n_eval += len(idx)
        j = int(np.argmax(v))
        if v[j] > best_v:
            best_v, best_a, best_c = float(v[j]), a[j], int(idx[j])
    return _result(am, best_v, best_a, best_c, method, per_area, float(ub.max()), n_areas_optimized=n_eval)


def worst_case_phase_only(
    am: AreaMatrices,
    power: float = 1.0,
    n_starts: int = 8,
    seed: int = 0,
    max_iter: int = 200,
    tol: float = 1e-12,
    init_excitations: Optional[np.ndarray] = None,
    prune: bool = True,
    return_map: bool = False,
    chunk_size: int = 2000,
) -> WorstCaseResult:
    """mpsAPD for equal-amplitude, phase-only steering (``|a_i|^2 = power/N``).

    Per area: coordinate ascent on the phases. With the others fixed,
    ``f(phi_k) = const + 2 Re(conj(a_k) s_k)``, ``s_k = sum_{j!=k} Q_kj a_j``,
    maximised by ``arg a_k = arg s_k`` -- monotone, converges to a local
    optimum. Starts: phases of the dominant eigenvector, ``init_excitations``
    (e.g. a codebook -- guarantees the result >= every codebook entry), and
    random phases. Areas are visited in decreasing order of the exact
    total-power upper bound and skipped once that bound cannot beat the best
    value found (``prune``; exact, disabled when ``return_map``).
    """
    init = None if init_excitations is None else np.atleast_2d(np.asarray(init_excitations, dtype=complex))
    return _search(
        am, power, None, n_starts, seed, max_iter, tol, init, prune, return_map, chunk_size, "phase", "phase_only_coordinate_ascent"
    )


def worst_case_power_caps(
    am: AreaMatrices,
    power: float = 1.0,
    port_caps: Optional[Union[float, Sequence[float]]] = None,
    n_starts: int = 8,
    seed: int = 0,
    max_iter: int = 500,
    tol: float = 1e-12,
    init_excitations: Optional[np.ndarray] = None,
    prune: bool = True,
    return_map: bool = False,
    chunk_size: int = 2000,
) -> WorstCaseResult:
    """mpsAPD with ``||a||^2 = power`` and per-port caps ``|a_i|^2 <= port_caps_i``.

    This is the constraint set of Wu et al. (2024), eq. (7), which they relax
    to an SDP. Here: generalized power method on ``Q - min(lambda_min, 0) I``
    (convex surrogate, same objective on the sphere): each step solves the
    linearised problem exactly (phase alignment + capped water-filling), so
    the objective is non-decreasing. Result is a feasible lower bound;
    ``upper_bound`` (total power) is an upper bound. With caps >= power it is
    the eigen solution; with caps = power/N it is the phase-only problem.
    """
    if port_caps is None:
        raise ValueError("port_caps is required")
    caps = np.broadcast_to(np.asarray(port_caps, dtype=float), (am.n_ports,)).copy()
    if caps.sum() < power * (1 - 1e-12):
        raise ValueError("Infeasible: sum(port_caps) < power")
    init = None if init_excitations is None else np.atleast_2d(np.asarray(init_excitations, dtype=complex))
    return _search(am, power, caps, n_starts, seed, max_iter, tol, init, prune, return_map, chunk_size, "caps", "power_caps_gpm")


def phase_codebook(n_ports: int, n_levels: int = 4, power: float = 1.0) -> np.ndarray:
    """All equal-amplitude excitations with phases ``2 pi k / n_levels``.

    Port 0 is fixed at phase 0 (global phase is irrelevant), giving
    ``n_levels**(n_ports-1)`` beams of total power ``power``.
    """
    lv = np.exp(2j * np.pi * np.arange(n_levels) / n_levels)
    combos = np.array(list(itertools.product(range(n_levels), repeat=n_ports - 1)), dtype=int).reshape(-1, n_ports - 1)
    A = np.ones((len(combos), n_ports), dtype=complex)
    A[:, 1:] = lv[combos]
    return A * np.sqrt(power / n_ports)


def evaluate_codebook(
    am: AreaMatrices,
    codebook: np.ndarray,
    return_map: bool = True,
    chunk_size: int = 20000,
    beam_chunk: int = 4096,
) -> CodebookResult:
    """Evaluate a beam codebook ``(K, N)`` (used as given, no renormalisation).

    Returns the max over beams and areas, each beam's psAPD and, optionally,
    the full ``(K, C)`` spatial-average APD map.
    """
    A = np.atleast_2d(np.asarray(codebook, dtype=complex))
    K = len(A)
    if A.shape[1] != am.n_ports:
        raise ValueError(f"codebook has {A.shape[1]} ports, matrices have {am.n_ports}")
    peak = np.full(K, -np.inf)
    arg = np.zeros(K, dtype=np.int64)
    full = np.empty((K, am.n_areas)) if return_map else None
    for s in range(0, am.n_areas, chunk_size):
        Qc = am.Q[s : s + chunk_size]
        for b in range(0, K, beam_chunk):
            vals = _quad(Qc, A[b : b + beam_chunk])  # (k, c)
            if full is not None:
                full[b : b + beam_chunk, s : s + chunk_size] = vals
            j = np.argmax(vals, axis=1)
            v = vals[np.arange(len(j)), j]
            better = v > peak[b : b + beam_chunk]
            peak[b : b + beam_chunk] = np.where(better, v, peak[b : b + beam_chunk])
            arg[b : b + beam_chunk] = np.where(better, j + s, arg[b : b + beam_chunk])
    k = int(np.argmax(peak))
    return CodebookResult(
        value=float(peak[k]),
        beam_index=k,
        area_index=int(arg[k]),
        excitation=A[k],
        per_beam_peak=peak,
        per_beam_area_index=arg,
        per_beam_map=full,
    )


def worst_case_phase_exhaustive(
    am: AreaMatrices,
    power: float = 1.0,
    n_levels: int = 4,
    max_beams: int = 2_000_000,
    chunk_size: int = 20000,
) -> WorstCaseResult:
    """Exhaustive search over the quantized phase codebook (:func:`phase_codebook`)."""
    nb = n_levels ** (am.n_ports - 1)
    if nb > max_beams:
        raise ValueError(f"{nb} beams exceeds max_beams={max_beams}; use worst_case_phase_only")
    A = phase_codebook(am.n_ports, n_levels, power)
    cb = evaluate_codebook(am, A, return_map=False, chunk_size=chunk_size)
    return _result(am, cb.value, cb.excitation, cb.area_index, f"phase_exhaustive_{n_levels}lvl", None, None, n_beams=nb)
