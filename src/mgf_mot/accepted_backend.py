"""Strict factory for the Run 009D-accepted provisional Track P backend."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from .conventions import GroundZeemanConvention
from .excited_hyperfine import ExcitedHyperfineModel, SourceAlignedSplittingCase
from .excited_zeeman import ExcitedZeemanModel
from .mgf_backend import ApproximationMode, MgFBackendCapabilityError
from .rateeq_backend import ProvisionalPylcpRateEquationBackend, RateEquationBackendConfig
from .force_field import FORCE_FIELD_LABEL, ForceFieldProvenance
from .tracks import ProjectTrack


@dataclass(frozen=True)
class AcceptedProvisionalBackendSelection:
    track: ProjectTrack = ProjectTrack.PROVISIONAL
    ground_zeeman_convention: GroundZeemanConvention = (
        GroundZeemanConvention.PROJECT_ENERGY_SLOPE_CORRECTED
    )
    excited_zeeman_model: ExcitedZeemanModel = (
        ExcitedZeemanModel.RODRIGUEZ_EFFECTIVE_G_0P001
    )
    excited_hyperfine_model: ExcitedHyperfineModel = (
        ExcitedHyperfineModel.SOURCE_ALIGNED_EFFECTIVE_FPRIME_SPLITTING
    )
    splitting_case: SourceAlignedSplittingCase = (
        SourceAlignedSplittingCase.MID_RANGE_0P5_MHZ
    )
    splitting_interval_mhz: tuple[float, float] = (0.0, 1.0)
    splitting_note: str = (
        "0.5 MHz is the reproducible midpoint of the source-supported <1 MHz "
        "interval, not a measured value"
    )
    replication_valid: bool = False
    exact_track_blocked: bool = True
    unresolved_terms: tuple[str, ...] = (
        "independent Doppelbauer d operator in the retained/effective basis",
        "d-dependent J'=1/2 to J'=3/2 mixing",
        "exact positive-parity excited-state spectroscopy",
    )

    def validate(self) -> None:
        expected = AcceptedProvisionalBackendSelection()
        if self != expected:
            raise MgFBackendCapabilityError(
                "accepted force-field path requires the immutable Run 009D backend selection"
            )


def build_accepted_provisional_rateeq_backend(
    *,
    explicit_provisional_opt_in: bool,
    selection: AcceptedProvisionalBackendSelection | None = None,
) -> ProvisionalPylcpRateEquationBackend:
    """Build only the Run 009D-accepted backend; no collapsed choice is exposed."""

    if not explicit_provisional_opt_in:
        raise MgFBackendCapabilityError(
            "accepted force-field backend requires explicit provisional opt-in"
        )
    selected = AcceptedProvisionalBackendSelection() if selection is None else selection
    selected.validate()
    backend = ProvisionalPylcpRateEquationBackend(
        RateEquationBackendConfig(
            explicit_provisional_opt_in=True,
            track=ProjectTrack.PROVISIONAL,
            approximation_mode=ApproximationMode.COLLAPSED_PYLCP_ASTATE,
            magnetic_gradient_t_m=0.2,
            ground_zeeman_convention=selected.ground_zeeman_convention,
            excited_zeeman_model=selected.excited_zeeman_model,
            excited_hyperfine_model=selected.excited_hyperfine_model,
            excited_hyperfine_splitting_case=selected.splitting_case,
        )
    )
    if backend.status.replication_valid:
        raise MgFBackendCapabilityError("accepted Track P backend must not be replication-valid")
    if backend.status.excited_zeeman_model != selected.excited_zeeman_model.value:
        raise MgFBackendCapabilityError("accepted excited-Zeeman selection was not applied")
    if backend.status.excited_hyperfine_model != selected.excited_hyperfine_model.value:
        raise MgFBackendCapabilityError("accepted excited-hyperfine selection was not applied")
    if backend.status.excited_hyperfine_splitting_mhz != selected.splitting_case.splitting_mhz:
        raise MgFBackendCapabilityError("accepted 0.5 MHz interval midpoint was not applied")
    return backend


def accepted_force_field_source_hashes(repo_root: Path) -> tuple[tuple[str, str], ...]:
    """Return the exact backend/optics inputs covered by Run 010 cache provenance."""

    paths = (
        repo_root / "configs" / "provisional_force_field_run_010.yaml",
        repo_root / "configs" / "rodriguez_baseline_linear_chirp.yaml",
        repo_root / "configs" / "rodriguez_static_3_plus_1.yaml",
        repo_root / "configs" / "rodriguez_gaussian_baseline.yaml",
        repo_root / "src" / "mgf_mot" / "accepted_backend.py",
        repo_root / "src" / "mgf_mot" / "excited_hyperfine.py",
        repo_root / "src" / "mgf_mot" / "force_field.py",
        repo_root / "src" / "mgf_mot" / "gaussian_beams.py",
        repo_root / "src" / "mgf_mot" / "mgf_backend.py",
        repo_root / "src" / "mgf_mot" / "rateeq_backend.py",
        repo_root / "src" / "mgf_mot" / "spectroscopy.py",
    )
    return tuple(
        (path.relative_to(repo_root).as_posix(), sha256(path.read_bytes()).hexdigest())
        for path in paths
    )


def build_accepted_force_field_provenance(
    *,
    repo_root: Path,
    backend: ProvisionalPylcpRateEquationBackend,
    selection: AcceptedProvisionalBackendSelection,
    field_kind: str,
) -> ForceFieldProvenance:
    """Construct the immutable provenance expected by both Run 010 and Run 011."""

    if field_kind not in ("pre_handoff_chirp_3", "post_handoff_trap_3_plus_1"):
        raise MgFBackendCapabilityError("unknown accepted force-field kind")
    selection.validate()
    pre = field_kind == "pre_handoff_chirp_3"
    return ForceFieldProvenance(
        label=FORCE_FIELD_LABEL,
        field_kind=field_kind,  # type: ignore[arg-type]
        track="provisional",
        backend_mode=backend.status.backend_mode,
        ground_zeeman_convention=backend.status.ground_zeeman_convention,
        excited_zeeman_model=backend.status.excited_zeeman_model,
        excited_hyperfine_model=backend.status.excited_hyperfine_model,
        splitting_case=selection.splitting_case.value,
        splitting_mhz=selection.splitting_case.splitting_mhz,
        splitting_interval_mhz=selection.splitting_interval_mhz,
        splitting_note=selection.splitting_note,
        replication_valid=False,
        exact_track_blocked=True,
        unresolved_terms=selection.unresolved_terms,
        normalized_force_unit="hbar*k*Gamma",
        canonical_values_are_si_acceleration=False,
        field_gradient_t_m=0.2,
        beam_mode="elliptical_gaussian",
        component_order=(1, 2, 3, 4),
        saturation_vector=(1.45, 1.45, 2.89, 0.0) if pre else (1.45, 1.45, 2.17, 0.72),
        detuning_specification=(
            "common -8 to -1 Gamma for active components (1,2,3); component 4 parked/off"
            if pre else "(-1,-1,-1,+2) Gamma; component 4 active"
        ),
        source_hashes=accepted_force_field_source_hashes(repo_root),
        interpolation_method="trilinear" if pre else "bilinear",
    )
