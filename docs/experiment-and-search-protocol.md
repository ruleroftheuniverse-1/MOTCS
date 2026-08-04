# Run 017 experiment and search protocol

`MODEL_INDEPENDENT · NOT_RODRIGUEZ_REPLICATION · RUN_017 · EXPERIMENT_SEARCH_PROTOCOL_ONLY`

Run 017 is a deterministic evaluation ledger around the accepted control interfaces. It is not an optimizer and it does not evaluate MgF physics. The accepted Track P molecular model and Runs 010–016 artifacts remain frozen.

## Identity and schemas

Experiments, contexts, metric registries, search spaces, trials, runs, and checkpoints carry explicit `mgf-mot-…-v1` schema identifiers. Canonical JSON uses sorted mapping keys and rejects callables and non-finite numbers. Semantic experiment identity includes the candidate plan, context, evaluator/version, metrics, objectives, seed ledger, software versions, provenance, and output contract. Volatile timestamps do not enter semantic hashes.

Candidate identity is content-based, not name-based. It preserves ordered parameter layouts, values, units and source hashes. Human-readable candidate IDs are excluded from the semantic candidate hash, so renaming an otherwise identical candidate neither hides nor creates a distinct candidate. Duplicate hashes are recorded and may be deterministically deduplicated.

## Evaluation contexts and physics references

The closed context classes are:

- `MODEL_INDEPENDENT_STRUCTURAL` for policy, schedule, report, and replay structure;
- `SYNTHETIC_CONTROL_FIXTURE`, requiring `MODEL_INDEPENDENT`, `SYNTHETIC_TEST_FIXTURE`, and `NOT_MGF_PHYSICS`;
- `FROZEN_PROVISIONAL_PHYSICS_REFERENCE`, an opaque non-executing reference only;
- `EXACT_MODEL_PENDING`, which remains execution-blocked.

An opaque physics reference may record package and force-field hashes, validation gates, status, and evaluator versions. Run 017 never loads it. A missing reference never selects the provisional model by default.

## Closed candidates and evaluators

Candidate kinds cover Run 015 policies and vectors, Run 014 compiled schedules, Run 016 controller/session records, synthetic vectors, and recorded references. Candidate payloads are JSON data only. Runtime objects live in an explicit hash-addressed asset registry; arbitrary callables and dynamic imports are forbidden.

Run 017 authorizes only:

- `POLICY_STRUCTURAL_EVALUATOR`;
- `SCHEDULE_COMPILATION_EVALUATOR`;
- `FEEDBACK_REPLAY_EVALUATOR`;
- `SYNTHETIC_VECTOR_EVALUATOR`.

MgF force, MgF trajectory, MgF capture, and hardware evaluators are reserved but unauthorized. Evaluator resolution is closed by ID and version, and all context and metric authorization happens before an evaluator runs.

## Metrics and objectives

The versioned metric registry explicitly records units, shape, dtype, compatible contexts/evaluators, aggregation, authorization, meaning, objective eligibility, and provenance. Authorized metrics describe policy structure, apparatus compilation, synthetic feedback replay, or the explicitly synthetic vector fixture.

Physical placeholders—including `capture_velocity`, captured or bounded fractions, population, cooling/loading rates, temperature, robust capture, and experimental success—are locked. A lock produces `METRIC_LOCKED` with a reason and future required gate. Its value is absent: never zero, NaN, cached history, provisional physics, or a synthetic stand-in.

Objectives require explicit `MINIMIZE`, `MAXIMIZE`, or `TARGET` direction and an explicit role. Run 017 executes objective plumbing only for metrics authorized as synthetic. It performs no default ranking, scalarization, weighted sum, or physically “best” selection.

## Search spaces, transforms, and plans

Search dimensions preserve parameter-layout entries, dtype, shape, units, fixed/adjustable state, explicit/unknown bounds, provenance, transform, and serialization order. Unknown bounds stay unknown and block bounded generation.

The closed invertible transforms are identity, linear unit interval, positive log, signed log, and categorical index. Parameters serialize explicitly; there is no hidden normalization or expression evaluator.

Plans are nonadaptive: explicit candidate list, Cartesian synthetic fixture, recorded proposal sequence, or one baseline. They cannot inspect results to create later candidates. The optimizer-adapter record is an interface-only no-op or recorded-proposal boundary. `optimizer_adapter_interface_authorized` may be true; optimizer implementation and optimization runs remain false.

## Trials, seeds, checkpoint, and resume

A trial hash derives from the experiment hash, candidate hash, evaluator hash, metric hashes, context hash, namespaced seed identity, replicate index, and trial schema—not order or time. Separate deterministic seed streams exist for candidate fixtures, synthetic evaluation, observation noise, synthetic plants, and controllers. No global RNG is used.

The lifecycle distinguishes planned, validated, running, succeeded, locked, failed, duplicate, and cancelled states. Locks and failures cannot become successful results. Failures contain a stage, issue codes, safe exception class, reproduction keys, retry eligibility, and failure scope.

Each successful pipeline authorizes context/evaluator/metrics before evaluation, validates output, writes content-hashed trial artifacts atomically, and then updates the checkpoint and manifest. Canonical trial artifacts are conflict-detecting. Checkpoints bind experiment, plan, evaluator, metric-derived trials, seed ledger, completed/locked/failed/pending identities, and artifact hashes. Resume rejects any changed specification, evaluator, seed ledger, or corrupt artifact.

## Replay and integrity

Full replay rematerializes candidates, derives the same trials/seeds, reruns evaluators, and compares result and manifest hashes. Metrics-only replay recalculates registered metric records from recorded evaluator output. Manifest-only audit verifies checkpoint bindings and every recorded artifact hash. Run 017 demonstrates forward, reverse, interrupted/resumed, corruption, and conflict cases using disposable Run 017 artifacts.

Experiment-operation counts—planned, unique, duplicate, successful, locked, failed, resumed, reused, checkpoints, and replay equality—are ledger diagnostics, not scientific performance metrics.

## Included examples

- Policy structural comparison: baseline-equivalent Run 015 families and synthetic nonbaseline structure, with no physical ranking.
- Apparatus compilation: exact identity, approximate quantized, infeasible rate-limited, and diagnostic incomplete-profile records; none is a real hardware claim.
- Feedback replay: validated Run 016 synthetic sessions and exact replay records.
- Synthetic search fixture: a deterministic two-dimensional Cartesian grid with `SYNTHETIC_OBJECTIVE` and `NOT_PHYSICAL_PERFORMANCE` on every output.
- Locked physical metric: requests `capture_velocity`, never invokes the evaluator, and returns no numeric value.

## Authorization limit

No molecular force is evaluated, no accepted force cache is queried, no molecular trajectory is integrated, no capture is calculated, no physical objective is evaluated, no optimizer or reinforcement-learning library runs, no controller is trained, and no real apparatus or sensor model is validated. Successful synthetic trials are not evidence of physical performance.

Once the exact molecular package is author-validated, a later separately authorized evaluator can consume the same identity, trial, checkpoint, and replay protocol. Run 017 itself does not authorize that integration.
