# Apparatus constraints and deterministic schedule compilation

`MODEL_INDEPENDENT_NOT_RODRIGUEZ_REPLICATION_RUN_014_APPARATUS_SCHEDULE_COMPILER_ONLY`

Run 014 introduces `mgf-mot-apparatus-constraints-v1` and
`mgf-mot-compiled-control-schedule-v1`. The layer converts an ideal ABI-v2
policy into channel commands and a realized schedule without importing any
molecular, force, trajectory, capture, feedback, or optimization code.

## Knowledge and provenance

Every capability is `KNOWN`, `UNKNOWN`, `UNBOUNDED`, or `NOT_APPLICABLE`.
Unknown never means unlimited, unbounded must be explicit, and not-applicable
requires a reason. Known numerical values require units. Provenance is one of
`SOURCE_SUPPORTED`, `APPARATUS_ASSUMPTION`, `ENGINEERING_STRESS_TEST`,
`SYNTHETIC_TEST_FIXTURE`, or `UNKNOWN` and records source, hash/citation where
available, interpretation, and direct/derived status.

Profiles declare channel-level detuning/saturation ranges, update periods,
resolution, first derivative, second finite difference, dwell, allowed sets,
and activation restrictions. Saturation is not called optical power. Only an
explicit abstract aggregate-saturation budget is supported without a physical
power calibration.

Hardware status is `SYNTHETIC_ONLY`, `SOURCE_INCOMPLETE`,
`SOURCE_SUPPORTED_NOT_HARDWARE_VALIDATED`, or `HARDWARE_VALIDATED`; Run 014
rejects the last label.

## Clock, latency, horizon, and initial state

Every request has finite explicit start/end times. It chooses
`EXPLICIT_INITIAL_STATE`, `POLICY_STATE_AT_START`, or `REQUIRE_PRE_ROLL`.
Latency never implies hidden preconfiguration: commands record requested
effective, issued, and actual effective times, and insufficient pre-roll fails.

Finite clocks declare origin, period, shared/per-channel semantics, minimum
separation, atomicity, and one deterministic rule: `REQUIRE_EXACT`, `FLOOR`,
`CEIL`, or decimal `NEAREST_TIES_TO_EVEN`. Every displacement is retained.

## Modes and compilation order

- `EXACT_ONLY` rejects sampling, quantization, or event displacement.
- `SAMPLE_AND_HOLD` samples the declared clock, quantizes deterministically,
  and reconstructs with zero-order hold.
- `DIAGNOSTIC_PARTIAL_PROFILE` exercises known constraints but is incomplete,
  non-hardware-executable, and unsuitable for apparatus claims.

The recorded pipeline order is validation; channel/horizon/event resolution;
effective grid construction; ideal evaluation; event alignment; quantization;
command generation; latency; reconstruction; deduplication; hard-constraint
checks; metrics; serialization/hashing. Violations are reported and never
silently clipped, stretched, smoothed, or fitted.

## Events and channel relationships

ABI events survive as requested/realized event records. Rules include exact,
floor, ceil, nearest, and reject-if-unaligned. The handoff retains chirped `[3]`
before the realized event and static `[3+1]` from the event onward. Atomic
updates share a group ID.

One ABI SHARED channel produces one command stream. AFFINE_DERIVED ownership
remains declarative and acyclic; derived values are checked against their own
capabilities. Fields are never compiled independently per shared member.

## Quantization, constraints, reconstruction, and metrics

Commands record ideal and quantized values, units, step, rule, and error.
Ranges, first derivative, second finite difference, dwell, and activation are
hard checks. Consecutive identical commands are deduplicated without changing
boundary behavior. Finite-clock realized schedules use exact zero-order-hold
semantics: initial state before the first command, new value at its effective
time, and final hold through the horizon.

The formal synthetic identity profile uses an explicitly idealized continuous
channel binding so the existing continuous linear chirp can be compared exactly.
This is the mathematical identity fixture, not a finite ZOH device and not
hardware evidence. All finite-clock profiles use true zero-order hold.

Per-channel metrics separate detuning from saturation and report value errors,
endpoint/event-adjacent errors, first/second differences, quantization errors,
and raw/deduplicated counts. Whole-schedule metadata reports event displacement,
commands/groups, horizon, completeness, feasibility, and hardware status.

## Deterministic identity and fixtures

SHA-256 identities cover apparatus profile, request, ABI-v2 source policy,
command stream, realized schedule, and complete package. Mapping order and
volatile timestamps do not affect identity; constraints, clock, latency,
events, horizon, initial state, or compiler version do.

Run 014 includes only clearly labeled fixtures: formal synthetic identity,
synthetic quantized, deliberately rate-limited, and source-incomplete. None is
the Rodriguez apparatus. Run:

```powershell
python scripts/compile_control_policies_run_014.py
```

The compiler gate permits future Run 015 open-loop-family infrastructure and
future population of source-supported apparatus profiles. It does not validate
real hardware or authorize physical simulation, feedback, optimization, or
capture calculations.
