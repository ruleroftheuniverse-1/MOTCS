# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_HANDOFF_VALIDATION_ONLY Run 005

This validates an instantaneous chirp-to-[3+1] policy handoff and event-aware trajectory plumbing only.

Exact MgF force readiness remains blocked.
The provisional backend is approximate and not replication-valid.
No capture velocity or capture/loss classification was computed.
No molecular-beam source distribution was used.
No Gaussian beams or optimizer were used.
No physical conclusions should be drawn from this trajectory.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_HANDOFF_VALIDATION_ONLY Boundary convention

- `t < tau`: chirped `[3]` state.
- `t >= tau`: final static `[3+1]` state.
- The handoff is instantaneous; no smoothing or interpolation is applied.
- `tau = 0.001` s.
- `epsilon = 1e-09` s, used only to inspect either side of the policy boundary.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_HANDOFF_VALIDATION_ONLY Policy-state snapshots

### PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_HANDOFF_VALIDATION_ONLY t_0

- time: `0.0` s
- current policy segment: `chirp_3`
- handoff occurred: `False`

| component | detuning [Gamma] | saturation | enabled | active | role | off reason |
|---:|---:|---:|:---:|:---:|---|---|
| 1 | -8.0 | 1.45 | True | True | lower_F1 | None |
| 2 | -8.0 | 1.45 | True | True | F0 | None |
| 3 | -8.0 | 2.89 | True | True | upper_F1_F2_mean | None |
| 4 | 2.0 | 0.0 | False | False | upper_F1_F2_mean_confinement | parked_off_until_3_plus_1_handoff |

### PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_HANDOFF_VALIDATION_ONLY t_tau_over_2

- time: `0.0005` s
- current policy segment: `chirp_3`
- handoff occurred: `False`

| component | detuning [Gamma] | saturation | enabled | active | role | off reason |
|---:|---:|---:|:---:|:---:|---|---|
| 1 | -4.5 | 1.45 | True | True | lower_F1 | None |
| 2 | -4.5 | 1.45 | True | True | F0 | None |
| 3 | -4.5 | 2.89 | True | True | upper_F1_F2_mean | None |
| 4 | 2.0 | 0.0 | False | False | upper_F1_F2_mean_confinement | parked_off_until_3_plus_1_handoff |

### PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_HANDOFF_VALIDATION_ONLY t_tau_minus_epsilon

- time: `0.0009999990000000001` s
- current policy segment: `chirp_3`
- handoff occurred: `False`

| component | detuning [Gamma] | saturation | enabled | active | role | off reason |
|---:|---:|---:|:---:|:---:|---|---|
| 1 | -1.0000069999999992 | 1.45 | True | True | lower_F1 | None |
| 2 | -1.0000069999999992 | 1.45 | True | True | F0 | None |
| 3 | -1.0000069999999992 | 2.89 | True | True | upper_F1_F2_mean | None |
| 4 | 2.0 | 0.0 | False | False | upper_F1_F2_mean_confinement | parked_off_until_3_plus_1_handoff |

### PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_HANDOFF_VALIDATION_ONLY t_tau

- time: `0.001` s
- current policy segment: `trap_3_plus_1`
- handoff occurred: `True`

| component | detuning [Gamma] | saturation | enabled | active | role | off reason |
|---:|---:|---:|:---:|:---:|---|---|
| 1 | -1.0 | 1.45 | True | True | lower_F1 | None |
| 2 | -1.0 | 1.45 | True | True | F0 | None |
| 3 | -1.0 | 2.17 | True | True | upper_F1_F2_mean | None |
| 4 | 2.0 | 0.72 | True | True | upper_F1_F2_mean_confinement | None |

### PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_HANDOFF_VALIDATION_ONLY t_tau_plus_epsilon

- time: `0.001000001` s
- current policy segment: `trap_3_plus_1`
- handoff occurred: `True`

| component | detuning [Gamma] | saturation | enabled | active | role | off reason |
|---:|---:|---:|:---:|:---:|---|---|
| 1 | -1.0 | 1.45 | True | True | lower_F1 | None |
| 2 | -1.0 | 1.45 | True | True | F0 | None |
| 3 | -1.0 | 2.17 | True | True | upper_F1_F2_mean | None |
| 4 | 2.0 | 0.72 | True | True | upper_F1_F2_mean_confinement | None |

### PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_HANDOFF_VALIDATION_ONLY t_2tau

- time: `0.002` s
- current policy segment: `trap_3_plus_1`
- handoff occurred: `True`

| component | detuning [Gamma] | saturation | enabled | active | role | off reason |
|---:|---:|---:|:---:|:---:|---|---|
| 1 | -1.0 | 1.45 | True | True | lower_F1 | None |
| 2 | -1.0 | 1.45 | True | True | F0 | None |
| 3 | -1.0 | 2.17 | True | True | upper_F1_F2_mean | None |
| 4 | 2.0 | 0.72 | True | True | upper_F1_F2_mean_confinement | None |

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_HANDOFF_VALIDATION_ONLY Event-aware trajectory checks

- requested timestep: `0.0005` s
- trajectory times: `[0.0007, 0.001, 0.0013]`
- time array contains tau exactly: `True`
- a step ends exactly at tau: `True`
- next step starts at tau with post-handoff state: `True`
- component 4 inactive before tau: `True`
- component 4 active at tau: `True`
- component 4 active after tau: `True`
- component 3 saturation before/at tau: `2.89` / `2.17`
- encountered event times: `[0.001]`
- arrays: `PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_HANDOFF_VALIDATION_ONLY_run_005_arrays.npz`
- metadata: `PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_HANDOFF_VALIDATION_ONLY_run_005_metadata.json`
- plot: `PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_HANDOFF_VALIDATION_ONLY_run_005_z_state.png`