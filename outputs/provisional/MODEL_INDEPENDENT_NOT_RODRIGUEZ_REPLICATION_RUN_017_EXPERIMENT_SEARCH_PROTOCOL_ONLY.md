# MODEL_INDEPENDENT_NOT_RODRIGUEZ_REPLICATION_RUN_017_EXPERIMENT_SEARCH_PROTOCOL_ONLY

**No molecular force was evaluated. No molecular trajectory was integrated. No capture metric was calculated. No physical objective was evaluated. No optimizer was run. No controller was trained. No real apparatus or sensor model was validated. Successful synthetic trials are not evidence of physical performance.**

## Experiment ledger

| Experiment | Hash | Trials | Successful | Locked |
|---|---:|---:|---:|---:|
| `apparatus_compilation` | `9af5047ce4fe` | 4 | 4 | 0 |
| `feedback_replay` | `9e566898347d` | 5 | 5 | 0 |
| `locked_physical_metric` | `d81f13b1d0bc` | 1 | 0 | 1 |
| `policy_structural_comparison` | `b1e32812d868` | 4 | 4 | 0 |
| `synthetic_search_plumbing` | `a0b8e79265f5` | 9 | 9 | 0 |

## Determinism, resume, replay, and integrity

- `forward_reverse_trial_hashes_equal`: `True`
- `forward_reverse_manifest_hash_equal`: `True`
- `interrupted_resumed_trial_hashes_equal`: `True`
- `interrupted_resumed_manifest_hash_equal`: `True`
- `metrics_only_replay_equal`: `True`
- `manifest_integrity_valid`: `True`
- `artifact_corruption_detected`: `True`
- `artifact_conflict_detected`: `True`
- `partial_completed`: `3`
- `resumed_completed`: `9`
- `checkpoint_semantic_hash`: `4703d62c1c738f1752cc73623b04f85a8175839c7dd4bbf1f33dbb2ba9958b46`

## Locked physical metric

`capture_velocity` ended as `METRIC_LOCKED`. The evaluator output is absent and the metric value is absent. No zero, NaN, cached value, provisional estimate, or synthetic substitute was emitted.

## Authorization boundary

The optimizer adapter is an interface-only no-op boundary. Candidate plans are deterministic and nonadaptive. Physical evaluators, physical objectives, capture, hardware execution, optimization, training, and reinforcement learning remain unauthorized.

CONTROL_EXPERIMENT_INFRA_READY
