"""Run 009A static-only acceptance-audit helpers.

These helpers classify already-defined provisional rate-equation behavior. They
do not add a force model, integrate motion, or promote Track P results.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping

import numpy as np

from .policies import ComponentState, PolicySample


RUN009A_LABEL = (
    "PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RATEEQ_STATIC_ACCEPTANCE_AUDIT_ONLY"
)


@dataclass(frozen=True)
class AcceptanceGate:
    label: str
    decision: str
    checks: Mapping[str, bool]
    diagnoses: tuple[str, ...]
    trajectories_authorized: bool


def flip_policy_polarizations(sample: PolicySample) -> PolicySample:
    """Return the same policy state with every explicit helicity reversed."""

    mapping = {"sigma_plus": "sigma_minus", "sigma_minus": "sigma_plus"}
    flipped: list[ComponentState] = []
    for component in sample.components:
        try:
            polarization = mapping[component.polarization]
        except KeyError as exc:
            raise ValueError(
                f"component {component.component_id} polarization is not explicit"
            ) from exc
        flipped.append(replace(component, polarization=polarization))
    return replace(sample, components=tuple(flipped))  # type: ignore[arg-type]


def centered_slope(axis: np.ndarray, values: np.ndarray) -> float:
    """Return the centered finite-difference slope at the grid origin."""

    axis = np.asarray(axis, dtype=float)
    values = np.asarray(values, dtype=float)
    if axis.ndim != 1 or values.shape != axis.shape or axis.size < 3:
        raise ValueError("axis and values must be matching one-dimensional arrays")
    center = int(np.argmin(np.abs(axis)))
    if center == 0 or center == axis.size - 1 or not np.isclose(axis[center], 0.0):
        raise ValueError("axis must contain an interior zero")
    return float(
        (values[center + 1] - values[center - 1])
        / (axis[center + 1] - axis[center - 1])
    )


def topology_label(slope: float, *, negative: str, positive: str) -> str:
    if slope < 0:
        return negative
    if slope > 0:
        return positive
    return "flat"


def relative_change(first: float, second: float, *, floor: float = 1.0e-15) -> float:
    return float(abs(second - first) / max(abs(first), abs(second), floor))


def decide_acceptance_gate(
    checks: Mapping[str, bool], diagnosis_by_check: Mapping[str, str]
) -> AcceptanceGate:
    """Return GO only when every named acceptance condition is true."""

    missing = set(checks) - set(diagnosis_by_check)
    if missing:
        raise ValueError(f"missing diagnosis text for checks: {sorted(missing)}")
    failed = tuple(diagnosis_by_check[name] for name, passed in checks.items() if not passed)
    decision = "GO" if not failed else "NO-GO"
    return AcceptanceGate(
        label=RUN009A_LABEL,
        decision=decision,
        checks=dict(checks),
        diagnoses=failed,
        trajectories_authorized=decision == "GO",
    )
