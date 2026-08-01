# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY

This is an offline force-budget and implementation audit. It did not integrate or alter a trajectory, change an outcome, or open an exact-force path.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY Primary finding

The primary suspect is the provisional force adapter, not classifier cadence: Run 008 applied no physical `hbar k Gamma / m` acceleration conversion, applied one mean Gaussian envelope after forming an aggregate force, ignored detuning and backend transition topology, and represented [3] and [3+1] by the same total active saturation. These are engineering findings, not MgF physical conclusions.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY Unit and acceleration chain

- `k = 17487295.5947 rad/m`
- `Gamma = 131318572.92 rad/s`
- `hbar k Gamma = 2.42172578801e-19 N`
- `m(24Mg19F) = 7.13756895064e-26 kg` (`derived_approximate`; Sum of neutral-atom isotope masses; molecular binding mass is neglected. This is sufficient for the Track P unit audit and is not spectroscopy input.)
- `hbar k Gamma / m = 3392928.04702 m/s^2`
- acceleration examples for 0.01, 0.015, 0.03, and 1.0: `{'0.01': 33929.280470171885, '0.015': 50893.920705257835, '0.03': 101787.84141051567, '1': 3392928.0470171887}` m/s^2
- Run 008 adapter: `1.0`; adapter/physical ratio: `2.94730682803e-07`
- The physical conversion was applied zero times in Run 008 and exactly once in this audit conversion helper; it was not applied twice.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY Required versus delivered impulse

| Gamma/k | saved dv (m/s) | normalized integral | physical Jx if converted once (N s) | J/stopping J | Run008 dv/stopping dv | diagnosis |
|---:|---:|---:|---:|---:|---:|---|
| 2 | -0.00559784 | -0.00559784 | -1.35564e-21 | 1261.16 | 0.000371702 | `UNIT_CONVERSION_SUSPECT, GAUSSIAN_APPLICATION_SUSPECT, PROVISIONAL_BACKEND_TOPOLOGY_SUSPECT` |
| 4 | -0.00559782 | -0.00559782 | -1.35564e-21 | 630.577 | 0.000185851 | `UNIT_CONVERSION_SUSPECT, GAUSSIAN_APPLICATION_SUSPECT, PROVISIONAL_BACKEND_TOPOLOGY_SUSPECT` |
| 6 | -0.00559782 | -0.0055978 | -1.35563e-21 | 420.384 | 0.0001239 | `UNIT_CONVERSION_SUSPECT, GAUSSIAN_APPLICATION_SUSPECT, PROVISIONAL_BACKEND_TOPOLOGY_SUSPECT` |
| 7.5 | -0.00559782 | -0.00559779 | -1.35563e-21 | 336.306 | 9.91203e-05 | `UNIT_CONVERSION_SUSPECT, GAUSSIAN_APPLICATION_SUSPECT, PROVISIONAL_BACKEND_TOPOLOGY_SUSPECT` |
| 9 | -0.00559782 | -0.00559777 | -1.35563e-21 | 280.254 | 8.26002e-05 | `UNIT_CONVERSION_SUSPECT, GAUSSIAN_APPLICATION_SUSPECT, PROVISIONAL_BACKEND_TOPOLOGY_SUSPECT` |

The physical impulse ratios are counterfactual single-conversion diagnostics and are not capture efficiencies. The saved trajectories instead used the unit adapter and show only the small recorded velocity changes.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY Static post-handoff local-force audit

- `{'label': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY', 'title': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY plane_wave post-handoff local-force audit', 'beam_mode': 'plane_wave', 'position_probe_m': [-0.0001, 0.0, 0.0001], 'force_at_v_zero': [0.000579, -0.0, -0.000579], 'velocity_probe_m_s': [-0.01, 0.0, 0.01], 'force_at_x_zero': [0.002, -0.0, -0.002], 'dFdx_normalized_per_m': -5.789999999999999, 'dFdv_normalized_per_m_s': -0.2, 'restoring_status': 'restoring', 'damping_status': 'damping', 'numerical_asymmetry_x': 0.0, 'numerical_asymmetry_v': 0.0}`
- `{'label': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY', 'title': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY elliptical_gaussian post-handoff local-force audit', 'beam_mode': 'elliptical_gaussian', 'position_probe_m': [-0.0001, 0.0, 0.0001], 'force_at_v_zero': [0.0005789747924540662, -0.0, -0.0005789747924540662], 'velocity_probe_m_s': [-0.01, 0.0, 0.01], 'force_at_x_zero': [0.002, -0.0, -0.002], 'dFdx_normalized_per_m': -5.789747924540662, 'dFdv_normalized_per_m_s': -0.2, 'restoring_status': 'restoring', 'damping_status': 'damping', 'numerical_asymmetry_x': 0.0, 'numerical_asymmetry_v': 0.0}`

