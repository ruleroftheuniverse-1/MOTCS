"""Strict factory for the Run 009D-accepted provisional Track P backend."""

from __future__ import annotations

from dataclasses import dataclass

from .conventions import GroundZeemanConvention
from .excited_hyperfine import ExcitedHyperfineModel, SourceAlignedSplittingCase
from .excited_zeeman import ExcitedZeemanModel
from .mgf_backend import ApproximationMode, MgFBackendCapabilityError
from .rateeq_backend import ProvisionalPylcpRateEquationBackend, RateEquationBackendConfig
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
