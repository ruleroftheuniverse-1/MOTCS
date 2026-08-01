"""Opt-in Track P pylcp rate-equation static force backend.

This is physics-bearing within a deliberately provisional scope. It uses the
collapsed pylcp A-state approximation and must never be represented as an exact
MgF or Rodriguez-valid backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray
import pylcp

from .conventions import (
    GroundZeemanConvention,
    PaperHelicityTranslation,
    paper_helicity_to_pylcp_pol,
    translate_xstate_ground_muq_for_pylcp,
)
from .force_units import build_mgf_force_unit_audit
from .excited_zeeman import (
    ExcitedZeemanModel,
    ExcitedZeemanOperator,
    build_excited_zeeman_operator,
)
from .gaussian_beams import GaussianBeamSet
from .geometry import MOT_BEAM_DIRECTIONS, quadrupole_field
from .mgf_backend import (
    ApproximateMgFHamiltonian,
    ApproximationMode,
    MgFBackendCapabilityError,
    build_mgf_hamiltonian_from_sources,
)
from .policies import COMPONENT_ORDER, PolicySample
from .spectroscopy import LINEWIDTH_MHZ
from .tracks import ProjectTrack


FloatArray = NDArray[np.float64]
BeamMode = Literal["plane_wave", "elliptical_gaussian"]
RATEEQ_STATIC_LABEL = (
    "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_PYLCP_RATEEQ_STATIC_VALIDATION_ONLY"
)


class ProvisionalForceBackendMode(str, Enum):
    PYLCP_RATE_EQUATION = "pylcp_rate_equation"


@dataclass(frozen=True)
class RateEquationBackendConfig:
    explicit_provisional_opt_in: bool = False
    track: ProjectTrack = ProjectTrack.PROVISIONAL
    approximation_mode: ApproximationMode = ApproximationMode.NONE
    backend_mode: ProvisionalForceBackendMode = (
        ProvisionalForceBackendMode.PYLCP_RATE_EQUATION
    )
    magnetic_gradient_t_m: float = 0.2
    svd_eps: float = 1.0e-10
    paper_helicity_translation: PaperHelicityTranslation = (
        PaperHelicityTranslation.DIRECT_BEAM_RELATIVE
    )
    ground_zeeman_convention: GroundZeemanConvention = (
        GroundZeemanConvention.PROJECT_ENERGY_SLOPE_CORRECTED
    )
    excited_zeeman_model: ExcitedZeemanModel = (
        ExcitedZeemanModel.PYLCP_COLLAPSED_DEFAULT
    )

    def __post_init__(self) -> None:
        if not self.explicit_provisional_opt_in:
            raise MgFBackendCapabilityError(
                "pylcp rate-equation backend requires explicit provisional opt-in"
            )
        if self.track is not ProjectTrack.PROVISIONAL:
            raise MgFBackendCapabilityError(
                "pylcp rate-equation backend is available only on Track P"
            )
        if self.approximation_mode is not ApproximationMode.COLLAPSED_PYLCP_ASTATE:
            raise MgFBackendCapabilityError(
                "pylcp rate-equation backend requires "
                "ApproximationMode.COLLAPSED_PYLCP_ASTATE"
            )
        if not np.isfinite(self.magnetic_gradient_t_m) or self.magnetic_gradient_t_m == 0:
            raise ValueError("magnetic gradient must be finite and nonzero")
        if not np.isfinite(self.svd_eps) or self.svd_eps <= 0:
            raise ValueError("svd_eps must be finite and positive")


@dataclass(frozen=True)
class RateEquationBackendStatus:
    label: str
    title: str
    track: ProjectTrack
    backend_mode: str
    approximation_mode: str
    paper_helicity_translation: str
    ground_zeeman_convention: str
    ground_magnetic_moment_correction_applied: bool
    ground_magnetic_moment_correction_count: int
    ground_magnetic_moment_correction_location: str
    downstream_zeeman_sign_correction_count: int
    excited_zeeman_model: str
    excited_zeeman_model_application_count: int
    excited_zeeman_model_application_location: str
    excited_zeeman_override_applied: bool
    excited_zeeman_source: str
    force_model: str
    physics_valid: bool
    physics_scope: str
    static_force_ready: bool
    trajectory_force_ready: bool
    replication_valid: bool
    force_unit: str
    warnings: tuple[str, ...]
    omitted_terms: tuple[str, ...]
    collapsed_terms: tuple[str, ...]
    supersedes_run_outputs: str


@dataclass(frozen=True)
class LaserComponentSpec:
    component_id: int
    detuning_gamma: float
    pylcp_carrier_detuning_gamma: float
    peak_saturation: float
    polarization: str
    pylcp_helicity: int
    enabled: bool
    active: bool
    addressed_role: str
    policy_name: str
    policy_time_s: float


@dataclass(frozen=True)
class PhysicalBeamSpec:
    name: str
    direction: tuple[float, float, float]
    beam_mode: BeamMode
    components: tuple[LaserComponentSpec, ...]


@dataclass(frozen=True)
class RateEquationOpticalSystem:
    label: str
    title: str
    beam_mode: BeamMode
    policy_name: str
    policy_time_s: float
    physical_beams: tuple[PhysicalBeamSpec, ...]
    pylcp_beams: pylcp.laserBeams
    pylcp_beam_index: tuple[tuple[str, int], ...]
    combined_solve: bool
    per_beam_envelope_before_solve: bool
    post_sum_envelope_used: bool
    component_order: tuple[int, int, int, int]

    @property
    def active_component_count(self) -> int:
        return len(self.pylcp_beam_index)


@dataclass(frozen=True)
class RateEquationForceResult:
    normalized_force: FloatArray
    equilibrium_populations: FloatArray
    per_laser_normalized_force: FloatArray
    per_physical_beam_normalized_force: dict[str, FloatArray]
    per_component_normalized_force: dict[int, FloatArray]
    pumping_rate_matrices: FloatArray
    per_laser_pumping_rate_sum: FloatArray
    magnetic_force: FloatArray
    population_sum: float
    population_minimum: float
    steady_state_residual_linf: float
    steady_state_residual_l2: float
    singular_values: FloatArray
    nullspace_dimension: int
    svd_eps: float
    equilibrium_solver: str
    singular_solver_fallback_used: bool
    optical_system: RateEquationOpticalSystem
    status: RateEquationBackendStatus


class _PerBeamSaturation:
    """Callable accepted by pylcp that evaluates one physical beam envelope."""

    def __init__(self, peak_saturation: float, envelope_beam: Any):
        self.peak_saturation = float(peak_saturation)
        self.envelope_beam = envelope_beam

    def __call__(self, R):
        return self.peak_saturation * float(self.envelope_beam.envelope(R))


def _block_matrices(hamiltonian: pylcp.hamiltonian, index: int) -> tuple[np.ndarray, np.ndarray]:
    block = hamiltonian.blocks[index, index]
    if not isinstance(block, tuple) or len(block) != 2:
        raise MgFBackendCapabilityError("collapsed Hamiltonian lacks H0/mu_q blocks")
    return np.asarray(block[0].matrix), np.asarray(block[1].matrix)


def _normalized_hamiltonian(
    source: ApproximateMgFHamiltonian,
    ground_zeeman_convention: GroundZeemanConvention,
    excited_zeeman_model: ExcitedZeemanModel,
) -> tuple[pylcp.hamiltonian, ExcitedZeemanOperator]:
    """Apply the official CaF-example MHz/Gamma normalization convention."""

    linewidth_mhz = LINEWIDTH_MHZ.require()
    ground_h0, ground_muq = _block_matrices(source.hamiltonian, 0)
    excited_h0, excited_muq = _block_matrices(source.hamiltonian, 1)
    dipole = np.asarray(source.hamiltonian.blocks[0, 1].matrix)
    translated_ground_muq = translate_xstate_ground_muq_for_pylcp(
        ground_muq, convention=ground_zeeman_convention
    )
    excited_operator = build_excited_zeeman_operator(
        excited_zeeman_model,
        basis=source.validation_model.excited_basis,
        pylcp_collapsed_tensor_mhz_per_gauss=excited_muq,
    )
    hamiltonian = pylcp.hamiltonian(
        np.asarray(np.real_if_close(ground_h0), dtype=float) / linewidth_mhz,
        np.asarray(np.real_if_close(excited_h0), dtype=float) / linewidth_mhz,
        np.asarray(np.real_if_close(translated_ground_muq), dtype=float)
        / linewidth_mhz,
        np.asarray(
            np.real_if_close(excited_operator.tensor_mhz_per_gauss), dtype=float
        ) / linewidth_mhz,
        np.asarray(np.real_if_close(dipole), dtype=float),
        mass=1.0,
        muB=1.0,
        gamma=1.0,
        k=1.0,
    )
    return hamiltonian, excited_operator


class ProvisionalPylcpRateEquationBackend:
    """Combined-population pylcp rate-equation solver for static Track P calls."""

    def __init__(self, config: RateEquationBackendConfig):
        self.config = config
        source = build_mgf_hamiltonian_from_sources(
            approximation_mode=config.approximation_mode
        )
        if not isinstance(source, ApproximateMgFHamiltonian):
            raise MgFBackendCapabilityError("collapsed approximation did not return its provenance wrapper")
        self.source_backend = source
        self.hamiltonian, self.excited_zeeman_operator = _normalized_hamiltonian(
            source, config.ground_zeeman_convention, config.excited_zeeman_model
        )
        self.force_units = build_mgf_force_unit_audit()
        self.status = RateEquationBackendStatus(
            label=RATEEQ_STATIC_LABEL,
            title=f"{RATEEQ_STATIC_LABEL} backend status",
            track=ProjectTrack.PROVISIONAL,
            backend_mode=config.backend_mode.value,
            approximation_mode=config.approximation_mode.value,
            paper_helicity_translation=config.paper_helicity_translation.value,
            ground_zeeman_convention=config.ground_zeeman_convention.value,
            ground_magnetic_moment_correction_applied=(
                config.ground_zeeman_convention
                is GroundZeemanConvention.PROJECT_ENERGY_SLOPE_CORRECTED
            ),
            ground_magnetic_moment_correction_count=(
                1
                if config.ground_zeeman_convention
                is GroundZeemanConvention.PROJECT_ENERGY_SLOPE_CORRECTED
                else 0
            ),
            ground_magnetic_moment_correction_location="Hamiltonian boundary",
            downstream_zeeman_sign_correction_count=0,
            excited_zeeman_model=config.excited_zeeman_model.value,
            excited_zeeman_model_application_count=(
                self.excited_zeeman_operator.model_application_count
            ),
            excited_zeeman_model_application_location=(
                self.excited_zeeman_operator.application_location
            ),
            excited_zeeman_override_applied=(
                self.excited_zeeman_operator.override_applied
            ),
            excited_zeeman_source=self.excited_zeeman_operator.source,
            force_model="pylcp_rate_equation_combined_equilibrium_populations",
            physics_valid=True,
            physics_scope="static provisional rate-equation validation only",
            static_force_ready=True,
            trajectory_force_ready=False,
            replication_valid=False,
            force_unit="hbar*k*Gamma",
            warnings=source.provenance.warnings
            + (
                "PYLCP_RATEEQ_STATIC_VALIDATION_ONLY: no trajectories or capture result.",
                "Helicity strings are interpreted relative to each beam k-vector using pylcp pol=+1/-1.",
                "Component carrier offsets use the upper collapsed excited level and explicit addressed-role ground energies.",
                "Ground Xstate mu_q is translated once at the pylcp Hamiltonian boundary according to the named convention mode.",
                "The excited Zeeman tensor is selected by one explicit named model at the Hamiltonian boundary.",
            ) + self.excited_zeeman_operator.warnings,
            omitted_terms=source.provenance.omitted_terms,
            collapsed_terms=source.provenance.collapsed_terms,
            supersedes_run_outputs=(
                "Run 008B supersedes physical interpretation of force-dependent Runs 001-008"
            ),
        )
        gradient_gauss_per_m = config.magnetic_gradient_t_m * 1.0e4

        def field(R):
            tesla = quadrupole_field(R, config.magnetic_gradient_t_m)
            return np.asarray(tesla, dtype=float) * 1.0e4

        self.mag_field = pylcp.magField(field, eps=1.0e-6)
        self.gradient_gauss_per_m = gradient_gauss_per_m
        self._role_ground_energy = self._ground_role_energies()
        excited_h0, _ = _block_matrices(self.hamiltonian, 1)
        self._excited_reference_energy = float(np.max(np.real(np.diag(excited_h0))))

    def _ground_role_energies(self) -> dict[str, float]:
        diagonal = np.real(np.diag(_block_matrices(self.hamiltonian, 0)[0]))
        result: dict[str, float] = {}
        for level in self.source_backend.validation_model.ground_levels:
            members = [
                state.index
                for state in self.source_backend.validation_model.ground_eigenstates
                if np.isclose(state.relative_energy_mhz, level.relative_energy_mhz, atol=1e-7)
            ]
            result[level.label] = float(np.mean(diagonal[members]))
        result["upper_F1_F2_mean"] = 0.5 * (
            result["upper_F1"] + result["F2"]
        )
        result["upper_F1_F2_mean_confinement"] = result["upper_F1_F2_mean"]
        return result

    def _component_spec(self, component: Any, policy_name: str, time_s: float) -> LaserComponentSpec:
        if component.role not in self._role_ground_energy:
            raise ValueError(f"unknown addressed role {component.role!r}")
        helicity = paper_helicity_to_pylcp_pol(
            component.polarization,
            translation=self.config.paper_helicity_translation,
        )
        carrier = (
            self._excited_reference_energy
            - self._role_ground_energy[component.role]
            + float(component.detuning_gamma)
        )
        return LaserComponentSpec(
            component_id=int(component.component_id),
            detuning_gamma=float(component.detuning_gamma),
            pylcp_carrier_detuning_gamma=carrier,
            peak_saturation=float(component.saturation),
            polarization=component.polarization,
            pylcp_helicity=helicity,
            enabled=bool(component.enabled),
            active=bool(component.active),
            addressed_role=component.role,
            policy_name=policy_name,
            policy_time_s=float(time_s),
        )

    def build_optical_system(
        self,
        sample: PolicySample,
        *,
        policy_name: str,
        beam_mode: BeamMode,
        gaussian_beam_set: GaussianBeamSet | None = None,
    ) -> RateEquationOpticalSystem:
        if tuple(sample.component_order) != COMPONENT_ORDER:
            raise ValueError(f"component order must remain exactly {COMPONENT_ORDER}")
        if beam_mode == "elliptical_gaussian" and gaussian_beam_set is None:
            raise ValueError("Gaussian rate-equation mode requires a GaussianBeamSet")
        if beam_mode == "plane_wave" and gaussian_beam_set is not None:
            raise ValueError("plane-wave rate-equation mode cannot carry Gaussian envelopes")
        gaussian_by_name = (
            {} if gaussian_beam_set is None else {beam.name: beam for beam in gaussian_beam_set.beams}
        )
        pylcp_beams = pylcp.laserBeams()
        physical_specs: list[PhysicalBeamSpec] = []
        beam_index: list[tuple[str, int]] = []
        for beam_name, direction_values in MOT_BEAM_DIRECTIONS.items():
            direction = np.asarray(direction_values, dtype=float)
            components = tuple(
                self._component_spec(component, policy_name, sample.time_s)
                for component in sample.components
            )
            for component in components:
                if not component.active:
                    continue
                if beam_mode == "plane_wave":
                    beam = pylcp.infinitePlaneWaveBeam(
                        kvec=direction,
                        pol=component.pylcp_helicity,
                        s=component.peak_saturation,
                        delta=component.pylcp_carrier_detuning_gamma,
                    )
                else:
                    beam = pylcp.laserBeam(
                        kvec=direction,
                        pol=component.pylcp_helicity,
                        s=_PerBeamSaturation(
                            component.peak_saturation, gaussian_by_name[beam_name]
                        ),
                        delta=component.pylcp_carrier_detuning_gamma,
                    )
                pylcp_beams.add_laser(beam)
                beam_index.append((beam_name, component.component_id))
            physical_specs.append(
                PhysicalBeamSpec(
                    name=beam_name,
                    direction=tuple(float(value) for value in direction),
                    beam_mode=beam_mode,
                    components=components,
                )
            )
        return RateEquationOpticalSystem(
            label=RATEEQ_STATIC_LABEL,
            title=f"{RATEEQ_STATIC_LABEL} {policy_name} {beam_mode} optical system",
            beam_mode=beam_mode,
            policy_name=policy_name,
            policy_time_s=float(sample.time_s),
            physical_beams=tuple(physical_specs),
            pylcp_beams=pylcp_beams,
            pylcp_beam_index=tuple(beam_index),
            combined_solve=True,
            per_beam_envelope_before_solve=beam_mode == "elliptical_gaussian",
            post_sum_envelope_used=False,
            component_order=tuple(sample.component_order),
        )

    def force_at(
        self,
        position_m: FloatArray,
        velocity_m_s: FloatArray,
        optical_system: RateEquationOpticalSystem,
        *,
        collect_solver_diagnostics: bool = False,
        svd_eps: float | None = None,
    ) -> RateEquationForceResult:
        position = np.asarray(position_m, dtype=float)
        velocity = np.asarray(velocity_m_s, dtype=float)
        if position.shape != (3,) or velocity.shape != (3,):
            raise ValueError("position and velocity must be finite 3-vectors")
        if not np.isfinite(position).all() or not np.isfinite(velocity).all():
            raise ValueError("position and velocity must be finite 3-vectors")
        solver_eps = self.config.svd_eps if svd_eps is None else float(svd_eps)
        if not np.isfinite(solver_eps) or solver_eps <= 0:
            raise ValueError("svd_eps must be finite and positive")
        normalized_velocity = velocity / (
            self.force_units.linewidth_rad_s / self.force_units.wave_number_rad_m
        )
        equation = pylcp.rateeq(
            optical_system.pylcp_beams,
            self.mag_field,
            self.hamiltonian,
            include_mag_forces=False,
            svd_eps=solver_eps,
            r0=position,
            v0=normalized_velocity,
        )
        if collect_solver_diagnostics:
            populations, evolution_matrix, pumping_rates = equation.equilibrium_populations(
                position,
                normalized_velocity,
                t=0.0,
                return_details=True,
            )
            force, per_laser_dict, magnetic_force = equation.force(
                position, 0.0, populations, return_details=True
            )
            residual = np.asarray(evolution_matrix) @ np.asarray(populations)
            singular_values = np.linalg.svd(evolution_matrix, compute_uv=False)
            residual_linf = float(np.linalg.norm(residual, ord=np.inf))
            residual_l2 = float(np.linalg.norm(residual))
            nullspace_dimension = int(
                np.count_nonzero(singular_values <= solver_eps)
            )
        else:
            force, per_laser_dict, populations, pumping_rates, magnetic_force = (
                equation.find_equilibrium_force(return_details=True)
            )
            singular_values = np.empty(0, dtype=float)
            residual_linf = float("nan")
            residual_l2 = float("nan")
            nullspace_dimension = -1
        if not np.isfinite(populations).all() or not np.isfinite(force).all():
            raise RuntimeError("pylcp rate-equation solution was nonfinite")
        per_laser = np.asarray(per_laser_dict["g->e"], dtype=float)
        pumping_matrix = np.asarray(pumping_rates["g->e"], dtype=float)
        per_beam = {name: np.zeros(3, dtype=float) for name in MOT_BEAM_DIRECTIONS}
        per_component = {component: np.zeros(3, dtype=float) for component in COMPONENT_ORDER}
        for index, (beam_name, component_id) in enumerate(optical_system.pylcp_beam_index):
            per_beam[beam_name] += per_laser[:, index]
            per_component[component_id] += per_laser[:, index]
        return RateEquationForceResult(
            normalized_force=np.asarray(force, dtype=float),
            equilibrium_populations=np.asarray(populations, dtype=float),
            per_laser_normalized_force=per_laser,
            per_physical_beam_normalized_force=per_beam,
            per_component_normalized_force=per_component,
            pumping_rate_matrices=pumping_matrix,
            per_laser_pumping_rate_sum=np.sum(pumping_matrix, axis=(1, 2)),
            magnetic_force=np.asarray(magnetic_force, dtype=float),
            population_sum=float(np.sum(populations)),
            population_minimum=float(np.min(populations)),
            steady_state_residual_linf=residual_linf,
            steady_state_residual_l2=residual_l2,
            singular_values=np.asarray(singular_values, dtype=float),
            nullspace_dimension=nullspace_dimension,
            svd_eps=solver_eps,
            equilibrium_solver="pylcp_svd_nullspace",
            singular_solver_fallback_used=False,
            optical_system=optical_system,
            status=self.status,
        )
