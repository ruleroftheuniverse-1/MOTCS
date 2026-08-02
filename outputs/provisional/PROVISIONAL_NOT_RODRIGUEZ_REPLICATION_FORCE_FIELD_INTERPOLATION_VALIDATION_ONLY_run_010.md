# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_FORCE_FIELD_INTERPOLATION_VALIDATION_ONLY Run 010

This run validates reusable equilibrium-force interpolation only. No trajectory, capture search, source distribution, stochastic diffusion, optimization, or exact-replication calculation was performed.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_FORCE_FIELD_INTERPOLATION_VALIDATION_ONLY Accepted backend lock

The path requires the corrected ground tensor, `g'=+0.001`, `SOURCE_ALIGNED_EFFECTIVE_FPRIME_SPLITTING`, and the explicit `MID_RANGE_0P5_MHZ` selection. The `0.5 MHz` value is an interval midpoint of the source-supported `0-1 MHz` range, not a measured value. The independent `d` physics remains unresolved and Track E remains blocked.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_FORCE_FIELD_INTERPOLATION_VALIDATION_ONLY Fields and domain

Pre-handoff shape: `(25, 33, 15)` (12375 equilibrium solves), trilinear in `(x,v,Delta)`. Post-handoff shape: `(25, 33)` (825 solves), bilinear in `(x,v)`. Canonical stored values are `F_x/(hbar k Gamma)`, not acceleration.
The initial `(25,33,8)` baseline failed the predeclared important-extremum threshold at `-4.5 Gamma`; the detuning axis was refined from `1 Gamma` to `0.5 Gamma` spacing without changing thresholds.
Domain: x=`[-0.06, 0.06] m`, v=`[-100.0, 100.0] m/s`, detuning=`[-8.0, -1.0] Gamma`. Build elapsed: `0.000 s`; cache reused: `True`.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_FORCE_FIELD_INTERPOLATION_VALIDATION_ONLY Interpolation validation

Declared thresholds: RMS/range <= `0.03`, important max/range <= `0.08`, local slope relative error <= `0.15`.
Holdouts: `51`, all off grid nodes: `True`. RMS/range: `0.0047804`; maximum/range: `0.0204331`; important maximum/range: `0.0204331`.
Refined-slice topology preserved: `True`. Component (4) strengthens confinement: `True`. Outside queries rejected: `True`.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_FORCE_FIELD_INTERPOLATION_VALIDATION_ONLY Acceptance checks

- `accepted_backend_models`: `True`
- `canonical_normalized_force`: `True`
- `pre_post_separate`: `True`
- `build_population_health`: `True`
- `holdout_population_health`: `True`
- `refined_slice_population_health`: `True`
- `holdouts_off_grid_nodes`: `True`
- `interpolation_errors`: `True`
- `topology_preserved`: `True`
- `component4_effect`: `True`
- `post_stronger_than_static_3`: `True`
- `component4_population_health`: `True`
- `gaussian_attenuation`: `True`
- `gaussian_attenuation_population_health`: `True`
- `no_silent_extrapolation`: `True`
- `boundary_queries`: `True`

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_FORCE_FIELD_INTERPOLATION_VALIDATION_ONLY Final gate: PROVISIONAL_FORCE_FIELD_INTERPOLATION_GO

**PROVISIONAL_FORCE_FIELD_INTERPOLATION_GO**

`provisional_static_authorized = true`; `provisional_force_field_authorized = true`; `provisional_trajectory_authorized = true`; `capture_authorized = false`; `exact_replication_valid = false`; `exact_track_blocked = true`.
A GO authorizes only reconnection of these accepted tables to the named non-capture trajectory scaffold. It does not authorize capture thresholds, source distributions, diffusion, optimization, or exact-replication claims.

# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_FORCE_FIELD_INTERPOLATION_VALIDATION_ONLY FINAL_PROVISIONAL_FORCE_FIELD_INTERPOLATION_GO
