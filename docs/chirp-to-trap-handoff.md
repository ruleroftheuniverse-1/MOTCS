# Track P chirp-to-[3+1] handoff

`ChirpToTrapHandoffPolicy` represents the provisional Rodriguez-style
instantaneous switch from a chirped three-frequency slowing state to a static
four-frequency confinement state. It is policy and integrator plumbing only,
not an MgF/Rodriguez trajectory reproduction.

Every Run 005 artifact is stamped:

- `PROVISIONAL`
- `NOT_RODRIGUEZ_REPLICATION`
- `HANDOFF_VALIDATION_ONLY`

## Piecewise policy

The boundary convention is deterministic:

- for `t < tau`, components `(1, 2, 3)` chirp from `-8 Gamma` toward
  `-1 Gamma`; their saturations are `(1.45, 1.45, 2.89)`;
- component `(4)` is parked at `+2 Gamma` before the handoff, but is disabled,
  inactive, and has zero saturation;
- for `t >= tau`, detunings are `(-1, -1, -1, +2) Gamma` and saturations are
  `(1.45, 1.45, 2.17, 0.72)`;
- component `(4)` becomes enabled and active exactly at `tau`;
- the policy reports `chirp_3` before the event and `trap_3_plus_1` at and
  after the event.

The handoff is not smoothed or interpolated. The policy exposes
`event_times_s = (tau,)` so consumers do not have to infer the discontinuity.

Run 005 samples `0`, `tau/2`, `tau-epsilon`, `tau`, `tau+epsilon`, and `2*tau`.
It uses `epsilon = 1e-9 s` only to inspect the two sides of the policy
boundary. Epsilon is not an apparatus timescale or integration setting.

## Event-aware RK4 splitting

A normal fixed RK4 step could straddle `tau` and mix pre- and post-handoff
policy states. The trajectory scaffold therefore shortens a proposed crossing
step so it ends exactly at `tau`, then restarts the requested step sequence
from `tau`.

The step ending at the discontinuity evaluates its final RK4 stage at the
left-hand time limit. The next step evaluates its first stage at exactly
`tau`, where the `t >= tau` convention selects `[3+1]`. The result metadata
records both known and encountered event times and documents this one-sided
stage convention.

## Scope boundary

Run 005 uses one short plane-wave-only provisional trajectory to validate event
handling. It defines no capture or loss criterion, capture velocity, loading,
molecular-beam source distribution, Gaussian profile, optimizer, or exact
force-map path. No physical conclusion should be drawn from its trajectory.

Track E remains blocked by the unresolved independent Doppelbauer `d` operator
and excited-state Zeeman mappings. A future exact backend may reuse this event
interface only after its Hamiltonian and force calculations are independently
validated.