Both modes are locally restoring and damping and numerically symmetric. At the origin the Gaussian envelope is unity, so their small-signal slopes coincide. This does not validate global topology.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY Force-scale comparison

Sampling domain: x in `(-0.05, 0.05)` m and vx in `(-7.53, 7.53)` m/s.
- plane_wave_[3]: max `1.7955`; much larger than 0.03 and much larger than 0.015.
- plane_wave_[3+1]: max `1.7955`; much larger than 0.03 and much larger than 0.015.
- gaussian_[3]: max `1.506`; much larger than 0.03 and much larger than 0.015.
- gaussian_[3+1]: max `1.506`; much larger than 0.03 and much larger than 0.015.
- gaussian_chirp_-8Gamma: max `1.506`; much larger than 0.03 and much larger than 0.015.
- gaussian_chirp_-4.5Gamma: max `1.506`; much larger than 0.03 and much larger than 0.015.
- gaussian_chirp_-1Gamma: max `1.506`; much larger than 0.03 and much larger than 0.015.

These descriptive comparisons do not claim reproduction or disagreement. Identical chirp values expose that detuning is metadata-only in the toy force law.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY Gaussian-envelope application audit

- `{'label': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY', 'title': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY Gaussian application implementation audit', 'per_beam_envelopes_available': True, 'counterpropagating_pair_envelopes_equal': True, 'per_beam_envelopes_applied_before_force_summation': False, 'mean_envelope_applied_after_force_summation': True, 'saturation_squared': False, 'all_beams_multiplied_by_weakest_envelope': False, 'all_force_components_multiplied_by_single_mean_envelope': True, 'position_units_m': True, 'implementation_summary': 'force_at forms one aggregate spring/damping vector, then multiplies it by GaussianBeamSet.mean_envelope(position)', 'diagnosis': 'GAUSSIAN_APPLICATION_SUSPECT', 'representative_points': [{'label': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY', 'title': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY Gaussian envelopes x=-50 mm', 'x_mm': -50.0, 'per_beam': {'+x_prime': 0.00028493048887656935, '-x_prime': 0.00028493048887656935, '+y_prime': 0.00028493048887656935, '-y_prime': 0.00028493048887656935, '+z': 8.118538349144053e-08, '-z': 8.118538349144053e-08}}, {'label': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY', 'title': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY Gaussian envelopes x=-25 mm', 'x_mm': -25.0, 'per_beam': {'+x_prime': 0.12992260830505953, '-x_prime': 0.12992260830505953, '+y_prime': 0.12992260830505953, '-y_prime': 0.12992260830505953, '+z': 0.01687988414878991, '-z': 0.01687988414878991}}, {'label': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY', 'title': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY Gaussian envelopes x=0 mm', 'x_mm': 0.0, 'per_beam': {'+x_prime': 1.0, '-x_prime': 1.0, '+y_prime': 1.0, '-y_prime': 1.0, '+z': 1.0, '-z': 1.0}}, {'label': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY', 'title': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY Gaussian envelopes x=25 mm', 'x_mm': 25.0, 'per_beam': {'+x_prime': 0.12992260830505953, '-x_prime': 0.12992260830505953, '+y_prime': 0.12992260830505953, '-y_prime': 0.12992260830505953, '+z': 0.01687988414878991, '-z': 0.01687988414878991}}, {'label': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY', 'title': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY Gaussian envelopes x=50 mm', 'x_mm': 50.0, 'per_beam': {'+x_prime': 0.00028493048887656935, '-x_prime': 0.00028493048887656935, '+y_prime': 0.00028493048887656935, '-y_prime': 0.00028493048887656935, '+z': 8.118538349144053e-08, '-z': 8.118538349144053e-08}}]}`
- Result: `GAUSSIAN_APPLICATION_SUSPECT`. Per-beam envelopes exist and counterpropagating partners agree, but the current force path applies their mean after aggregate force summation. Saturation is linear rather than squared, and position is in metres.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY Beam and frequency contribution limitation

