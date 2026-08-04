"""Run 017 model-independent experiment and deterministic search protocol.

This module is deliberately independent of molecular force, molecular trajectory,
capture, optimizer, reinforcement-learning, and hardware-driver implementations.
Serialized specifications contain data only.  Runtime assets are supplied through
an explicit hash-addressed registry and are never dynamically imported.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass, replace
from enum import Enum
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence


EXPERIMENT_SCHEMA_VERSION = "mgf-mot-experiment-spec-v1"
EVALUATION_CONTEXT_SCHEMA_VERSION = "mgf-mot-evaluation-context-v1"
METRIC_REGISTRY_SCHEMA_VERSION = "mgf-mot-metric-registry-v1"
SEARCH_SPACE_SCHEMA_VERSION = "mgf-mot-search-space-v1"
TRIAL_SCHEMA_VERSION = "mgf-mot-trial-manifest-v1"
EXPERIMENT_RUN_SCHEMA_VERSION = "mgf-mot-experiment-run-v1"
CHECKPOINT_SCHEMA_VERSION = "mgf-mot-experiment-checkpoint-v1"
PIPELINE_VERSION = "run017-authorize-before-evaluate-v1"
SEED_DERIVATION_VERSION = "sha256-namespaced-uint64-v1"
IMPLEMENTATION_VERSION = "run017-experiment-protocol-v1"
RUN017_LABEL = "MODEL_INDEPENDENT_NOT_RODRIGUEZ_REPLICATION_RUN_017_EXPERIMENT_SEARCH_PROTOCOL_ONLY"
SYNTHETIC_LABELS = ("MODEL_INDEPENDENT", "SYNTHETIC_TEST_FIXTURE", "NOT_MGF_PHYSICS")
SYNTHETIC_OBJECTIVE_LABELS = ("SYNTHETIC_OBJECTIVE", "NOT_PHYSICAL_PERFORMANCE")


class ExperimentProtocolError(ValueError):
    pass


class EvaluationContextClass(str, Enum):
    MODEL_INDEPENDENT_STRUCTURAL = "MODEL_INDEPENDENT_STRUCTURAL"
    SYNTHETIC_CONTROL_FIXTURE = "SYNTHETIC_CONTROL_FIXTURE"
    FROZEN_PROVISIONAL_PHYSICS_REFERENCE = "FROZEN_PROVISIONAL_PHYSICS_REFERENCE"
    EXACT_MODEL_PENDING = "EXACT_MODEL_PENDING"


class CandidateKind(str, Enum):
    OPEN_LOOP_POLICY_SPEC = "OPEN_LOOP_POLICY_SPEC"
    OPEN_LOOP_PARAMETER_VECTOR = "OPEN_LOOP_PARAMETER_VECTOR"
    COMPILED_CONTROL_SCHEDULE = "COMPILED_CONTROL_SCHEDULE"
    FEEDBACK_CONTROLLER_SPEC = "FEEDBACK_CONTROLLER_SPEC"
    FEEDBACK_SESSION_SPEC = "FEEDBACK_SESSION_SPEC"
    SYNTHETIC_PARAMETER_VECTOR = "SYNTHETIC_PARAMETER_VECTOR"
    RECORDED_CANDIDATE_REFERENCE = "RECORDED_CANDIDATE_REFERENCE"


class EvaluatorId(str, Enum):
    POLICY_STRUCTURAL_EVALUATOR = "POLICY_STRUCTURAL_EVALUATOR"
    SCHEDULE_COMPILATION_EVALUATOR = "SCHEDULE_COMPILATION_EVALUATOR"
    FEEDBACK_REPLAY_EVALUATOR = "FEEDBACK_REPLAY_EVALUATOR"
    SYNTHETIC_VECTOR_EVALUATOR = "SYNTHETIC_VECTOR_EVALUATOR"
    MGF_FORCE_EVALUATOR = "MGF_FORCE_EVALUATOR"
    MGF_TRAJECTORY_EVALUATOR = "MGF_TRAJECTORY_EVALUATOR"
    MGF_CAPTURE_EVALUATOR = "MGF_CAPTURE_EVALUATOR"
    HARDWARE_EXPERIMENT_EVALUATOR = "HARDWARE_EXPERIMENT_EVALUATOR"


class MetricAuthorization(str, Enum):
    AUTHORIZED_MODEL_INDEPENDENT = "AUTHORIZED_MODEL_INDEPENDENT"
    AUTHORIZED_SYNTHETIC_ONLY = "AUTHORIZED_SYNTHETIC_ONLY"
    LOCKED_BASELINE_NOT_REPRODUCED = "LOCKED_BASELINE_NOT_REPRODUCED"
    LOCKED_EVALUATOR_NOT_AUTHORIZED = "LOCKED_EVALUATOR_NOT_AUTHORIZED"
    LOCKED_REQUIRED_MODEL_MISSING = "LOCKED_REQUIRED_MODEL_MISSING"
    LOCKED_REQUIRED_APPARATUS_PROFILE_MISSING = "LOCKED_REQUIRED_APPARATUS_PROFILE_MISSING"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class MetricResultStatus(str, Enum):
    VALUE = "VALUE"
    METRIC_LOCKED = "METRIC_LOCKED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ObjectiveDirection(str, Enum):
    MINIMIZE = "MINIMIZE"
    MAXIMIZE = "MAXIMIZE"
    TARGET = "TARGET"


class ObjectiveRole(str, Enum):
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    CONSTRAINT = "CONSTRAINT"
    DIAGNOSTIC = "DIAGNOSTIC"


class SearchDType(str, Enum):
    REAL = "real"
    INTEGER = "integer"
    CATEGORICAL = "categorical"


class ParameterTransform(str, Enum):
    IDENTITY = "IDENTITY"
    LINEAR_UNIT_INTERVAL = "LINEAR_UNIT_INTERVAL"
    LOG_POSITIVE = "LOG_POSITIVE"
    SIGNED_LOG = "SIGNED_LOG"
    CATEGORICAL_INDEX = "CATEGORICAL_INDEX"


class CandidatePlanKind(str, Enum):
    EXPLICIT_CANDIDATE_LIST = "EXPLICIT_CANDIDATE_LIST"
    CARTESIAN_GRID_FIXTURE = "CARTESIAN_GRID_FIXTURE"
    RECORDED_PROPOSAL_SEQUENCE = "RECORDED_PROPOSAL_SEQUENCE"
    SINGLE_BASELINE_CANDIDATE = "SINGLE_BASELINE_CANDIDATE"


class TrialStatus(str, Enum):
    PLANNED = "PLANNED"
    VALIDATED = "VALIDATED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    SUCCEEDED_WITH_DIAGNOSTICS = "SUCCEEDED_WITH_DIAGNOSTICS"
    METRIC_LOCKED = "METRIC_LOCKED"
    FAILED_VALIDATION = "FAILED_VALIDATION"
    FAILED_AUTHORIZATION = "FAILED_AUTHORIZATION"
    FAILED_EVALUATION = "FAILED_EVALUATION"
    FAILED_ARTIFACT_INTEGRITY = "FAILED_ARTIFACT_INTEGRITY"
    SKIPPED_DUPLICATE = "SKIPPED_DUPLICATE"
    CANCELLED = "CANCELLED"


class IssueSeverity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass(frozen=True)
class Provenance:
    provenance_class: str
    source_description: str
    source_hashes: tuple[str, ...] = ()
    labels: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class PhysicsReference:
    model_package_hash: str | None
    model_schema_version: str | None
    validation_gate: str
    model_status: str
    benchmark_status: str
    force_field_hash: str | None = None
    trajectory_evaluator_version: str | None = None
    opaque_nonexecuting: bool = True


@dataclass(frozen=True)
class EvaluationContext:
    schema_version: str
    context_id: str
    context_class: EvaluationContextClass
    labels: tuple[str, ...]
    apparatus_profile_hash: str | None = None
    observation_spec_hash: str | None = None
    controller_spec_hash: str | None = None
    policy_spec_hash: str | None = None
    parameter_layout_hash: str | None = None
    synthetic_plant_hash: str | None = None
    physics_reference: PhysicsReference | None = None
    execution_authorized: bool = True
    provenance: Provenance = field(default_factory=lambda: Provenance("MODEL_INDEPENDENT", "unspecified"))


@dataclass(frozen=True)
class CandidateSpec:
    candidate_id: str
    candidate_kind: CandidateKind
    payload: Mapping[str, Any]
    source_specification_hashes: tuple[str, ...]
    parameter_layout_hash: str | None
    parameter_values: tuple[Any, ...] | None
    provenance: Provenance
    authorization_labels: tuple[str, ...]
    declared_semantic_hash: str | None = None

    @property
    def semantic_hash(self) -> str:
        value = replace(self, candidate_id="", declared_semantic_hash=None)
        return semantic_hash(value)


@dataclass(frozen=True)
class EvaluatorSpec:
    evaluator_id: EvaluatorId
    evaluator_version: str
    implementation_version: str
    input_schema: str
    output_schema: str
    authorized: bool
    provenance: Provenance


@dataclass(frozen=True)
class MetricSpec:
    metric_id: str
    name: str
    description: str
    units: str
    shape: tuple[int, ...]
    dtype: str
    compatible_evaluators: tuple[EvaluatorId, ...]
    compatible_contexts: tuple[EvaluationContextClass, ...]
    aggregation: str
    authorization: MetricAuthorization
    meaning: str | None
    objective_eligible: bool
    provenance: Provenance
    required_future_artifact_or_gate: str | None = None


@dataclass(frozen=True)
class MetricResult:
    metric_id: str
    status: MetricResultStatus
    units: str
    value: Any | None
    lock_reason: str | None
    required_missing_authorization: str | None
    required_future_artifact_or_gate: str | None
    labels: tuple[str, ...]


@dataclass(frozen=True)
class ObjectiveSpec:
    metric_id: str
    direction: ObjectiveDirection
    target: float | None
    units: str
    authorization_requirement: MetricAuthorization
    role: ObjectiveRole
    provenance: Provenance


@dataclass(frozen=True)
class SearchDimensionSpec:
    dimension_id: str
    parameter_layout_entry: str
    name: str
    dtype: SearchDType
    shape: tuple[int, ...]
    units: str
    adjustable: bool
    lower_bound: float | None
    upper_bound: float | None
    allowed_values: tuple[Any, ...] | None
    bound_provenance: str
    transform: ParameterTransform
    transform_parameters: Mapping[str, Any]
    serialization_order: int


@dataclass(frozen=True)
class SearchSpaceSpec:
    schema_version: str
    search_space_id: str
    parameter_layout_hash: str
    dimensions: tuple[SearchDimensionSpec, ...]
    provenance: Provenance

    @property
    def semantic_hash(self) -> str:
        return semantic_hash(self)


@dataclass(frozen=True)
class CandidatePlan:
    plan_id: str
    plan_kind: CandidatePlanKind
    candidates: tuple[CandidateSpec, ...]
    search_space: SearchSpaceSpec | None
    grid_values: Mapping[str, tuple[Any, ...]]
    recorded_source_hash: str | None
    deduplicate: bool
    adaptive: bool
    provenance: Provenance

    @property
    def semantic_hash(self) -> str:
        return semantic_hash(self)


@dataclass(frozen=True)
class SeedLedger:
    root_seed: int
    derivation_version: str
    stream_names: tuple[str, ...]

    def derive(self, trial_identity: str, stream_name: str) -> int:
        if stream_name not in self.stream_names:
            raise ExperimentProtocolError(f"UNDECLARED_SEED_STREAM: {stream_name}")
        material = f"{self.derivation_version}|{self.root_seed}|{trial_identity}|{stream_name}"
        return int.from_bytes(sha256(material.encode()).digest()[:8], "big")


@dataclass(frozen=True)
class OutputContract:
    artifact_schema: str
    required_files: tuple[str, ...]
    atomic_write_required: bool
    warning_labels: tuple[str, ...]


@dataclass(frozen=True)
class OptimizerAdapterSpec:
    adapter_id: str
    adapter_version: str
    search_space_hash: str
    objective_spec_hashes: tuple[str, ...]
    proposal_history_hash: str | None
    seed: int | None
    optimizer_family_id: str
    optimizer_interface_authorized: bool
    optimization_run_authorized: bool = False


@dataclass(frozen=True)
class ExperimentSpec:
    schema_version: str
    experiment_id: str
    experiment_name: str
    purpose: str
    candidate_kind: CandidateKind
    candidate_plan: CandidatePlan
    evaluation_context: EvaluationContext
    evaluator: EvaluatorSpec
    metric_specs: tuple[MetricSpec, ...]
    objectives: tuple[ObjectiveSpec, ...]
    seed_ledger: SeedLedger
    software_versions: Mapping[str, str]
    authorization_labels: tuple[str, ...]
    provenance: Provenance
    output_contract: OutputContract
    optimizer_adapter: OptimizerAdapterSpec | None = None
    volatile_created_at: str | None = field(default=None, compare=False)

    @property
    def semantic_hash(self) -> str:
        return semantic_hash(replace(self, volatile_created_at=None))


@dataclass(frozen=True)
class ExperimentValidationIssue:
    code: str
    severity: IssueSeverity
    field_path: str
    message: str
    offending_value: Any = None
    suggested_correction: str | None = None


@dataclass(frozen=True)
class ExperimentValidationResult:
    issues: tuple[ExperimentValidationIssue, ...]

    @property
    def errors(self) -> tuple[ExperimentValidationIssue, ...]:
        return tuple(item for item in self.issues if item.severity is IssueSeverity.ERROR)

    @property
    def valid(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class TrialSpec:
    schema_version: str
    experiment_hash: str
    candidate: CandidateSpec
    evaluator_hash: str
    metric_hashes: tuple[str, ...]
    context_hash: str
    seed_identity: str
    replicate_index: int
    artifact_labels: tuple[str, ...]

    @property
    def trial_hash(self) -> str:
        return semantic_hash(self)


@dataclass(frozen=True)
class TrialFailure:
    failure_stage: str
    issue_codes: tuple[str, ...]
    exception_class: str | None
    reproduction_data: Mapping[str, Any]
    retry_eligible: bool
    candidate_specific: bool


@dataclass(frozen=True)
class TrialResult:
    trial_hash: str
    candidate_hash: str
    status: TrialStatus
    transitions: tuple[TrialStatus, ...]
    metrics: tuple[MetricResult, ...]
    evaluator_output: Mapping[str, Any] | None
    issues: tuple[ExperimentValidationIssue, ...]
    failure: TrialFailure | None
    seeds: Mapping[str, int]
    provenance: Mapping[str, Any]

    @property
    def result_hash(self) -> str:
        return semantic_hash(self)


@dataclass(frozen=True)
class ExperimentCheckpoint:
    schema_version: str
    experiment_hash: str
    candidate_plan_hash: str
    completed_trial_identities: tuple[str, ...]
    locked_trial_identities: tuple[str, ...]
    failed_trial_identities: tuple[str, ...]
    pending_trial_identities: tuple[str, ...]
    artifact_hashes: Mapping[str, str]
    seed_ledger_hash: str
    evaluator_version_hashes: tuple[str, ...]
    artifact_labels: tuple[str, ...]
    volatile_write_time: str | None = field(default=None, compare=False)

    @property
    def semantic_hash(self) -> str:
        return semantic_hash(replace(self, volatile_write_time=None))


@dataclass(frozen=True)
class ExperimentManifest:
    schema_version: str
    experiment_hash: str
    candidate_plan_hash: str
    trial_result_hashes: Mapping[str, str]
    duplicate_candidate_hashes: tuple[str, ...]
    pipeline_version: str
    authorization_summary: Mapping[str, bool]
    warning_labels: tuple[str, ...]
    volatile_runtime_metadata: Mapping[str, Any] = field(default_factory=dict, compare=False)

    @property
    def semantic_hash(self) -> str:
        return semantic_hash(replace(self, volatile_runtime_metadata={}))


@dataclass(frozen=True)
class ExperimentReplay:
    experiment_hash: str
    source_manifest_hash: str
    replay_manifest_hash: str
    trial_hashes_equal: bool
    manifest_semantic_hash_equal: bool
    execution_order: tuple[str, ...]


@dataclass(frozen=True)
class ExperimentOperationMetrics:
    planned_trial_count: int
    unique_candidate_count: int
    duplicate_candidate_count: int
    successful_trial_count: int
    locked_trial_count: int
    failed_trial_count: int
    resumed_trial_count: int
    artifact_reuse_count: int
    checkpoint_count: int
    replay_equality_status: bool | None
    classification: str = "EXPERIMENT_OPERATION_METRICS_NOT_SCIENTIFIC_PERFORMANCE"


@dataclass(frozen=True)
class MetricsOnlyReplay:
    trial_hash: str
    recorded_output_hash: str
    recorded_metrics_hash: str
    replayed_metrics_hash: str
    equal: bool


@dataclass(frozen=True)
class ManifestIntegrityAudit:
    experiment_hash: str
    checked_artifact_count: int
    valid: bool
    issues: tuple[ExperimentValidationIssue, ...]


@dataclass(frozen=True)
class RuntimeAssets:
    """Explicit, non-serialized registry of already validated runtime objects."""

    assets: Mapping[str, Any]

    def resolve(self, asset_hash: str) -> Any:
        if asset_hash not in self.assets:
            raise ExperimentProtocolError(f"MISSING_RUNTIME_ASSET: {asset_hash}")
        asset = self.assets[asset_hash]
        if callable(asset):
            raise ExperimentProtocolError("ARBITRARY_EXECUTABLE_ASSET_FORBIDDEN")
        return asset


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: _plain(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    if callable(value):
        raise ExperimentProtocolError("ARBITRARY_EXECUTABLE_CONTENT_FORBIDDEN")
    if isinstance(value, float) and not math.isfinite(value):
        raise ExperimentProtocolError("NONFINITE_SERIALIZED_VALUE")
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(_plain(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def semantic_hash(value: Any) -> str:
    return sha256(canonical_json(value).encode()).hexdigest()


def evaluator_spec(evaluator_id: EvaluatorId) -> EvaluatorSpec:
    authorized = evaluator_id in {
        EvaluatorId.POLICY_STRUCTURAL_EVALUATOR,
        EvaluatorId.SCHEDULE_COMPILATION_EVALUATOR,
        EvaluatorId.FEEDBACK_REPLAY_EVALUATOR,
        EvaluatorId.SYNTHETIC_VECTOR_EVALUATOR,
    }
    versions = {
        EvaluatorId.POLICY_STRUCTURAL_EVALUATOR: "run015-structural-v1",
        EvaluatorId.SCHEDULE_COMPILATION_EVALUATOR: "run014-compiler-v1",
        EvaluatorId.FEEDBACK_REPLAY_EVALUATOR: "run016-feedback-v1",
        EvaluatorId.SYNTHETIC_VECTOR_EVALUATOR: "quadratic-fixture-v1",
    }
    return EvaluatorSpec(evaluator_id, "1", versions.get(evaluator_id, "reserved-v1"),
                         "mgf-mot-candidate-v1", "mgf-mot-evaluator-output-v1", authorized,
                         Provenance("CLOSED_REGISTRY", "Run 017 evaluator registry"))


PHYSICAL_METRIC_IDS = (
    "capture_velocity", "captured_fraction", "bounded_fraction", "retained_population",
    "final_velocity_distribution", "cooling_rate", "loading_rate", "temperature",
    "robust_capture_objective", "experimental_success_rate",
)


def _metric(metric_id: str, units: str, evaluators: tuple[EvaluatorId, ...], contexts: tuple[EvaluationContextClass, ...],
            authorization: MetricAuthorization, *, dtype: str = "float64", shape: tuple[int, ...] = (),
            objective: bool = False, meaning: str | None = None, gate: str | None = None) -> MetricSpec:
    return MetricSpec(metric_id, metric_id.replace("_", " "), f"Run 017 registered metric {metric_id}", units,
                      shape, dtype, evaluators, contexts, "NONE", authorization, meaning, objective,
                      Provenance("CLOSED_REGISTRY", "Run 017 metric registry"), gate)


def build_metric_registry() -> Mapping[str, MetricSpec]:
    structural = (EvaluationContextClass.MODEL_INDEPENDENT_STRUCTURAL,)
    synthetic = (EvaluationContextClass.SYNTHETIC_CONTROL_FIXTURE,)
    p = EvaluatorId.POLICY_STRUCTURAL_EVALUATOR
    c = EvaluatorId.SCHEDULE_COMPILATION_EVALUATOR
    f = EvaluatorId.FEEDBACK_REPLAY_EVALUATOR
    s = EvaluatorId.SYNTHETIC_VECTOR_EVALUATOR
    specs = [
        _metric("parameter_count", "count", (p,), structural, MetricAuthorization.AUTHORIZED_MODEL_INDEPENDENT, dtype="int64"),
        _metric("adjustable_parameter_count", "count", (p,), structural, MetricAuthorization.AUTHORIZED_MODEL_INDEPENDENT, dtype="int64"),
        _metric("event_count", "count", (p,), structural, MetricAuthorization.AUTHORIZED_MODEL_INDEPENDENT, dtype="int64"),
        _metric("structural_boundary_count", "count", (p,), structural, MetricAuthorization.AUTHORIZED_MODEL_INDEPENDENT, dtype="int64"),
        _metric("command_count", "count", (c,), structural, MetricAuthorization.AUTHORIZED_MODEL_INDEPENDENT, dtype="int64"),
        _metric("simultaneous_command_group_count", "count", (c,), structural, MetricAuthorization.AUTHORIZED_MODEL_INDEPENDENT, dtype="int64"),
        _metric("maximum_event_displacement", "s", (c,), structural, MetricAuthorization.AUTHORIZED_MODEL_INDEPENDENT),
        _metric("infeasibility_issue_count", "count", (c,), structural, MetricAuthorization.AUTHORIZED_MODEL_INDEPENDENT, dtype="int64"),
        _metric("profile_completeness", "boolean", (c,), structural, MetricAuthorization.AUTHORIZED_MODEL_INDEPENDENT, dtype="bool"),
        _metric("observation_packet_count", "count", (f,), synthetic, MetricAuthorization.AUTHORIZED_SYNTHETIC_ONLY, dtype="int64"),
        _metric("missing_packet_count", "count", (f,), synthetic, MetricAuthorization.AUTHORIZED_SYNTHETIC_ONLY, dtype="int64"),
        _metric("fallback_count", "count", (f,), synthetic, MetricAuthorization.AUTHORIZED_SYNTHETIC_ONLY, dtype="int64"),
        _metric("replay_equality", "boolean", (f,), synthetic, MetricAuthorization.AUTHORIZED_SYNTHETIC_ONLY, dtype="bool"),
        _metric("maximum_action_to_effect_latency", "s", (f,), synthetic, MetricAuthorization.AUTHORIZED_SYNTHETIC_ONLY),
        _metric("synthetic_fixture_value", "dimensionless", (s,), synthetic, MetricAuthorization.AUTHORIZED_SYNTHETIC_ONLY,
                objective=True, meaning="lower or higher only when an ObjectiveSpec explicitly declares direction"),
        _metric("synthetic_coordinate_terms", "dimensionless", (s,), synthetic, MetricAuthorization.AUTHORIZED_SYNTHETIC_ONLY,
                shape=(-1,)),
    ]
    specs.extend(_metric(mid, "UNRESOLVED", (), (), MetricAuthorization.LOCKED_REQUIRED_MODEL_MISSING,
                         gate="EXACT_MGF_MODEL_AND_AUTHORIZED_PHYSICS_EVALUATOR") for mid in PHYSICAL_METRIC_IDS)
    return {item.metric_id: item for item in specs}


METRIC_REGISTRY = build_metric_registry()


def registered_metric(metric_id: str) -> MetricSpec:
    try:
        return METRIC_REGISTRY[metric_id]
    except KeyError as exc:
        raise ExperimentProtocolError(f"UNKNOWN_METRIC_FAIL_CLOSED: {metric_id}") from exc


def transform_forward(dimension: SearchDimensionSpec, value: Any) -> Any:
    t = dimension.transform
    if t is ParameterTransform.IDENTITY:
        return value
    if t is ParameterTransform.LINEAR_UNIT_INTERVAL:
        lo, hi = dimension.lower_bound, dimension.upper_bound
        if lo is None or hi is None or not hi > lo:
            raise ExperimentProtocolError("INVALID_LINEAR_UNIT_INTERVAL_DOMAIN")
        return (float(value) - lo) / (hi - lo)
    if t is ParameterTransform.LOG_POSITIVE:
        if float(value) <= 0:
            raise ExperimentProtocolError("LOG_POSITIVE_REQUIRES_POSITIVE_VALUE")
        return math.log(float(value))
    if t is ParameterTransform.SIGNED_LOG:
        scale = float(dimension.transform_parameters.get("scale", 0.0))
        if not scale > 0:
            raise ExperimentProtocolError("SIGNED_LOG_REQUIRES_POSITIVE_SCALE")
        v = float(value)
        return math.copysign(math.log1p(abs(v) / scale), v)
    if t is ParameterTransform.CATEGORICAL_INDEX:
        values = dimension.allowed_values
        if values is None or value not in values:
            raise ExperimentProtocolError("CATEGORICAL_VALUE_OUTSIDE_DOMAIN")
        return values.index(value)
    raise ExperimentProtocolError("UNKNOWN_TRANSFORM_FAIL_CLOSED")


def transform_inverse(dimension: SearchDimensionSpec, value: Any) -> Any:
    t = dimension.transform
    if t is ParameterTransform.IDENTITY:
        return value
    if t is ParameterTransform.LINEAR_UNIT_INTERVAL:
        lo, hi = dimension.lower_bound, dimension.upper_bound
        if lo is None or hi is None or not hi > lo:
            raise ExperimentProtocolError("INVALID_LINEAR_UNIT_INTERVAL_DOMAIN")
        return lo + float(value) * (hi - lo)
    if t is ParameterTransform.LOG_POSITIVE:
        return math.exp(float(value))
    if t is ParameterTransform.SIGNED_LOG:
        scale = float(dimension.transform_parameters.get("scale", 0.0))
        if not scale > 0:
            raise ExperimentProtocolError("SIGNED_LOG_REQUIRES_POSITIVE_SCALE")
        v = float(value)
        return math.copysign(scale * math.expm1(abs(v)), v)
    if t is ParameterTransform.CATEGORICAL_INDEX:
        values = dimension.allowed_values
        if values is None or not isinstance(value, int) or not 0 <= value < len(values):
            raise ExperimentProtocolError("CATEGORICAL_INDEX_OUTSIDE_DOMAIN")
        return values[value]
    raise ExperimentProtocolError("UNKNOWN_TRANSFORM_FAIL_CLOSED")


def validate_search_space(space: SearchSpaceSpec, *, bounded_generation: bool = False) -> ExperimentValidationResult:
    issues: list[ExperimentValidationIssue] = []
    if space.schema_version != SEARCH_SPACE_SCHEMA_VERSION:
        issues.append(_issue("UNKNOWN_SEARCH_SCHEMA", "schema_version", space.schema_version))
    orders = [item.serialization_order for item in space.dimensions]
    if len(set(orders)) != len(orders) or orders != sorted(orders):
        issues.append(_issue("INVALID_SERIALIZATION_ORDER", "dimensions", orders))
    for index, dim in enumerate(space.dimensions):
        path = f"dimensions[{index}]"
        if dim.adjustable and bounded_generation and dim.allowed_values is None and (dim.lower_bound is None or dim.upper_bound is None):
            issues.append(_issue("UNKNOWN_BOUNDS_BLOCK_BOUNDED_GENERATION", path, dim.dimension_id))
        if dim.lower_bound is not None and dim.upper_bound is not None and dim.lower_bound > dim.upper_bound:
            issues.append(_issue("INVALID_BOUNDS", path, (dim.lower_bound, dim.upper_bound)))
        try:
            probe = (dim.allowed_values[0] if dim.allowed_values else
                     (dim.lower_bound if dim.lower_bound is not None else 1.0))
            inverse = transform_inverse(dim, transform_forward(dim, probe))
            if isinstance(probe, (int, float)) and not math.isclose(float(probe), float(inverse), rel_tol=1e-12, abs_tol=1e-12):
                issues.append(_issue("NONINVERTIBLE_TRANSFORM", path, dim.transform.value))
        except (ExperimentProtocolError, ValueError, OverflowError) as exc:
            issues.append(_issue("INVALID_TRANSFORM_DOMAIN", path, str(exc)))
    return ExperimentValidationResult(tuple(issues))


def _issue(code: str, field_path: str, value: Any, message: str | None = None,
           severity: IssueSeverity = IssueSeverity.ERROR) -> ExperimentValidationIssue:
    return ExperimentValidationIssue(code, severity, field_path, message or code.replace("_", " ").lower(), value)


def validate_context(context: EvaluationContext) -> ExperimentValidationResult:
    issues: list[ExperimentValidationIssue] = []
    if context.schema_version != EVALUATION_CONTEXT_SCHEMA_VERSION:
        issues.append(_issue("UNKNOWN_CONTEXT_SCHEMA", "evaluation_context.schema_version", context.schema_version))
    if not isinstance(context.context_class, EvaluationContextClass):
        issues.append(_issue("UNKNOWN_EVALUATION_CONTEXT", "evaluation_context.context_class", context.context_class))
    if context.context_class is EvaluationContextClass.SYNTHETIC_CONTROL_FIXTURE and not set(SYNTHETIC_LABELS).issubset(context.labels):
        issues.append(_issue("MISSING_SYNTHETIC_CONTEXT_LABELS", "evaluation_context.labels", context.labels))
    if context.context_class in {EvaluationContextClass.FROZEN_PROVISIONAL_PHYSICS_REFERENCE, EvaluationContextClass.EXACT_MODEL_PENDING}:
        if context.physics_reference is None:
            issues.append(_issue("MISSING_OPAQUE_PHYSICS_REFERENCE", "evaluation_context.physics_reference", None))
        if context.execution_authorized:
            issues.append(_issue("PHYSICS_CONTEXT_EXECUTION_FORBIDDEN_RUN017", "evaluation_context.execution_authorized", True))
    if context.physics_reference is not None and not context.physics_reference.opaque_nonexecuting:
        issues.append(_issue("PHYSICS_REFERENCE_MUST_REMAIN_OPAQUE", "evaluation_context.physics_reference", False))
    return ExperimentValidationResult(tuple(issues))


def validate_candidate(candidate: CandidateSpec) -> ExperimentValidationResult:
    issues: list[ExperimentValidationIssue] = []
    if not isinstance(candidate.candidate_kind, CandidateKind):
        issues.append(_issue("UNKNOWN_CANDIDATE_KIND", "candidate.candidate_kind", candidate.candidate_kind))
    try:
        canonical_json(candidate.payload)
    except ExperimentProtocolError as exc:
        issues.append(_issue("ARBITRARY_OR_INVALID_CANDIDATE_PAYLOAD", "candidate.payload", str(exc)))
    if candidate.declared_semantic_hash is not None and candidate.declared_semantic_hash != candidate.semantic_hash:
        issues.append(_issue("CANDIDATE_HASH_MISMATCH", "candidate.declared_semantic_hash", candidate.declared_semantic_hash))
    if candidate.candidate_kind in {CandidateKind.OPEN_LOOP_PARAMETER_VECTOR, CandidateKind.SYNTHETIC_PARAMETER_VECTOR}:
        if candidate.parameter_values is None or candidate.parameter_layout_hash is None:
            issues.append(_issue("MISSING_PARAMETER_VECTOR_IDENTITY", "candidate", candidate.candidate_id))
    return ExperimentValidationResult(tuple(issues))


def validate_experiment(spec: ExperimentSpec) -> ExperimentValidationResult:
    issues: list[ExperimentValidationIssue] = []
    if spec.schema_version != EXPERIMENT_SCHEMA_VERSION:
        issues.append(_issue("UNKNOWN_EXPERIMENT_SCHEMA", "schema_version", spec.schema_version))
    issues.extend(validate_context(spec.evaluation_context).issues)
    bounded = spec.candidate_plan.plan_kind is CandidatePlanKind.CARTESIAN_GRID_FIXTURE
    if not isinstance(spec.candidate_plan.plan_kind, CandidatePlanKind):
        issues.append(_issue("UNSUPPORTED_CANDIDATE_PLAN_TYPE", "candidate_plan.plan_kind", spec.candidate_plan.plan_kind))
    if spec.candidate_plan.search_space is not None:
        issues.extend(validate_search_space(spec.candidate_plan.search_space, bounded_generation=bounded).issues)
    if spec.candidate_plan.adaptive:
        issues.append(_issue("ADAPTIVE_CANDIDATE_PLANNING_FORBIDDEN", "candidate_plan.adaptive", True))
    if spec.candidate_plan.plan_kind is CandidatePlanKind.CARTESIAN_GRID_FIXTURE and spec.candidate_plan.search_space is None:
        issues.append(_issue("GRID_REQUIRES_SEARCH_SPACE", "candidate_plan.search_space", None))
    try:
        if not isinstance(spec.evaluator.evaluator_id, EvaluatorId):
            raise ExperimentProtocolError(f"unknown evaluator {spec.evaluator.evaluator_id}")
        registered = evaluator_spec(spec.evaluator.evaluator_id)
        if registered != spec.evaluator:
            issues.append(_issue("EVALUATOR_REGISTRY_MISMATCH", "evaluator", spec.evaluator))
    except (ValueError, ExperimentProtocolError) as exc:
        issues.append(_issue("UNKNOWN_EVALUATOR_FAIL_CLOSED", "evaluator", str(exc)))
    if not spec.evaluator.authorized:
        issues.append(_issue("EVALUATOR_NOT_AUTHORIZED", "evaluator.authorized", spec.evaluator.evaluator_id.value))
    if spec.candidate_kind not in {candidate.candidate_kind for candidate in spec.candidate_plan.candidates} and spec.candidate_plan.candidates:
        issues.append(_issue("CANDIDATE_KIND_MISMATCH", "candidate_kind", spec.candidate_kind.value))
    for candidate in spec.candidate_plan.candidates:
        issues.extend(validate_candidate(candidate).issues)
    metric_ids: set[str] = set()
    for index, metric in enumerate(spec.metric_specs):
        if metric.metric_id in metric_ids:
            issues.append(_issue("DUPLICATE_METRIC_ID", f"metric_specs[{index}]", metric.metric_id))
        metric_ids.add(metric.metric_id)
        if not metric.units:
            issues.append(_issue("MISSING_METRIC_UNITS", f"metric_specs[{index}].units", metric.units))
        try:
            if registered_metric(metric.metric_id) != metric:
                issues.append(_issue("METRIC_REGISTRY_MISMATCH", f"metric_specs[{index}]", metric.metric_id))
        except ExperimentProtocolError as exc:
            issues.append(_issue("UNKNOWN_METRIC_FAIL_CLOSED", f"metric_specs[{index}]", str(exc)))
        if metric.authorization not in {MetricAuthorization.AUTHORIZED_MODEL_INDEPENDENT, MetricAuthorization.AUTHORIZED_SYNTHETIC_ONLY}:
            issues.append(_issue("LOCKED_METRIC_REQUESTED", f"metric_specs[{index}]", metric.metric_id,
                                 severity=IssueSeverity.WARNING))
    for objective in spec.objectives:
        if objective.metric_id not in metric_ids:
            issues.append(_issue("OBJECTIVE_METRIC_NOT_REQUESTED", "objectives", objective.metric_id))
        if not isinstance(objective.direction, ObjectiveDirection):
            issues.append(_issue("OBJECTIVE_DIRECTION_MISSING_OR_UNKNOWN", "objectives", objective.metric_id))
        metric = METRIC_REGISTRY.get(objective.metric_id)
        if metric is not None and not metric.objective_eligible:
            issues.append(_issue("METRIC_NOT_OBJECTIVE_ELIGIBLE", "objectives", objective.metric_id))
        if objective.direction is ObjectiveDirection.TARGET and objective.target is None:
            issues.append(_issue("TARGET_OBJECTIVE_REQUIRES_TARGET", "objectives", objective.metric_id))
        if objective.direction is not ObjectiveDirection.TARGET and objective.target is not None:
            issues.append(_issue("NONTARGET_OBJECTIVE_FORBIDS_TARGET", "objectives", objective.metric_id))
        if metric is not None and metric.authorization is not MetricAuthorization.AUTHORIZED_SYNTHETIC_ONLY:
            issues.append(_issue("OBJECTIVE_METRIC_LOCKED", "objectives", objective.metric_id))
    if spec.optimizer_adapter is not None:
        if spec.optimizer_adapter.optimization_run_authorized:
            issues.append(_issue("OPTIMIZATION_RUN_FORBIDDEN_RUN017", "optimizer_adapter.optimization_run_authorized", True))
        if spec.optimizer_adapter.optimizer_family_id not in {"NO_OP_INTERFACE_VALIDATOR", "RECORDED_PROPOSAL_ADAPTER"}:
            issues.append(_issue("UNKNOWN_OPTIMIZER_ADAPTER_FAIL_CLOSED", "optimizer_adapter.optimizer_family_id", spec.optimizer_adapter.optimizer_family_id))
    if spec.evaluation_context.context_class is EvaluationContextClass.SYNTHETIC_CONTROL_FIXTURE:
        forbidden_claims = {"PHYSICAL_PERFORMANCE", "HARDWARE_EXECUTABLE", "MGF_REPLICATION_VALID"}
        found = forbidden_claims.intersection(spec.authorization_labels)
        if found:
            issues.append(_issue("PHYSICAL_CLAIM_FROM_SYNTHETIC_CONTEXT", "authorization_labels", sorted(found)))
    return ExperimentValidationResult(tuple(issues))


def materialize_candidates(plan: CandidatePlan) -> tuple[tuple[CandidateSpec, ...], tuple[str, ...]]:
    if plan.adaptive:
        raise ExperimentProtocolError("ADAPTIVE_CANDIDATE_PLANNING_FORBIDDEN")
    candidates = list(plan.candidates)
    if plan.plan_kind is CandidatePlanKind.CARTESIAN_GRID_FIXTURE:
        if plan.search_space is None:
            raise ExperimentProtocolError("GRID_REQUIRES_SEARCH_SPACE")
        validation = validate_search_space(plan.search_space, bounded_generation=True)
        if not validation.valid:
            raise ExperimentProtocolError("INVALID_GRID_SEARCH_SPACE: " + ",".join(item.code for item in validation.errors))
        dims = sorted((item for item in plan.search_space.dimensions if item.adjustable), key=lambda item: item.serialization_order)
        value_lists: list[tuple[Any, ...]] = []
        for dim in dims:
            values = plan.grid_values.get(dim.dimension_id, dim.allowed_values)
            if not values:
                raise ExperimentProtocolError(f"MISSING_GRID_VALUES: {dim.dimension_id}")
            value_lists.append(tuple(values))
        import itertools
        candidates = []
        for index, values in enumerate(itertools.product(*value_lists)):
            candidates.append(CandidateSpec(f"{plan.plan_id}-{index:04d}", CandidateKind.SYNTHETIC_PARAMETER_VECTOR,
                {"dimension_ids": [item.dimension_id for item in dims]}, (plan.search_space.semantic_hash,),
                plan.search_space.parameter_layout_hash, tuple(values), plan.provenance,
                SYNTHETIC_LABELS + SYNTHETIC_OBJECTIVE_LABELS))
    if plan.plan_kind is CandidatePlanKind.SINGLE_BASELINE_CANDIDATE and len(candidates) != 1:
        raise ExperimentProtocolError("SINGLE_BASELINE_REQUIRES_EXACTLY_ONE_CANDIDATE")
    if plan.plan_kind is CandidatePlanKind.RECORDED_PROPOSAL_SEQUENCE and not plan.recorded_source_hash:
        raise ExperimentProtocolError("RECORDED_PROPOSALS_REQUIRE_SOURCE_HASH")
    unique: list[CandidateSpec] = []
    seen: set[str] = set()
    duplicates: list[str] = []
    for candidate in candidates:
        h = candidate.semantic_hash
        if h in seen:
            duplicates.append(h)
            if plan.deduplicate:
                continue
        seen.add(h)
        unique.append(candidate)
    return tuple(unique), tuple(duplicates)


def build_trial_specs(spec: ExperimentSpec) -> tuple[tuple[TrialSpec, ...], tuple[str, ...]]:
    candidates, duplicates = materialize_candidates(spec.candidate_plan)
    evaluator_hash = semantic_hash(spec.evaluator)
    metric_hashes = tuple(semantic_hash(item) for item in spec.metric_specs)
    context_hash = semantic_hash(spec.evaluation_context)
    trials = tuple(TrialSpec(TRIAL_SCHEMA_VERSION, spec.semantic_hash, candidate, evaluator_hash,
                             metric_hashes, context_hash, semantic_hash((candidate.semantic_hash, 0)), 0,
                             spec.output_contract.warning_labels)
                   for candidate in candidates)
    return trials, duplicates


def _metric_lock(metric: MetricSpec) -> MetricResult:
    return MetricResult(metric.metric_id, MetricResultStatus.METRIC_LOCKED, metric.units, None,
                        metric.authorization.value, metric.authorization.value,
                        metric.required_future_artifact_or_gate, (RUN017_LABEL, "NO_NUMERIC_STAND_IN"))


def _authorize_metric(metric: MetricSpec, spec: ExperimentSpec) -> str | None:
    if metric.authorization not in {MetricAuthorization.AUTHORIZED_MODEL_INDEPENDENT, MetricAuthorization.AUTHORIZED_SYNTHETIC_ONLY}:
        return metric.authorization.value
    if spec.evaluator.evaluator_id not in metric.compatible_evaluators:
        return MetricAuthorization.LOCKED_EVALUATOR_NOT_AUTHORIZED.value
    if spec.evaluation_context.context_class not in metric.compatible_contexts:
        return "INCOMPATIBLE_EVALUATION_CONTEXT"
    if metric.authorization is MetricAuthorization.AUTHORIZED_SYNTHETIC_ONLY and not set(SYNTHETIC_LABELS).issubset(spec.evaluation_context.labels):
        return "MISSING_SYNTHETIC_AUTHORIZATION_LABELS"
    return None


def _evaluate(spec: ExperimentSpec, trial: TrialSpec, assets: RuntimeAssets) -> Mapping[str, Any]:
    eid = spec.evaluator.evaluator_id
    candidate = trial.candidate
    asset_hash = str(candidate.payload.get("asset_hash", ""))
    if eid is EvaluatorId.SYNTHETIC_VECTOR_EVALUATOR:
        values = tuple(float(item) for item in (candidate.parameter_values or ()))
        center = tuple(float(item) for item in candidate.payload.get("center", [0.0] * len(values)))
        if len(center) != len(values):
            raise ExperimentProtocolError("SYNTHETIC_CENTER_SHAPE_MISMATCH")
        terms = tuple((x - c) ** 2 for x, c in zip(values, center))
        return {"synthetic_fixture_value": sum(terms), "synthetic_coordinate_terms": terms,
                "labels": SYNTHETIC_OBJECTIVE_LABELS + SYNTHETIC_LABELS}
    asset = assets.resolve(asset_hash)
    if eid is EvaluatorId.POLICY_STRUCTURAL_EVALUATOR:
        from .open_loop_policy_families import structural_metrics
        metrics = structural_metrics(asset)
        return {"parameter_count": metrics.parameter_count,
                "adjustable_parameter_count": metrics.adjustable_parameter_count,
                "event_count": metrics.event_count,
                "structural_boundary_count": metrics.structural_boundary_count}
    if eid is EvaluatorId.SCHEDULE_COMPILATION_EVALUATOR:
        compiled = asset
        return {"command_count": compiled.total_command_count,
                "simultaneous_command_group_count": compiled.simultaneous_command_group_count,
                "maximum_event_displacement": compiled.maximum_event_displacement_s,
                "infeasibility_issue_count": len(compiled.violations),
                "profile_completeness": compiled.profile_complete}
    if eid is EvaluatorId.FEEDBACK_REPLAY_EVALUATOR:
        session_spec, recorded = asset
        from .feedback_policy import replay_full_session
        replay = replay_full_session(session_spec, recorded)
        m = recorded.metrics
        return {"observation_packet_count": m.packet_count, "missing_packet_count": m.missing_count,
                "fallback_count": m.fallback_count, "replay_equality": replay.replay_equal,
                "maximum_action_to_effect_latency": m.maximum_action_to_effect_latency_s,
                "labels": SYNTHETIC_LABELS}
    raise ExperimentProtocolError(f"EVALUATOR_NOT_AUTHORIZED: {eid.value}")


def execute_trial(spec: ExperimentSpec, trial: TrialSpec, assets: RuntimeAssets | None = None) -> TrialResult:
    validation = validate_candidate(trial.candidate)
    seeds = {name: spec.seed_ledger.derive(trial.trial_hash, name) for name in spec.seed_ledger.stream_names}
    provenance = {"pipeline_version": PIPELINE_VERSION, "evaluator_hash": trial.evaluator_hash,
                  "context_hash": trial.context_hash, "labels": list(spec.output_contract.warning_labels)}
    if not validation.valid:
        failure = TrialFailure("validate_candidate", tuple(item.code for item in validation.errors), None,
                               {"trial_hash": trial.trial_hash}, False, True)
        return TrialResult(trial.trial_hash, trial.candidate.semantic_hash, TrialStatus.FAILED_VALIDATION,
                           (TrialStatus.PLANNED, TrialStatus.FAILED_VALIDATION), (), None,
                           validation.issues, failure, seeds, provenance)
    locks: list[MetricResult] = []
    for metric in spec.metric_specs:
        reason = _authorize_metric(metric, spec)
        if reason is not None:
            base = _metric_lock(metric)
            locks.append(replace(base, lock_reason=reason, required_missing_authorization=reason))
    if locks:
        return TrialResult(trial.trial_hash, trial.candidate.semantic_hash, TrialStatus.METRIC_LOCKED,
                           (TrialStatus.PLANNED, TrialStatus.VALIDATED, TrialStatus.METRIC_LOCKED), tuple(locks),
                           None, (), None, seeds, provenance)
    if not spec.evaluator.authorized or not spec.evaluation_context.execution_authorized:
        issue = _issue("EVALUATION_NOT_AUTHORIZED", "evaluation_context", spec.evaluation_context.context_class.value)
        failure = TrialFailure("authorize", (issue.code,), None, {"trial_hash": trial.trial_hash}, False, False)
        return TrialResult(trial.trial_hash, trial.candidate.semantic_hash, TrialStatus.FAILED_AUTHORIZATION,
                           (TrialStatus.PLANNED, TrialStatus.VALIDATED, TrialStatus.FAILED_AUTHORIZATION), (), None,
                           (issue,), failure, seeds, provenance)
    try:
        output = _evaluate(spec, trial, assets or RuntimeAssets({}))
        results = tuple(MetricResult(metric.metric_id, MetricResultStatus.VALUE, metric.units,
                                     output[metric.metric_id], None, None, None,
                                     tuple(output.get("labels", (RUN017_LABEL,)))) for metric in spec.metric_specs)
        return TrialResult(trial.trial_hash, trial.candidate.semantic_hash, TrialStatus.SUCCEEDED,
                           (TrialStatus.PLANNED, TrialStatus.VALIDATED, TrialStatus.RUNNING, TrialStatus.SUCCEEDED),
                           results, output, (), None, seeds, provenance)
    except Exception as exc:  # converted into a deterministic structured failure
        issue = _issue("EVALUATOR_EXECUTION_FAILED", "evaluator", spec.evaluator.evaluator_id.value, str(exc))
        failure = TrialFailure("execute_evaluator", (issue.code,), type(exc).__name__,
                               {"trial_hash": trial.trial_hash, "candidate_hash": trial.candidate.semantic_hash},
                               False, True)
        return TrialResult(trial.trial_hash, trial.candidate.semantic_hash, TrialStatus.FAILED_EVALUATION,
                           (TrialStatus.PLANNED, TrialStatus.VALIDATED, TrialStatus.RUNNING, TrialStatus.FAILED_EVALUATION),
                           (), None, (issue,), failure, seeds, provenance)


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(_plain(value), indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _write_trial_artifacts(root: Path, trial: TrialSpec, result: TrialResult) -> Mapping[str, str]:
    trial_root = root / "trials" / trial.trial_hash
    labels = trial.artifact_labels
    if result.evaluator_output and set(SYNTHETIC_OBJECTIVE_LABELS).issubset(result.evaluator_output.get("labels", ())):
        labels = labels + SYNTHETIC_OBJECTIVE_LABELS
    paths = {
        "trial.json": {"artifact_labels": labels, "trial": trial},
        "metrics.json": {"artifact_labels": labels, "metrics": result.metrics},
        "evaluator-output.json": {"artifact_labels": labels, "evaluator_output": result.evaluator_output},
        "issues.json": {"artifact_labels": labels, "issues": result.issues, "failure": result.failure},
    }
    hashes: dict[str, str] = {}
    for name, value in paths.items():
        path = trial_root / name
        if path.exists():
            expected = json.dumps(_plain(value), indent=2, sort_keys=True, allow_nan=False) + "\n"
            if path.read_text(encoding="utf-8") != expected:
                raise ExperimentProtocolError(f"ARTIFACT_CONFLICT: {path}")
        else:
            _atomic_json(path, value)
        hashes[str(path.relative_to(root))] = file_hash(path)
    return hashes


def _checkpoint(spec: ExperimentSpec, trials: Sequence[TrialSpec], results: Mapping[str, TrialResult],
                artifacts: Mapping[str, str]) -> ExperimentCheckpoint:
    completed = tuple(sorted(key for key, value in results.items() if value.status in {TrialStatus.SUCCEEDED, TrialStatus.SUCCEEDED_WITH_DIAGNOSTICS}))
    locked = tuple(sorted(key for key, value in results.items() if value.status is TrialStatus.METRIC_LOCKED))
    failed = tuple(sorted(key for key, value in results.items() if value.status.value.startswith("FAILED_")))
    pending = tuple(trial.trial_hash for trial in trials if trial.trial_hash not in results)
    return ExperimentCheckpoint(CHECKPOINT_SCHEMA_VERSION, spec.semantic_hash, spec.candidate_plan.semantic_hash,
                                completed, locked, failed, pending, dict(sorted(artifacts.items())),
                                semantic_hash(spec.seed_ledger), (semantic_hash(spec.evaluator),),
                                spec.output_contract.warning_labels)


def validate_checkpoint(checkpoint: ExperimentCheckpoint, spec: ExperimentSpec, root: Path) -> ExperimentValidationResult:
    issues: list[ExperimentValidationIssue] = []
    if checkpoint.schema_version != CHECKPOINT_SCHEMA_VERSION:
        issues.append(_issue("CHECKPOINT_SCHEMA_MISMATCH", "checkpoint.schema_version", checkpoint.schema_version))
    if checkpoint.experiment_hash != spec.semantic_hash:
        issues.append(_issue("CHECKPOINT_EXPERIMENT_HASH_MISMATCH", "checkpoint.experiment_hash", checkpoint.experiment_hash))
    if checkpoint.candidate_plan_hash != spec.candidate_plan.semantic_hash:
        issues.append(_issue("CHECKPOINT_PLAN_HASH_MISMATCH", "checkpoint.candidate_plan_hash", checkpoint.candidate_plan_hash))
    if checkpoint.seed_ledger_hash != semantic_hash(spec.seed_ledger):
        issues.append(_issue("CHECKPOINT_SEED_HASH_MISMATCH", "checkpoint.seed_ledger_hash", checkpoint.seed_ledger_hash))
    if checkpoint.evaluator_version_hashes != (semantic_hash(spec.evaluator),):
        issues.append(_issue("CHECKPOINT_EVALUATOR_HASH_MISMATCH", "checkpoint.evaluator_version_hashes", checkpoint.evaluator_version_hashes))
    for relative, expected in checkpoint.artifact_hashes.items():
        path = root / relative
        if not path.is_file() or file_hash(path) != expected:
            issues.append(_issue("CHECKPOINT_ARTIFACT_INTEGRITY_FAILURE", relative, expected))
    return ExperimentValidationResult(tuple(issues))


def run_experiment(spec: ExperimentSpec, assets: RuntimeAssets, output_root: Path,
                   *, execution_order: Sequence[int] | None = None, stop_after: int | None = None,
                   existing_results: Mapping[str, TrialResult] | None = None,
                   existing_checkpoint: ExperimentCheckpoint | None = None) -> tuple[ExperimentManifest, ExperimentCheckpoint, Mapping[str, TrialResult]]:
    validation = validate_experiment(spec)
    # Metric locks are executable protocol outcomes, but all other validation errors block the run.
    nonlock_errors = tuple(item for item in validation.errors if item.code not in {"RUN017_OBJECTIVE_NOT_SYNTHETIC"})
    if nonlock_errors:
        raise ExperimentProtocolError("INVALID_EXPERIMENT: " + ",".join(item.code for item in nonlock_errors))
    trials, duplicates = build_trial_specs(spec)
    root = output_root / spec.semantic_hash
    results: dict[str, TrialResult] = dict(existing_results or {})
    artifacts: dict[str, str] = {}
    if existing_checkpoint is not None:
        resume_validation = validate_checkpoint(existing_checkpoint, spec, root)
        if not resume_validation.valid:
            raise ExperimentProtocolError("INVALID_RESUME: " + ",".join(item.code for item in resume_validation.errors))
        artifacts.update(existing_checkpoint.artifact_hashes)
    order = list(range(len(trials))) if execution_order is None else list(execution_order)
    if sorted(order) != list(range(len(trials))):
        raise ExperimentProtocolError("EXECUTION_ORDER_MUST_BE_A_PERMUTATION")
    executed = 0
    for index in order:
        trial = trials[index]
        if trial.trial_hash in results:
            continue
        result = execute_trial(spec, trial, assets)
        results[trial.trial_hash] = result
        artifacts.update(_write_trial_artifacts(root, trial, result))
        executed += 1
        checkpoint = _checkpoint(spec, trials, results, artifacts)
        _atomic_json(root / "checkpoint.json", checkpoint)
        if stop_after is not None and executed >= stop_after:
            break
    checkpoint = _checkpoint(spec, trials, results, artifacts)
    manifest = ExperimentManifest(EXPERIMENT_RUN_SCHEMA_VERSION, spec.semantic_hash, spec.candidate_plan.semantic_hash,
                                  {key: value.result_hash for key, value in sorted(results.items())}, duplicates,
                                  PIPELINE_VERSION,
                                  {"optimizer_interface_authorized": spec.optimizer_adapter is not None and spec.optimizer_adapter.optimizer_interface_authorized,
                                   "optimization_run_authorized": False, "physical_evaluation_authorized": False,
                                   "hardware_executable_claim_valid": False}, spec.output_contract.warning_labels)
    _atomic_json(root / "experiment.json", {"spec": spec, "manifest": manifest})
    _atomic_json(root / "checkpoint.json", checkpoint)
    return manifest, checkpoint, results


def compare_replay(source: ExperimentManifest, replay: ExperimentManifest,
                   execution_order: Sequence[str]) -> ExperimentReplay:
    return ExperimentReplay(source.experiment_hash, source.semantic_hash, replay.semantic_hash,
                            source.trial_result_hashes == replay.trial_result_hashes,
                            source.semantic_hash == replay.semantic_hash, tuple(execution_order))


def metrics_only_replay(spec: ExperimentSpec, result: TrialResult) -> MetricsOnlyReplay:
    """Recalculate registered metric records from a recorded evaluator output only."""
    if result.evaluator_output is None:
        raise ExperimentProtocolError("METRICS_ONLY_REPLAY_REQUIRES_RECORDED_EVALUATOR_OUTPUT")
    replayed = tuple(MetricResult(metric.metric_id, MetricResultStatus.VALUE, metric.units,
                                  result.evaluator_output[metric.metric_id], None, None, None,
                                  tuple(result.evaluator_output.get("labels", (RUN017_LABEL,))))
                     for metric in spec.metric_specs)
    return MetricsOnlyReplay(result.trial_hash, semantic_hash(result.evaluator_output),
                             semantic_hash(result.metrics), semantic_hash(replayed), replayed == result.metrics)


def manifest_integrity_audit(checkpoint: ExperimentCheckpoint, spec: ExperimentSpec,
                             experiment_root: Path) -> ManifestIntegrityAudit:
    validation = validate_checkpoint(checkpoint, spec, experiment_root)
    return ManifestIntegrityAudit(spec.semantic_hash, len(checkpoint.artifact_hashes),
                                  validation.valid, validation.issues)


def experiment_operation_metrics(spec: ExperimentSpec, manifest: ExperimentManifest,
                                 results: Mapping[str, TrialResult], *, resumed_trial_count: int = 0,
                                 artifact_reuse_count: int = 0, checkpoint_count: int = 1,
                                 replay_equal: bool | None = None) -> ExperimentOperationMetrics:
    trials, duplicates = build_trial_specs(spec)
    return ExperimentOperationMetrics(
        len(trials), len({trial.candidate.semantic_hash for trial in trials}), len(duplicates),
        sum(item.status in {TrialStatus.SUCCEEDED, TrialStatus.SUCCEEDED_WITH_DIAGNOSTICS} for item in results.values()),
        sum(item.status is TrialStatus.METRIC_LOCKED for item in results.values()),
        sum(item.status.value.startswith("FAILED_") for item in results.values()),
        resumed_trial_count, artifact_reuse_count, checkpoint_count, replay_equal,
    )


ALLOWED_TRANSITIONS: Mapping[TrialStatus, tuple[TrialStatus, ...]] = {
    TrialStatus.PLANNED: (TrialStatus.VALIDATED, TrialStatus.FAILED_VALIDATION, TrialStatus.CANCELLED, TrialStatus.SKIPPED_DUPLICATE),
    TrialStatus.VALIDATED: (TrialStatus.RUNNING, TrialStatus.METRIC_LOCKED, TrialStatus.FAILED_AUTHORIZATION, TrialStatus.CANCELLED),
    TrialStatus.RUNNING: (TrialStatus.SUCCEEDED, TrialStatus.SUCCEEDED_WITH_DIAGNOSTICS, TrialStatus.FAILED_EVALUATION, TrialStatus.FAILED_ARTIFACT_INTEGRITY, TrialStatus.CANCELLED),
}


def validate_status_transitions(statuses: Sequence[TrialStatus]) -> bool:
    return all(after in ALLOWED_TRANSITIONS.get(before, ()) for before, after in zip(statuses, statuses[1:]))
