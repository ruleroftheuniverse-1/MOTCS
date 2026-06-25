"""Project track and provenance labels for MgF backend outputs."""

from dataclasses import dataclass
from enum import Enum


class ProjectTrack(str, Enum):
    """Top-level project tracks."""

    EXACT = "exact"
    PROVISIONAL = "provisional"


@dataclass(frozen=True)
class BackendProvenance:
    """Machine-readable status carried by backend and force-map outputs."""

    track: ProjectTrack
    backend_mode: str
    force_ready: bool
    replication_valid: bool
    warnings: tuple[str, ...]
    omitted_terms: tuple[str, ...]
    collapsed_terms: tuple[str, ...]
