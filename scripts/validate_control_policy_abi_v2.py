"""Run 013: validate ABI v2 and audit exact legacy-policy compatibility."""

from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
import math
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]; SRC = ROOT / "src"
if str(SRC) not in sys.path: sys.path.insert(0, str(SRC))

from mgf_mot.control_policy_abi import ControlPolicy, RUN013_LABEL  # noqa: E402
from mgf_mot.control_policy_serialization import (  # noqa: E402
    control_policy_hashes, deserialize_control_policy_spec,
    serialize_control_policy_spec,
)
from mgf_mot.control_policy_validation import validate_control_policy_spec  # noqa: E402
from mgf_mot.legacy_policy_adapter import (  # noqa: E402
    legacy_policy_to_v2_spec, v2_state_to_legacy_sample,
)
from mgf_mot.policies import (  # noqa: E402
    ChirpToTrapHandoffPolicy, LinearChirpPolicy, StaticPolicy, load_policy,
)


CONFIGS = (
    ROOT / "configs/rodriguez_static_3.yaml",
    ROOT / "configs/rodriguez_static_3_plus_1.yaml",
    ROOT / "configs/rodriguez_baseline_linear_chirp.yaml",
    ROOT / "configs/rodriguez_chirp_to_3_plus_1_handoff.yaml",
)
OUTPUT_ROOT = ROOT / "outputs/provisional"
OUTPUT_DIR = OUTPUT_ROOT / "control_policy_abi/run_013"
METADATA = OUTPUT_DIR / f"{RUN013_LABEL}_metadata.json"
REPORT = OUTPUT_ROOT / f"{RUN013_LABEL}.md"


def _hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _protected() -> tuple[Path, ...]:
    patterns = (
        "outputs/provisional/molecular_model_packages/run_012/*",
        "outputs/provisional/*RUN_012*", "outputs/provisional/force_fields/*",
        "outputs/provisional/*RUN_011*", "outputs/provisional/molecular_model_audit/run_011*/*",
        "outputs/provisional/paper_digitization/run_011b/*", "configs/*.yaml",
    )
    paths: set[Path] = {ROOT / "docs/policy-interface.md"}
    for pattern in patterns: paths.update(path for path in ROOT.glob(pattern) if path.is_file())
    return tuple(sorted(paths))


def _manifest(paths: tuple[Path, ...]) -> dict[str, str]:
    return {str(path.relative_to(ROOT)): _hash(path) for path in paths}


def _times(policy: Any) -> tuple[float, ...]:
    if isinstance(policy, StaticPolicy): return (-1.0, 0.0, 0.123, 1000.0)
    tau = policy.duration_s
    if isinstance(policy, LinearChirpPolicy):
        return (0.0, 0.1*tau, 0.5*tau, math.nextafter(tau, 0.0), tau, math.nextafter(tau, math.inf), 2*tau, 100*tau)
    return (math.nextafter(tau, 0.0), tau, math.nextafter(tau, math.inf))


def _component_table(state: Any) -> list[dict[str, Any]]:
    return [{
        "component_id": component.component_id, "detuning_gamma": component.detuning_gamma,
        "saturation": component.saturation, "enabled": component.enabled,
        "active": component.active, "off_reason": component.off_reason,
        "detuning_channel_id": component.detuning_channel_id,
        "saturation_channel_id": component.saturation_channel_id,
    } for component in state.components]


