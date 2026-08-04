"""Validate Run 017 model-independent experiment infrastructure only."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mgf_mot.experiment_examples import ARTIFACT_LABELS, load_example_config  # noqa: E402
from mgf_mot.experiment_protocol import (  # noqa: E402
    RUN017_LABEL, MetricResultStatus, TrialStatus, compare_replay,
    experiment_operation_metrics, file_hash, manifest_integrity_audit,
    metrics_only_replay, run_experiment, validate_experiment,
)


CONFIG_DIR = ROOT / "configs/run_017"
OUTPUT_ROOT = ROOT / "outputs/provisional/experiments/run_017"
DETAIL = ROOT / "outputs/provisional/experiment_search_protocol/run_017"
REPORT = ROOT / "outputs/provisional" / f"{RUN017_LABEL}.md"
METADATA = DETAIL / f"{RUN017_LABEL}_metadata.json"


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: _plain(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(_plain(value), indent=2, sort_keys=True, allow_nan=False) + "\n"
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _protected_paths() -> tuple[Path, ...]:
    patterns = (
        "outputs/provisional/*RUN_010*", "outputs/provisional/*RUN_011*", "outputs/provisional/*RUN_012*",
        "outputs/provisional/*RUN_013*", "outputs/provisional/*RUN_014*", "outputs/provisional/*RUN_015*",
        "outputs/provisional/*RUN_016*", "outputs/provisional/force_fields/**/*",
        "outputs/provisional/molecular_model_packages/**/*", "outputs/provisional/control_policy_abi/**/*",
        "outputs/provisional/apparatus_schedule_compiler/**/*", "outputs/provisional/open_loop_policy_families/**/*",
        "outputs/provisional/feedback_policy_interface/**/*", "outputs/provisional/molecular_model_audit/**/*",
        "outputs/provisional/paper_digitization/**/*", "outputs/provisional/named_trajectories/**/*",
        "configs/run_015/*", "configs/run_016/*",
    )
    paths: set[Path] = set()
    for pattern in patterns:
        paths.update(item for item in ROOT.glob(pattern) if item.is_file())
    for name in (
        "control_policy_abi.py", "control_policy_serialization.py", "control_policy_validation.py",
        "apparatus_constraints.py", "control_schedule_compiler.py", "open_loop_policy_families.py",
        "feedback_policy.py", "feedback_examples.py",
    ):
        paths.add(ROOT / "src/mgf_mot" / name)
    return tuple(sorted(paths))


def _manifest(paths: tuple[Path, ...]) -> dict[str, str]:
    return {str(path.relative_to(ROOT)): file_hash(path) for path in paths}


def _prerequisites() -> dict[str, str]:
    folders = {
        "run013": ROOT / "outputs/provisional/control_policy_abi/run_013",
        "run014": ROOT / "outputs/provisional/apparatus_schedule_compiler/run_014",
        "run015": ROOT / "outputs/provisional/open_loop_policy_families/run_015",
        "run016": ROOT / "outputs/provisional/feedback_policy_interface/run_016",
    }
    expected = {
        "run013": "CONTROL_POLICY_ABI_GO", "run014": "APPARATUS_SCHEDULE_COMPILER_GO",
        "run015": "OPEN_LOOP_POLICY_FAMILIES_GO", "run016": "FEEDBACK_POLICY_INTERFACE_GO",
    }
    actual = {}
    for name, folder in folders.items():
        path = next(folder.glob("*metadata.json"))
        actual[name] = json.loads(path.read_text(encoding="utf-8"))["gate"]
    if actual != expected:
        raise RuntimeError(f"Run 017 prerequisites changed: {actual}")
    return actual


def _print_table(title: str, headers: tuple[str, ...], rows: list[tuple[Any, ...]]) -> None:
    print(f"\n{title}")
    print(" | ".join(headers))
    print("-|-".join("-" * len(item) for item in headers))
    for row in rows:
        print(" | ".join(str(item) for item in row))


def run() -> dict[str, Any]:
    protected = _protected_paths(); before = _manifest(protected); prerequisites = _prerequisites()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True); DETAIL.mkdir(parents=True, exist_ok=True)
    experiment_rows = []; candidate_rows = []; trial_rows = []; metric_rows = []; objective_rows = []
    specs = {}; assets_by_id = {}; manifests = {}; checkpoints = {}; results_by_id = {}
    for path in sorted(CONFIG_DIR.glob("*.yaml")):
        spec, assets = load_example_config(path, ROOT); validation = validate_experiment(spec)
        if not validation.valid:
            raise RuntimeError(f"invalid example {spec.experiment_id}: {[item.code for item in validation.errors]}")
        manifest, checkpoint, results = run_experiment(spec, assets, OUTPUT_ROOT)
        specs[spec.experiment_id] = spec; assets_by_id[spec.experiment_id] = assets
        manifests[spec.experiment_id] = manifest; checkpoints[spec.experiment_id] = checkpoint; results_by_id[spec.experiment_id] = results
        operations = experiment_operation_metrics(spec, manifest, results)
        experiment_rows.append((spec.experiment_id, spec.semantic_hash[:12], len(results), manifest.semantic_hash[:12]))
        for result in results.values():
            candidate_rows.append((spec.experiment_id, result.candidate_hash[:12], result.status.value))
            trial_rows.append((result.trial_hash[:12], spec.evaluator.evaluator_id.value, result.status.value))
            for metric in result.metrics:
                metric_rows.append((metric.metric_id, metric.status.value, "NO_VALUE" if metric.value is None else str(metric.value)[:28]))
        for objective in spec.objectives:
            objective_rows.append((spec.experiment_id, objective.metric_id, objective.direction.value, objective.role.value))
        experiment_rows[-1] += (operations.successful_trial_count, operations.locked_trial_count)

    synthetic = specs["synthetic_search_plumbing"]; synthetic_assets = assets_by_id[synthetic.experiment_id]
    trials = tuple(results_by_id[synthetic.experiment_id])
    with tempfile.TemporaryDirectory(prefix="mgf_run017_") as temp_name:
        temp = Path(temp_name)
        forward, forward_checkpoint, forward_results = run_experiment(synthetic, synthetic_assets, temp / "forward")
        reverse, _, reverse_results = run_experiment(synthetic, synthetic_assets, temp / "reverse",
                                                     execution_order=tuple(reversed(range(len(trials)))))
        interrupted, partial_checkpoint, partial_results = run_experiment(synthetic, synthetic_assets, temp / "resume", stop_after=3)
        resumed, resumed_checkpoint, resumed_results = run_experiment(synthetic, synthetic_assets, temp / "resume",
            existing_results=partial_results, existing_checkpoint=partial_checkpoint)
        replay = compare_replay(forward, reverse, tuple(reversed(trials)))
        resume_replay = compare_replay(forward, resumed, tuple(trials))
        metric_replays = [metrics_only_replay(synthetic, item) for item in resumed_results.values()]
        integrity = manifest_integrity_audit(resumed_checkpoint, synthetic, temp / "resume" / synthetic.semantic_hash)
        copied = temp / "corrupt"; shutil.copytree(temp / "resume" / synthetic.semantic_hash, copied)
        corrupt_target = next((copied / "trials").glob("*/metrics.json")); corrupt_target.write_text("{}\n", encoding="utf-8")
        corruption_audit = manifest_integrity_audit(resumed_checkpoint, synthetic, copied)
        conflict_detected = False
        conflict_target = next((temp / "forward" / synthetic.semantic_hash / "trials").glob("*/metrics.json"))
        original_conflict = conflict_target.read_bytes(); conflict_target.write_text("{}\n", encoding="utf-8")
        try:
            run_experiment(synthetic, synthetic_assets, temp / "forward")
        except ValueError as exc:
            conflict_detected = "ARTIFACT_CONFLICT" in str(exc)
        finally:
            conflict_target.write_bytes(original_conflict)
        replay_audit = {
            "forward_reverse_trial_hashes_equal": replay.trial_hashes_equal,
            "forward_reverse_manifest_hash_equal": replay.manifest_semantic_hash_equal,
            "interrupted_resumed_trial_hashes_equal": resume_replay.trial_hashes_equal,
            "interrupted_resumed_manifest_hash_equal": resume_replay.manifest_semantic_hash_equal,
            "metrics_only_replay_equal": all(item.equal for item in metric_replays),
            "manifest_integrity_valid": integrity.valid,
            "artifact_corruption_detected": not corruption_audit.valid,
            "artifact_conflict_detected": conflict_detected,
            "partial_completed": len(partial_results), "resumed_completed": len(resumed_results),
            "checkpoint_semantic_hash": resumed_checkpoint.semantic_hash,
        }

    locked = tuple(results_by_id["locked_physical_metric"].values())
    locked_audit = {
        "status": locked[0].status.value,
        "no_evaluator_output": locked[0].evaluator_output is None,
        "all_metrics_locked": all(item.status is MetricResultStatus.METRIC_LOCKED for item in locked[0].metrics),
        "all_values_absent": all(item.value is None for item in locked[0].metrics),
        "lock_reasons": [item.lock_reason for item in locked[0].metrics],
    }
    after = _manifest(protected)
    ready = (
        before == after and all(value.endswith("_GO") for value in prerequisites.values())
        and all(row[2] in {TrialStatus.SUCCEEDED.value, TrialStatus.METRIC_LOCKED.value} for row in candidate_rows)
        and all(replay_audit[key] for key in (
            "forward_reverse_trial_hashes_equal", "forward_reverse_manifest_hash_equal",
            "interrupted_resumed_trial_hashes_equal", "interrupted_resumed_manifest_hash_equal",
            "metrics_only_replay_equal", "manifest_integrity_valid", "artifact_corruption_detected", "artifact_conflict_detected"))
        and locked_audit["status"] == TrialStatus.METRIC_LOCKED.value and locked_audit["no_evaluator_output"]
        and locked_audit["all_metrics_locked"] and locked_audit["all_values_absent"]
    )
    gate = "CONTROL_EXPERIMENT_INFRA_READY" if ready else "CONTROL_EXPERIMENT_INFRA_REFINEMENT_REQUIRED"
    authorization = {
        "control_policy_abi_authorized": True, "apparatus_schedule_compiler_authorized": True,
        "open_loop_policy_families_authorized": True, "feedback_policy_interface_authorized": True,
        "experiment_protocol_authorized": ready, "synthetic_trial_execution_authorized": ready,
        "optimizer_adapter_interface_authorized": ready, "optimizer_implementation_authorized": False,
        "optimization_run_authorized": False, "physical_evaluator_authorized": False,
        "physical_objective_authorized": False, "capture_metric_authorized": False,
        "real_sensor_model_validated": False, "real_apparatus_profile_validated": False,
        "hardware_executable_claim_valid": False, "reinforcement_learning_authorized": False,
        "exact_replication_valid": False,
    }
    metadata = {
        "artifact_labels": ARTIFACT_LABELS, "label": RUN017_LABEL, "gate": gate,
        "schema_versions": {
            "experiment": "mgf-mot-experiment-spec-v1", "context": "mgf-mot-evaluation-context-v1",
            "metric_registry": "mgf-mot-metric-registry-v1", "search_space": "mgf-mot-search-space-v1",
            "trial_manifest": "mgf-mot-trial-manifest-v1", "experiment_run": "mgf-mot-experiment-run-v1",
            "checkpoint": "mgf-mot-experiment-checkpoint-v1",
        },
        "prerequisites": prerequisites, "experiments": experiment_rows,
        "candidate_rows": candidate_rows, "trial_rows": trial_rows, "metric_rows": metric_rows,
        "objective_rows": objective_rows, "replay_audit": replay_audit, "locked_metric_audit": locked_audit,
        "authorization": authorization, "protected_hashes_before": before, "protected_hashes_after": after,
        "protected_artifacts_unchanged": before == after,
        "molecular_force_evaluations": 0, "force_field_queries": 0, "molecular_trajectory_integrations": 0,
        "capture_metrics_calculated": 0, "physical_objectives_evaluated": 0, "optimization_runs": 0,
        "controller_training_runs": 0, "reinforcement_learning_runs": 0,
    }
    _write_json(METADATA, metadata)
    report_lines = [
        f"# {RUN017_LABEL}", "",
        "**No molecular force was evaluated. No molecular trajectory was integrated. No capture metric was calculated. No physical objective was evaluated. No optimizer was run. No controller was trained. No real apparatus or sensor model was validated. Successful synthetic trials are not evidence of physical performance.**",
        "", "## Experiment ledger", "",
        "| Experiment | Hash | Trials | Successful | Locked |", "|---|---:|---:|---:|---:|",
        *[f"| `{row[0]}` | `{row[1]}` | {row[2]} | {row[4]} | {row[5]} |" for row in experiment_rows],
        "", "## Determinism, resume, replay, and integrity", "",
        *[f"- `{key}`: `{value}`" for key, value in replay_audit.items()],
        "", "## Locked physical metric", "",
        f"`capture_velocity` ended as `{locked_audit['status']}`. The evaluator output is absent and the metric value is absent. No zero, NaN, cached value, provisional estimate, or synthetic substitute was emitted.",
        "", "## Authorization boundary", "",
        "The optimizer adapter is an interface-only no-op boundary. Candidate plans are deterministic and nonadaptive. Physical evaluators, physical objectives, capture, hardware execution, optimization, training, and reinforcement learning remain unauthorized.",
        "", gate,
    ]
    REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    _print_table("Experiments", ("experiment", "hash", "trials", "manifest", "success", "locked"), experiment_rows)
    _print_table("Trials", ("trial", "evaluator", "status"), trial_rows)
    _print_table("Metrics", ("metric", "status", "value/lock"), metric_rows)
    _print_table("Objectives", ("experiment", "metric", "direction", "role"), objective_rows)
    print("\nCheckpoint/replay", json.dumps(replay_audit, sort_keys=True))
    print(gate)
    if before != after:
        raise RuntimeError("Run 017 modified a protected Run 010-016 artifact")
    return metadata


if __name__ == "__main__":
    run()

