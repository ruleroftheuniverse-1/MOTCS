# PROVISIONAL NOT_RODRIGUEZ_REPLICATION ACCEPTED_FORCE_FIELD_NAMED_TRAJECTORIES_ONLY RUN_011

Run 011 reconnects the exact five-case named protocol to the Run 010 accepted interpolated rate-equation force fields. It is a provisional trajectory diagnostic, not a capture-velocity calculation, loading simulation, source-distribution study, or Rodriguez replication.

## Accepted adapter

`InterpolatedRateEquationTrajectoryForce` can be constructed only with:

- Track P and explicit provisional opt-in;
- explicit acknowledgment that `0.5 MHz` is the reproducible midpoint of the source-supported `0-1 MHz` interval, not a measured value;
- corrected ground Zeeman convention;
- Rodriguez effective `g'=+0.001`;
- source-aligned effective excited splitting at the named midpoint;
- exact provenance matches for both Run 010 caches.

It has no toy-force or arbitrary spectroscopy input. Track E requests fail, and cache hash mismatches fail before integration. The independent Doppelbauer `d` operator and exact excited spectroscopy remain unresolved, `replication_valid=false`, and Track E remains blocked.

## Integration contract

For `t < 1 ms`, the adapter samples the handoff policy, extracts the common chirp detuning, and queries the trilinear Gaussian `[3]` field. For `t >= 1 ms`, it queries the separate bilinear Gaussian `[3+1]` field. RK4 steps land exactly at the event; the pre-event endpoint uses the left-hand limit and the next step begins with the post-event field. The optical systems are never blended or smoothed.

The field returns canonical `F_x/(hbar k Gamma)`. `normalized_force_to_newtons` and `normalized_force_to_acceleration_m_s2` apply the sourced conversion exactly once. Cumulative acceleration and impulse use the same RK4 weights as the state update, so velocity change, momentum change, integrated acceleration, and integrated SI force form one auditable chain.

No query is clamped or extrapolated. If an RK4 substage would leave the Run 010 domain, termination is localized to the exact violated boundary and recorded as `FORCE_FIELD_DOMAIN_EXIT`. The record includes time, position, velocity, segment, detuning, field selection, violated coordinate, attempted value, and allowed interval. This numerical termination remains separate from the official outcome label and is not interpreted as capture or escape.

## Named protocol and outcomes

The unchanged protocol uses `x0=-50 mm`, velocities `(2,4,6,7.5,9) Gamma/k`, a 20 ms interval, 1 ms handoff, the source Gaussian waists, `0.2 T/m` gradient, and the established pre/post saturation vectors. No additional velocities were evaluated.

The official engineering labels remain `BOUNDED_FINAL_STATE`, `ESCAPED`, `UNRESOLVED`, and `INVALID`. `BOUNDED_FINAL_STATE` is never renamed to “captured.” Classification still requires the multi-sample final dwell window; a center crossing alone is insufficient. Integration status and qualitative motion are separate fields.

Run 011 produced:

| initial velocity | termination | engineering outcome | qualitative description |
|---:|---|---|---|
| `2 Gamma/k` | `COMPLETED_TIME_INTERVAL` | `BOUNDED_FINAL_STATE` | `SLOWED_BEFORE_CENTER` |
| `4 Gamma/k` | `COMPLETED_TIME_INTERVAL` | `BOUNDED_FINAL_STATE` | `SLOWED_BEFORE_CENTER` |
| `6 Gamma/k` | `FORCE_FIELD_DOMAIN_EXIT` at `x=+60 mm` | `UNRESOLVED` | `FORCE_FIELD_DOMAIN_EXIT` |
| `7.5 Gamma/k` | `FORCE_FIELD_DOMAIN_EXIT` at `x=+60 mm` | `UNRESOLVED` | `FORCE_FIELD_DOMAIN_EXIT` |
| `9 Gamma/k` | `FORCE_FIELD_DOMAIN_EXIT` at `x=+60 mm` | `UNRESOLVED` | `FORCE_FIELD_DOMAIN_EXIT` |

These are results of the provisional accepted model only. They are not statements of agreement or disagreement with the paper and do not define a capture threshold.

## Numerical validation

Thresholds were fixed in `configs/provisional_named_trajectory_run_011.yaml` before integration. Baseline `100 us` and refined `50 us` trajectories were compared for `2`, `7.5`, and `9 Gamma/k`. Exact boundary localization makes domain-exit comparisons meaningful. All final/termination states, closest approaches, crossing times, impulses, outcome labels, and termination statuses pass; the 100 us timestep is retained.

Pathwise validation selects deterministic saved states without reintegrating or altering trajectories. Fresh accepted rate-equation solves are performed at initial, illuminated, large-force, handoff-adjacent, closest-approach/crossing, late, and final states as available. All five paths return `PATHWISE_INTERPOLATION_PASS`. Direct-solve results are validation samples only.

Every result stores time, position, velocity, normalized and SI force, SI acceleration, RK4 cumulative impulse, segment, detuning, component state, field selection, Gaussian envelopes, interpolation-cell metadata, event status, and domain status.

## Historical boundary and gate

Run 008 artifacts remain byte-for-byte unchanged. Run 008 validated toy-force plumbing, omitted the physical acceleration conversion, and its force-dependent outcomes are physically uninterpretable. Numerical comparison between Run 008 and Run 011 is not scientifically meaningful.

Final gate: **`PROVISIONAL_NAMED_TRAJECTORY_GO`**. This permits further provisional named-trajectory analysis and design of a later paper-grounded capture protocol. Capture velocity, threshold interpolation, molecular source distributions, stochastic diffusion, optimization, and exact-replication claims remain unauthorized.