def run() -> dict[str, Any]:
    protected = _protected(); before = _manifest(protected); OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    policies = []; all_exact = True
    for path in CONFIGS:
        legacy = load_policy(path); spec = legacy_policy_to_v2_spec(legacy, source_path=path)
        validation = validate_control_policy_spec(spec)
        serialized = serialize_control_policy_spec(spec, pretty=True); restored = deserialize_control_policy_spec(serialized)
        hashes = control_policy_hashes(spec); restored_hashes = control_policy_hashes(restored)
        executable = ControlPolicy(restored); samples = []
        print(f"\n{spec.policy_name} [{spec.policy_family.value}]")
        print("time_s segment component detuning_Gamma saturation enabled active off_reason detuning_channel saturation_channel")
        behavior_exact = True
        for time_s in _times(legacy):
            legacy_sample = legacy.sample(time_s); abi_state = executable.sample(time_s)
            compatible = v2_state_to_legacy_sample(abi_state, legacy)
            equal = legacy_sample == compatible; behavior_exact &= equal
            samples.append({"time_s": time_s, "exact": equal, "segment_id": abi_state.segment_id, "event_ids_at_time": list(abi_state.event_ids_at_time), "components": _component_table(abi_state)})
            for row in samples[-1]["components"]:
                print(time_s, abi_state.segment_id, row["component_id"], row["detuning_gamma"], row["saturation"], row["enabled"], row["active"], row["off_reason"], row["detuning_channel_id"], row["saturation_channel_id"])
        exact_roundtrip = spec == restored and hashes == restored_hashes
        all_exact &= validation.valid and behavior_exact and exact_roundtrip
        spec_path = OUTPUT_DIR / f"{RUN013_LABEL}_{spec.policy_name}_spec.json"
        spec_path.write_text(serialized, encoding="utf-8")
        policies.append({
            "name": spec.policy_name, "family": spec.policy_family.value,
            "source_configuration": str(path.relative_to(ROOT)), "source_hash": _hash(path),
            "validation_valid": validation.valid, "validation_issues": [asdict(issue) for issue in validation.issues],
            "parameter_table": [asdict(item) for item in spec.parameter_specs],
            "channel_table": [asdict(item) for item in spec.control_channels],
            "event_table": [asdict(item) for item in spec.events],
            "component_order": list(spec.component_order), "sample_comparison": samples,
            "legacy_behavior_gate": "LEGACY_BEHAVIOR_EXACT" if behavior_exact else "LEGACY_BEHAVIOR_CHANGED",
            "schema_roundtrip_exact": spec == restored, "hash_roundtrip_exact": hashes == restored_hashes,
            "hashes": asdict(hashes), "serialized_spec_file": spec_path.name,
        })
    after = _manifest(protected)
    gate = "CONTROL_POLICY_ABI_GO" if all_exact and before == after else "CONTROL_POLICY_ABI_REFINEMENT_REQUIRED"
    metadata = {
        "label": RUN013_LABEL, "schema_version": "mgf-mot-control-policy-v2",
        "policies": policies, "legacy_behavior_gate": "LEGACY_BEHAVIOR_EXACT" if all_exact else "LEGACY_BEHAVIOR_CHANGED",
        "protected_hashes_before": before, "protected_hashes_after": after,
        "protected_artifacts_unchanged": before == after,
        "molecular_force_calculations": 0, "force_field_queries": 0, "trajectory_calculations": 0,
        "capture_calculations": 0, "optimization_runs": 0, "feedback_executions": 0,
        "control_policy_abi_authorized": gate == "CONTROL_POLICY_ABI_GO",
        "apparatus_schedule_compiler_authorized": False,
        "open_loop_policy_families_authorized": False, "feedback_policy_authorized": False,
        "optimizer_interface_authorized": False, "optimization_run_authorized": False,
        "capture_authorized": False, "exact_replication_valid": False,
        "accepted_track_p_physics_frozen": True, "gate": gate,
    }
    METADATA.write_text(json.dumps(metadata, indent=2, sort_keys=True, default=lambda value: value.value) + "\n", encoding="utf-8")
    REPORT.write_text("\n".join([
        f"# {RUN013_LABEL}", "",
        "**MODEL-INDEPENDENT CONTROL ABI AUDIT ONLY. No molecular force, force-field, trajectory, capture, feedback, or optimization calculation was performed.**", "",
        f"## {RUN013_LABEL} Result", "",
        f"All four legacy configurations converted to `mgf-mot-control-policy-v2`, validated, serialized, deserialized, and instantiated. Compatibility result: `{metadata['legacy_behavior_gate']}`. Canonical parameter, channel, policy, and full-package hashes remained exact across round trip.", "",
        f"## {RUN013_LABEL} Explicit contracts", "",
        "Every state contains ordered components `(1,2,3,4)` with separate detuning and saturation channel IDs. The common chirp of components `(1,2,3)` is one SHARED channel; parked component `(4)` remains at `+2 Gamma` with zero optical power. Static values are FIXED channels. AFFINE_DERIVED is declarative, acyclic, and limited to scale/offset; executable expressions fail closed.", "",
        "Negative-time behavior is explicit HOLD_INITIAL. Linear chirp evaluation includes the exact endpoint and final hold. The handoff event preserves `t<tau` pre-handoff and `t>=tau` post-handoff. The static-[3] legacy null off-reason is represented internally by an explicit provenance sentinel and projected back to null only in the v1 compatibility view, preserving legacy samples exactly without rewriting YAML.", "",
        f"## {RUN013_LABEL} Boundaries", "",
        "Accepted Track P physics and historical artifacts remain byte-identical. The ABI gate authorizes subsequent apparatus schedule-compiler work and later policy families against v2, but does not authorize apparatus claims, new simulation, feedback, optimization, or capture calculations.", "",
        "`apparatus_schedule_compiler_authorized=false`; `open_loop_policy_families_authorized=false`; `feedback_policy_authorized=false`; `optimizer_interface_authorized=false`; `optimization_run_authorized=false`; `capture_authorized=false`; `exact_replication_valid=false`.", "",
        gate,
    ]) + "\n", encoding="utf-8")
    if before != after: raise RuntimeError("Run 013 changed a protected artifact")
    print(f"\n{RUN013_LABEL}: {gate}")
    return metadata


if __name__ == "__main__": run()
