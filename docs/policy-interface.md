# Policy interface for Track P laser schedules

This document describes the pure laser-control schedule layer added for Track P.
It is control plumbing only. It does not run trajectories, compute capture
velocities, model Gaussian beams, optimize parameters, open exact force maps, or
claim Rodriguez/MgF replication.

## Scope

The policy layer answers one question:

> At time `t`, what detuning and saturation/intensity state should each laser
> frequency component have?

The component order is always explicit:

`(1, 2, 3, 4)`

No component may be silently missing. Component `(4)` being off must be an
explicit state, not a default inferred by absence.

Each component state separates frequency from optical activity:

- `detuning_gamma`: where that component is tuned or parked;
- `saturation`: optical intensity scale;
- `enabled`: whether the schedule enables that component;
- `active`: true only when the component is enabled and has positive
  saturation;
- `off_reason`: why an inactive component is off.

A component can therefore have a detuning value while still being optically off.
For the Rodriguez baseline linear policy, component `(4)` is parked at
`+2 Gamma` with zero saturation and `active = false` until a separate `[3+1]`
handoff policy activates it.

## Units

The policy interface currently uses:

- time: `s`
- detuning: `Gamma`
- saturation: `saturation_parameter`

The validation layer rejects unknown units, non-finite detunings, non-finite
saturations, and negative saturation values.

## Implemented policies

### `StaticPolicy`

`StaticPolicy` represents the existing Rodriguez-style static `[3]` and `[3+1]`
configuration files:

- `configs/rodriguez_static_3.yaml`
- `configs/rodriguez_static_3_plus_1.yaml`

It returns the same per-component detuning and saturation at every sampled time.

### `LinearChirpPolicy`

`LinearChirpPolicy` represents the Rodriguez baseline linear schedule as a
policy object, not as a dynamics run:

- components `(1, 2, 3)` start at `-8 Gamma`;
- components `(1, 2, 3)` reach `-1 Gamma` at `tau = 1 ms`;
- after `tau`, components `(1, 2, 3)` remain at `-1 Gamma`;
- component `(4)` is explicitly off during the baseline chirp unless a later
  reviewed handoff policy turns it on. Its `+2 Gamma` detuning is a parked
  frequency, not active optical power.

The config is:

- `configs/rodriguez_baseline_linear_chirp.yaml`

The policy tests assert the exact endpoint values at `t=0` and `t=tau`, plus
the hold value for `t>tau`.

### `ChirpToTrapHandoffPolicy`

The Rodriguez-style instantaneous handoff is represented separately by
`ChirpToTrapHandoffPolicy` and
`configs/rodriguez_chirp_to_3_plus_1_handoff.yaml`. It exposes `tau` through
`event_times_s`, uses the chirped `[3]` state for `t < tau`, and selects the
static `[3+1]` state for `t >= tau`. See
`docs/chirp-to-trap-handoff.md` for its event-boundary contract.

## Apparatus-realism bounds

Policy configs may carry optional bounds as data:

- max chirp rate;
- allowed detuning range;
- allowed saturation range;
- optional frequency-update granularity;
- optional intensity-update granularity.

These are not optimization constraints yet. They are metadata for future review.

## Inspection script

Run:

```powershell
python scripts/inspect_policies.py
```

The script loads all policy configs, samples each policy at representative
times, prints a component table, and writes quarantined Track P outputs under:

`outputs/provisional/`

The report and metadata are labeled:

- `PROVISIONAL`
- `NOT_RODRIGUEZ_REPLICATION`
- `POLICY_INTERFACE_ONLY`

## Future connection points

Later force-map and trajectory code can consume policy samples instead of
hard-coding detunings and intensities. That future work must still obey the
track split:

- Track E remains blocked until the exact excited-state Hamiltonian and Zeeman
  model are resolved.
- Track P may use policy samples only for provisional plumbing artifacts with
  visible non-replication labels.

This policy interface alone does not constitute a Rodriguez replication and
does not support physical conclusions.
