# Model-independent feedback-policy interface

`MODEL_INDEPENDENT_NOT_RODRIGUEZ_REPLICATION_RUN_016_FEEDBACK_POLICY_INTERFACE_ONLY`

Run 016 adds versioned observation, controller, action, timing, synthetic-plant,
session, and replay infrastructure. It is feedback plumbing only. It evaluates
no molecular force, integrates no molecular trajectory, computes no capture
metric, trains no controller, and defines no reward or optimization objective.

The schema identifiers are:

- `mgf-mot-observation-spec-v1`;
- `mgf-mot-feedback-action-spec-v1`;
- `mgf-mot-feedback-controller-v1`;
- `mgf-mot-feedback-session-v1`;
- `mgf-mot-feedback-replay-v1`.

## Hidden-state boundary

`HiddenPlantState` is consumed only by a declared `ObservationModel`. A
controller's only input is an `ObservationPacket` plus explicit
`ControllerMemory`. Runtime type checks reject plant or hidden-state objects,
and the API has no arbitrary keyword passthrough, plant callbacks, force-field
handles, or molecular-model handles. Session validation also checks that every
requested hidden field belongs to the synthetic plant schema.

The access classes are `FULL_STATE_ORACLE`, `PARTIAL_STATE_SYNTHETIC`,
`SENSOR_MODEL_SYNTHETIC`, and the reserved
`SOURCE_SUPPORTED_SENSOR_MODEL`. Run 016 rejects claims that the reserved class
exists. Every oracle specification, result, replay, filename, and artifact
carries `FULL_STATE_ORACLE`, `SIMULATION_ONLY`, and
`NOT_APPARATUS_REALIZABLE`.

## Observation channels and transforms

No channel meaning is inferred from its name. Each channel declares units,
shape, dtype, meaning, source fields, dependencies, transform and version,
sampling cadence, latency, noise, missing-data behavior, quantization,
clipping, access class, and provenance.

The closed transform registry contains identity/select, affine, linear
projection, norm, windowed mean/sum, finite difference, quantize, clip, delayed
sample, and constant transforms. Graph dependencies must be acyclic. Callable
payloads, expressions, dynamic imports, learned encoders, and undeclared
transforms fail closed. A missing upstream channel propagates `MISSING`; it is
never converted to an empty or zero-valued observation.

Packets distinguish hidden-state timestamp, sensor sample time, observation
availability time, and controller receive time. Fixed schedules, explicit
latency, communication latency, deterministic jitter fixtures, and declared
dropout patterns retain these separate timestamps.

## Noise, status, and stale data

The closed noise registry includes `NONE`, `ADDITIVE_GAUSSIAN`,
`UNIFORM_QUANTIZATION`, `DETERMINISTIC_BIAS`, and `DROPOUT_PATTERN`. Gaussian
streams use a channel/stream-specific seed derived by SHA-256 and a local NumPy
PCG64 generator. Global RNG state is never used. Noise realizations and missing
events enter replay records.

Observation status is explicitly `VALID`, `MISSING`, `STALE`, `INVALID`, or
`SATURATED`. Every controller declares a behavior for every status:
`REJECT_STEP`, `HOLD_LAST_ACTION`, `USE_LAST_VALID_OBSERVATION`, or
`USE_DECLARED_FALLBACK_ACTION`. There is no default fallback, and missing data
is represented by `None`, never zero.

## Controllers, memory, and actions

The closed plumbing-only controller registry contains no-op, baseline replay,
scripted sequence, bounded affine, and optional hold-last families. It contains
no PID claims, estimator, Kalman filter, neural policy, reinforcement-learning
policy, reward, or training behavior. Affine clipping is permitted only when
the serialized controller explicitly selects `EXPLICIT_CLIP`; rejection is the
other explicit behavior.

Memory schemas declare field name, dtype, shape, units, initial value, and
update semantics. Memory is passed into and returned from every step. There is
no mutable controller singleton. Stateless controllers use a declared empty
schema and an explicit empty memory object.

Actions operate on ABI-v2 channel IDs and distinguish action timestamp from
requested effective time. They record values, units, source, step ID,
complete/partial/hold semantics, validity, fallback origin, and provenance.
Partial updates retain unspecified channels. Validation rejects unknown or
duplicate channels, unit mismatches, nonfinite values, direct affine-derived
updates, divergent shared requests, incomplete complete-actions, and actions
created before packet receipt. Invalid actions never reach compilation and are
never silently clipped or repaired.

## Timing, apparatus compilation, and event ordering

`FeedbackTimingSpec` separately declares plant, observation, controller,
communication, computation, and apparatus timing. It supports observation-
driven, fixed-control-clock, and scripted-controller-time scheduling. Maximum
observation age and initial/pre-roll behavior are explicit; one ambiguous `dt`
does not represent all timing layers.

Accepted action history is converted to ABI-v2 semantic action events and sent
through the Run 014 compiler using its channel ranges, clock, quantization,
latency, slew, second-difference, dwell, shared, and derived-channel checks.
The controller never mutates realized state. Infeasible actions follow the
session's explicit terminate, reject-and-hold, safe-action, or diagnostic rule.
No projection, smoothing, stretching, or automatic repair occurs. Partial
profiles remain diagnostic and cannot support a hardware claim.

The deterministic event priority is versioned as effective apparatus commands,
plant update, sensor sample, observation arrival, controller evaluation,
command issue record, and checkpoint. Simultaneous-event order is stable and
enters session provenance.

## Synthetic plants

Only `STATIC_PLANT`, `DISCRETE_INTEGRATOR_PLANT`, and `FIRST_ORDER_LAG_PLANT`
fixtures are present. They are abstract discrete control fixtures labeled
`SYNTHETIC_TEST_FIXTURE`, `MODEL_INDEPENDENT`, and `NOT_MGF_PHYSICS`. They do not
use MgF, MOT, Newtonian, force, or capture semantics.

## Replay and hashes

Each step records the synthetic state hash, observation and noise realization,
packet status and timing, memory before/after, requested action, compilation,
issued/effective commands, realized control state, fallback decision,
validation issues, and hashes. Hidden values are included only in explicitly
oracle-labeled synthetic records; other records retain only their hash.

Run 016 supports full replay from specs and seeds, controller-only replay from
recorded packets, and apparatus-only replay from recorded actions. Changed
session, observation, controller, timing, plant, apparatus, or policy hashes
fail visibly. Deterministic SHA-256 identities cover every specification and
observation/action/command/replay stream; mapping order and timestamps outside
the declarative content do not affect identity.

The baseline replay controller compiles the original Run 015 composed
chirp-to-`[3+1]` policy directly through Run 014. Requested actions are audited
at controller times, while commands, exact handoff event, effective timing, and
realized component states remain identical. The audit outcome is
`OPEN_LOOP_FEEDBACK_REPLAY_EXACT`.

## Metrics, examples, and authorization

Metrics separately report packet validity/missing/stale/saturation and latency;
controller steps/actions/fallbacks/invalid actions/memory size; and compilation
status, commands, action-to-effect latency, and per-channel quantization. They
are neutral diagnostics, not a reward or combined score.

`configs/run_016/` contains baseline replay, oracle affine, partial delayed,
infeasible-action, and deterministic-noise examples. They are synthetic or
control-baseline fixtures, never optimized or physically superior policies.
Run the audit with:

```powershell
python scripts/validate_feedback_policy_interface_run_016.py
```

This layer authorizes later experiment-protocol interfaces only. It does not
authorize physical feedback evaluation, state estimation, controller training,
reinforcement learning, optimization, real apparatus execution, or capture
calculations.
