# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011A_BASELINE_DISCREPANCY_AUDIT_ONLY

This is a read-only discrepancy audit of saved Track P artifacts. It is provisional, is not a Rodriguez replication, and makes no capture claim.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011A_BASELINE_DISCREPANCY_AUDIT_ONLY Immutable input verification

Protected Run 010/011 arrays, metadata, reports, caches, spectroscopy, and apparatus configs: `True` (30 files). No force field was rebuilt and no trajectory was reintegrated.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011A_BASELINE_DISCREPANCY_AUDIT_ONLY Benchmark ledger

| parameter | paper | code | units | conversion | source/config | status |
|---|---|---|---|---|---|---|
| initial position | -50 | -0.050 | mm -> m | mm*1e-3 | Rodriguez Sec. IV/Fig. 4(a); rodriguez_named_trajectory_protocol.yaml | exact match |
| initial velocity | 7.5 Gamma/k about 57 | 56.475 | Gamma/k -> m/s | 7.5*7.53 m/s | Rodriguez Sec. IV/Fig. 4(a); rodriguez_named_trajectory_protocol.yaml | derived match |
| velocity direction | +x from x<0 toward center | +x | direction | none | Rodriguez Sec. II/IV; protocol coordinate_convention | exact match |
| chirp start | 0 | 0 | s | none | Rodriguez Eq. (6)/Sec. IV; handoff policy | exact match |
| chirp endpoints | -8 to -1 | -8 to -1 | Gamma | angular detuning/Gamma | Rodriguez Fig. 4 caption/Sec. IV; handoff YAML | exact match |
| chirp duration | 1 | 0.001 | ms -> s | ms*1e-3 | Rodriguez Fig. 4 caption/Sec. IV; handoff policy | exact match |
| pre saturation | (1.45,1.45,2.89,0) | same per beam | I/I_sat | none | Rodriguez Sec. IV; handoff policy | exact match |
| post saturation | (1.45,1.45,2.17,0.72) | same per beam | I/I_sat | none | Rodriguez Sec. IV; handoff policy | exact match |
| component 4 | +2, on at tau | +2 parked/off before tau; active at t>=tau | Gamma, s | none | Rodriguez Fig. 1/Sec. IV; handoff policy | exact match |
| field gradient | 2 | 0.2 | mT/cm -> T/m | 1 mT/cm=0.1 T/m | Rodriguez Fig. 4 caption; accepted_backend.py | exact match |
| beam axes | +/-x', +/-y', +/-z; 45 | same six unit vectors | degrees/unit vectors | x',y' lab projections 1/sqrt(2) | Rodriguez Sec. II; geometry.py | exact match |
| Gaussian radii | 17.5, 10, 1/e^2 | 0.0175, 0.010, exp(-2r^2/w^2) | mm -> m | mm*1e-3 | Rodriguez Sec. II/Fig. 4; Gaussian baseline YAML | exact match |
| total-power statement | 1 | 1 metadata only | W | no inferred allocation | Rodriguez Fig. 4 caption/Sec. IV; Gaussian baseline YAML | ambiguity |
| operative saturation | s_lm=I_lm/I_sat for each beam/component | reported peak s per physical beam/component | dimensionless | none | Rodriguez Eq. (4)/notation after Eq. (5); rateeq_backend.py | exact match |
| simulation duration | not stated for Fig. 4(a) | 0.020 | s | none | Rodriguez Fig. 4(a); Run 011 YAML | ambiguity |
| capture terminology | largest initial velocity captured; curve reaches v=0,x=0 | engineering BOUNDED_FINAL_STATE or UNRESOLVED | classification | none | Rodriguez Fig. 4(a)/Sec. III wording; Run 011 outcome classifier | not comparable |

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011A_BASELINE_DISCREPANCY_AUDIT_ONLY Moving slowing-force region

Appreciable illumination is defined as mean six-beam envelope >= `0.01`. A useful slowing sample satisfies `F <= -0.05*abs(F_min(detuning)) on the cached pre-handoff field`. Phase-space distance uses the paper guide widths `24.749 mm` and `7.530 m/s`.

