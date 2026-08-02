"""Normalized-force tables and fail-closed interpolation for Track P Run 010."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Literal

import numpy as np
from numpy.typing import NDArray


FloatArray = NDArray[np.float64]
FieldKind = Literal["pre_handoff_chirp_3", "post_handoff_trap_3_plus_1"]
FORCE_FIELD_LABEL = (
    "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_"
    "FORCE_FIELD_INTERPOLATION_VALIDATION_ONLY"
)


class ForceFieldError(ValueError):
    pass


class ForceFieldDomainError(ForceFieldError):
    """Raised when interpolation would require clamping or extrapolation."""


class ForceFieldCacheMismatchError(ForceFieldError):
    """Raised when cache provenance differs from the requested construction."""


def _axis(values, name: str, *, minimum_size: int = 2) -> FloatArray:
    result = np.asarray(values, dtype=float)
    if result.ndim != 1 or result.size < minimum_size:
        raise ForceFieldError(f"{name} must be a one-dimensional axis with at least {minimum_size} values")
    if not np.isfinite(result).all() or np.any(np.diff(result) <= 0):
        raise ForceFieldError(f"{name} must be finite and strictly increasing")
    return result


@dataclass(frozen=True)
class ForceFieldDomain:
    positions_m: FloatArray
    velocities_m_s: FloatArray
    detunings_gamma: FloatArray | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "positions_m", _axis(self.positions_m, "positions_m"))
        object.__setattr__(self, "velocities_m_s", _axis(self.velocities_m_s, "velocities_m_s"))
        if self.detunings_gamma is not None:
            object.__setattr__(self, "detunings_gamma", _axis(self.detunings_gamma, "detunings_gamma"))

    @property
    def shape(self) -> tuple[int, ...]:
        base = (self.positions_m.size, self.velocities_m_s.size)
        return base if self.detunings_gamma is None else base + (self.detunings_gamma.size,)

    @property
    def equilibrium_solve_count(self) -> int:
        return int(np.prod(self.shape))


@dataclass(frozen=True)
class ForceFieldProvenance:
    label: str
    field_kind: FieldKind
    track: str
    backend_mode: str
    ground_zeeman_convention: str
    excited_zeeman_model: str
    excited_hyperfine_model: str
    splitting_case: str
    splitting_mhz: float
    splitting_interval_mhz: tuple[float, float]
    splitting_note: str
    replication_valid: bool
    exact_track_blocked: bool
    unresolved_terms: tuple[str, ...]
    normalized_force_unit: str
    canonical_values_are_si_acceleration: bool
    field_gradient_t_m: float
    beam_mode: str
    component_order: tuple[int, int, int, int]
    saturation_vector: tuple[float, float, float, float]
    detuning_specification: str
    source_hashes: tuple[tuple[str, str], ...]
    interpolation_method: str

    def __post_init__(self) -> None:
        required = ("PROVISIONAL", "NOT_RODRIGUEZ_REPLICATION", "FORCE_FIELD_INTERPOLATION_VALIDATION_ONLY")
        if not all(item in self.label for item in required):
            raise ForceFieldError("force-field provenance label is missing a required warning stamp")
        if self.track != "provisional" or self.replication_valid or not self.exact_track_blocked:
            raise ForceFieldError("force-field provenance must remain provisional and non-replication-valid")
        if self.normalized_force_unit != "hbar*k*Gamma" or self.canonical_values_are_si_acceleration:
            raise ForceFieldError("canonical force-field values must be normalized force, not SI acceleration")

    @property
    def cache_key(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ForceFieldGrid:
    domain: ForceFieldDomain
    normalized_force_x: FloatArray
    provenance: ForceFieldProvenance
    position_scale_m: float
    velocity_scale_m_s: float

    def __post_init__(self) -> None:
        values = np.asarray(self.normalized_force_x, dtype=float)
        if values.shape != self.domain.shape:
            raise ForceFieldError(f"force array shape {values.shape} does not match domain {self.domain.shape}")
        if not np.isfinite(values).all():
            raise ForceFieldError("force field contains nonfinite values")
        if self.position_scale_m <= 0 or self.velocity_scale_m_s <= 0:
            raise ForceFieldError("dimensionless coordinate scales must be positive")
        object.__setattr__(self, "normalized_force_x", values)

    @property
    def dimensionless_coordinates(self) -> dict[str, FloatArray]:
        result = {
            "x_over_hbarGamma_over_muB_gradient": self.domain.positions_m / self.position_scale_m,
            "v_over_Gamma_over_k": self.domain.velocities_m_s / self.velocity_scale_m_s,
        }
        if self.domain.detunings_gamma is not None:
            result["detuning_over_Gamma"] = self.domain.detunings_gamma.copy()
        return result


@dataclass(frozen=True)
class ForceFieldValidation:
    label: str
    normalized_rms_error_over_force_range: float
    maximum_error_over_force_range: float
    maximum_important_region_error_over_force_range: float
    holdout_count: int
    population_solves_healthy: bool
    topology_preserved: bool
    passed: bool


def _bracket(axis: FloatArray, value: float, name: str) -> tuple[int, float]:
    value = float(value)
    tolerance = 16 * np.finfo(float).eps * max(1.0, abs(axis[0]), abs(axis[-1]))
    if value < axis[0] - tolerance or value > axis[-1] + tolerance:
        raise ForceFieldDomainError(
            f"{name}={value} is outside [{axis[0]}, {axis[-1]}]; extrapolation is disabled"
        )
    value = min(max(value, float(axis[0])), float(axis[-1]))
    if value == axis[-1]:
        return axis.size - 2, 1.0
    index = int(np.searchsorted(axis, value, side="right") - 1)
    index = max(0, min(index, axis.size - 2))
    fraction = (value - axis[index]) / (axis[index + 1] - axis[index])
    return index, float(fraction)


class InterpolatedForceField:
    """Bilinear/post or trilinear/pre interpolation with no extrapolation."""

    def __init__(self, grid: ForceFieldGrid):
        self.grid = grid
        expected = "trilinear" if grid.domain.detunings_gamma is not None else "bilinear"
        if grid.provenance.interpolation_method != expected:
            raise ForceFieldError(f"{grid.provenance.field_kind} requires {expected} interpolation")

    def force_normalized(self, x_m: float, vx_m_s: float, detuning_gamma: float | None = None) -> float:
        domain, values = self.grid.domain, self.grid.normalized_force_x
        ix, tx = _bracket(domain.positions_m, x_m, "x_m")
        iv, tv = _bracket(domain.velocities_m_s, vx_m_s, "vx_m_s")
        if domain.detunings_gamma is None:
            if detuning_gamma is not None:
                raise ForceFieldError("post-handoff field does not accept a detuning coordinate")
            corners = values[ix : ix + 2, iv : iv + 2]
            return float(
                (1 - tx) * (1 - tv) * corners[0, 0]
                + tx * (1 - tv) * corners[1, 0]
                + (1 - tx) * tv * corners[0, 1]
                + tx * tv * corners[1, 1]
            )
        if detuning_gamma is None:
            raise ForceFieldError("pre-handoff field requires an explicit detuning coordinate")
        idelta, td = _bracket(domain.detunings_gamma, detuning_gamma, "detuning_gamma")
        result = 0.0
        for ax, wx in ((0, 1 - tx), (1, tx)):
            for av, wv in ((0, 1 - tv), (1, tv)):
                for ad, wd in ((0, 1 - td), (1, td)):
                    result += wx * wv * wd * values[ix + ax, iv + av, idelta + ad]
        return float(result)


@dataclass(frozen=True)
class SeparatedHandoffForceFields:
    pre: InterpolatedForceField
    post: InterpolatedForceField
    handoff_time_s: float

    def __post_init__(self) -> None:
        if self.pre.grid.provenance.field_kind != "pre_handoff_chirp_3":
            raise ForceFieldError("pre field has the wrong optical-system provenance")
        if self.post.grid.provenance.field_kind != "post_handoff_trap_3_plus_1":
            raise ForceFieldError("post field has the wrong optical-system provenance")
        if self.handoff_time_s <= 0:
            raise ForceFieldError("handoff time must be positive")

    def force_normalized(self, t_s: float, x_m: float, vx_m_s: float, detuning_gamma: float) -> float:
        if t_s < self.handoff_time_s:
            return self.pre.force_normalized(x_m, vx_m_s, detuning_gamma)
        return self.post.force_normalized(x_m, vx_m_s)


def save_force_field_cache(grid: ForceFieldGrid, npz_path: Path, metadata_path: Path, *, validation: dict | None = None) -> None:
    npz_path.parent.mkdir(parents=True, exist_ok=True)
    if not all(stamp in npz_path.name and stamp in metadata_path.name for stamp in (
        "PROVISIONAL", "NOT_RODRIGUEZ_REPLICATION", "FORCE_FIELD_INTERPOLATION_VALIDATION_ONLY"
    )):
        raise ForceFieldError("cache filenames must carry all provisional warning stamps")
    arrays = {
        "positions_m": grid.domain.positions_m,
        "velocities_m_s": grid.domain.velocities_m_s,
        "normalized_force_x": grid.normalized_force_x,
        **grid.dimensionless_coordinates,
    }
    if grid.domain.detunings_gamma is not None:
        arrays["detunings_gamma"] = grid.domain.detunings_gamma
    np.savez_compressed(npz_path, **arrays)
    metadata = {
        "label": FORCE_FIELD_LABEL,
        "title": f"{FORCE_FIELD_LABEL} {grid.provenance.field_kind} cache metadata",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "cache_key": grid.provenance.cache_key,
        "npz_filename": npz_path.name,
        "npz_sha256": sha256(npz_path.read_bytes()).hexdigest(),
        "force_array_name": "normalized_force_x",
        "force_unit": "hbar*k*Gamma",
        "canonical_values_are_si_acceleration": False,
        "provenance": asdict(grid.provenance),
        "shape": list(grid.domain.shape),
        "equilibrium_solve_count": grid.domain.equilibrium_solve_count,
        "position_scale_m": grid.position_scale_m,
        "velocity_scale_m_s": grid.velocity_scale_m_s,
        "validation": validation,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")


def load_force_field_cache(npz_path: Path, metadata_path: Path, expected: ForceFieldProvenance) -> ForceFieldGrid:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("cache_key") != expected.cache_key:
        raise ForceFieldCacheMismatchError("force-field cache provenance hash differs; rebuild required")
    if metadata.get("npz_sha256") != sha256(npz_path.read_bytes()).hexdigest():
        raise ForceFieldCacheMismatchError("force-field NPZ content hash differs; rebuild required")
    with np.load(npz_path) as arrays:
        detunings = arrays["detunings_gamma"] if "detunings_gamma" in arrays.files else None
        domain = ForceFieldDomain(arrays["positions_m"], arrays["velocities_m_s"], detunings)
        values = arrays["normalized_force_x"]
    return ForceFieldGrid(
        domain=domain,
        normalized_force_x=values,
        provenance=expected,
        position_scale_m=float(metadata["position_scale_m"]),
        velocity_scale_m_s=float(metadata["velocity_scale_m_s"]),
    )
