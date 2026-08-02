# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_ACCEPTED_FORCE_FIELD_NAMED_TRAJECTORIES_ONLY_RUN_011

This is the first named-trajectory run using the accepted provisional physics-bearing rate-equation force fields. It is not a capture study and not a Rodriguez replication.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_ACCEPTED_FORCE_FIELD_NAMED_TRAJECTORIES_ONLY_RUN_011 Historical separation

Run 008 validated plumbing only. Its toy-force outcomes omitted the physical acceleration conversion, are physically uninterpretable, and are superseded for force-dependent discussion. Numerical comparison to Run 008 is not scientifically meaningful. All Run 008 artifacts were preserved unchanged.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_ACCEPTED_FORCE_FIELD_NAMED_TRAJECTORIES_ONLY_RUN_011 Backend and numerics

The adapter used the accepted `g'=0.001`, source-aligned 0.5 MHz interval-midpoint model, provenance-matched Run 010 caches, and one `hbar*k*Gamma/m` conversion. Baseline dt=`0.0001` s, refined dt=`5e-05` s, selected dt=`0.0001` s. Convergence passed: `True`. Pathwise gate: `PATHWISE_INTERPOLATION_PASS`.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_ACCEPTED_FORCE_FIELD_NAMED_TRAJECTORIES_ONLY_RUN_011 Named trajectory diagnostics

| name | Gamma/k | termination | outcome | qualitative motion | final x m | final v m/s | closest m | crossings |
|---|---:|---|---|---|---:|---:|---:|---:|
| v_2_gamma_over_k | 2.0 | COMPLETED_TIME_INTERVAL | BOUNDED_FINAL_STATE | SLOWED_BEFORE_CENTER | -0.00265215 | 0.246277 | 0.00265215 | 0 |
| v_4_gamma_over_k | 4.0 | COMPLETED_TIME_INTERVAL | BOUNDED_FINAL_STATE | SLOWED_BEFORE_CENTER | -0.00142925 | 0.123054 | 0.00142925 | 0 |
| v_6_gamma_over_k | 6.0 | FORCE_FIELD_DOMAIN_EXIT | UNRESOLVED | FORCE_FIELD_DOMAIN_EXIT | 0.06 | 45.247 | 0 | 1 |
| v_7p5_gamma_over_k | 7.5 | FORCE_FIELD_DOMAIN_EXIT | UNRESOLVED | FORCE_FIELD_DOMAIN_EXIT | 0.06 | 57.3735 | 0 | 1 |
| v_9_gamma_over_k | 9.0 | FORCE_FIELD_DOMAIN_EXIT | UNRESOLVED | FORCE_FIELD_DOMAIN_EXIT | 0.06 | 62.2706 | 0 | 1 |

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_ACCEPTED_FORCE_FIELD_NAMED_TRAJECTORIES_ONLY_RUN_011 Acceptance checks

- `accepted_cache_and_backend_provenance`: `True`
- `si_conversion_exactly_once`: `True`
- `event_aware_handoff_exact`: `True`
- `timestep_convergence`: `True`
- `pathwise_interpolation`: `True`
- `no_silent_domain_extrapolation`: `True`
- `finite_saved_arrays`: `True`
- `explicit_non_capture_outcomes`: `True`
- `historical_run008_unchanged`: `True`

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_ACCEPTED_FORCE_FIELD_NAMED_TRAJECTORIES_ONLY_RUN_011 Final gate: PROVISIONAL_NAMED_TRAJECTORY_GO

**PROVISIONAL_NAMED_TRAJECTORY_GO**

`provisional_static_authorized = true`; `provisional_force_field_authorized = true`; `provisional_named_trajectory_authorized = true`; `capture_authorized = false`; `capture_velocity_authorized = false`; `optimizer_authorized = false`; `exact_replication_valid = false`; `exact_track_blocked = true`.
A GO authorizes further provisional named-trajectory analysis and design of a later paper-grounded capture protocol. It does not authorize capture thresholds, source distributions, optimization, or exact-replication claims.

# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_ACCEPTED_FORCE_FIELD_NAMED_TRAJECTORIES_ONLY_RUN_011 FINAL_PROVISIONAL_NAMED_TRAJECTORY_GO