| case | first illuminated ms | closest ms | closest x mm | closest v m/s | cached extremum v m/s | distance | useful time ms | arrival |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| v_2_gamma_over_k | 1.000 | 0.900 | -36.453 | 14.988 | 18.750 | 1.555 | 0.000 | near_slowing_feature_in_velocity_but_spatially_offset |
| v_4_gamma_over_k | 0.500 | 0.700 | -28.939 | 29.811 | 31.250 | 1.185 | 0.000 | near_slowing_feature_in_velocity_but_spatially_offset |
| v_6_gamma_over_k | 0.400 | 0.600 | -23.027 | 43.202 | 43.750 | 0.933 | 0.200 | near_slowing_feature_in_velocity_but_spatially_offset |
| v_7p5_gamma_over_k | 0.300 | 0.400 | -27.430 | 56.126 | 56.250 | 1.108 | 0.200 | near_slowing_feature_in_velocity_but_spatially_offset |
| v_9_gamma_over_k | 0.300 | 0.300 | -29.679 | 67.578 | 62.500 | 1.376 | 0.100 | near_slowing_feature_in_velocity_but_spatially_offset |

For 7.5 Gamma/k, the trajectory is velocity-matched to the cached slowing extremum near 0.4 ms but is still near x=-27 mm, outside the cached major negative-force region. It then falls behind the rapidly descending velocity feature. This is primarily a spatial-then-velocity miss, not a chirp-sign error.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011A_BASELINE_DISCREPANCY_AUDIT_ONLY Force and impulse budget

| case | p initial | p final | net impulse | negative impulse | positive impulse | pre-tau | post-tau | negative/stop | Fmin | Fmax |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v_2_gamma_over_k | 1.075e-24 | 1.758e-26 | -1.057e-24 | -1.057e-24 | 1.783e-30 | -1.360e-26 | -1.044e-24 | 0.983 | -0.0034 | 0.0000 |
| v_4_gamma_over_k | 2.150e-24 | 8.783e-27 | -2.141e-24 | -2.117e-24 | 0.000e+00 | -2.315e-25 | -1.910e-24 | 0.985 | -0.0242 | -0.0000 |
| v_6_gamma_over_k | 3.225e-24 | 3.230e-24 | 4.781e-27 | -5.934e-25 | 5.802e-25 | -5.632e-25 | 5.680e-25 | 0.184 | -0.0088 | 0.0053 |
| v_7p5_gamma_over_k | 4.031e-24 | 4.095e-24 | 6.413e-26 | -4.583e-25 | 5.302e-25 | -1.872e-25 | 2.514e-25 | 0.114 | -0.0059 | 0.0082 |
| v_9_gamma_over_k | 4.837e-24 | 4.445e-24 | -3.925e-25 | -3.890e-25 | 9.393e-28 | -3.732e-25 | -1.929e-26 | 0.080 | -0.0030 | 0.0000 |

The 7.5 Gamma/k case exits about 0.90 m/s faster than it entered: its post-handoff accelerating impulse exceeds its pre-handoff slowing impulse. The 9 Gamma/k case slows more because it crosses the center before the handoff and continues sampling the moving negative pre-handoff feature; 7.5 crosses at the handoff and 6 crosses afterward, where the post-handoff positive lobe cancels much of their slowing. The 2 and 4 cases remain on x<0 because post-handoff negative force removes nearly all incident momentum before either reaches the origin; their residual speeds are small and the 20 ms interval ends before crossing.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011A_BASELINE_DISCREPANCY_AUDIT_ONLY Optical-frequency construction

rotating-frame carrier coordinates in units of Gamma; the 834.3 THz optical common offset is not represented. The addressed F'=1 transitions receive exactly the policy detuning. The F'=0 transition is shifted by +0.023923 Gamma because the accepted 0.5 MHz splitting is retained. No material common-reference mismatch was found.

| segment | component | role | policy detuning | carrier coordinate | polarization | saturation | active |
|---|---:|---|---:|---:|---|---:|---|
| pre_handoff | 1 | lower_F1 | -8.000 | -0.033322 | sigma_plus -> pylcp +1 | 1.450 | True |
| pre_handoff | 2 | F0 | -8.000 | -5.283636 | sigma_minus -> pylcp -1 | 1.450 | True |
| pre_handoff | 3 | upper_F1_F2_mean | -8.000 | -11.262645 | sigma_minus -> pylcp -1 | 2.890 | True |
| pre_handoff | 4 | upper_F1_F2_mean_confinement | 2.000 | -1.262645 | sigma_plus -> pylcp +1 | 0.000 | False |
| post_handoff | 1 | lower_F1 | -1.000 | 6.966678 | sigma_plus -> pylcp +1 | 1.450 | True |
| post_handoff | 2 | F0 | -1.000 | 1.716364 | sigma_minus -> pylcp -1 | 1.450 | True |
| post_handoff | 3 | upper_F1_F2_mean | -1.000 | -4.262645 | sigma_minus -> pylcp -1 | 2.170 | True |
| post_handoff | 4 | upper_F1_F2_mean_confinement | 2.000 | -1.262645 | sigma_plus -> pylcp +1 | 0.720 | True |

