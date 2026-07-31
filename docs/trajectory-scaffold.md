# Track P provisional trajectory scaffold

`mgf_mot.trajectory` connects a time-dependent laser policy to the existing
pointwise provisional force harness through a small fixed-step RK4 integrator.
It is an engineering interface validation, not a Rodriguez trajectory
reproduction.

Every policy-conditioned result is stamped:

- `PROVISIONAL`
- `NOT_RODRIGUEZ_REPLICATION`
- `TRAJECTORY_SCAFFOLD_ONLY`

The policy path requires both:

1. an `ApproximateMgFHamiltonian` whose provenance is Track P and has
   `replication_valid = false`; and
2. `ProvisionalForceMapConfig(explicit_provisional_opt_in=True)`.

Exact validation objects and default force configurations fail clearly.

## Interface

`TrajectoryInitialState` stores one three-dimensional position and velocity.
`TrajectoryConfig` defines the start time, end time, fixed step, units, and an
explicit normalized force-to-acceleration scale. `TrajectoryResult` returns:

- sample times;
- position and velocity arrays;
- provisional force samples;
- per-component detunings;
- per-component saturations;
- per-component active/off flags;
- Track P backend provenance, warnings, omitted terms, and collapsed terms.

At every RK4 evaluation, the policy is sampled at the current stage time. Only
components with nonzero active optical power contribute to the provisional
diagnostic spring scale. A parked detuning does not activate a component. Thus
component `(4)` remains parked at `+2 Gamma`, with zero saturation and
`active = false`, throughout the baseline chirp unless a separate policy
explicitly enables it.

Policies may expose known discontinuities through `event_times_s`. The RK4
grid lands exactly on each event inside the integration interval and restarts
the requested timestep sequence there. A step ending at an event uses the
left-hand policy limit for its final stage; the next step starts at the event
with the deterministic `t >= event` state. Encountered events and this stage
convention are recorded in trajectory metadata.

The existing force harness returns a normalized diagnostic force. Run 004 uses
the explicitly configured `normalized_force_to_acceleration` value to exercise
state integration. This value is not an MgF mass conversion, and the resulting
motion has no calibrated physical meaning.

## Analytic test hook

`integrate_analytic_test_trajectory` is a separate integrator-only entry point.
It accepts an explicitly named acceleration function and does not accept or
carry an MgF backend. It validates the RK4 core against zero acceleration,
constant acceleration, and linear damping without conflating those checks with
the provisional molecular backend.

## Scope boundary

This scaffold does not define:

- capture velocity;
- capture or loss criteria;
- loading;
- molecular-beam source distributions;
- Gaussian beam profiles;
- optimizers;
- exact force maps.

The Run 004 smoke path integrates one initial state for a short interval using
plane-wave-only Track P plumbing. No physical conclusion should be drawn from
its position, velocity, force magnitude, or topology.

Track E remains blocked by the unresolved independent Doppelbauer `d` operator
and excited-state Zeeman mappings. Once a source-faithful exact Hamiltonian and
force backend are validated, the same state/config/result interface can be
reused with a separately reviewed exact force adapter. Labels alone cannot
promote a Track P result into Track E.
