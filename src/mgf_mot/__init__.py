"""Pre-force-map utilities for static MgF MOT replication."""

from .constants import MGF, RODRIGUEZ_STATIC
from .geometry import MOT_BEAM_DIRECTIONS, quadrupole_field
from .gaussian_beams import (
    EllipticalGaussianBeam,
    GaussianBeamSet,
    GaussianEnvelopeConfig,
    build_rodriguez_gaussian_beam_set,
    load_gaussian_envelope_config,
)
from .mgf_backend import (
    ApproximationMode,
    ExactBackendMode,
    analyze_mgf_exact_backend_feasibility,
    build_mgf_hamiltonian_from_sources,
    build_mgf_validation_model_from_sources,
)
from .named_protocol import (
    NamedInitialVelocity,
    RodriguezTrajectoryProtocol,
    load_rodriguez_named_trajectory_protocol,
)
from .outcomes import (
    OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL,
    OutcomeCriteria,
    OutcomeLabel,
    TrajectoryEnsembleResult,
    TrajectoryOutcome,
    classify_trajectory,
    run_trajectory_ensemble,
)
from .policies import (
    COMPONENT_ORDER,
    ChirpToTrapHandoffPolicy,
    LinearChirpPolicy,
    PolicyValidationError,
    StaticPolicy,
    load_policy,
    policy_from_config,
)
from .policy_force import (
    POLICY_FORCE_SNAPSHOT_LABEL,
    PolicyForceGridConfig,
    force_config_for_policy_sample,
    force_grid_for_policy_snapshot,
)
from .provisional_force import (
    ProvisionalForceMapConfig,
    diagnostic_configs,
    force_at,
    force_grid_1d,
)
from .tracks import BackendProvenance, ProjectTrack
from .trajectory import (
    ANALYTIC_TEST_HOOK_LABEL,
    TRAJECTORY_SCAFFOLD_LABEL,
    AnalyticIntegratorResult,
    TrajectoryConfig,
    TrajectoryInitialState,
    TrajectoryResult,
    integrate_analytic_test_trajectory,
    integrate_policy_trajectory,
)

__all__ = [
    "MGF",
    "RODRIGUEZ_STATIC",
    "MOT_BEAM_DIRECTIONS",
    "quadrupole_field",
    "EllipticalGaussianBeam",
    "GaussianBeamSet",
    "GaussianEnvelopeConfig",
    "build_rodriguez_gaussian_beam_set",
    "load_gaussian_envelope_config",
    "ApproximationMode",
    "ExactBackendMode",
    "analyze_mgf_exact_backend_feasibility",
    "build_mgf_hamiltonian_from_sources",
    "build_mgf_validation_model_from_sources",
    "NamedInitialVelocity",
    "RodriguezTrajectoryProtocol",
    "load_rodriguez_named_trajectory_protocol",
    "OUTCOME_CLASSIFICATION_SCAFFOLD_LABEL",
    "OutcomeCriteria",
    "OutcomeLabel",
    "TrajectoryEnsembleResult",
    "TrajectoryOutcome",
    "classify_trajectory",
    "run_trajectory_ensemble",
    "BackendProvenance",
    "ProjectTrack",
    "COMPONENT_ORDER",
    "ChirpToTrapHandoffPolicy",
    "LinearChirpPolicy",
    "PolicyValidationError",
    "StaticPolicy",
    "load_policy",
    "policy_from_config",
    "POLICY_FORCE_SNAPSHOT_LABEL",
    "PolicyForceGridConfig",
    "force_config_for_policy_sample",
    "force_grid_for_policy_snapshot",
    "ProvisionalForceMapConfig",
    "diagnostic_configs",
    "force_at",
    "force_grid_1d",
    "ANALYTIC_TEST_HOOK_LABEL",
    "TRAJECTORY_SCAFFOLD_LABEL",
    "AnalyticIntegratorResult",
    "TrajectoryConfig",
    "TrajectoryInitialState",
    "TrajectoryResult",
    "integrate_analytic_test_trajectory",
    "integrate_policy_trajectory",
]
