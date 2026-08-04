from __future__ import annotations

from dataclasses import replace
from copy import deepcopy
import json
import math
from pathlib import Path

import pytest

from mgf_mot.control_policy_abi import (
    ChannelRelationship, ChannelSignalKind, ChannelTarget, ControlChannelSpec,
    ControlPolicy, ControlPolicyABIError, PolicyStatefulness, RUN013_LABEL,
)
from mgf_mot.control_policy_serialization import (
    canonical_control_policy_json, control_policy_hashes,
    control_policy_spec_from_mapping, control_policy_spec_to_mapping,
    deserialize_control_policy_spec, serialize_control_policy_spec,
)
from mgf_mot.control_policy_validation import (
    PolicyIssueSeverity, validate_control_policy_mapping,
    validate_control_policy_spec,
)
from mgf_mot.legacy_policy_adapter import (
    LEGACY_UNSPECIFIED_OFF_REASON, legacy_policy_to_v2_spec,
    v2_state_to_legacy_sample,
)
from mgf_mot.policies import (
    ChirpToTrapHandoffPolicy, LinearChirpPolicy, StaticPolicy, load_policy,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIGS = {
    name: ROOT / "configs" / filename for name, filename in {
        "static_3": "rodriguez_static_3.yaml",
        "static_3_plus_1": "rodriguez_static_3_plus_1.yaml",
        "chirp": "rodriguez_baseline_linear_chirp.yaml",
        "handoff": "rodriguez_chirp_to_3_plus_1_handoff.yaml",
    }.items()
}
OUTPUT_DIR = ROOT / "outputs/provisional/control_policy_abi/run_013"
METADATA = OUTPUT_DIR / f"{RUN013_LABEL}_metadata.json"
REPORT = ROOT / "outputs/provisional" / f"{RUN013_LABEL}.md"


@pytest.fixture(scope="module")
def policies():
    return {name: load_policy(path) for name, path in CONFIGS.items()}


@pytest.fixture(scope="module")
def specs(policies):
    return {name: legacy_policy_to_v2_spec(policies[name], source_path=CONFIGS[name]) for name in policies}


def test_every_state_has_explicit_ordered_components_and_activity(specs) -> None:
    for spec in specs.values():
        assert validate_control_policy_spec(spec).valid
        policy = ControlPolicy(spec)
        for time_s in (-1.0, 0.0, 0.0005, 0.001, 1.0):
            state = policy.sample(time_s)
            assert state.component_order == (1, 2, 3, 4)
            assert tuple(component.component_id for component in state.components) == (1, 2, 3, 4)
            for component in state.components:
                assert component.active == (component.enabled and component.saturation > 0)
                if not component.active:
                    assert component.off_reason
    parked = ControlPolicy(specs["chirp"]).sample(0.0005).components[3]
    assert parked.detuning_gamma == 2.0
    assert parked.saturation == 0.0 and parked.active is False
    assert parked.off_reason == "parked_off_until_3_plus_1_handoff"
    static_legacy_reason = ControlPolicy(specs["static_3"]).sample(0).components[3]
    assert static_legacy_reason.off_reason == LEGACY_UNSPECIFIED_OFF_REASON


def test_shared_channels_and_affine_derivation_are_explicit_and_acyclic(specs) -> None:
    chirp = specs["chirp"]
    shared = [channel for channel in chirp.control_channels if channel.relationship is ChannelRelationship.SHARED]
    assert len(shared) == 1
    assert {target.component_id for target in shared[0].targets} == {1, 2, 3}
    state = ControlPolicy(chirp).sample(0.00037)
    assert state.components[0].detuning_gamma == state.components[1].detuning_gamma == state.components[2].detuning_gamma

    base = specs["static_3"]
    old = next(channel for channel in base.control_channels if channel.channel_id == "static_component_2_saturation")
    derived = ControlChannelSpec(
        channel_id=old.channel_id, relationship=ChannelRelationship.AFFINE_DERIVED,
        signal_kind=ChannelSignalKind.AFFINE, field="saturation", targets=old.targets,
        source_channel_id="static_component_1_saturation", affine_scale=1.0,
        affine_offset=0.0, description="test-only declared affine equality",
    )
    channels = tuple(derived if channel.channel_id == old.channel_id else channel for channel in base.control_channels)
    affine_spec = replace(base, control_channels=channels)
    assert validate_control_policy_spec(affine_spec).valid
    assert ControlPolicy(affine_spec).sample(0).components[1].saturation == 1.45

    cycle_a = ControlChannelSpec("cycle_a", ChannelRelationship.AFFINE_DERIVED, ChannelSignalKind.AFFINE, "saturation", (), source_channel_id="cycle_b", affine_scale=1.0, affine_offset=0.0)
    cycle_b = ControlChannelSpec("cycle_b", ChannelRelationship.AFFINE_DERIVED, ChannelSignalKind.AFFINE, "saturation", (), source_channel_id="cycle_a", affine_scale=1.0, affine_offset=0.0)
    invalid = validate_control_policy_spec(replace(base, control_channels=base.control_channels + (cycle_a, cycle_b)))
    assert any(issue.code == "CYCLIC_DERIVED_CHANNEL" for issue in invalid.errors)


def test_conflicting_ownership_missing_fields_and_executable_content_fail(specs) -> None:
    base = specs["static_3"]
    conflict = ControlChannelSpec(
        "conflict", ChannelRelationship.FIXED, ChannelSignalKind.FIXED,
        "detuning_gamma", (ChannelTarget("static", 1, "detuning_gamma"),), fixed_value=-1.0,
    )
    result = validate_control_policy_spec(replace(base, control_channels=base.control_channels + (conflict,)))
    assert any(issue.code == "DUPLICATE_CHANNEL_OWNERSHIP" for issue in result.errors)
    mapping = control_policy_spec_to_mapping(base); del mapping["segments"]
    with pytest.raises(ValueError, match="no defaults"):
        control_policy_spec_from_mapping(mapping)
    malformed = deepcopy(control_policy_spec_to_mapping(base)); malformed["expression"] = "lambda t: t"
    issues = validate_control_policy_mapping(malformed)
    executable = [issue for issue in issues.errors if issue.code == "ARBITRARY_EXECUTABLE_CONTENT"]
    assert executable and executable[0].severity is PolicyIssueSeverity.ERROR


def test_static_linear_and_handoff_legacy_behavior_is_exact(policies, specs) -> None:
    for name, legacy in policies.items():
        abi = ControlPolicy(specs[name])
        if isinstance(legacy, StaticPolicy): times = (-1.0, 0.0, 0.4, 1000.0)
        elif isinstance(legacy, LinearChirpPolicy):
            tau = legacy.duration_s; times = (0.0, 0.1*tau, 0.5*tau, math.nextafter(tau, 0), tau, math.nextafter(tau, math.inf), 2*tau, 100*tau)
        else:
            tau = legacy.duration_s; times = (math.nextafter(tau, 0), tau, math.nextafter(tau, math.inf))
        for time_s in times:
            assert v2_state_to_legacy_sample(abi.sample(time_s), legacy) == legacy.sample(time_s)
    handoff = ControlPolicy(specs["handoff"]); tau = policies["handoff"].duration_s
    assert handoff.sample(math.nextafter(tau, 0)).segment_id == "pre_handoff"
    assert handoff.sample(tau).segment_id == "post_handoff"
    assert handoff.sample(tau).event_ids_at_time == ("chirp_to_trap_handoff",)
    assert handoff.sample(math.nextafter(tau, math.inf)).segment_id == "post_handoff"


def test_serialization_hashes_and_mapping_order_are_deterministic(specs) -> None:
    for spec in specs.values():
        text = serialize_control_policy_spec(spec)
        restored = deserialize_control_policy_spec(text)
        assert restored == spec
        assert serialize_control_policy_spec(restored) == text
        assert control_policy_hashes(restored) == control_policy_hashes(spec)
        mapping = control_policy_spec_to_mapping(spec)
        reversed_mapping = dict(reversed(list(mapping.items())))
        assert canonical_control_policy_json(mapping) == canonical_control_policy_json(reversed_mapping)
    base = specs["chirp"]; original = control_policy_hashes(base)
    values = dict(base.parameter_values); values["chirp_final_detuning_gamma"] = -1.1
    changed = control_policy_hashes(replace(base, parameter_values=values))
    assert changed.parameter_specification != original.parameter_specification
    assert changed.full_policy_package != original.full_policy_package
    event = replace(base.events[0], event_time_s=0.0011)
    changed_event = control_policy_hashes(replace(base, events=(event,)))
    assert changed_event.policy_specification != original.policy_specification
    changed_provenance = control_policy_hashes(replace(base, provenance=replace(base.provenance, notes=base.provenance.notes + ("meaningful",))))
    assert changed_provenance.policy_specification == original.policy_specification
    assert changed_provenance.full_policy_package != original.full_policy_package


def test_unknown_schema_nonfinite_json_and_stateful_execution_fail_closed(specs) -> None:
    bad_schema = validate_control_policy_spec(replace(specs["static_3"], schema_version="future-v99"))
    assert any(issue.code == "UNKNOWN_SCHEMA_VERSION" for issue in bad_schema.errors)
    with pytest.raises(ValueError, match="nonfinite"):
        deserialize_control_policy_spec('{"value": NaN}')
    stateful = replace(specs["static_3"], statefulness=PolicyStatefulness.STATEFUL_CONTROLLER)
    validation = validate_control_policy_spec(stateful)
    assert validation.valid
    assert any(issue.code == "STATEFUL_EXECUTION_UNSUPPORTED" for issue in validation.warnings)
    with pytest.raises(ControlPolicyABIError, match="STATEFUL_CONTROLLER"):
        ControlPolicy(stateful)


def test_run013_outputs_protected_artifacts_and_authorization_boundaries() -> None:
    metadata = json.loads(METADATA.read_text(encoding="utf-8"))
    assert metadata["gate"] == "CONTROL_POLICY_ABI_GO"
    assert metadata["legacy_behavior_gate"] == "LEGACY_BEHAVIOR_EXACT"
    assert metadata["protected_artifacts_unchanged"] is True
    assert metadata["protected_hashes_before"] == metadata["protected_hashes_after"]
    assert len(metadata["policies"]) == 4
    assert all(row["schema_roundtrip_exact"] and row["hash_roundtrip_exact"] for row in metadata["policies"])
    for key in ("apparatus_schedule_compiler_authorized", "open_loop_policy_families_authorized", "feedback_policy_authorized", "optimizer_interface_authorized", "optimization_run_authorized", "capture_authorized", "exact_replication_valid"):
        assert metadata[key] is False
    assert metadata["molecular_force_calculations"] == metadata["force_field_queries"] == metadata["trajectory_calculations"] == 0
    paths = list(OUTPUT_DIR.iterdir()) + [REPORT]
    stamps = ("MODEL_INDEPENDENT", "NOT_RODRIGUEZ_REPLICATION", "RUN_013", "CONTROL_POLICY_ABI_ONLY")
    assert all(all(stamp in path.name for stamp in stamps) for path in paths)
    report = REPORT.read_text(encoding="utf-8")
    assert "No molecular force, force-field, trajectory, capture, feedback, or optimization calculation was performed" in report
    source = (ROOT / "scripts/validate_control_policy_abi_v2.py").read_text(encoding="utf-8")
    for forbidden in ("rateeq", "force_at(", "load_force_field_cache(", "integrate_", "capture_velocity(", "optimizer(", "feedback_policy("):
        assert forbidden not in source