Components 3 and 4 reference the arithmetic mean of the upper F=1/F=2 ground energies. The internal optical carrier uses the retained F'=1 energy as its excited reference. Full detunings from every retained ground-role/excited-basis combination are preserved in the JSON metadata. No material centroid/reference mismatch was demonstrated.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011A_BASELINE_DISCREPANCY_AUDIT_ONLY Saturation and Rabi convention

At the selected transition, paper rate/Gamma = `0.0145956425877` and pylcp rate/Gamma = `0.0145956425877` (absolute difference `0.000e+00`). The Rabi factor, angular-linewidth convention, and single line-strength application match. Saturation is applied to each physical beam and component; six beams are explicit rather than folded into s. The 1 W field is metadata and does not separately rescale the already supplied peak saturation vector.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011A_BASELINE_DISCREPANCY_AUDIT_ONLY Gaussian timing and width

| x mm | +/-x' | +/-y' | +/-z | mean |
|---:|---:|---:|---:|---:|
| -50 | 0.000285 | 0.000285 | 0.000000 | 0.000190 |
| -40 | 0.005383 | 0.005383 | 0.000029 | 0.003598 |
| -30 | 0.052931 | 0.052931 | 0.002802 | 0.036221 |
| -25 | 0.129923 | 0.129923 | 0.016880 | 0.092242 |
| -20 | 0.270868 | 0.270868 | 0.073370 | 0.205035 |
| 0 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |

Saved 7.5 Gamma/k path envelope events:

| event | t ms | x mm | v m/s | min envelope | mean envelope | max envelope |
|---|---:|---:|---:|---:|---:|---:|
| first_useful_force_encounter | 0.500 | -21.855 | 55.270 | 0.044187 | 0.154868 | 0.210208 |
| closest_to_slowing_extremum | 0.400 | -27.430 | 56.126 | 0.007345 | 0.059582 | 0.085701 |
| handoff | 1.000 | 4.221 | 53.852 | 0.890176 | 0.925719 | 0.943491 |
| center_crossing | 1.000 | 4.221 | 53.852 | 0.890176 | 0.925719 | 0.943491 |
| last_appreciable_illumination | 1.500 | 32.520 | 57.354 | 0.001001 | 0.021428 | 0.031642 |

The analytic Gaussian frames have the intended sqrt(2) projection. Nevertheless, after molecular/Zeeman response is included, the cached major negative-force region has exp(-2)-level half-extents mostly 15-20 mm rather than the paper's rough 25 mm. Thus the operative provisional force boat is materially narrower even though the bare optical envelope is correctly wired.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011A_BASELINE_DISCREPANCY_AUDIT_ONLY Direct rate-equation audit points on 7.5 Gamma/k

| point | t ms | x mm | v m/s | cached | direct | direction | solver healthy |
|---|---:|---:|---:|---:|---:|---|---|
| initial_state | 0.000 | -50.000 | 56.475 | -0.000001 | -0.000001 | slowing | True |
| first_appreciably_illuminated_state | 0.300 | -33.061 | 56.412 | -0.000352 | -0.000296 | slowing | True |
| closest_to_slowing_extremum | 0.400 | -27.430 | 56.126 | -0.001651 | -0.001603 | slowing | True |
| strongest_negative_force | 0.600 | -16.403 | 53.632 | -0.005896 | -0.005374 | slowing | True |
| immediately_before_handoff | 0.900 | -1.014 | 50.932 | 0.006928 | 0.004581 | accelerating | True |
| immediately_after_handoff | 1.000 | 4.221 | 53.852 | 0.008173 | 0.008699 | accelerating | True |
| center_crossing | 1.000 | 4.221 | 53.852 | 0.008173 | 0.008699 | accelerating | True |
| strongest_positive_force | 1.000 | 4.221 | 53.852 | 0.008173 | 0.008699 | accelerating | True |
| domain_exit | 1.979 | 60.000 | 57.374 | 0.000000 | 0.000000 | accelerating | True |

