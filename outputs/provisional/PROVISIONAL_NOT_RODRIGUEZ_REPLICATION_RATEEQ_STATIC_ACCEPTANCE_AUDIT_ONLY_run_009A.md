# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RATEEQ_STATIC_ACCEPTANCE_AUDIT_ONLY Run 009A

This is a static acceptance audit of the saved Run 009 provisional pylcp rate-equation results. It adds no physics, runs no trajectory, calculates no capture result, and makes no Rodriguez-replication claim.
Exact Track E remains blocked. Trajectories must remain disconnected unless every gate condition passes.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RATEEQ_STATIC_ACCEPTANCE_AUDIT_ONLY Coordinate conventions

The audited quantity is `F_x(x,v_x)`: position `[x,0,0]`, velocity `[v_x,0,0]`, and returned force component 0. The four rotated beams have lab-x projection magnitude `1/sqrt(2)`; the z beams have zero lab-x Doppler projection. This is not an inherited z map.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RATEEQ_STATIC_ACCEPTANCE_AUDIT_ONLY Equilibrium solves

- points audited: `2023`; all saved points: `True`
- minimum population: `0.000333968`
- maximum population-sum error: `4.44089e-16`
- maximum steady-state residual infinity norm: `1.82146e-16`
- nullspace dimensions: `[1]`; fallbacks: `0`
- tolerance stability: `True`, max force difference `0`

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RATEEQ_STATIC_ACCEPTANCE_AUDIT_ONLY [3] versus [3+1] and reversal signs

- [3] dF_x/dx: `0.172096`; dF_x/dv_x: `-0.00402511`
- [3+1] dF_x/dx: `0.307137`; dF_x/dv_x: `-0.00369145`
- component (4) materially changes the surface: `True`
- [3] extrema: `{'maximum_normalized_force': 0.03652662272621478, 'maximum_location': {'x_m': 0.0, 'vx_m_s': -9.412500000000001}, 'minimum_normalized_force': -0.03652662272621485, 'minimum_location': {'x_m': 0.0, 'vx_m_s': 9.4125}}`
- [3+1] extrema: `{'maximum_normalized_force': 0.03365466202569616, 'maximum_location': {'x_m': 0.0, 'vx_m_s': -9.412500000000001}, 'minimum_normalized_force': -0.03365466202569625, 'minimum_location': {'x_m': 0.0, 'vx_m_s': 9.4125}}`

| case | dF_x/dx | dF_x/dv_x | spatial | velocity |
|---|---:|---:|---|---|
| nominal | 0.299954 | -0.00364237 | anti-restoring | damping |
| polarization_flipped | -0.299954 | -0.00364237 | restoring | damping |
| gradient_flipped | -0.299954 | -0.00364237 | restoring | damping |
| both_flipped | 0.299954 | -0.00364237 | anti-restoring | damping |

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RATEEQ_STATIC_ACCEPTANCE_AUDIT_ONLY Chirp moving-boat audit

| detuning | rough sqrt(2)|Delta|/k [m/s] | found slowing extremum [m/s] | force | boundary limited |
|---:|---:|---:|---:|---|
| -8 Gamma | 84.9588 | 85 | -0.0609319 | False |
| -4.5 Gamma | 47.7893 | 48 | -0.0517362 | False |
| -1 Gamma | 10.6199 | 10 | -0.0366978 | False |

Feature velocity decreases coherently: `True`; expected/found correlation: `0.99997`.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RATEEQ_STATIC_ACCEPTANCE_AUDIT_ONLY Gaussian manual points

Center agreement at nonzero velocity: `True`. Off-center attenuation count: `6/6`. Not a mean-envelope-after-sum result: `True`.
Counterpropagating envelope pairs agree exactly while the rotated and z beam groups differ along lab x; these differences are geometric rather than numerical asymmetry.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RATEEQ_STATIC_ACCEPTANCE_AUDIT_ONLY Force scale and convergence

- `plane_wave_3`: `0.0365266 hbar*k*Gamma`, `123932 m/s^2`, `same_order_as_0p03`
- `plane_wave_3_plus_1`: `0.0336547 hbar*k*Gamma`, `114188 m/s^2`, `same_order_as_0p03`
- `gaussian_3`: `0.0365266 hbar*k*Gamma`, `123932 m/s^2`, `same_order_as_0p03`
- `gaussian_3_plus_1`: `0.0336547 hbar*k*Gamma`, `114188 m/s^2`, `same_order_as_0p03`

Selected [3]/[3+1] lab-x slices refined by `2x`: convergence passed `True`. No acceleration was integrated.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RATEEQ_STATIC_ACCEPTANCE_AUDIT_ONLY Gate: NO-GO

**NO-GO**

Failed conditions:

- polarization/component wiring error: nominal local signs are not both restoring and damping
- polarization or magnetic-gradient reversal behavior is wrong
- component (4) behavior wrong: [3+1] does not strengthen restoring confinement

Trajectory reconnection authorized by this audit: `False`.

# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RATEEQ_STATIC_ACCEPTANCE_AUDIT_ONLY FINAL_GATE_NO-GO
