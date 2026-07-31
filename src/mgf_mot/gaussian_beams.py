"""Rodriguez-style finite elliptical Gaussian beam geometry for Track P.

This module implements only the stated transverse intensity envelopes. It does
not infer power allocation, model longitudinal diffraction, or open an exact
force path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import math
import numpy as np
import yaml

from .geometry import MOT_BEAM_DIRECTIONS
from .tracks import ProjectTrack

Vector3 = tuple[float, float, float]


def _vector3(value: tuple[float, float, float], label: str) -> np.ndarray:
    vector = np.asarray(value, dtype=float)
    if vector.shape != (3,) or not np.isfinite(vector).all():
        raise ValueError(f"{label} must be a finite 3-vector")
    return vector


def _unit_vector(value: Vector3, label: str) -> np.ndarray:
    vector = _vector3(value, label)
    norm = float(np.linalg.norm(vector))
    if not np.isclose(norm, 1.0, atol=1e-12, rtol=0.0):
        raise ValueError(f"{label} must be normalized")
    return vector


@dataclass(frozen=True)
class GaussianGeometryProvenance:
    """Source and project status carried by every finite-beam object."""

    track: ProjectTrack
    replication_valid: bool
    source: str
    radius_convention: str
    longitudinal_model: str
    total_power_w: float
    power_allocation_status: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class GaussianEnvelopeConfig:
    """Source geometry and unresolved power-allocation metadata."""

    wxy_m: float
    wz_m: float
    total_power_w: float
    reported_peak_saturation_vectors: Mapping[str, tuple[float, float, float, float]]
    source: str
    radius_convention: str = "1/e^2_intensity_radius"
    longitudinal_model: str = "none"
    equal_peak_intensity: bool = True
    power_allocation_status: str = "unresolved_no_conversion"

    def __post_init__(self) -> None:
        for name in ("wxy_m", "wz_m", "total_power_w"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        if self.radius_convention != "1/e^2_intensity_radius":
            raise ValueError("radius convention must be 1/e^2_intensity_radius")
        if self.longitudinal_model != "none":
            raise ValueError("no longitudinal diffraction model is supported")
        if not self.equal_peak_intensity:
            raise ValueError("Rodriguez baseline requires equal peak beam intensity")
        if self.power_allocation_status != "unresolved_no_conversion":
            raise ValueError("total power must not be converted through an inferred allocation")
        if not self.reported_peak_saturation_vectors:
            raise ValueError("reported peak saturation vectors must be explicit")
        for name, values in self.reported_peak_saturation_vectors.items():
            if len(values) != 4 or not np.isfinite(values).all():
                raise ValueError(f"peak saturation vector {name!r} must have four finite values")
            if any(value < 0.0 for value in values):
                raise ValueError("peak saturation values must be nonnegative")

    @property
    def provenance(self) -> GaussianGeometryProvenance:
        return GaussianGeometryProvenance(
            track=ProjectTrack.PROVISIONAL,
            replication_valid=False,
            source=self.source,
            radius_convention=self.radius_convention,
            longitudinal_model=self.longitudinal_model,
            total_power_w=self.total_power_w,
            power_allocation_status=self.power_allocation_status,
            warnings=(
                "PROVISIONAL Gaussian geometry for engineering validation only.",
                "NOT_RODRIGUEZ_REPLICATION: exact MgF force readiness remains blocked.",
                "Reported peak saturation vectors are used directly.",
                "Total 1 W power is metadata only; no per-beam or per-component allocation is inferred.",
            ),
        )


@dataclass(frozen=True)
class EllipticalGaussianBeam:
    """One right-handed transverse beam frame and its intensity envelope."""

    name: str
    pair_name: str
    propagation_direction: Vector3
    transverse_u: Vector3
    transverse_v: Vector3
    radius_u_m: float
    radius_v_m: float
    center_m: Vector3
    peak_intensity_multiplier: float
    component_saturations: tuple[float, float, float, float]
    provenance: GaussianGeometryProvenance

    def __post_init__(self) -> None:
        k = _unit_vector(self.propagation_direction, "propagation_direction")
        u = _unit_vector(self.transverse_u, "transverse_u")
        v = _unit_vector(self.transverse_v, "transverse_v")
        if not np.isclose(np.dot(k, u), 0.0, atol=1e-12, rtol=0.0):
            raise ValueError("propagation_direction and transverse_u must be orthogonal")
        if not np.isclose(np.dot(k, v), 0.0, atol=1e-12, rtol=0.0):
            raise ValueError("propagation_direction and transverse_v must be orthogonal")
        if not np.isclose(np.dot(u, v), 0.0, atol=1e-12, rtol=0.0):
            raise ValueError("transverse axes must be orthogonal")
        if not np.allclose(np.cross(u, v), k, atol=1e-12, rtol=0.0):
            raise ValueError("beam frame must use the right-handed convention u x v = k")
        for name in ("radius_u_m", "radius_v_m", "peak_intensity_multiplier"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        _vector3(self.center_m, "center_m")
        if len(self.component_saturations) != 4:
            raise ValueError("component_saturations must contain four values")
        if not np.isfinite(self.component_saturations).all():
            raise ValueError("component_saturations must be finite")
        if any(value < 0.0 for value in self.component_saturations):
            raise ValueError("component_saturations must be nonnegative")
        if self.provenance.track is not ProjectTrack.PROVISIONAL:
            raise ValueError("Gaussian beam provenance must be Track P provisional")
        if self.provenance.replication_valid:
            raise ValueError("Gaussian beam geometry must not be replication-valid")

    def envelope(self, position_m: Vector3 | np.ndarray) -> float:
        """Return I(r)/I0 with no longitudinal dependence."""
        displacement = _vector3(tuple(position_m), "position_m") - _vector3(
            self.center_m, "center_m"
        )
        u_coordinate = float(np.dot(displacement, self.transverse_u))
        v_coordinate = float(np.dot(displacement, self.transverse_v))
        exponent = -2.0 * (
            (u_coordinate / self.radius_u_m) ** 2
            + (v_coordinate / self.radius_v_m) ** 2
        )
        value = float(self.peak_intensity_multiplier * math.exp(exponent))
        if not math.isfinite(value) or value < 0.0:
            raise ValueError("Gaussian envelope evaluation was nonfinite")
        return value


@dataclass(frozen=True)
class GaussianBeamSet:
    """The six Rodriguez beams with explicit counterpropagating pairs."""

    beams: tuple[
        EllipticalGaussianBeam,
        EllipticalGaussianBeam,
        EllipticalGaussianBeam,
        EllipticalGaussianBeam,
        EllipticalGaussianBeam,
        EllipticalGaussianBeam,
    ]
    config: GaussianEnvelopeConfig

    def __post_init__(self) -> None:
        expected_names = tuple(MOT_BEAM_DIRECTIONS)
        names = tuple(beam.name for beam in self.beams)
        if names != expected_names:
            raise ValueError(f"beam order must be exactly {expected_names}")
        if any(
            not np.allclose(
                beam.propagation_direction,
                MOT_BEAM_DIRECTIONS[beam.name],
                atol=1e-12,
                rtol=0.0,
            )
            for beam in self.beams
        ):
            raise ValueError("beam directions do not match MOT_BEAM_DIRECTIONS")
        if any(
            not np.isclose(
                beam.peak_intensity_multiplier,
                self.beams[0].peak_intensity_multiplier,
                atol=0.0,
                rtol=0.0,
            )
            for beam in self.beams
        ):
            raise ValueError("all six beams must have equal peak intensity")
        for pair_name in ("x_prime", "y_prime", "z"):
            forward, backward = self.pair(pair_name)
            if not np.allclose(
                forward.propagation_direction,
                -np.asarray(backward.propagation_direction),
                atol=1e-12,
                rtol=0.0,
            ):
                raise ValueError(f"{pair_name} directions are not counterpropagating")

    @property
    def provenance(self) -> GaussianGeometryProvenance:
        return self.config.provenance

    def pair(
        self, pair_name: str
    ) -> tuple[EllipticalGaussianBeam, EllipticalGaussianBeam]:
        members = tuple(beam for beam in self.beams if beam.pair_name == pair_name)
        if len(members) != 2:
            raise ValueError(f"pair {pair_name!r} must contain exactly two beams")
        return members  # type: ignore[return-value]

    def envelopes(self, position_m: Vector3 | np.ndarray) -> dict[str, float]:
        return {beam.name: beam.envelope(position_m) for beam in self.beams}

    def mean_envelope(self, position_m: Vector3 | np.ndarray) -> float:
        """Return the equal-peak arithmetic mean used by Track P force plumbing."""
        values = np.asarray(tuple(self.envelopes(position_m).values()), dtype=float)
        return float(np.mean(values))


def load_gaussian_envelope_config(path: str | Path) -> GaussianEnvelopeConfig:
    with Path(path).open("r", encoding="utf-8") as handle:
        data: dict[str, Any] = yaml.safe_load(handle)
    geometry = data["gaussian_geometry"]
    if geometry["wxy"]["unit"] != "mm" or geometry["wz"]["unit"] != "mm":
        raise ValueError("Gaussian radii must be provided explicitly in mm")
    if data["total_laser_power"]["unit"] != "W":
        raise ValueError("total laser power unit must be W")
    vectors = {
        str(name): tuple(float(value) for value in values)
        for name, values in data["reported_peak_saturation_vectors"].items()
    }
    return GaussianEnvelopeConfig(
        wxy_m=float(geometry["wxy"]["value"]) * 1e-3,
        wz_m=float(geometry["wz"]["value"]) * 1e-3,
        total_power_w=float(data["total_laser_power"]["value"]),
        reported_peak_saturation_vectors=vectors,  # type: ignore[arg-type]
        source=str(data["source"]),
        radius_convention=str(geometry["radius_convention"]),
        longitudinal_model=str(geometry["longitudinal_model"]),
        equal_peak_intensity=bool(geometry["equal_peak_intensity"]),
        power_allocation_status=str(data["total_laser_power"]["allocation_status"]),
    )


def build_rodriguez_gaussian_beam_set(
    config: GaussianEnvelopeConfig,
    component_saturations: tuple[float, float, float, float],
) -> GaussianBeamSet:
    """Build all six source-geometry frames for an explicit peak vector."""
    if component_saturations not in tuple(
        config.reported_peak_saturation_vectors.values()
    ):
        raise ValueError(
            "component saturations must match an explicitly reported peak vector"
        )
    inv_sqrt_2 = 1.0 / math.sqrt(2.0)
    frames: dict[str, tuple[Vector3, Vector3, str]] = {
        "+x_prime": ((-inv_sqrt_2, inv_sqrt_2, 0.0), (0.0, 0.0, 1.0), "x_prime"),
        "-x_prime": ((inv_sqrt_2, -inv_sqrt_2, 0.0), (0.0, 0.0, 1.0), "x_prime"),
        "+y_prime": ((-inv_sqrt_2, -inv_sqrt_2, 0.0), (0.0, 0.0, 1.0), "y_prime"),
        "-y_prime": ((inv_sqrt_2, inv_sqrt_2, 0.0), (0.0, 0.0, 1.0), "y_prime"),
        "+z": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), "z"),
        "-z": ((-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), "z"),
    }
    beams = tuple(
        EllipticalGaussianBeam(
            name=name,
            pair_name=frames[name][2],
            propagation_direction=MOT_BEAM_DIRECTIONS[name],
            transverse_u=frames[name][0],
            transverse_v=frames[name][1],
            radius_u_m=config.wxy_m,
            radius_v_m=config.wz_m,
            center_m=(0.0, 0.0, 0.0),
            peak_intensity_multiplier=1.0,
            component_saturations=component_saturations,
            provenance=config.provenance,
        )
        for name in MOT_BEAM_DIRECTIONS
    )
    return GaussianBeamSet(beams=beams, config=config)  # type: ignore[arg-type]
