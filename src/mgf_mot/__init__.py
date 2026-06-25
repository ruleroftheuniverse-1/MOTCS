"""Pre-force-map utilities for static MgF MOT replication."""

from .constants import MGF, RODRIGUEZ_STATIC
from .geometry import MOT_BEAM_DIRECTIONS, quadrupole_field
from .mgf_backend import (
    ApproximationMode,
    ExactBackendMode,
    analyze_mgf_exact_backend_feasibility,
    build_mgf_hamiltonian_from_sources,
    build_mgf_validation_model_from_sources,
)
from .provisional_force import (
    ProvisionalForceMapConfig,
    diagnostic_configs,
    force_at,
    force_grid_1d,
)
from .tracks import BackendProvenance, ProjectTrack

__all__ = [
    "MGF",
    "RODRIGUEZ_STATIC",
    "MOT_BEAM_DIRECTIONS",
    "quadrupole_field",
    "ApproximationMode",
    "ExactBackendMode",
    "analyze_mgf_exact_backend_feasibility",
    "build_mgf_hamiltonian_from_sources",
    "build_mgf_validation_model_from_sources",
    "BackendProvenance",
    "ProjectTrack",
    "ProvisionalForceMapConfig",
    "diagnostic_configs",
    "force_at",
    "force_grid_1d",
]
