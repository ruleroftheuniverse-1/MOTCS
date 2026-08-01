# Track P named finite-beam trajectory protocol

Run 008 connects the provisional handoff policy, finite Gaussian geometry,
pointwise force adapter, event-aware RK4 integrator, and dwell-window outcome
classifier for five fixed diagnostic initial velocities. It is an end-to-end
engineering test, not a Rodriguez reproduction or velocity-boundary search.

Every artifact is stamped:

- `PROVISIONAL`
- `NOT_RODRIGUEZ_REPLICATION`
- `NAMED_TRAJECTORY_PROTOCOL_ONLY`

## Baseline protocol

The coordinate and sign convention is:

- motion is along lab `x`;
- the initial position is exactly `(-0.050, 0, 0) m`;
- positive `v_x` points toward the MOT center at the origin;
- initial `v_y` and `v_z` are zero;
- positions use metres, velocities use metres/second, and time uses seconds.

The simulation lasts `20 ms` with a fixed requested timestep of `0.1 ms`.
Event-aware splitting still lands exactly at the `1 ms` policy handoff.

The source apparatus data carried by the protocol includes:

- quadrupole gradient `2 mT/cm = 0.2 T/m`;
- Gaussian radii `wxy = 17.5 mm` and `wz = 10 mm`;
- components `(1,2,3)` chirped from `-8 Gamma` to `-1 Gamma`;
- pre-handoff saturations `(1.45, 1.45, 2.89, 0.00)`;
- post-handoff saturations `(1.45, 1.45, 2.17, 0.72)`;
- post-handoff detunings `(-1,-1,-1,+2) Gamma`;
- component `(4)` off for `t < 1 ms` and active for `t >= 1 ms`;
- total power `1 W` as metadata with no inferred allocation.

The reported peak saturation vectors remain operative through the policy.
The normalized Track P force-to-acceleration adapter is not a calibrated MgF
conversion.

## Named velocity set

The exact dimensionless source values and derived SI values are:

| name | Gamma/k | velocity |
|---|---:|---:|
| `v_2_gamma_over_k` | 2 | 15.06 m/s |
| `v_4_gamma_over_k` | 4 | 30.12 m/s |
| `v_6_gamma_over_k` | 6 | 45.18 m/s |
| `v_7p5_gamma_over_k` | 7.5 | 56.475 m/s |
| `v_9_gamma_over_k` | 9 | 67.77 m/s |

The conversion uses `Gamma/k = 7.53 m/s`. The list is deterministic and
ordered. No intermediate velocities are inserted and no transition boundary
is interpolated.

## Recorded diagnostics

Each named case records:

- final position and velocity;
- closest approach and its time;
- minimum and maximum `v_x`;
- whether `x=0` was crossed;
- first and last times inside each configured position bound;
- whether it approached, crossed, slowed near, or remained near the origin;
- final dwell-window statistics;
- explicit outcome label and numerical reason;
- integration status;
- exact handoff event metadata;
- component `(4)` activity on either side of the handoff;
- backend omissions, collapsed terms, and replication status.

A center crossing alone is never promoted to `BOUNDED_FINAL_STATE`. Remaining
inside the final position and speed bounds for the configured dwell window is a
separate diagnostic.

## Finite Gaussian force path

Elliptical-Gaussian mode is explicitly selected with a source-configured
`GaussianBeamSet`. The force and trajectory position units are both metres.
The `2 mT/cm` gradient is carried explicitly and corresponds to a unit
normalized-gradient scale for this provisional adapter.

These choices validate apparatus wiring only. No conclusion may be drawn from
the provisional trajectory shapes or outcomes.

## Named cases versus a boundary search

Run 008 evaluates exactly five named inputs. It does not calculate a maximum
successful velocity, search for a threshold, refine the velocity spacing,
construct a source distribution, add stochastic recoil or diffusion, optimize
parameters, or open an exact-force path.

Track E remains blocked by the unresolved independent Doppelbauer `d` operator
and excited-state Zeeman mappings. Once an exact backend is validated, it can
reuse this config-backed protocol, named inputs, diagnostics, and output
interfaces without changing the apparatus definition.
