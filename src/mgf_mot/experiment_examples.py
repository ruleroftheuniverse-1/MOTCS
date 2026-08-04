"""Closed Run 017 example experiment construction.

The YAML files select examples by ID; they cannot inject code or evaluators.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Mapping

import yaml

from .apparatus_constraints import (
    apparatus_profile_hash, source_incomplete_profile, synthetic_identity_profile,
    synthetic_quantized_profile, synthetic_rate_limited_profile,
)
from .control_schedule_compiler import CompilationMode, CompilationRequest, InitialStateMode, ReconstructionMode
from .experiment_protocol import (
    CandidateKind, CandidatePlan, CandidatePlanKind, CandidateSpec, EvaluationContext,
    EvaluationContextClass, EvaluatorId, EVALUATION_CONTEXT_SCHEMA_VERSION,
    EXPERIMENT_SCHEMA_VERSION, ExperimentSpec, ObjectiveDirection, ObjectiveRole,
    ObjectiveSpec, OptimizerAdapterSpec, OutputContract, ParameterTransform, Provenance,
    RUN017_LABEL, RuntimeAssets, SEARCH_SPACE_SCHEMA_VERSION, SYNTHETIC_LABELS,
    SYNTHETIC_OBJECTIVE_LABELS, SearchDType, SearchDimensionSpec, SearchSpaceSpec,
    SeedLedger, evaluator_spec, registered_metric, semantic_hash,
)
from .feedback_examples import load_feedback_example
from .feedback_policy import feedback_hash, run_feedback_session
from .open_loop_policy_families import (
    compile_family_policy, family_hashes, load_family_config,
)


EXAMPLE_IDS = (
    "policy_structural_comparison", "apparatus_compilation", "feedback_replay",
    "synthetic_search_plumbing", "locked_physical_metric",
)
ARTIFACT_LABELS = (RUN017_LABEL, "MODEL_INDEPENDENT", "NOT_RODRIGUEZ_REPLICATION", "RUN_017", "EXPERIMENT_SEARCH_PROTOCOL_ONLY")


def _prov(description: str, *, synthetic: bool = False) -> Provenance:
    labels = SYNTHETIC_LABELS + SYNTHETIC_OBJECTIVE_LABELS if synthetic else ("MODEL_INDEPENDENT",)
    return Provenance("SYNTHETIC_TEST_FIXTURE" if synthetic else "MODEL_INDEPENDENT", description, labels=labels)


def _output(*, synthetic: bool = False) -> OutputContract:
    labels = ARTIFACT_LABELS + (SYNTHETIC_OBJECTIVE_LABELS if synthetic else ())
    return OutputContract("run017-deterministic-artifacts-v1",
                          ("experiment.json", "checkpoint.json", "trial.json", "metrics.json", "evaluator-output.json", "issues.json"),
                          True, labels)


def _context(kind: EvaluationContextClass, context_id: str, *, synthetic_plant_hash: str | None = None,
             apparatus_profile_hash_value: str | None = None) -> EvaluationContext:
    synthetic = kind is EvaluationContextClass.SYNTHETIC_CONTROL_FIXTURE
    return EvaluationContext(EVALUATION_CONTEXT_SCHEMA_VERSION, context_id, kind,
                             SYNTHETIC_LABELS if synthetic else ("MODEL_INDEPENDENT",),
                             apparatus_profile_hash=apparatus_profile_hash_value,
                             synthetic_plant_hash=synthetic_plant_hash,
                             provenance=_prov(context_id, synthetic=synthetic))


def _base(experiment_id: str, kind: CandidateKind, plan: CandidatePlan, context: EvaluationContext,
          evaluator: EvaluatorId, metrics: tuple[str, ...], *, synthetic: bool = False,
          objectives: tuple[ObjectiveSpec, ...] = ()) -> ExperimentSpec:
    adapter = OptimizerAdapterSpec("run017-no-op-boundary", "1",
        plan.search_space.semantic_hash if plan.search_space else "NOT_APPLICABLE",
        tuple(semantic_hash(item) for item in objectives), None, 17, "NO_OP_INTERFACE_VALIDATOR", True, False)
    return ExperimentSpec(EXPERIMENT_SCHEMA_VERSION, experiment_id, experiment_id.replace("_", " "),
        "Run 017 model-independent protocol validation; never physical performance", kind, plan, context,
        evaluator_spec(evaluator), tuple(registered_metric(item) for item in metrics), objectives,
        SeedLedger(170017, "sha256-namespaced-uint64-v1",
                   ("candidate_fixture_generation", "synthetic_evaluator_behavior", "observation_noise", "synthetic_plant_behavior", "controller_behavior")),
        {"experiment_protocol": "run017-experiment-protocol-v1"}, ARTIFACT_LABELS,
        _prov(experiment_id, synthetic=synthetic), _output(synthetic=synthetic), adapter)


def _family_paths(root: Path) -> Mapping[str, Path]:
    return {name: next((root / "configs/run_015").glob(f"*_{name}.yaml")) for name in (
        "piecewise_baseline", "cubic_baseline", "fourier_zero", "piecewise_multiknot", "fourier_high_bandwidth")}


def _policy_structural(root: Path) -> tuple[ExperimentSpec, Mapping[str, object]]:
    paths = _family_paths(root)
    candidates = []
    assets = {}
    for name in ("piecewise_baseline", "cubic_baseline", "fourier_zero", "piecewise_multiknot"):
        family = load_family_config(paths[name]); h = family_hashes(family).complete_policy_package; assets[h] = family
        candidates.append(CandidateSpec(name, CandidateKind.OPEN_LOOP_POLICY_SPEC, {"asset_hash": h}, (h,), None, None,
                                        _prov(f"Run 015 family {name}"), ("MODEL_INDEPENDENT",)))
    plan = CandidatePlan("policy-structural-plan", CandidatePlanKind.EXPLICIT_CANDIDATE_LIST, tuple(candidates), None, {}, None, True, False, _prov("explicit structural candidates"))
    return _base("policy_structural_comparison", CandidateKind.OPEN_LOOP_POLICY_SPEC, plan,
                 _context(EvaluationContextClass.MODEL_INDEPENDENT_STRUCTURAL, "run017-structural"),
                 EvaluatorId.POLICY_STRUCTURAL_EVALUATOR,
                 ("parameter_count", "adjustable_parameter_count", "event_count", "structural_boundary_count")), assets


def _request(family, profile, mode, reconstruction, diagnostic=None):
    return CompilationRequest(family_hashes(family).complete_policy_package, apparatus_profile_hash(profile), mode,
                              0.0, .002, InitialStateMode.POLICY_STATE_AT_START, None, None, diagnostic, reconstruction)


def _apparatus(root: Path) -> tuple[ExperimentSpec, Mapping[str, object]]:
    paths = _family_paths(root); base = load_family_config(paths["piecewise_multiknot"]); high = load_family_config(paths["fourier_high_bandwidth"])
    fields = {item.channel_id: item.field for item in base.abi_spec.control_channels}
    cases = []
    identity = synthetic_identity_profile(fields)
    cases.append(("exact", base, identity, CompilationMode.EXACT_ONLY, ReconstructionMode.SYNTHETIC_CONTINUOUS_IDENTITY_BINDING, None))
    cases.append(("approximate", base, synthetic_quantized_profile(fields), CompilationMode.SAMPLE_AND_HOLD, ReconstructionMode.ZERO_ORDER_HOLD, None))
    high_fields = {item.channel_id: item.field for item in high.abi_spec.control_channels}
    cases.append(("infeasible", high, synthetic_rate_limited_profile(high_fields), CompilationMode.SAMPLE_AND_HOLD, ReconstructionMode.ZERO_ORDER_HOLD, None))
    cases.append(("diagnostic_incomplete", base, source_incomplete_profile(fields), CompilationMode.DIAGNOSTIC_PARTIAL_PROFILE, ReconstructionMode.ZERO_ORDER_HOLD, .0005))
    assets = {}; candidates = []
    for name, family, profile, mode, reconstruction, diagnostic in cases:
        compiled, _ = compile_family_policy(family, profile, _request(family, profile, mode, reconstruction, diagnostic))
        h = semantic_hash(compiled); assets[h] = compiled
        candidates.append(CandidateSpec(name, CandidateKind.COMPILED_CONTROL_SCHEDULE, {"asset_hash": h},
                                        (family_hashes(family).complete_policy_package, apparatus_profile_hash(profile)), None, None,
                                        _prov(f"Run 014 compilation fixture {name}"), ("MODEL_INDEPENDENT", "NOT_HARDWARE_EVIDENCE")))
    plan = CandidatePlan("apparatus-compilation-plan", CandidatePlanKind.EXPLICIT_CANDIDATE_LIST, tuple(candidates), None, {}, None, True, False, _prov("Run 014 compiler outputs"))
    return _base("apparatus_compilation", CandidateKind.COMPILED_CONTROL_SCHEDULE, plan,
                 _context(EvaluationContextClass.MODEL_INDEPENDENT_STRUCTURAL, "run017-compilation"),
                 EvaluatorId.SCHEDULE_COMPILATION_EVALUATOR,
                 ("command_count", "simultaneous_command_group_count", "maximum_event_displacement", "infeasibility_issue_count", "profile_completeness")), assets


def _feedback(root: Path) -> tuple[ExperimentSpec, Mapping[str, object]]:
    assets = {}; candidates = []
    for path in sorted((root / "configs/run_016").glob("*.yaml")):
        session = load_feedback_example(path, root); recorded = run_feedback_session(session); h = feedback_hash(session)
        assets[h] = (session, recorded)
        candidates.append(CandidateSpec(session.session_id, CandidateKind.FEEDBACK_SESSION_SPEC, {"asset_hash": h},
                                        tuple(recorded.spec_hashes.values()), None, None, _prov("Run 016 synthetic feedback session", synthetic=True), SYNTHETIC_LABELS))
    plan = CandidatePlan("feedback-replay-plan", CandidatePlanKind.EXPLICIT_CANDIDATE_LIST, tuple(candidates), None, {}, None, True, False, _prov("Run 016 session replay", synthetic=True))
    plant_hash = semantic_hash(tuple(candidate.semantic_hash for candidate in candidates))
    return _base("feedback_replay", CandidateKind.FEEDBACK_SESSION_SPEC, plan,
                 _context(EvaluationContextClass.SYNTHETIC_CONTROL_FIXTURE, "run017-feedback", synthetic_plant_hash=plant_hash),
                 EvaluatorId.FEEDBACK_REPLAY_EVALUATOR,
                 ("observation_packet_count", "missing_packet_count", "fallback_count", "replay_equality", "maximum_action_to_effect_latency"), synthetic=True), assets


def _synthetic() -> tuple[ExperimentSpec, Mapping[str, object]]:
    dims = (
        SearchDimensionSpec("x", "synthetic[0]", "x", SearchDType.REAL, (), "dimensionless", True, -1.0, 1.0, (-1.0, 0.0, 1.0), "EXPLICIT_SYNTHETIC_FIXTURE", ParameterTransform.LINEAR_UNIT_INTERVAL, {}, 0),
        SearchDimensionSpec("category", "synthetic[1]", "category", SearchDType.INTEGER, (), "dimensionless", True, 0, 2, (0, 1, 2), "EXPLICIT_SYNTHETIC_FIXTURE", ParameterTransform.IDENTITY, {}, 1),
    )
    space = SearchSpaceSpec(SEARCH_SPACE_SCHEMA_VERSION, "run017-quadratic-grid", semantic_hash(("x", "category")), dims, _prov("synthetic two-dimensional layout", synthetic=True))
    plan = CandidatePlan("synthetic-grid-plan", CandidatePlanKind.CARTESIAN_GRID_FIXTURE, (), space, {"x": (-1.0, 0.0, 1.0), "category": (0, 1, 2)}, None, True, False, _prov("deterministic Cartesian fixture", synthetic=True))
    metric = registered_metric("synthetic_fixture_value")
    objective = ObjectiveSpec(metric.metric_id, ObjectiveDirection.MINIMIZE, None, metric.units,
                              metric.authorization, ObjectiveRole.PRIMARY, _prov("synthetic objective declaration", synthetic=True))
    return _base("synthetic_search_plumbing", CandidateKind.SYNTHETIC_PARAMETER_VECTOR, plan,
                 _context(EvaluationContextClass.SYNTHETIC_CONTROL_FIXTURE, "run017-synthetic-vector", synthetic_plant_hash="NO_PLANT_PURE_MATH_FIXTURE"),
                 EvaluatorId.SYNTHETIC_VECTOR_EVALUATOR, ("synthetic_fixture_value", "synthetic_coordinate_terms"), synthetic=True, objectives=(objective,)), {}


def _locked() -> tuple[ExperimentSpec, Mapping[str, object]]:
    candidate = CandidateSpec("locked-physical-request", CandidateKind.SYNTHETIC_PARAMETER_VECTOR,
        {"center": [0.0]}, ("NO_MOLECULAR_MODEL_SELECTED",), "synthetic-locked-layout", (0.0,),
        _prov("candidate used only to prove pre-evaluation lock", synthetic=True), SYNTHETIC_LABELS)
    plan = CandidatePlan("locked-metric-plan", CandidatePlanKind.SINGLE_BASELINE_CANDIDATE, (candidate,), None, {}, None, True, False, _prov("locked metric protocol fixture", synthetic=True))
    return _base("locked_physical_metric", CandidateKind.SYNTHETIC_PARAMETER_VECTOR, plan,
                 _context(EvaluationContextClass.SYNTHETIC_CONTROL_FIXTURE, "run017-lock-check", synthetic_plant_hash="NO_PHYSICS"),
                 EvaluatorId.SYNTHETIC_VECTOR_EVALUATOR, ("capture_velocity",), synthetic=True), {}


BUILDERS = {
    "policy_structural_comparison": _policy_structural,
    "apparatus_compilation": _apparatus,
    "feedback_replay": _feedback,
    "synthetic_search_plumbing": lambda root: _synthetic(),
    "locked_physical_metric": lambda root: _locked(),
}


def build_example(example_id: str, root: Path) -> tuple[ExperimentSpec, RuntimeAssets]:
    if example_id not in BUILDERS:
        raise ValueError(f"unknown Run 017 example {example_id}; registry is closed")
    spec, assets = BUILDERS[example_id](root)
    return spec, RuntimeAssets(assets)


def load_example_config(path: str | Path, root: Path) -> tuple[ExperimentSpec, RuntimeAssets]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != "mgf-mot-experiment-example-selector-v1":
        raise ValueError("unknown Run 017 example selector schema")
    return build_example(str(data.get("example_id")), root)

