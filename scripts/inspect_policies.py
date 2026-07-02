"""Inspect Track P laser schedule policies without running dynamics."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import numpy as np

from mgf_mot.policies import (
    COMPONENT_ORDER,
    LinearChirpPolicy,
    PolicySample,
    load_policy,
)
from mgf_mot.provisional_force import FULL_WARNING_LABEL

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs" / "provisional"
POLICY_INTERFACE_LABEL = f"{FULL_WARNING_LABEL}_POLICY_INTERFACE_ONLY"
POLICY_CONFIG_PATHS = (
    REPO_ROOT / "configs" / "rodriguez_static_3.yaml",
    REPO_ROOT / "configs" / "rodriguez_static_3_plus_1.yaml",
    REPO_ROOT / "configs" / "rodriguez_baseline_linear_chirp.yaml",
)


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


def _sample_times(policy: object) -> tuple[float, ...]:
    if isinstance(policy, LinearChirpPolicy):
        tau = policy.duration_s
        return (0.0, tau / 2.0, tau, 1.5 * tau)
    return (0.0,)


def _row(policy_name: str, sample: PolicySample) -> str:
    parts = [f"{policy_name:34s}", f"t={sample.time_s:9.6g}s"]
    for component in sample.components:
        enabled = "on" if component.enabled else "off"
        parts.append(
            f"c{component.component_id}: detuning={component.detuning_gamma:6.3g} Gamma "
            f"s={component.saturation:5.3g} {enabled}"
        )
    return " | ".join(parts)


def run(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    print(POLICY_INTERFACE_LABEL)
    print(f"component_order: {COMPONENT_ORDER}")

    policies = [load_policy(path) for path in POLICY_CONFIG_PATHS]
    records: list[dict[str, Any]] = []
    table_lines: list[str] = []

    for policy, path in zip(policies, POLICY_CONFIG_PATHS):
        print(f"\npolicy: {policy.name} ({policy.policy_type})")
        for t in _sample_times(policy):
            sample = policy.sample(t)
            line = _row(policy.name, sample)
            print(line)
            table_lines.append(line)
            records.append(
                {
                    "policy_config_path": str(path.relative_to(REPO_ROOT)),
                    "policy_name": policy.name,
                    "policy_type": policy.policy_type,
                    "component_order": list(policy.component_order),
                    "detuning_unit": policy.detuning_unit,
                    "saturation_unit": policy.saturation_unit,
                    "time_unit": policy.time_unit,
                    "sample": _json_safe(sample),
                    "apparatus_bounds": _json_safe(policy.apparatus_bounds),
                    "label": POLICY_INTERFACE_LABEL,
                    "replication_valid": False,
                    "force_ready": False,
                    "disclaimer": (
                        "PROVISIONAL NOT_RODRIGUEZ_REPLICATION POLICY_INTERFACE_ONLY; "
                        "control-schedule plumbing only; no dynamics or physical conclusions."
                    ),
                }
            )

    metadata = {
        "label": POLICY_INTERFACE_LABEL,
        "run_type": "policy_interface_inspection",
        "replication_valid": False,
        "force_ready": False,
        "component_order": list(COMPONENT_ORDER),
        "records": records,
        "warnings": [
            "PROVISIONAL",
            "NOT_RODRIGUEZ_REPLICATION",
            "POLICY_INTERFACE_ONLY",
            "Track E exact MgF force readiness remains blocked.",
            "No trajectories, capture velocities, Gaussian beams, optimizers, or exact force maps are run.",
        ],
    }
    metadata_path = output_dir / f"{POLICY_INTERFACE_LABEL}_metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    report_path = output_dir / f"{POLICY_INTERFACE_LABEL}_report.md"
    report_lines = [
        f"# {POLICY_INTERFACE_LABEL} report",
        "",
        "This is pure control-schedule plumbing for Track P.",
        "",
        "This is not an MgF/Rodriguez reproduction.",
        "Track E exact MgF force readiness remains blocked.",
        "No trajectory integration, capture velocity calculation, Gaussian beam model, optimizer, or exact force-map path is used.",
        "No physical conclusions should be drawn from these policy samples.",
        "",
        "## Component order",
        "",
        f"`{COMPONENT_ORDER}`",
        "",
        "## Samples",
        "",
        "```text",
        *table_lines,
        "```",
        "",
        f"Metadata: `{metadata_path.name}`",
    ]
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\nwrote metadata: {metadata_path}")
    print(f"wrote report: {report_path}")
    return {"metadata_path": metadata_path, "report_path": report_path, "records": records}


def main() -> None:
    run()


if __name__ == "__main__":
    main()
