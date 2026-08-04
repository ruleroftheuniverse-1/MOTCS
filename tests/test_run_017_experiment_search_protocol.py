from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile

import pytest

from mgf_mot.experiment_examples import ARTIFACT_LABELS, build_example
from mgf_mot.experiment_protocol import (
    CHECKPOINT_SCHEMA_VERSION, EVALUATION_CONTEXT_SCHEMA_VERSION, EXPERIMENT_RUN_SCHEMA_VERSION,
    EXPERIMENT_SCHEMA_VERSION, METRIC_REGISTRY_SCHEMA_VERSION, SEARCH_SPACE_SCHEMA_VERSION,
    TRIAL_SCHEMA_VERSION, CandidateKind, CandidatePlanKind, EvaluationContextClass,
    EvaluatorId, ExperimentProtocolError, MetricResultStatus, ObjectiveDirection,
    ParameterTransform, PhysicsReference, SearchDType, TrialStatus, build_trial_specs,
    compare_replay, execute_trial, manifest_integrity_audit, materialize_candidates,
    metrics_only_replay, run_experiment, transform_forward, transform_inverse,
    validate_candidate, validate_context, validate_experiment, validate_search_space,
    validate_status_transitions,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/provisional/experiments/run_017"


@pytest.fixture(scope="module")
def synthetic():
    return build_example("synthetic_search_plumbing", ROOT)


@pytest.fixture(scope="module")
def locked():
    return build_example("locked_physical_metric", ROOT)


def test_all_protocol_schemas_are_explicit_and_versioned():
    assert EXPERIMENT_SCHEMA_VERSION == "mgf-mot-experiment-spec-v1"
    assert EVALUATION_CONTEXT_SCHEMA_VERSION == "mgf-mot-evaluation-context-v1"
    assert METRIC_REGISTRY_SCHEMA_VERSION == "mgf-mot-metric-registry-v1"
    assert SEARCH_SPACE_SCHEMA_VERSION == "mgf-mot-search-space-v1"
    assert TRIAL_SCHEMA_VERSION == "mgf-mot-trial-manifest-v1"
    assert EXPERIMENT_RUN_SCHEMA_VERSION == "mgf-mot-experiment-run-v1"
    assert CHECKPOINT_SCHEMA_VERSION == "mgf-mot-experiment-checkpoint-v1"


def test_unknown_context_and_missing_physics_reference_fail_closed(synthetic):
    spec, _ = synthetic
    unknown = replace(spec.evaluation_context, context_class="UNKNOWN")
    assert any(item.code == "UNKNOWN_EVALUATION_CONTEXT" for item in validate_context(unknown).errors)
    pending = replace(spec.evaluation_context, context_class=EvaluationContextClass.EXACT_MODEL_PENDING,
                      labels=("EXACT_MODEL_PENDING",), execution_authorized=False, physics_reference=None)
    assert any(item.code == "MISSING_OPAQUE_PHYSICS_REFERENCE" for item in validate_context(pending).errors)
    opaque = replace(pending, physics_reference=PhysicsReference(None, None, "TRACK_E_BLOCKED", "EXACT_PENDING", "NOT_BENCHMARKED"))
    assert validate_context(opaque).valid and opaque.physics_reference.model_package_hash is None


def test_candidate_hash_ignores_name_but_preserves_semantics_and_mapping_order(locked):
    spec, _ = locked; candidate = spec.candidate_plan.candidates[0]
    renamed = replace(candidate, candidate_id="a different human label")
    reordered = replace(candidate, payload=dict(reversed(list(candidate.payload.items()))))
    changed = replace(candidate, parameter_values=(1.0,))
    assert candidate.semantic_hash == renamed.semantic_hash == reordered.semantic_hash
    assert candidate.semantic_hash != changed.semantic_hash
    assert any(item.code == "CANDIDATE_HASH_MISMATCH" for item in validate_candidate(replace(candidate, declared_semantic_hash="bad")).errors)


def test_duplicate_candidates_are_recorded_and_deduplicated(locked):
    spec, _ = locked; candidate = spec.candidate_plan.candidates[0]
    plan = replace(spec.candidate_plan, plan_kind=CandidatePlanKind.EXPLICIT_CANDIDATE_LIST,
                   candidates=(candidate, replace(candidate, candidate_id="duplicate")), deduplicate=True)
    unique, duplicates = materialize_candidates(plan)
    assert len(unique) == 1 and duplicates == (candidate.semantic_hash,)


def test_unknown_candidate_evaluator_plan_and_callable_payload_fail_closed(synthetic):
    spec, _ = synthetic
    candidate = replace(materialize_candidates(spec.candidate_plan)[0][0], candidate_kind="UNKNOWN")
    assert any(item.code == "UNKNOWN_CANDIDATE_KIND" for item in validate_candidate(candidate).errors)
    executable = replace(candidate, candidate_kind=CandidateKind.SYNTHETIC_PARAMETER_VECTOR, payload={"run": lambda: None})
    assert any(item.code == "ARBITRARY_OR_INVALID_CANDIDATE_PAYLOAD" for item in validate_candidate(executable).errors)
    bad_eval = replace(spec, evaluator=replace(spec.evaluator, evaluator_id="UNKNOWN"))
    assert any(item.code == "UNKNOWN_EVALUATOR_FAIL_CLOSED" for item in validate_experiment(bad_eval).errors)
    bad_plan = replace(spec, candidate_plan=replace(spec.candidate_plan, plan_kind="ADAPTIVE_MAGIC"))
    assert any(item.code == "UNSUPPORTED_CANDIDATE_PLAN_TYPE" for item in validate_experiment(bad_plan).errors)


def test_synthetic_context_labels_and_physical_claims_are_enforced(synthetic):
    spec, _ = synthetic
    missing = replace(spec, evaluation_context=replace(spec.evaluation_context, labels=()))
    assert any(item.code == "MISSING_SYNTHETIC_CONTEXT_LABELS" for item in validate_experiment(missing).errors)
    claim = replace(spec, authorization_labels=spec.authorization_labels + ("PHYSICAL_PERFORMANCE",))
    assert any(item.code == "PHYSICAL_CLAIM_FROM_SYNTHETIC_CONTEXT" for item in validate_experiment(claim).errors)


def test_search_dimensions_preserve_units_order_unknown_bounds_and_transform_roundtrip(synthetic):
    spec, _ = synthetic; space = spec.candidate_plan.search_space
    assert [item.serialization_order for item in space.dimensions] == [0, 1]
    assert all(item.units == "dimensionless" for item in space.dimensions)
    for dim in space.dimensions:
        for value in dim.allowed_values:
            assert transform_inverse(dim, transform_forward(dim, value)) == pytest.approx(value)
    unknown = replace(space.dimensions[0], lower_bound=None, upper_bound=None, allowed_values=None)
    result = validate_search_space(replace(space, dimensions=(unknown, space.dimensions[1])), bounded_generation=True)
    assert any(item.code == "UNKNOWN_BOUNDS_BLOCK_BOUNDED_GENERATION" for item in result.errors)
    invalid = replace(space.dimensions[0], transform=ParameterTransform.LOG_POSITIVE, lower_bound=-1.0, allowed_values=(-1.0,))
    assert any(item.code == "INVALID_TRANSFORM_DOMAIN" for item in validate_search_space(replace(space, dimensions=(invalid,))).errors)


def test_adaptive_plans_and_optimizer_execution_are_rejected(synthetic):
    spec, _ = synthetic
    adaptive = replace(spec, candidate_plan=replace(spec.candidate_plan, adaptive=True))
    assert any(item.code == "ADAPTIVE_CANDIDATE_PLANNING_FORBIDDEN" for item in validate_experiment(adaptive).errors)
    optimizer = replace(spec, optimizer_adapter=replace(spec.optimizer_adapter, optimization_run_authorized=True))
    assert any(item.code == "OPTIMIZATION_RUN_FORBIDDEN_RUN017" for item in validate_experiment(optimizer).errors)


def test_locked_physical_metric_has_no_value_and_evaluator_never_runs(locked):
    spec, assets = locked; trial = build_trial_specs(spec)[0][0]; result = execute_trial(spec, trial, assets)
    assert result.status is TrialStatus.METRIC_LOCKED and result.evaluator_output is None
    assert all(item.status is MetricResultStatus.METRIC_LOCKED and item.value is None for item in result.metrics)
    assert result.metrics[0].metric_id == "capture_velocity" and "SYNTHETIC" not in result.metrics[0].metric_id


def test_physical_evaluator_is_unauthorized_before_execution(synthetic):
    spec, assets = synthetic
    physical = replace(spec, evaluator=replace(spec.evaluator, evaluator_id=EvaluatorId.MGF_FORCE_EVALUATOR,
                                               evaluator_version="1", implementation_version="reserved-v1", authorized=False))
    codes = {item.code for item in validate_experiment(physical).errors}
    assert "EVALUATOR_NOT_AUTHORIZED" in codes
    with pytest.raises(ExperimentProtocolError, match="INVALID_EXPERIMENT"):
        run_experiment(physical, assets, Path("unused"))


def test_objective_direction_is_explicit_and_locked_objective_blocks(synthetic, locked):
    spec, _ = synthetic; objective = spec.objectives[0]
    assert objective.direction is ObjectiveDirection.MINIMIZE
    missing = replace(spec, objectives=(replace(objective, direction=None),))
    assert any(item.code == "OBJECTIVE_DIRECTION_MISSING_OR_UNKNOWN" for item in validate_experiment(missing).errors)
    locked_spec, _ = locked
    locked_objective = replace(objective, metric_id="capture_velocity", units="UNRESOLVED",
                               authorization_requirement=locked_spec.metric_specs[0].authorization)
    invalid = replace(locked_spec, objectives=(locked_objective,))
    assert any(item.code == "OBJECTIVE_METRIC_LOCKED" for item in validate_experiment(invalid).errors)


def test_trial_ids_and_namespaced_seeds_are_execution_order_independent(synthetic):
    spec, _ = synthetic; trials, _ = build_trial_specs(spec)
    assert [item.trial_hash for item in trials] == [item.trial_hash for item in build_trial_specs(spec)[0]]
    forward = {trial.trial_hash: spec.seed_ledger.derive(trial.trial_hash, "synthetic_evaluator_behavior") for trial in trials}
    reverse = {trial.trial_hash: spec.seed_ledger.derive(trial.trial_hash, "synthetic_evaluator_behavior") for trial in reversed(trials)}
    assert forward == reverse and len(set(forward.values())) == len(trials)


def test_forward_reverse_interrupted_resume_and_metrics_replay_match(synthetic):
    spec, assets = synthetic; count = len(build_trial_specs(spec)[0]); (ROOT / "tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="r17_", dir=ROOT / "tmp") as name:
        tmp_path = Path(name)
        forward, _, forward_results = run_experiment(spec, assets, tmp_path / "f")
        reverse, _, _ = run_experiment(spec, assets, tmp_path / "r", execution_order=tuple(reversed(range(count))))
        _, partial_checkpoint, partial_results = run_experiment(spec, assets, tmp_path / "u", stop_after=2)
        resumed, checkpoint, resumed_results = run_experiment(spec, assets, tmp_path / "u",
            existing_results=partial_results, existing_checkpoint=partial_checkpoint)
        assert compare_replay(forward, reverse, ()).trial_hashes_equal
        assert compare_replay(forward, reverse, ()).manifest_semantic_hash_equal
        assert compare_replay(forward, resumed, ()).manifest_semantic_hash_equal
        assert len(partial_results) == 2 and len(resumed_results) == count
        assert all(metrics_only_replay(spec, item).equal for item in resumed_results.values())
        assert manifest_integrity_audit(checkpoint, spec, tmp_path / "u" / spec.semantic_hash).valid


def test_resume_rejects_changed_spec_and_artifact_corruption(tmp_path, synthetic):
    spec, assets = synthetic
    _, checkpoint, results = run_experiment(spec, assets, tmp_path, stop_after=1)
    changed = replace(spec, purpose=spec.purpose + " changed")
    with pytest.raises(ExperimentProtocolError, match="INVALID_RESUME"):
        run_experiment(changed, assets, tmp_path, existing_results=results, existing_checkpoint=checkpoint)
    artifact = next((tmp_path / spec.semantic_hash / "trials").glob("*/metrics.json")); artifact.write_text("{}\n", encoding="utf-8")
    audit = manifest_integrity_audit(checkpoint, spec, tmp_path / spec.semantic_hash)
    assert not audit.valid and any(item.code == "CHECKPOINT_ARTIFACT_INTEGRITY_FAILURE" for item in audit.issues)
    with pytest.raises(ExperimentProtocolError, match="INVALID_RESUME"):
        run_experiment(spec, assets, tmp_path, existing_results=results, existing_checkpoint=checkpoint)


def test_status_transitions_are_closed():
    assert validate_status_transitions((TrialStatus.PLANNED, TrialStatus.VALIDATED, TrialStatus.RUNNING, TrialStatus.SUCCEEDED))
    assert validate_status_transitions((TrialStatus.PLANNED, TrialStatus.VALIDATED, TrialStatus.METRIC_LOCKED))
    assert not validate_status_transitions((TrialStatus.PLANNED, TrialStatus.SUCCEEDED))


def test_source_incomplete_compilation_never_claims_hardware():
    spec, assets = build_example("apparatus_compilation", ROOT)
    candidate = next(item for item in spec.candidate_plan.candidates if item.candidate_id == "diagnostic_incomplete")
    compiled = assets.resolve(candidate.payload["asset_hash"])
    assert not compiled.profile_complete and not compiled.hardware_executable_claim_valid


def test_generated_outputs_have_required_labels_and_gate():
    metadata_path = next((ROOT / "outputs/provisional/experiment_search_protocol/run_017").glob("*metadata.json"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["gate"] == "CONTROL_EXPERIMENT_INFRA_READY" and metadata["protected_artifacts_unchanged"]
    assert set(ARTIFACT_LABELS).issubset(metadata["artifact_labels"])
    for path in OUTPUT.glob("*/*.json"):
        text = path.read_text(encoding="utf-8")
        assert all(label in text for label in ("MODEL_INDEPENDENT", "NOT_RODRIGUEZ_REPLICATION", "RUN_017", "EXPERIMENT_SEARCH_PROTOCOL_ONLY"))
    synthetic_spec, _ = build_example("synthetic_search_plumbing", ROOT)
    for path in (OUTPUT / synthetic_spec.semantic_hash).glob("trials/*/*.json"):
        text = path.read_text(encoding="utf-8")
        assert "SYNTHETIC_OBJECTIVE" in text and "NOT_PHYSICAL_PERFORMANCE" in text


def test_run017_source_has_no_physics_cache_trajectory_capture_optimizer_training_or_rl_path():
    texts = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in (
        "src/mgf_mot/experiment_protocol.py", "src/mgf_mot/experiment_examples.py",
        "scripts/validate_experiment_search_protocol_run_017.py",
    ))
    forbidden = (
        "import scipy.optimize", "import gym", "import torch", "load_force_field_cache(",
        "force_at(", "integrate_policy_trajectory(", "capture_velocity(", "rateeq",
        "molecular_hamiltonian", "optimizer.minimize(", ".fit(", ".train(",
    )
    assert all(item not in texts for item in forbidden)