- `{'label': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY', 'title': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY beam and frequency decomposition limitation', 'decomposition_available': False, 'reason': 'the provisional force law aggregates active saturation into one spring coefficient, ignores detuning and backend transition matrices, and has no beam- or component-resolved force terms', 'component_4_conclusion': 'the [3] and [3+1] saturation sums are both 5.79, so component 4 only redistributes aggregate saturation and changes neither magnitude nor topology in this toy law', 'aggregate_pre_post_comparison': [{'label': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY', 'title': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY aggregate pre-post comparison inbound_x_minus_25_mm', 'point': 'inbound_x_minus_25_mm', 'x_m': -0.025, 'vx_m_s': 30.12, 'pre_handoff_Fx': -0.542312016212272, 'post_handoff_Fx': -0.542312016212272, 'difference': 0.0}, {'label': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY', 'title': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY aggregate pre-post comparison near_origin_positive_velocity', 'point': 'near_origin_positive_velocity', 'x_m': -0.001, 'vx_m_s': 15.06, 'pre_handoff_Fx': -2.9931537335996534, 'post_handoff_Fx': -2.9931537335996534, 'difference': 0.0}, {'label': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY', 'title': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY aggregate pre-post comparison origin_zero_velocity', 'point': 'origin_zero_velocity', 'x_m': 0.0, 'vx_m_s': 0.0, 'pre_handoff_Fx': -0.0, 'post_handoff_Fx': -0.0, 'difference': 0.0}, {'label': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY', 'title': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY aggregate pre-post comparison outbound_x_plus_25_mm', 'point': 'outbound_x_plus_25_mm', 'x_m': 0.025, 'vx_m_s': 30.12, 'pre_handoff_Fx': -0.5690159884355067, 'post_handoff_Fx': -0.5690159884355067, 'difference': 0.0}], 'diagnosis': 'PROVISIONAL_BACKEND_TOPOLOGY_SUSPECT'}`
- A beam-pair/component decomposition cannot be obtained honestly from the current law. Component 4 does not improve confinement here because [3] and [3+1] both reduce to aggregate saturation 5.79.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY Saved-trajectory force audit

### PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY v_2_gamma_over_k

- official outcome remains `UNRESOLVED`: only 0/21 dwell samples satisfied the engineering bounds; required fraction is 1
- pre/post/appreciably-illuminated impulse: `[-2.2127309857895804e-24, 0.0, 0.0]` / `[-1.3534299520147389e-21, 0.0, 0.0]` / `[-1.3554574958769982e-21, 0.0, 0.0]` N s
- first/last appreciable illumination: `0.00030000000000000003` / `0.0063000000000000035` s
- handoff / closest approach / center crossing: `0.001` / `0.0032999999999999982` / `[0.0033201626359715334]` s
- plot: `PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY_v_2_gamma_over_k.png`

### PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY v_4_gamma_over_k

- official outcome remains `UNRESOLVED`: only 0/21 dwell samples satisfied the engineering bounds; required fraction is 1
- pre/post/appreciably-illuminated impulse: `[-5.792067899136827e-23, 0.0, 0.0]` / `[-1.2977166686531326e-21, 0.0, 0.0]` / `[-1.3554893774840225e-21, 0.0, 0.0]` N s
- first/last appreciable illumination: `0.0002` / `0.0030999999999999986` s
- handoff / closest approach / center crossing: `0.001` / `0.0017000000000000003` / `[0.0016600545315840639]` s
- plot: `PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY_v_4_gamma_over_k.png`

### PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY v_6_gamma_over_k

- official outcome remains `UNRESOLVED`: only 0/21 dwell samples satisfied the engineering bounds; required fraction is 1
- pre/post/appreciably-illuminated impulse: `[-4.514811636202127e-22, 0.0, 0.0]` / `[-9.041526230767401e-22, 0.0, 0.0]` / `[-1.3553600322183866e-21, 0.0, 0.0]` N s
- first/last appreciable illumination: `0.0001` / `0.0021000000000000003` s
- handoff / closest approach / center crossing: `0.001` / `0.0011` / `[0.001106696819160063]` s
- plot: `PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY_v_6_gamma_over_k.png`

### PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY v_7p5_gamma_over_k

- official outcome remains `UNRESOLVED`: only 0/21 dwell samples satisfied the engineering bounds; required fraction is 1
- pre/post/appreciably-illuminated impulse: `[-9.647512942588167e-22, 0.0, 0.0]` / `[-3.9087955247274674e-22, 0.0, 0.0]` / `[-1.3553321529844186e-21, 0.0, 0.0]` N s
- first/last appreciable illumination: `0.0001` / `0.0016000000000000003` s
- handoff / closest approach / center crossing: `0.001` / `0.0009000000000000002` / `[0.0008853555628760331]` s
- plot: `PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY_v_7p5_gamma_over_k.png`

### PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY v_9_gamma_over_k

- official outcome remains `UNRESOLVED`: only 0/21 dwell samples satisfied the engineering bounds; required fraction is 1
- pre/post/appreciably-illuminated impulse: `[-1.2647185791255971e-21, 0.0, 0.0]` / `[-9.090896366785509e-23, 0.0, 0.0]` / `[-1.3554316676060651e-21, 0.0, 0.0]` N s
- first/last appreciable illumination: `0.0001` / `0.0014000000000000002` s
- handoff / closest approach / center crossing: `0.001` / `0.0007000000000000001` / `[0.0007377953370147633]` s
- plot: `PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY_v_9_gamma_over_k.png`

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008B_FORCE_BUDGET_AUDIT_ONLY Immutability and scope

- all source hashes unchanged: `True`
- official outcomes unchanged: `True`
- trajectory integrations performed: `0`
- No new velocity, longer integration, capture threshold, source distribution, stochastic recoil, optimizer, or exact-force API was added. Track E remains blocked.
