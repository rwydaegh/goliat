"""Link GOLIAT/Sim4Life field results to high-frequency (mmWave) measurements.

This module is the physics-based interface between a simulated field map and a
measured (or reconstructed, e.g. super-resolved) field map on a plane in front
of a device, following the incident-power-density (IPD) assessment chain of
IEC/IEEE 63195-1 (measurement) and IEC/IEEE 63195-2 (computation):

1. :class:`PlanarField` holds complex E (and optionally H) samples on a uniform
   ``x``-``y`` grid at a fixed plane ``z``; loaders/writers exist for a small,
   documented CSV/NPZ/HDF5 layout and for the Sim4Life ``_Output.h5`` file.
2. Plane-wave spectrum (PWS, angular spectrum, "plane-wave integral
   representation") propagation: from the tangential E-field on one plane the
   full E and H are obtained on any parallel plane (:func:`propagate`,
   :func:`reconstruct_fields`, :func:`spectral_upsample`).
3. Poynting vector and spatially averaged power density, ``sPDn`` and
   ``sPDtot`` over a square averaging area, with peak search
   (:func:`spatial_average_pd`).
4. Comparison metrics between measured and simulated maps: translation
   registration, magnitude/phase errors, the MRE of Yi et al. (2026), psPD
   error, and a least-squares calibration factor (:func:`compare_fields`).

Conventions
-----------
* SI units throughout (metres, Hz, V/m, A/m, W/m^2).
* Arrays are indexed ``[ix, iy, component]`` (x first, like Sim4Life).
* Complex amplitudes are **peak** phasors by default (Sim4Life convention), so
  ``S = 0.5 Re(E x H*)``. Set ``amplitude="rms"`` for RMS phasors
  (``S = Re(E x H*)``).
* Time convention ``exp(+j w t)`` by default (a wave travelling towards +z is
  ``exp(-j kz z)``). Data in the physics convention ``exp(-i w t)`` must be
  flagged with ``time_convention="-jwt"``; it is handled by conjugation.
* The measurement plane normal is +z, and "forward" propagation is towards
  larger z (away from the source). Sources must lie at ``z < plane``.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)

C0 = 299_792_458.0
MU0 = 4e-7 * np.pi
EPS0 = 1.0 / (MU0 * C0**2)
ETA0 = MU0 * C0

PathLike = Union[str, Path]

_COMPONENTS = ("x", "y", "z")
_LENGTH_SCALE = {"m": 1.0, "mm": 1e-3, "cm": 1e-2, "um": 1e-6}


# ---------------------------------------------------------------------------
# Data container
# ---------------------------------------------------------------------------


@dataclass
class PlanarField:
    """Complex E (and optionally H) samples on a planar rectangular grid.

    Attributes:
        x: Sample x coordinates in m, shape ``(Nx,)``, strictly increasing.
        y: Sample y coordinates in m, shape ``(Ny,)``, strictly increasing.
        z: Plane position in m.
        frequency_hz: Frequency in Hz.
        E: Complex E-field, shape ``(Nx, Ny, 3)``. A missing Ez (e.g. a probe
            that only measures tangential components) is stored as NaN and is
            reconstructed by :func:`reconstruct_fields`.
        H: Optional complex H-field, shape ``(Nx, Ny, 3)``.
        amplitude: ``"peak"`` or ``"rms"`` phasor amplitude.
        time_convention: ``"+jwt"`` (engineering) or ``"-jwt"`` (physics).
        phase_valid: False for magnitude-only maps (e.g. amplitude-only probes
            or image-based super-resolution that outputs ``|E|``). PWS
            propagation then refuses to run and PD falls back to the
            plane-wave estimate.
        metadata: Free-form provenance (source file, instrument, ...).
    """

    x: np.ndarray
    y: np.ndarray
    z: float
    frequency_hz: float
    E: np.ndarray
    H: Optional[np.ndarray] = None
    amplitude: str = "peak"
    time_convention: str = "+jwt"
    phase_valid: bool = True
    metadata: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self):
        self.x = np.asarray(self.x, dtype=float).ravel()
        self.y = np.asarray(self.y, dtype=float).ravel()
        self.z = float(self.z)
        self.frequency_hz = float(self.frequency_hz)
        self.E = _as_vector_field(self.E, self.x.size, self.y.size, "E")
        if self.H is not None:
            self.H = _as_vector_field(self.H, self.x.size, self.y.size, "H")
        if self.amplitude not in ("peak", "rms"):
            raise ValueError("amplitude must be 'peak' or 'rms'")
        if self.time_convention not in ("+jwt", "-jwt"):
            raise ValueError("time_convention must be '+jwt' or '-jwt'")
        for name, ax in (("x", self.x), ("y", self.y)):
            if ax.size > 1 and np.any(np.diff(ax) <= 0):
                raise ValueError(f"{name} coordinates must be strictly increasing")
        if self.frequency_hz <= 0:
            raise ValueError("frequency_hz must be positive")

    # -- basic properties -------------------------------------------------
    @property
    def shape(self) -> Tuple[int, int]:
        return (self.x.size, self.y.size)

    @property
    def dx(self) -> float:
        return _uniform_step(self.x, "x")

    @property
    def dy(self) -> float:
        return _uniform_step(self.y, "y")

    @property
    def wavelength(self) -> float:
        return C0 / self.frequency_hz

    @property
    def k0(self) -> float:
        return 2.0 * np.pi / self.wavelength

    @property
    def has_ez(self) -> bool:
        return bool(np.all(np.isfinite(self.E[..., 2])))

    def e_magnitude(self, tangential_only: bool = False) -> np.ndarray:
        """Return ``|E|`` (or ``|E_t|``) per sample, ignoring a missing Ez."""
        comps = self.E[..., :2] if tangential_only or not self.has_ez else self.E
        return np.sqrt(np.sum(np.abs(comps) ** 2, axis=-1))

    def to_rms(self) -> "PlanarField":
        if self.amplitude == "rms":
            return self
        s = 1.0 / np.sqrt(2.0)
        return replace(self, E=self.E * s, H=None if self.H is None else self.H * s, amplitude="rms")

    def to_peak(self) -> "PlanarField":
        if self.amplitude == "peak":
            return self
        s = np.sqrt(2.0)
        return replace(self, E=self.E * s, H=None if self.H is None else self.H * s, amplitude="peak")

    def scaled(self, factor: complex) -> "PlanarField":
        """Return a copy with E and H multiplied by a (complex) factor."""
        return replace(self, E=self.E * factor, H=None if self.H is None else self.H * factor)

    def shifted(self, dx: float, dy: float) -> "PlanarField":
        """Return a copy translated by ``(dx, dy)`` (coordinates move, data stays)."""
        return replace(self, x=self.x + dx, y=self.y + dy)

    def crop(self, xlim: Tuple[float, float], ylim: Tuple[float, float]) -> "PlanarField":
        ix = (self.x >= xlim[0]) & (self.x <= xlim[1])
        iy = (self.y >= ylim[0]) & (self.y <= ylim[1])
        return replace(
            self,
            x=self.x[ix],
            y=self.y[iy],
            E=self.E[ix][:, iy],
            H=None if self.H is None else self.H[ix][:, iy],
        )

    def resample(self, x: np.ndarray, y: np.ndarray, method: str = "linear", fill_value: complex = np.nan) -> "PlanarField":
        """Interpolate E (and H) onto a new rectilinear grid.

        Real and imaginary parts are interpolated separately with
        :class:`scipy.interpolate.RegularGridInterpolator`. Points outside the
        original extent receive ``fill_value`` (NaN by default, so overlap masks
        can be derived). For band-limited (exact) upsampling of a uniformly
        sampled, phase-valid map prefer :func:`spectral_upsample`.
        """
        x = np.asarray(x, dtype=float).ravel()
        y = np.asarray(y, dtype=float).ravel()
        E = _interp_vector(self.x, self.y, self.E, x, y, method, fill_value)
        H = None if self.H is None else _interp_vector(self.x, self.y, self.H, x, y, method, fill_value)
        return replace(self, x=x, y=y, E=E, H=H)


def _as_vector_field(a, nx: int, ny: int, name: str) -> np.ndarray:
    a = np.asarray(a)
    if a.ndim == 3 and a.shape[-1] == 2:  # tangential only -> append NaN Ez
        a = np.concatenate([a, np.full(a.shape[:2] + (1,), np.nan)], axis=-1)
    if a.shape != (nx, ny, 3):
        raise ValueError(f"{name} must have shape ({nx}, {ny}, 3) or ({nx}, {ny}, 2); got {a.shape}")
    return a.astype(np.complex128)


def _uniform_step(ax: np.ndarray, name: str, rtol: float = 1e-6) -> float:
    if ax.size < 2:
        raise ValueError(f"need at least two samples along {name}")
    d = np.diff(ax)
    step = float(np.mean(d))
    if np.max(np.abs(d - step)) > rtol * max(abs(step), 1e-30) + 1e-12:
        raise ValueError(f"{name} grid is not uniform; call PlanarField.resample() first")
    return step


def _interp_vector(x0, y0, V, x1, y1, method, fill_value) -> np.ndarray:
    from scipy.interpolate import RegularGridInterpolator

    X, Y = np.meshgrid(x1, y1, indexing="ij")
    pts = np.stack([X.ravel(), Y.ravel()], axis=-1)
    out = np.empty((x1.size, y1.size, 3), dtype=np.complex128)
    for c in range(3):
        parts = []
        for part in (V[..., c].real, V[..., c].imag):
            rgi = RegularGridInterpolator((x0, y0), part, method=method, bounds_error=False, fill_value=np.nan)
            parts.append(rgi(pts).reshape(x1.size, y1.size))
        out[..., c] = parts[0] + 1j * parts[1]
    outside = ~np.isfinite(out)
    if np.any(outside) and not (isinstance(fill_value, float) and np.isnan(fill_value)):
        out[outside] = fill_value
    return out


def common_grid(a: PlanarField, b: PlanarField, step: Optional[float] = None) -> Tuple[np.ndarray, np.ndarray]:
    """Uniform grid over the overlap of two maps (default step: the finer one)."""
    if step is None:
        step = min(np.min(np.diff(a.x)), np.min(np.diff(a.y)), np.min(np.diff(b.x)), np.min(np.diff(b.y)))
    x0, x1 = max(a.x[0], b.x[0]), min(a.x[-1], b.x[-1])
    y0, y1 = max(a.y[0], b.y[0]), min(a.y[-1], b.y[-1])
    if x1 <= x0 or y1 <= y0:
        raise ValueError("maps do not overlap")
    nx = int(np.floor((x1 - x0) / step + 1e-9)) + 1
    ny = int(np.floor((y1 - y0) / step + 1e-9)) + 1
    return x0 + step * np.arange(nx), y0 + step * np.arange(ny)


# ---------------------------------------------------------------------------
# File formats
# ---------------------------------------------------------------------------
#
# CSV: optional "# key = value" metadata lines (frequency_hz, z, length_unit,
# amplitude, time_convention, phase_valid), then a header row and one row per
# sample. Required columns: x, y, Ex_re, Ex_im, Ey_re, Ey_im. Optional: z,
# Ez_re, Ez_im, Hx_re, Hx_im, Hy_re, Hy_im, Hz_re, Hz_im. Rows must cover a full
# rectangular x-y grid (any order).
#
# NPZ: arrays x (Nx,), y (Ny,), E (Nx, Ny, 2|3) complex, optional H; scalars
# z, frequency_hz; optional strings amplitude, time_convention, length_unit.
#
# HDF5: in group `group` (default "/"): datasets x, y, E, optional H. E/H are
# complex or real with a trailing [re, im] axis of length 2. Attributes:
# z, frequency_hz, optional amplitude, time_convention, length_unit, phase_valid.


def _bool(v) -> bool:
    if isinstance(v, (bytes, np.bytes_)):
        v = v.decode()
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes")
    return bool(v)


def _str(v) -> str:
    if isinstance(v, (bytes, np.bytes_)):
        return v.decode()
    if isinstance(v, np.ndarray):
        return str(v.item())
    return str(v)


def load_csv(
    path: PathLike, frequency_hz: Optional[float] = None, z: Optional[float] = None, length_unit: Optional[str] = None
) -> PlanarField:
    """Load a planar field map from the CSV layout described in the module."""
    meta: Dict[str, str] = {}
    rows = []
    header = None
    with open(path, newline="") as fh:
        for line in fh:
            s = line.strip()
            if not s:
                continue
            if s.startswith("#"):
                if "=" in s:
                    k, v = s[1:].split("=", 1)
                    meta[k.strip()] = v.strip()
                continue
            if header is None:
                header = [h.strip() for h in next(csv.reader([s]))]
                continue
            rows.append([float(v) for v in next(csv.reader([s]))])
    if header is None or not rows:
        raise ValueError(f"{path}: no data")
    data = np.asarray(rows)
    col = {h: i for i, h in enumerate(header)}
    for req in ("x", "y", "Ex_re", "Ex_im", "Ey_re", "Ey_im"):
        if req not in col:
            raise ValueError(f"{path}: missing column '{req}'")
    unit = length_unit or meta.get("length_unit", "m")
    scale = _LENGTH_SCALE[unit]
    xs, ys = data[:, col["x"]] * scale, data[:, col["y"]] * scale
    ux, ix = _unique_coords(xs)
    uy, iy = _unique_coords(ys)
    if ux.size * uy.size != data.shape[0]:
        raise ValueError(f"{path}: rows do not form a full {ux.size}x{uy.size} grid")

    def grid(prefix: str) -> Optional[np.ndarray]:
        if f"{prefix}x_re" not in col:
            return None
        out = np.full((ux.size, uy.size, 3), np.nan, dtype=np.complex128)
        for c, name in enumerate(_COMPONENTS):
            re, im = f"{prefix}{name}_re", f"{prefix}{name}_im"
            if re in col and im in col:
                out[ix, iy, c] = data[:, col[re]] + 1j * data[:, col[im]]
        return out

    if z is None:
        z = float(meta["z"]) * scale if "z" in meta else (float(np.mean(data[:, col["z"]])) * scale if "z" in col else 0.0)
    freq = frequency_hz if frequency_hz is not None else float(meta["frequency_hz"])
    return PlanarField(
        x=ux,
        y=uy,
        z=z,
        frequency_hz=freq,
        E=grid("E"),
        H=grid("H"),
        amplitude=meta.get("amplitude", "peak"),
        time_convention=meta.get("time_convention", "+jwt"),
        phase_valid=_bool(meta.get("phase_valid", True)),
        metadata={"source": str(path), **{k: v for k, v in meta.items()}},
    )


def _unique_coords(v: np.ndarray, rtol: float = 1e-9) -> Tuple[np.ndarray, np.ndarray]:
    span = max(np.ptp(v), 1e-30)
    key = np.round(v / (span * rtol)).astype(np.int64) if span > 0 else np.zeros(v.size, dtype=np.int64)
    uk, inv = np.unique(key, return_inverse=True)
    vals = np.array([v[inv == i].mean() for i in range(uk.size)])
    return vals, inv


def save_csv(fld: PlanarField, path: PathLike) -> None:
    X, Y = np.meshgrid(fld.x, fld.y, indexing="ij")
    cols = {"x": X.ravel(), "y": Y.ravel()}
    for prefix, arr in (("E", fld.E), ("H", fld.H)):
        if arr is None:
            continue
        for c, name in enumerate(_COMPONENTS):
            v = arr[..., c].ravel()
            if np.all(np.isnan(v)):
                continue
            cols[f"{prefix}{name}_re"] = v.real
            cols[f"{prefix}{name}_im"] = v.imag
    with open(path, "w", newline="") as fh:
        fh.write(f"# frequency_hz = {fld.frequency_hz!r}\n# z = {fld.z!r}\n# length_unit = m\n")
        fh.write(f"# amplitude = {fld.amplitude}\n# time_convention = {fld.time_convention}\n")
        fh.write(f"# phase_valid = {fld.phase_valid}\n")
        w = csv.writer(fh)
        w.writerow(list(cols))
        w.writerows(np.column_stack(list(cols.values())).tolist())


def load_npz(path: PathLike) -> PlanarField:
    with np.load(path, allow_pickle=False) as d:
        scale = _LENGTH_SCALE[_str(d["length_unit"])] if "length_unit" in d else 1.0
        return PlanarField(
            x=d["x"] * scale,
            y=d["y"] * scale,
            z=float(d["z"]) * scale,
            frequency_hz=float(d["frequency_hz"]),
            E=d["E"],
            H=d["H"] if "H" in d else None,
            amplitude=_str(d["amplitude"]) if "amplitude" in d else "peak",
            time_convention=_str(d["time_convention"]) if "time_convention" in d else "+jwt",
            phase_valid=_bool(d["phase_valid"]) if "phase_valid" in d else True,
            metadata={"source": str(path)},
        )


def save_npz(fld: PlanarField, path: PathLike) -> None:
    extra = {} if fld.H is None else {"H": fld.H}
    np.savez(
        path,
        x=fld.x,
        y=fld.y,
        z=fld.z,
        frequency_hz=fld.frequency_hz,
        E=fld.E,
        amplitude=fld.amplitude,
        time_convention=fld.time_convention,
        phase_valid=fld.phase_valid,
        **extra,
    )


def _h5_complex(ds) -> np.ndarray:
    a = ds[()]
    if not np.iscomplexobj(a) and a.shape[-1] == 2 and a.ndim == 4:
        a = a[..., 0] + 1j * a[..., 1]
    return a


def load_hdf5(path: PathLike, group: str = "/") -> PlanarField:
    import h5py

    with h5py.File(path, "r") as f:
        g = f[group]
        at = g.attrs
        scale = _LENGTH_SCALE[_str(at["length_unit"])] if "length_unit" in at else 1.0
        return PlanarField(
            x=g["x"][()] * scale,
            y=g["y"][()] * scale,
            z=float(at["z"]) * scale,
            frequency_hz=float(at["frequency_hz"]),
            E=_h5_complex(g["E"]),
            H=_h5_complex(g["H"]) if "H" in g else None,
            amplitude=_str(at.get("amplitude", "peak")),
            time_convention=_str(at.get("time_convention", "+jwt")),
            phase_valid=_bool(at.get("phase_valid", True)),
            metadata={"source": str(path), "group": group},
        )


def save_hdf5(fld: PlanarField, path: PathLike, group: str = "/") -> None:
    import h5py

    with h5py.File(path, "a") as f:
        g = f.require_group(group)
        for name in ("x", "y", "E", "H"):
            if name in g:
                del g[name]
        g["x"], g["y"], g["E"] = fld.x, fld.y, fld.E
        if fld.H is not None:
            g["H"] = fld.H
        g.attrs.update(
            {
                "z": fld.z,
                "frequency_hz": fld.frequency_hz,
                "amplitude": fld.amplitude,
                "time_convention": fld.time_convention,
                "phase_valid": fld.phase_valid,
                "length_unit": "m",
            }
        )


def load_field_map(path: PathLike, **kwargs) -> PlanarField:
    """Dispatch on file extension (.csv, .npz, .h5/.hdf5)."""
    suffix = Path(path).suffix.lower()
    if suffix == ".csv":
        return load_csv(path, **kwargs)
    if suffix == ".npz":
        return load_npz(path)
    if suffix in (".h5", ".hdf5"):
        return load_hdf5(path, **kwargs)
    raise ValueError(f"unsupported field-map format: {suffix}")


# ---------------------------------------------------------------------------
# Simulation side: Sim4Life _Output.h5 -> PlanarField
# ---------------------------------------------------------------------------


def from_sim4life_output(
    h5_path: PathLike,
    z: float,
    frequency_hz: float,
    field_types: Sequence[str] = ("E", "H"),
    xlim: Optional[Tuple[float, float]] = None,
    ylim: Optional[Tuple[float, float]] = None,
) -> PlanarField:
    """Extract an x-y plane from a Sim4Life ``_Output.h5`` (Overall Field).

    Thin adapter over :mod:`goliat.extraction.field_reader`. Only the two
    z-slices around the requested plane are read. Yee-staggered components
    (comp0 ``(Nx-1, Ny, Nz)``, comp1 ``(Nx, Ny-1, Nz)``, comp2
    ``(Nx, Ny, Nz-1)``, as documented in ``field_reader``) are averaged to the
    x-y cell centres at the mesh node plane nearest to ``z``. This co-location
    is second-order accurate; for the H-field (dual grid) it is an
    approximation, and for compliance-grade work H should rather be
    recomputed from E with :func:`reconstruct_fields`. Sim4Life phasors are
    peak values in the ``exp(+j w t)`` convention.

    Args:
        h5_path: Path to ``*_Output.h5``.
        z: Requested plane position in metres (snapped to the nearest node).
        frequency_hz: Simulation frequency (not stored reliably in the file).
        field_types: Which of ``"E"``/``"H"`` to read.
        xlim, ylim: Optional crop window in metres.
    """
    import h5py

    from goliat.extraction.field_combiner_sliced import _get_mesh_axes
    from goliat.extraction.field_reader import find_overall_field_group, get_field_path

    with h5py.File(h5_path, "r") as f:
        fg = find_overall_field_group(f)
        if fg is None:
            raise ValueError(f"No 'Overall Field' found in {h5_path}")
        ax, ay, az = (np.asarray(a, dtype=float) for a in _get_mesh_axes(f))
        k = int(np.argmin(np.abs(az - z)))
        fields = {}
        for ft in field_types:
            fp = get_field_path(fg, ft)
            fields[ft] = _colocate_plane(f, fp, k)
    xc = 0.5 * (ax[1:] + ax[:-1])
    yc = 0.5 * (ay[1:] + ay[:-1])
    fld = PlanarField(
        x=xc,
        y=yc,
        z=az[k],
        frequency_hz=frequency_hz,
        E=fields.get("E", np.full((xc.size, yc.size, 3), np.nan)),
        H=fields.get("H"),
        metadata={"source": str(h5_path), "z_index": k, "colocation": "xy cell centres"},
    )
    if xlim is not None or ylim is not None:
        fld = fld.crop(xlim or (-np.inf, np.inf), ylim or (-np.inf, np.inf))
    return fld


def _colocate_plane(f, field_path: str, k: int) -> np.ndarray:
    def comp(c: int, zs: slice) -> np.ndarray:
        d = f[f"{field_path}/comp{c}"][:, :, zs, :]
        return d[..., 0] + 1j * d[..., 1]

    ex = comp(0, slice(k, k + 1))[:, :, 0]  # (Nx-1, Ny)
    ey = comp(1, slice(k, k + 1))[:, :, 0]  # (Nx, Ny-1)
    nz2 = f[f"{field_path}/comp2"].shape[2]
    k0, k1 = max(k - 1, 0), min(k, nz2 - 1)
    ez_s = comp(2, slice(k0, k1 + 1))  # (Nx, Ny, 1|2)
    ez = ez_s.mean(axis=2)
    ex_c = 0.5 * (ex[:, 1:] + ex[:, :-1])
    ey_c = 0.5 * (ey[1:, :] + ey[:-1, :])
    ez_c = 0.25 * (ez[1:, 1:] + ez[:-1, 1:] + ez[1:, :-1] + ez[:-1, :-1])
    return np.stack([ex_c, ey_c, ez_c], axis=-1)


def from_arrays(x, y, z, frequency_hz, E, H=None, length_unit: str = "m", **kwargs) -> PlanarField:
    """Build a :class:`PlanarField` from arrays (e.g. a Sim4Life slice viewer export)."""
    s = _LENGTH_SCALE[length_unit]
    return PlanarField(x=np.asarray(x) * s, y=np.asarray(y) * s, z=z * s, frequency_hz=frequency_hz, E=E, H=H, **kwargs)


# ---------------------------------------------------------------------------
# Plane-wave spectrum (angular spectrum) propagation
# ---------------------------------------------------------------------------


@dataclass
class AngularSpectrum:
    """Plane-wave spectrum of the tangential E-field on a (zero-padded) grid.

    ``Ex``/``Ey`` are unnormalised FFTs (``numpy.fft.fft2``) over the
    zero-padded ``(Mx, My)`` grid ``x``/``y`` (spacings ``dx``/``dy``) in which
    the scan is centred, starting at index ``offset``. All quantities follow the
    ``exp(+j w t)`` convention internally.
    """

    kx: np.ndarray  # (Mx, My)
    ky: np.ndarray
    kz: np.ndarray  # complex, Im(kz) <= 0
    k0: float
    Ex: np.ndarray
    Ey: np.ndarray
    dx: float
    dy: float
    weight: np.ndarray  # k-space filter (1 = pass)
    x: np.ndarray  # padded-grid coordinates (the scan occupies offset..offset+N)
    y: np.ndarray
    offset: Tuple[int, int]

    def full_spectrum(self, dz: float = 0.0, kz_floor: float = 1e-3) -> Tuple[np.ndarray, np.ndarray]:
        """E and H spectra (shape ``(Mx, My, 3)``) on the plane shifted by ``dz``.

        Ez follows from div E = 0: ``kx Ex + ky Ey + kz Ez = 0``; H from
        Faraday's law: ``H = (k x E) / (w mu0)``. Components with
        ``|kz| < kz_floor * k0`` (grazing, singular Ez) are discarded.
        """
        prop = np.exp(-1j * self.kz * dz) * self.weight
        ok = np.abs(self.kz) >= kz_floor * self.k0
        prop = np.where(ok, prop, 0.0)
        ex, ey = self.Ex * prop, self.Ey * prop
        kz_safe = np.where(ok, self.kz, 1.0)
        ez = np.where(ok, -(self.kx * ex + self.ky * ey) / kz_safe, 0.0)
        E = np.stack([ex, ey, ez], axis=-1)
        kvec = np.stack([np.broadcast_to(self.kx, ex.shape), np.broadcast_to(self.ky, ex.shape), self.kz], axis=-1)
        omega_mu = self.k0 * ETA0  # w*mu0 = k0*eta0
        H = np.cross(kvec, E) / omega_mu
        return E, H

    def plane_power(self, dz: float = 0.0, amplitude: str = "peak") -> float:
        """Total real power (W) crossing the plane, via Parseval in k-space."""
        E, H = self.full_spectrum(dz)
        m = E.shape[0] * E.shape[1]
        sz = np.real(E[..., 0] * np.conj(H[..., 1]) - E[..., 1] * np.conj(H[..., 0]))
        c = 0.5 if amplitude == "peak" else 1.0
        return float(c * np.sum(sz) * self.dx * self.dy / m)


def angular_spectrum(
    fld: PlanarField,
    pad_factor: float = 2.0,
    k_max_factor: Optional[float] = None,
    taper: float = 0.0,
) -> AngularSpectrum:
    """Compute the plane-wave spectrum of the tangential E on ``fld``.

    Args:
        fld: Phase-valid planar map on a uniform grid.
        pad_factor: Zero-padding factor (>= 1) of the FFT grid. Padding
            suppresses wrap-around of the periodic FFT model; it does not
            remove truncation error from a too-small scan aperture.
        k_max_factor: Optional low-pass filter in units of k0: spectral
            components with ``sqrt(kx^2+ky^2) > k_max_factor*k0`` are removed
            (1.0 keeps only propagating waves). Mandatory in practice for
            back-propagation and useful against probe noise.
        taper: Width (in units of k0) of a raised-cosine roll-off below the
            cut-off, reducing ringing. Ignored without ``k_max_factor``.
    """
    if not fld.phase_valid:
        raise ValueError("PWS needs complex (phase-valid) data; magnitude-only maps cannot be propagated")
    if pad_factor < 1:
        raise ValueError("pad_factor must be >= 1")
    dx, dy = fld.dx, fld.dy
    nx, ny = fld.shape
    mx, my = int(np.ceil(nx * pad_factor)), int(np.ceil(ny * pad_factor))
    Et = fld.E[..., :2]
    if np.any(~np.isfinite(Et)):
        raise ValueError("tangential E contains NaN; crop or fill the map first")
    if fld.time_convention == "-jwt":
        Et = np.conj(Et)
    ox, oy = (mx - nx) // 2, (my - ny) // 2  # centre the scan in the padded grid
    pad = np.zeros((mx, my, 2), dtype=np.complex128)
    pad[ox : ox + nx, oy : oy + ny] = Et
    spec = np.fft.fft2(pad, axes=(0, 1))
    # numpy's forward FFT maps exp(+j k x) to frequency +k; in the exp(+jwt)
    # convention a plane wave is exp(-j k.r), so the physical wavenumber of bin
    # m is the negated FFT frequency.
    kx1 = -2 * np.pi * np.fft.fftfreq(mx, dx)
    ky1 = -2 * np.pi * np.fft.fftfreq(my, dy)
    KX, KY = np.meshgrid(kx1, ky1, indexing="ij")
    k0 = fld.k0
    kt2 = KX**2 + KY**2
    kz = np.where(kt2 <= k0**2, np.sqrt(np.maximum(k0**2 - kt2, 0.0)) + 0j, -1j * np.sqrt(np.maximum(kt2 - k0**2, 0.0)))
    weight = np.ones_like(kt2)
    if k_max_factor is not None:
        kt = np.sqrt(kt2) / k0
        weight = np.where(kt <= k_max_factor, 1.0, 0.0)
        if taper > 0:
            lo = k_max_factor - taper
            band = (kt > lo) & (kt <= k_max_factor)
            weight[band] = 0.5 * (1 + np.cos(np.pi * (kt[band] - lo) / taper))
    return AngularSpectrum(
        kx=KX,
        ky=KY,
        kz=kz,
        k0=k0,
        Ex=spec[..., 0],
        Ey=spec[..., 1],
        dx=dx,
        dy=dy,
        weight=weight,
        x=fld.x[0] + dx * (np.arange(mx) - ox),
        y=fld.y[0] + dy * (np.arange(my) - oy),
        offset=(ox, oy),
    )


def propagate(
    fld: PlanarField,
    z_target: float,
    pad_factor: float = 2.0,
    k_max_factor: Optional[float] = None,
    taper: float = 0.0,
    kz_floor: float = 1e-3,
    keep_padding: bool = False,
) -> PlanarField:
    """Propagate a planar map to the plane ``z_target`` with the PWS method.

    Only the tangential E on ``fld`` is used (it determines the outgoing field
    uniquely in the source-free half-space ``z > sources``); the result
    carries full E (incl. Ez) and H on the same x-y grid. Back-propagation
    (``z_target < fld.z``) amplifies evanescent content and requires
    ``k_max_factor`` (typically <= 1). With ``keep_padding=True`` the result
    is returned on the whole zero-padded grid (the field spreads laterally as
    it propagates); otherwise it is cropped back to the input grid.
    """
    dz = float(z_target) - fld.z
    if dz < 0 and k_max_factor is None:
        raise ValueError("back-propagation (z_target < z) requires k_max_factor to bound evanescent growth")
    spec = angular_spectrum(fld, pad_factor=pad_factor, k_max_factor=k_max_factor, taper=taper)
    E_s, H_s = spec.full_spectrum(dz, kz_floor=kz_floor)
    E = np.fft.ifft2(E_s, axes=(0, 1))
    H = np.fft.ifft2(H_s, axes=(0, 1))
    x, y = spec.x, spec.y
    if not keep_padding:
        (nx, ny), (ox, oy) = fld.shape, spec.offset
        E, H = E[ox : ox + nx, oy : oy + ny], H[ox : ox + nx, oy : oy + ny]
        x, y = fld.x, fld.y
    if fld.time_convention == "-jwt":
        E, H = np.conj(E), np.conj(H)
    meta = dict(fld.metadata)
    meta.update({"pws_from_z": fld.z, "pws_pad_factor": pad_factor, "pws_k_max_factor": k_max_factor})
    return replace(fld, x=x, y=y, z=float(z_target), E=E, H=H, metadata=meta)


def reconstruct_fields(fld: PlanarField, **kwargs) -> PlanarField:
    """Full E (incl. Ez) and H on the same plane from tangential E (PWS, dz=0)."""
    return propagate(fld, fld.z, **kwargs)


def spectral_upsample(fld: PlanarField, factor: int, pad_factor: float = 1.0) -> PlanarField:
    """Band-limited (sinc) interpolation of a phase-valid map by an integer factor.

    Equivalent to evaluating the plane-wave spectrum on a finer grid; this is
    the physics-based baseline against which learned super-resolution can be
    judged. The output grid spans the original extent with step ``dx/factor``.
    Valid when the field on the plane is band-limited to the sampled
    bandwidth (sampling step <= lambda/2 resolves all propagating waves).
    """
    if not fld.phase_valid:
        raise ValueError("spectral upsampling needs complex (phase-valid) data")
    factor = int(factor)
    if factor < 1:
        raise ValueError("factor must be >= 1")
    nx, ny = fld.shape
    mx, my = int(np.ceil(nx * pad_factor)), int(np.ceil(ny * pad_factor))

    def up(V: np.ndarray) -> np.ndarray:
        V = np.where(np.isfinite(V), V, 0.0)
        pad = np.zeros((mx, my, V.shape[-1]), dtype=np.complex128)
        pad[:nx, :ny] = V
        S = np.fft.fftshift(np.fft.fft2(pad, axes=(0, 1)), axes=(0, 1))
        Mx, My = mx * factor, my * factor
        big = np.zeros((Mx, My, V.shape[-1]), dtype=np.complex128)
        ox, oy = (Mx - mx) // 2, (My - my) // 2
        big[ox : ox + mx, oy : oy + my] = S
        out = np.fft.ifft2(np.fft.ifftshift(big, axes=(0, 1)), axes=(0, 1)) * factor**2
        return out[: (nx - 1) * factor + 1, : (ny - 1) * factor + 1]

    E = up(fld.E)
    if not fld.has_ez:
        E[..., 2] = np.nan
    H = None if fld.H is None else up(fld.H)
    x = fld.x[0] + fld.dx / factor * np.arange(E.shape[0])
    y = fld.y[0] + fld.dy / factor * np.arange(E.shape[1])
    return replace(fld, x=x, y=y, E=E, H=H)


# ---------------------------------------------------------------------------
# Power density (IEC/IEEE 63195-1/-2)
# ---------------------------------------------------------------------------


def poynting(fld: PlanarField) -> np.ndarray:
    """Time-averaged Poynting vector ``Re(E x H*)/2`` (peak) in W/m^2, ``(Nx, Ny, 3)``."""
    if fld.H is None:
        raise ValueError("H is missing; call reconstruct_fields() (PWS) or use plane_wave_pd()")
    if not fld.has_ez:
        raise ValueError("Ez is missing; call reconstruct_fields() first")
    c = 0.5 if fld.amplitude == "peak" else 1.0
    return c * np.real(np.cross(fld.E, np.conj(fld.H)))


def plane_wave_pd(fld: PlanarField) -> np.ndarray:
    """Far-field / plane-wave estimate ``|E|^2 / (2 eta0)`` (peak) in W/m^2.

    The only PD estimate available for magnitude-only maps. It is not the
    IEC/IEEE 63195 quantity in the reactive near field, where it can be
    substantially biased; use PWS reconstruction whenever phase is available.
    """
    c = 0.5 if fld.amplitude == "peak" else 1.0
    return c * fld.e_magnitude() ** 2 / ETA0


def total_power(fld: PlanarField) -> float:
    """Real power (W) crossing the mapped area, integrating S_z over sample cells."""
    return float(np.sum(poynting(fld)[..., 2]) * fld.dx * fld.dy)


@dataclass
class AveragedPD:
    """Spatially averaged power density maps and their peaks.

    ``spdn`` and ``spdtot`` are defined at the window centres ``xc``/``yc``
    (all sample positions whose square window lies fully inside the map).
    """

    area_m2: float
    side_m: float
    xc: np.ndarray
    yc: np.ndarray
    spdn: np.ndarray
    spdtot: np.ndarray
    pspdn: float
    pspdn_location: Tuple[float, float]
    pspdtot: float
    pspdtot_location: Tuple[float, float]

    def as_dict(self) -> Dict[str, object]:
        return {
            "area_m2": self.area_m2,
            "psPDn_W_m2": self.pspdn,
            "psPDn_location_m": list(self.pspdn_location),
            "psPDtot_W_m2": self.pspdtot,
            "psPDtot_location_m": list(self.pspdtot_location),
        }


def _box_integral_1d(v: np.ndarray, coords: np.ndarray, step: float, centres: np.ndarray, side: float, axis: int) -> np.ndarray:
    """Integral of the piecewise-constant (cell-centred) samples over [c-side/2, c+side/2]."""
    v = np.moveaxis(v, axis, 0)
    edges = np.concatenate([[coords[0] - step / 2], coords + step / 2])
    cum = np.concatenate([np.zeros((1,) + v.shape[1:]), np.cumsum(v * step, axis=0)], axis=0)

    def interp(t: np.ndarray) -> np.ndarray:
        i = np.clip(np.searchsorted(edges, t, side="right") - 1, 0, edges.size - 2)
        w = (t - edges[i]) / step
        w = w.reshape((-1,) + (1,) * (v.ndim - 1))
        return cum[i] * (1 - w) + cum[i + 1] * w

    out = interp(centres + side / 2) - interp(centres - side / 2)
    return np.moveaxis(out, 0, axis)


def spatial_average_pd(
    fld: PlanarField,
    area_m2: float = 4e-4,
    normal_sign: float = 1.0,
    S: Optional[np.ndarray] = None,
) -> AveragedPD:
    """Spatially averaged incident power density per IEC/IEEE 63195-1/-2.

    ``sPDn = (1/A) * integral_A Re(S) . n dA`` and
    ``sPDtot = (1/A) * || integral_A Re(S) dA ||``, averaged over a square of
    area ``A`` (1 cm^2 = 1e-4 m^2 and 4 cm^2 = 4e-4 m^2 are the standard
    choices) aligned with the grid axes, evaluated with the square centred on
    every sample position whose window fits inside the map. The square need
    not span an integer number of cells: samples are treated as cell-centred
    piecewise-constant values and partial cells are weighted exactly.
    The standards require a grid step of at most min(1 mm, lambda/10) for
    this evaluation; use :func:`spectral_upsample` or :func:`propagate` on a
    finer grid if needed (a warning is logged otherwise).

    Args:
        fld: Map with E and H (see :func:`reconstruct_fields`).
        area_m2: Averaging area.
        normal_sign: +1 if the body/evaluation surface normal points to +z
            (wave travels towards +z), -1 otherwise.
        S: Optional precomputed Poynting vector (e.g. :func:`plane_wave_pd`
            placed in the z-component for magnitude-only data).
    """
    if S is None:
        S = poynting(fld)
    dx, dy = fld.dx, fld.dy
    side = float(np.sqrt(area_m2))
    if max(dx, dy) > min(1e-3, fld.wavelength / 10) * (1 + 1e-6):
        logger.warning(
            "grid step %.3g m exceeds min(1 mm, lambda/10)=%.3g m required by IEC/IEEE 63195 for psPD",
            max(dx, dy),
            min(1e-3, fld.wavelength / 10),
        )
    x_lo, x_hi = fld.x[0] - dx / 2, fld.x[-1] + dx / 2
    y_lo, y_hi = fld.y[0] - dy / 2, fld.y[-1] + dy / 2
    tol = 1e-9 * side
    xc = fld.x[(fld.x - side / 2 >= x_lo - tol) & (fld.x + side / 2 <= x_hi + tol)]
    yc = fld.y[(fld.y - side / 2 >= y_lo - tol) & (fld.y + side / 2 <= y_hi + tol)]
    if xc.size == 0 or yc.size == 0:
        raise ValueError("averaging square is larger than the mapped area")
    tmp = _box_integral_1d(S, fld.x, dx, xc, side, axis=0)
    avg = _box_integral_1d(tmp, fld.y, dy, yc, side, axis=1) / side**2
    spdn = normal_sign * avg[..., 2]
    spdtot = np.linalg.norm(avg, axis=-1)
    i_n = np.unravel_index(np.argmax(spdn), spdn.shape)
    i_t = np.unravel_index(np.argmax(spdtot), spdtot.shape)
    return AveragedPD(
        area_m2=area_m2,
        side_m=side,
        xc=xc,
        yc=yc,
        spdn=spdn,
        spdtot=spdtot,
        pspdn=float(spdn[i_n]),
        pspdn_location=(float(xc[i_n[0]]), float(yc[i_n[1]])),
        pspdtot=float(spdtot[i_t]),
        pspdtot_location=(float(xc[i_t[0]]), float(yc[i_t[1]])),
    )


def assess_pd(fld: PlanarField, areas_m2: Sequence[float] = (1e-4, 4e-4), **pws_kwargs) -> Dict[float, AveragedPD]:
    """Convenience: reconstruct H if needed (or plane-wave estimate) and average PD.

    Magnitude-only maps use :func:`plane_wave_pd` as the normal component.
    """
    if fld.phase_valid:
        if fld.H is None or not fld.has_ez:
            fld = reconstruct_fields(fld, **pws_kwargs)
        S = poynting(fld)
    else:
        S = np.zeros(fld.shape + (3,))
        S[..., 2] = plane_wave_pd(fld)
    return {a: spatial_average_pd(fld, a, S=S) for a in areas_m2}


# ---------------------------------------------------------------------------
# Measurement <-> simulation comparison
# ---------------------------------------------------------------------------


def register_translation(
    reference: PlanarField,
    moving: PlanarField,
    use_tangential: bool = True,
    min_overlap: float = 0.5,
    refine_subpixel: bool = True,
) -> Tuple[float, float]:
    """Estimate the in-plane shift ``s`` such that ``moving(r) ~ reference(r - s)``.

    Uses the normalised cross-correlation (NCC) of the E magnitudes, which is
    insensitive to an unknown global phase and gain. Each lag is normalised by
    the signal energy of both maps inside the overlapping region (masked NCC),
    which removes the bias towards zero shift that a plain correlation shows
    for maps that do not decay to zero at the scan edges. Lags whose overlap is
    below ``min_overlap`` of the map area are ignored. The integer peak is
    refined with a parabolic fit and, if ``refine_subpixel``, by maximising
    the NCC over continuous shifts (cubic-spline resampling). Both maps must share the same uniform grid
    (use :meth:`PlanarField.resample`). Apply the result with
    ``simulated.shifted(*s)`` followed by resampling.
    """
    if reference.shape != moving.shape or not (np.allclose(reference.x, moving.x) and np.allclose(reference.y, moving.y)):
        raise ValueError("maps must share the same grid; resample first")
    a = np.nan_to_num(reference.e_magnitude(tangential_only=use_tangential))
    b = np.nan_to_num(moving.e_magnitude(tangential_only=use_tangential))
    nx, ny = a.shape
    shp = (2 * nx, 2 * ny)

    def corr(p, q):  # sum_m p[m] q[m + n]
        return np.real(np.fft.ifft2(np.fft.fft2(q, s=shp) * np.conj(np.fft.fft2(p, s=shp))))

    ones = np.ones_like(a)
    num = corr(a, b)
    ea = corr(a**2, ones)
    eb = corr(ones, b**2)
    overlap = corr(ones, ones)
    valid = (overlap > min_overlap * nx * ny) & (ea > 0) & (eb > 0)
    xc = np.full(shp, -np.inf)
    xc[valid] = num[valid] / np.sqrt(ea[valid] * eb[valid])
    i, j = np.unravel_index(np.argmax(xc), xc.shape)
    xc = np.where(np.isfinite(xc), xc, 0.0)

    def refine(cm, c0, cp) -> float:
        den = cm - 2 * c0 + cp
        return 0.0 if den == 0 else 0.5 * (cm - cp) / den

    ip, jp = (i + 1) % shp[0], (j + 1) % shp[1]
    di = refine(xc[i - 1, j], xc[i, j], xc[ip, j]) if valid[i - 1, j] and valid[ip, j] else 0.0
    dj = refine(xc[i, j - 1], xc[i, j], xc[i, jp]) if valid[i, j - 1] and valid[i, jp] else 0.0
    si = (i if i < nx else i - 2 * nx) + di
    sj = (j if j < ny else j - 2 * ny) + dj
    if refine_subpixel:
        si, sj = _refine_shift(a, b, si, sj)
    return float(si * reference.dx), float(sj * reference.dy)


def _refine_shift(a: np.ndarray, b: np.ndarray, si: float, sj: float) -> Tuple[float, float]:
    """Maximise the overlap NCC over continuous shifts (cubic-spline resampling)."""
    from scipy import ndimage, optimize

    def neg_ncc(s):
        bs = ndimage.shift(b, (-s[0], -s[1]), order=3, mode="constant", cval=np.nan)
        ok = np.isfinite(bs)
        if ok.sum() < 0.25 * a.size:
            return 0.0
        num = np.sum(a[ok] * bs[ok])
        den = np.sqrt(np.sum(a[ok] ** 2) * np.sum(bs[ok] ** 2))
        return -num / den if den > 0 else 0.0

    res = optimize.minimize(
        neg_ncc,
        x0=[si, sj],
        method="Nelder-Mead",
        options={"xatol": 1e-3, "fatol": 1e-12, "initial_simplex": [[si, sj], [si + 0.5, sj], [si, sj + 0.5]]},
    )
    if res.success and abs(res.x[0] - si) <= 1.0 and abs(res.x[1] - sj) <= 1.0:
        return float(res.x[0]), float(res.x[1])
    return si, sj


@dataclass
class Calibration:
    """Least-squares scale from simulation to measurement.

    ``field_factor`` multiplies simulated E/H (complex if ``mode='complex'``);
    ``power_factor = |field_factor|^2`` multiplies simulated PD/SAR values,
    e.g. to renormalise a GOLIAT result to the measured device power.
    """

    mode: str
    field_factor: complex
    power_factor: float
    residual_rel: float


def calibration_factor(
    measured: PlanarField, simulated: PlanarField, mode: str = "complex", mask: Optional[np.ndarray] = None
) -> Calibration:
    """Least-squares scale ``a`` minimising ``||m - a s||`` over tangential E.

    ``mode='complex'``: ``a = <s, m> / <s, s>`` (gain + global phase);
    ``mode='magnitude'``: real ``a`` fitted on ``|E_t|`` (for magnitude-only
    measurements or when probe phase references differ).
    """
    m = measured.E[..., :2]
    s = simulated.E[..., :2]
    ok = np.all(np.isfinite(m), axis=-1) & np.all(np.isfinite(s), axis=-1)
    if mask is not None:
        ok &= mask
    if mode == "complex":
        if not (measured.phase_valid and simulated.phase_valid):
            raise ValueError("complex calibration requires phase-valid maps")
        mv, sv = m[ok].ravel(), s[ok].ravel()
        a = np.vdot(sv, mv) / np.vdot(sv, sv)
        res = np.linalg.norm(mv - a * sv) / np.linalg.norm(mv)
    elif mode == "magnitude":
        mv = np.sqrt(np.sum(np.abs(m[ok]) ** 2, axis=-1))
        sv = np.sqrt(np.sum(np.abs(s[ok]) ** 2, axis=-1))
        a = float(np.dot(sv, mv) / np.dot(sv, sv))
        res = np.linalg.norm(mv - a * sv) / np.linalg.norm(mv)
    else:
        raise ValueError("mode must be 'complex' or 'magnitude'")
    return Calibration(mode=mode, field_factor=complex(a), power_factor=float(abs(a) ** 2), residual_rel=float(res))


@dataclass
class ComparisonResult:
    """Agreement metrics between a measured and a simulated planar map."""

    shift_m: Tuple[float, float]
    magnitude_rel_l2: float
    mre: float
    phase_rms_deg: Optional[float]
    complex_rel_l2: Optional[float]
    calibration: Calibration
    pspd_measured: Dict[float, float]
    pspd_simulated: Dict[float, float]
    pspd_rel_error: Dict[float, float]
    n_points: int

    def as_dict(self) -> Dict[str, object]:
        d = {k: getattr(self, k) for k in ("shift_m", "magnitude_rel_l2", "mre", "phase_rms_deg", "complex_rel_l2", "n_points")}
        d["calibration"] = {
            "mode": self.calibration.mode,
            "field_factor": [self.calibration.field_factor.real, self.calibration.field_factor.imag],
            "power_factor": self.calibration.power_factor,
            "residual_rel": self.calibration.residual_rel,
        }
        d["psPDn"] = {
            str(a): {"measured": self.pspd_measured[a], "simulated": self.pspd_simulated[a], "rel_error": self.pspd_rel_error[a]}
            for a in self.pspd_measured
        }
        return d


def compare_fields(
    measured: PlanarField,
    simulated: PlanarField,
    register: bool = True,
    calibrate: bool = False,
    areas_m2: Sequence[float] = (1e-4, 4e-4),
    magnitude_floor: float = 0.05,
    resample_method: str = "linear",
    pws_kwargs: Optional[dict] = None,
) -> ComparisonResult:
    """Compare a measured/reconstructed map against a simulated map on the same plane.

    Steps: (1) resample the simulation onto the measurement grid; (2) if
    ``register``, estimate and remove the in-plane offset (positioning error of
    the device or scanner); (3) fit the least-squares calibration factor;
    (4) compute metrics on the overlap. If ``calibrate`` is True the metrics
    are computed after scaling the simulation by the fitted factor (shape-only
    comparison); otherwise they compare absolute levels.

    Metrics (over tangential E on points where both maps are defined):

    * ``magnitude_rel_l2 = || |m| - |s| ||_2 / || |m| ||_2``
    * ``mre``: mean relative error of ``|E|`` (Yi et al. 2026, Eq. 7), restricted
      to points with ``|m| > magnitude_floor * max|m|`` to avoid division by ~0;
    * ``phase_rms_deg``: |E_t|^2-weighted RMS phase difference after removing
      the best global phase (phase-valid maps only), above the same floor;
    * ``complex_rel_l2 = ||m - s|| / ||m||`` for phase-valid maps;
    * ``pspd_rel_error[A] = (psPDn_s - psPDn_m) / psPDn_m``.
    """
    pws_kwargs = pws_kwargs or {}
    phase_ok = measured.phase_valid and simulated.phase_valid
    sim = simulated
    if sim.z != measured.z:
        if abs(sim.z - measured.z) > 1e-6 and sim.phase_valid:
            sim = propagate(sim, measured.z, **pws_kwargs) if sim.z < measured.z else sim
        if abs(sim.z - measured.z) > 1e-6:
            logger.warning("simulated plane z=%.4g m differs from measured z=%.4g m", sim.z, measured.z)
    sim_r = sim.resample(measured.x, measured.y, method=resample_method)
    shift = (0.0, 0.0)
    if register:
        shift = register_translation(measured, _nan_to_zero(sim_r))
        sim_r = sim.shifted(*shift).resample(measured.x, measured.y, method=resample_method)

    mode = "complex" if phase_ok else "magnitude"
    cal = calibration_factor(measured, sim_r, mode=mode)
    sim_c = sim_r.scaled(cal.field_factor if calibrate else 1.0)

    m = measured.E[..., :2]
    s = sim_c.E[..., :2]
    ok = np.all(np.isfinite(m), axis=-1) & np.all(np.isfinite(s), axis=-1)
    am = np.sqrt(np.sum(np.abs(m) ** 2, axis=-1))
    as_ = np.sqrt(np.sum(np.abs(s) ** 2, axis=-1))
    mag_l2 = float(np.linalg.norm((am - as_)[ok]) / np.linalg.norm(am[ok]))
    strong = ok & (am > magnitude_floor * np.max(am[ok]))
    mre = float(np.mean(np.abs(as_[strong] - am[strong]) / am[strong]))

    phase_rms = cplx = None
    if phase_ok:
        cplx = float(np.linalg.norm((m - s)[ok]) / np.linalg.norm(m[ok]))
        g = np.vdot(s[strong].ravel(), m[strong].ravel())
        s_ph = s * np.exp(1j * np.angle(g))
        dphi = np.angle(m[strong] * np.conj(s_ph[strong]))
        w = np.abs(m[strong]) ** 2
        phase_rms = float(np.degrees(np.sqrt(np.sum(w * dphi**2) / np.sum(w))))

    pm, ps, pe = {}, {}, {}
    # Same PD estimator and same region on both sides: PWS if both maps carry
    # phase, else the plane-wave estimate (on |E_t| if either map lacks Ez).
    meas_box, sim_box = _common_finite_box(measured, sim_c)
    if not phase_ok and not (meas_box.has_ez and sim_box.has_ez):
        meas_box, sim_box = _drop_ez(meas_box), _drop_ez(sim_box)
    meas_pd = assess_pd(replace(meas_box, phase_valid=phase_ok), areas_m2, **pws_kwargs)
    sim_pd = assess_pd(replace(sim_box, phase_valid=phase_ok), areas_m2, **pws_kwargs)
    for a in areas_m2:
        pm[a], ps[a] = meas_pd[a].pspdn, sim_pd[a].pspdn
        pe[a] = (ps[a] - pm[a]) / pm[a] if pm[a] != 0 else float("nan")
    return ComparisonResult(
        shift_m=shift,
        magnitude_rel_l2=mag_l2,
        mre=mre,
        phase_rms_deg=phase_rms,
        complex_rel_l2=cplx,
        calibration=cal,
        pspd_measured=pm,
        pspd_simulated=ps,
        pspd_rel_error=pe,
        n_points=int(ok.sum()),
    )


def _nan_to_zero(fld: PlanarField) -> PlanarField:
    """Zero-fill NaN tangential samples (outside overlap); drop H/Ez if incomplete."""
    E = fld.E.copy()
    E[..., :2] = np.nan_to_num(E[..., :2])
    H = fld.H
    if H is not None and not np.all(np.isfinite(H)):
        H = None
        E[..., 2] = np.nan
    if not np.all(np.isfinite(E[..., 2])):
        E[..., 2] = np.nan
    return replace(fld, E=E, H=H)


def _drop_ez(fld: PlanarField) -> PlanarField:
    E = fld.E.copy()
    E[..., 2] = np.nan
    return replace(fld, E=E, H=None)


def _common_finite_box(a: PlanarField, b: PlanarField) -> Tuple[PlanarField, PlanarField]:
    """Crop two maps on the same grid to the largest box where both have finite E_t."""
    ok = np.all(np.isfinite(a.E[..., :2]), axis=-1) & np.all(np.isfinite(b.E[..., :2]), axis=-1)
    if not ok.any():
        raise ValueError("maps have no common finite region")
    i0, i1, j0, j1 = 0, ok.shape[0], 0, ok.shape[1]
    while i1 > i0 and j1 > j0:  # greedily trim the edge with the most invalid samples
        sub = ~ok[i0:i1, j0:j1]
        if not sub.any():
            break
        bad = [sub[0].sum(), sub[-1].sum(), sub[:, 0].sum(), sub[:, -1].sum()]
        k = int(np.argmax(bad))
        if bad[k] == 0:  # invalid samples only in the interior: keep box, zero-fill them
            break
        i0, i1, j0, j1 = (i0 + (k == 0), i1 - (k == 1), j0 + (k == 2), j1 - (k == 3))
    if i1 <= i0 or j1 <= j0:
        raise ValueError("maps have no common finite rectangle")
    xl, yl = (a.x[i0], a.x[i1 - 1]), (a.y[j0], a.y[j1 - 1])
    a_c, b_c = a.crop(xl, yl), b.crop(xl, yl)
    return _nan_to_zero(a_c) if not a_c.has_ez or a_c.H is None else a_c, _nan_to_zero(b_c)


__all__ = [
    "AngularSpectrum",
    "AveragedPD",
    "Calibration",
    "ComparisonResult",
    "PlanarField",
    "angular_spectrum",
    "assess_pd",
    "calibration_factor",
    "common_grid",
    "compare_fields",
    "from_arrays",
    "from_sim4life_output",
    "load_csv",
    "load_field_map",
    "load_hdf5",
    "load_npz",
    "plane_wave_pd",
    "poynting",
    "propagate",
    "reconstruct_fields",
    "register_translation",
    "save_csv",
    "save_hdf5",
    "save_npz",
    "spatial_average_pd",
    "spectral_upsample",
    "total_power",
]
