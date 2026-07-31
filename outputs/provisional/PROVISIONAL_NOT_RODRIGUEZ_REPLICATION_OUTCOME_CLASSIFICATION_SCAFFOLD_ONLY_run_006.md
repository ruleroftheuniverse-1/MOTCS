# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_OUTCOME_CLASSIFICATION_SCAFFOLD_ONLY Run 006

The outcome criteria are provisional and engineering-defined.
`BOUNDED_FINAL_STATE` is not equivalent to physical MOT capture.
Exact MgF force readiness remains blocked.
Infinite plane waves were used.
No Gaussian beam envelope or molecular source distribution was included.
No capture velocity was calculated and no threshold search was performed.
No physical conclusions should be drawn.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_OUTCOME_CLASSIFICATION_SCAFFOLD_ONLY Criteria

- position measure: `radius`
- final position bound: `0.1`
- final speed bound: `0.1`
- final dwell window: `0.0002` s
- minimum dwell samples: `2`
- required dwell fraction: `1.0`
- hard escape-position bound: `0.5`
- hard speed bound: `0.5`

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_OUTCOME_CLASSIFICATION_SCAFFOLD_ONLY Analytic classifier examples

- `damped_bounded`: `BOUNDED_FINAL_STATE` — 101/101 dwell samples satisfied radius<=0.05 and speed<=0.05
- `fast_escaped`: `ESCAPED` — maximum radius 5 exceeded hard escape bound 2
- `short_unresolved`: `UNRESOLVED` — trajectory duration 0.5 s is shorter than required dwell window 1 s
- `nonfinite_invalid`: `INVALID` — trajectory contains NaN or nonfinite values
- `center_crossing_not_bounded`: `UNRESOLVED` — only 0/101 dwell samples satisfied the engineering bounds; required fraction is 1

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_OUTCOME_CLASSIFICATION_SCAFFOLD_ONLY Ordered provisional ensemble

### PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_OUTCOME_CLASSIFICATION_SCAFFOLD_ONLY Member 0

- initial position: `(0.0, 0.0, 0.05)`
- initial velocity: `(0.0, 0.0, -0.05)`
- integration status: `completed`
- outcome: `BOUNDED_FINAL_STATE`
- numerical reason: 2/2 dwell samples satisfied radius<=0.1 and speed<=0.1
- event-aware handoff time encountered: `(0.001,)`

### PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_OUTCOME_CLASSIFICATION_SCAFFOLD_ONLY Member 1

- initial position: `(0.0, 0.0, 0.05)`
- initial velocity: `(0.0, 0.0, 0.0)`
- integration status: `completed`
- outcome: `BOUNDED_FINAL_STATE`
- numerical reason: 2/2 dwell samples satisfied radius<=0.1 and speed<=0.1
- event-aware handoff time encountered: `(0.001,)`

### PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_OUTCOME_CLASSIFICATION_SCAFFOLD_ONLY Member 2

- initial position: `(0.0, 0.0, 0.05)`
- initial velocity: `(0.0, 0.0, 0.05)`
- integration status: `completed`
- outcome: `BOUNDED_FINAL_STATE`
- numerical reason: 2/2 dwell samples satisfied radius<=0.1 and speed<=0.1
- event-aware handoff time encountered: `(0.001,)`

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_OUTCOME_CLASSIFICATION_SCAFFOLD_ONLY Quarantined artifacts

- arrays: `PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_OUTCOME_CLASSIFICATION_SCAFFOLD_ONLY_run_006_arrays.npz`
- metadata: `PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_OUTCOME_CLASSIFICATION_SCAFFOLD_ONLY_run_006_metadata.json`
- plot: `PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_OUTCOME_CLASSIFICATION_SCAFFOLD_ONLY_run_006_z_trajectories.png`