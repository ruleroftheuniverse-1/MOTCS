# Control-policy ABI v2

`MODEL_INDEPENDENT_NOT_RODRIGUEZ_REPLICATION_RUN_013_CONTROL_POLICY_ABI_ONLY`

## Purpose and scope

`mgf-mot-control-policy-v2` is the stable, model-independent contract between
declarative laser schedules and future apparatus compilers, controllers, and
experiment manifests. It contains no molecular Hamiltonian, force backend,
plant model, trajectory logic, capture rule, or optimizer interface. Run 013
executes only the existing stateless open-loop policy families.

## Component-state contract

Every segment and sampled state contains exactly four records ordered
`(1,2,3,4)`. Each record declares the component ID, detuning in `Gamma`,
saturation, enabled state, derived active state, inactive reason, and separate
detuning/saturation channel IDs. `active` must equal `enabled and saturation >
0`. An inactive component still has a parked detuning; the baseline component
4 remains parked at `+2 Gamma` with zero saturation.

Legacy static `[3]` explicitly says `enabled: false` but its frozen v1 YAML did
not include a textual reason. The v2 adapter records
`legacy_v1_explicit_disabled_no_text_reason`; only the v1 compatibility
projection maps that sentinel back to null. Thus ABI v2 has no unexplained off
state while the historical `PolicySample` remains exactly unchanged.

## Specification and execution

`ControlPolicySpec` is immutable, JSON-serializable, and declarative. It records
schema/family/name, units, component order, parameter and channel definitions,
segments, events, domain behavior, statefulness, and deterministic provenance.
`ControlPolicy` executes a validated spec. Callables, closures, source code, and
general expressions are never serialized.

Statefulness is either `STATELESS_OPEN_LOOP` or the reserved
`STATEFUL_CONTROLLER`. Run 013 rejects stateful instantiation and execution;
there are no observations, controller memory, rewards, or feedback logic.

## Parameters and bounds

Every execution parameter has a `PolicyParameterSpec` with name, description,
shape, units, data type, explicit value, optional true default, optional bounds,
fixed/adjustable status, and bound basis. Bound bases are
`SOURCE_SUPPORTED`, `APPARATUS_ASSUMPTION`, `ENGINEERING_STRESS_TEST`, and
`UNKNOWN`. Missing bounds remain null/unknown. Existing apparatus-bound YAML is
preserved as assumption metadata and is not an optimization constraint.

## Channels

Channel ownership resolves every `(segment, component, field)` exactly once.
Supported relationships are:

- `INDEPENDENT`: one independently controlled target;
- `SHARED`: one value for multiple targets;
- `FIXED`: a constant field;
- `AFFINE_DERIVED`: `target = scale * source + offset`.

Signal behavior is separately limited to fixed, linear-with-final-hold, and
affine. The Rodriguez detuning for components `(1,2,3)` is one SHARED linear
channel. Component 4 parked detuning and all current saturation settings are
explicit fixed channels. Derived dependencies must be acyclic; overlapping
ownership and unknown channel types fail closed.

## Time domains and events

Each spec declares minimum/maximum time, unbounded continuation, before/after
behavior, and endpoint semantics. Current policies use `t=0` as the minimum,
`HOLD_INITIAL` for negative requested times, and an unbounded final hold. The
requested time remains in the returned state while evaluation is clamped.

The linear chirp has a continuous `chirp_endpoint` event at `tau`; it evaluates
linearly for `0 <= t < tau`, exactly at its final detuning at `tau`, and holds
afterwards. The handoff has one explicit discontinuity using
`t_lt_event_left_t_ge_event_right`: chirped `[3]` for `t<tau`, static `[3+1]`
for `t>=tau`. Event IDs/times are finite, sorted, unique, and domain-checked.

## Provenance, serialization, and identity

Provenance includes schema/family, source paths and SHA-256 hashes,
implementation version, wrapped policy IDs, units, generation method,
non-replication labels, and assumptions. Volatile timestamps are absent.

Canonical JSON sorts mapping keys, preserves list/component/event ordering,
retains explicit nulls, rejects nonfinite numbers, and uses deterministic JSON
float rendering. Separate SHA-256 identities cover parameters, channels, the
policy spec (excluding provenance), and the full package (including
provenance). Equivalent mapping-key order does not affect identity; parameter,
channel, event, unit, or provenance changes affect the appropriate hash.

## Legacy conversion and validation

The frozen v1 YAML files continue to load through `StaticPolicy`,
`LinearChirpPolicy`, and `ChirpToTrapHandoffPolicy`. The adapter creates a
complete v2 spec without rewriting or silently reinterpreting source values.
Serialization round trips have no repository-default fallback.

Structured validation issues contain code, severity, field path, message,
relevant value, and suggested correction. Validation covers schema/units,
component completeness, finiteness, saturation and active state, off reasons,
parameter bounds, ownership, unresolved fields, affine cycles, domains/events,
stateful execution, and executable content. Invalid specs cannot execute.

Run the audit with:

```powershell
python scripts/validate_control_policy_abi_v2.py
```

## Future extension boundaries

The ABI reserves later apparatus compilation, additional open-loop families,
and stateful controllers. Run 013 implements none of them. Accepted molecular
physics remains frozen. Apparatus claims, force calculations, trajectories,
feedback, optimization, capture, and exact replication remain unauthorized.