These fresh solves are audit samples only. They confirm the cached force direction and population-solver health at dynamically meaningful saved states; they do not reopen the already-passed Run 011 interpolation gate.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011A_BASELINE_DISCREPANCY_AUDIT_ONLY Paper force-map expectations

| feature | classification | evidence |
|---|---|---|
| slowing extrema near sqrt(2)*abs(Delta)/k | CLOSE | cached extrema track the guide within about one 6.25 m/s velocity cell |
| useful force scale about 0.03 hbar*k*Gamma | MATERIALLY_DIFFERENT | sampled cached negative extrema reach 0.072 |
| velocity width about Gamma/k | CLOSE | cached exp(-2) spans are grid-limited but of order 6-13 m/s |
| spatial width about sqrt(2)wxy about 25 mm | MATERIALLY_DIFFERENT | cached exp(-2) negative-force half-extents are mostly 15-20 mm |
| smooth movement during chirp | MATCHES | accepted detuning slices move monotonically from about 88 to 13 m/s |
| nominal capture near 7.5 Gamma/k | MATERIALLY_DIFFERENT | saved path exits x=+60 mm at positive speed |

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011A_BASELINE_DISCREPANCY_AUDIT_ONLY Candidate diagnoses

Demonstrated causes:

- `GAUSSIAN_FORCE_REGION_TOO_NARROW`: cached exp(-2) slowing-force half-width is 15-20 mm rather than the paper's rough 25 mm
- `POST_HANDOFF_ACCELERATION_CANCELS_SLOWING`: 7.5 Gamma/k has negative impulse before tau and larger positive impulse after tau, ending faster than it entered

Likely contributor:

- `PROVISIONAL_HAMILTONIAN_FORCE_SHAPE_DIFFERENCE`: the accepted field is about twice the paper's rough peak scale yet spatially narrower; unresolved exact excited-state physics remains the principal model boundary

Ruled out by this audit:

- `CHIRP_TIMING_MISMATCH`: start, endpoints, duration, and exact handoff agree
- `VELOCITY_SIGN_OR_PROJECTION_MISMATCH`: positive lab-x motion and 45-degree Doppler projections agree; cached boat velocities follow sqrt(2)|Delta|/k
- `DETUNING_REFERENCE_MISMATCH`: addressed F'=1 carriers have exact policy detuning; retained F'=0 offset is only 0.023923 Gamma
- `SATURATION_CONVENTION_MISMATCH`: paper and code both apply s_lm per physical beam and component
- `RABI_RATE_NORMALIZATION_MISMATCH`: paper and pylcp pumping-rate formulas agree term by term and numerically
- `FORCE_FIELD_DOMAIN_ONLY`: the 7.5 Gamma/k path has already failed to slow before the +60 mm boundary; the boundary records failure rather than causing it

Unresolved:

- `COMPONENT_FREQUENCY_MAPPING_MISMATCH`: no mismatch found in the implemented common reference, but the exact Rodriguez code is unavailable for direct comparison
- `PAPER_CAPTURE_CRITERION_AMBIGUITY`: Fig. 4 calls the thick trajectory captured but does not state its numerical terminal rule or duration
- `INSUFFICIENT_EVIDENCE`: the paper force map was visually inspected but not digitized

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011A_BASELINE_DISCREPANCY_AUDIT_ONLY Final gate: BASELINE_DISCREPANCY_NARROWED

**BASELINE_DISCREPANCY_NARROWED**

The accepted provisional field's operative slowing region is demonstrably narrower than the paper guide, and the post-handoff accelerating lobe demonstrably cancels the 7.5 Gamma/k path's earlier slowing. The most likely common origin is provisional Hamiltonian force-shape physics, but the paper field has not been digitized and the exact excited-state model remains blocked, so a targeted corrective physics change is not yet justified.

`capture_authorized = false`; `capture_velocity_authorized = false`; `optimizer_authorized = false`; `exact_replication_valid = false`; Track E remains blocked.

# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011A_BASELINE_DISCREPANCY_AUDIT_ONLY FINAL_BASELINE_DISCREPANCY_NARROWED
