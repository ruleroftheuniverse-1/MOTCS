# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_009A_R1_CORRECTED_GROUND_ZEEMAN_RATEEQ_STATIC_ACCEPTANCE_AUDIT_ONLY

This rerun regenerates and audits corrected-ground-Zeeman static rate-equation surfaces only. It is provisional, not a Rodriguez reproduction, and invokes no trajectory or capture path.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_009A_R1_CORRECTED_GROUND_ZEEMAN_RATEEQ_STATIC_ACCEPTANCE_AUDIT_ONLY Convention and history

The ground magnetic-moment tensor was negated exactly once at the Hamiltonian boundary. Source YAML, paper-to-pylcp polarization translation, apparatus field, dipole ordering, and excited tensor were unchanged.
Historical Run 009, Run 009A, and Run 009B hashes remained unchanged: `True`. Corrected arrays were newly generated: `PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_009A_R1_CORRECTED_GROUND_ZEEMAN_RATEEQ_STATIC_ACCEPTANCE_AUDIT_ONLY_corrected_static_arrays.npz`.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_009A_R1_CORRECTED_GROUND_ZEEMAN_RATEEQ_STATIC_ACCEPTANCE_AUDIT_ONLY Population and geometry health

- solves: `2023`; population range: `0.000383894` to `0.368001`
- maximum normalization error: `3.33067e-16`; maximum residual: `2.13371e-16`
- nullspace dimensions: `[1]`; fallbacks: `0`; nonfinite: `0`
- lab F_x(x,v_x) geometry and 1/sqrt(2) rotated-beam projections: `True`

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_009A_R1_CORRECTED_GROUND_ZEEMAN_RATEEQ_STATIC_ACCEPTANCE_AUDIT_ONLY Local slopes

| case | dF_x/dx | dF_x/dv_x | spatial | velocity |
|---|---:|---:|---|---|
| plane_wave_3 | -0.00894088 | -0.00397668 | restoring | damping |
| plane_wave_3_plus_1 | -0.152767 | -0.00364237 | restoring | damping |
| gaussian_3 | -0.0089531 | -0.00397668 | restoring | damping |
| gaussian_3_plus_1 | -0.15276 | -0.00364237 | restoring | damping |

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_009A_R1_CORRECTED_GROUND_ZEEMAN_RATEEQ_STATIC_ACCEPTANCE_AUDIT_ONLY Corrected reversal matrix

| case | dF_x/dx | dF_x/dv_x | spatial | velocity |
|---|---:|---:|---|---|
| nominal | -0.152767 | -0.00364237 | restoring | damping |
| polarization_flipped | 0.152767 | -0.00364237 | anti-restoring | damping |
| gradient_flipped | 0.152767 | -0.00364237 | anti-restoring | damping |
| both_flipped | -0.152767 | -0.00364237 | restoring | damping |

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_009A_R1_CORRECTED_GROUND_ZEEMAN_RATEEQ_STATIC_ACCEPTANCE_AUDIT_ONLY Component 4 and chirp

Component (4) strengthens restoring confinement in plane-wave and Gaussian controlled optical-system comparisons: `True`. These are separate combined-equilibrium solves, not an additive decomposition.

| detuning | extremum velocity [m/s] | position [m] | force | rough velocity [m/s] | deviation [m/s] |
|---:|---:|---:|---:|---:|---:|
| -8 Gamma | 85 | 0 | -0.0609319 | 84.9588 | 0.0411768 |
| -4.5 Gamma | 48 | 0 | -0.0517362 | 47.7893 | 0.210662 |
| -1 Gamma | 10 | 0 | -0.0366978 | 10.6199 | -0.619853 |

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_009A_R1_CORRECTED_GROUND_ZEEMAN_RATEEQ_STATIC_ACCEPTANCE_AUDIT_ONLY Gaussian, force scale, and convergence

Per-beam Gaussian application before one combined solve passed: `True`. Grid refinement preserved topology: `True`. All original quantitative refinement thresholds passed: `False`; cautions: `['plane_wave_3: dFdx relative change exceeds 25%']`. Force scale passed the deliberately broad order-of-magnitude screen: `True`; this is not quantitative reproduction.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_009A_R1_CORRECTED_GROUND_ZEEMAN_RATEEQ_STATIC_ACCEPTANCE_AUDIT_ONLY Before versus after

The original anti-restoring Run 009 surfaces are superseded for provisional engineering use, but retained unchanged as historical diagnostic artifacts. Population health, force scales, and chirp ordering remain explicitly recorded in metadata for both audits.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_009A_R1_CORRECTED_GROUND_ZEEMAN_RATEEQ_STATIC_ACCEPTANCE_AUDIT_ONLY Gate: PROVISIONAL_STATIC_GO

**PROVISIONAL_STATIC_GO**

Every named provisional static gate criterion passed. The quantitative refinement caution above is retained and is not classified as a topology failure.

This gate authorizes only further corrected provisional static study. `trajectory_authorized = false`, `capture_authorized = false`, and `exact_replication_valid = false` regardless of the gate.
Reason: the excited-state magnetic tensor remains unresolved; provisional effective `g ~= 0.3337199` versus Rodriguez representative `g = 0.001`.

# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_009A_R1_CORRECTED_GROUND_ZEEMAN_RATEEQ_STATIC_ACCEPTANCE_AUDIT_ONLY FINAL_PROVISIONAL_STATIC_GO
