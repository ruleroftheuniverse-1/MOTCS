# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008A_DIAGNOSTIC_AUDIT_ONLY

This audits the saved Run 008 arrays and metadata only; no trajectory was rerun.
Official outcomes remain `UNRESOLVED`, and classifier criteria were not changed.
This is not a capture analysis or a Rodriguez replication. Track E remains blocked.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008A_DIAGNOSTIC_AUDIT_ONLY Compact diagnosis

| initial Gamma/k | initial m/s | final x (m) | final vx (m/s) | closest | crossings | dwell pos/vel/both | category | behavior |
|---:|---:|---:|---:|---:|---:|---:|---|---|
| 2 | 15.06 | 0.251107 | 15.0544 | 0.000303592 m at 0.0033 s | 1 | 0/0/0 of 21 | `CENTER_CROSSING_WITHOUT_SETTLING` | passing through / leaving |
| 4 | 30.12 | 0.552297 | 30.1144 | 0.00120305 m at 0.0017 s | 1 | 0/0/0 of 21 | `CENTER_CROSSING_WITHOUT_SETTLING` | passing through / leaving |
| 6 | 45.18 | 0.853494 | 45.1744 | 0.000302541 m at 0.0011 s | 1 | 0/0/0 of 21 | `CENTER_CROSSING_WITHOUT_SETTLING` | passing through / leaving |
| 7.5 | 56.475 | 1.07939 | 56.4694 | 0.00082701 m at 0.0009 s | 1 | 0/0/0 of 21 | `CENTER_CROSSING_WITHOUT_SETTLING` | passing through / leaving |
| 9 | 67.77 | 1.30529 | 67.7644 | 0.00256128 m at 0.0007 s | 1 | 0/0/0 of 21 | `CENTER_CROSSING_WITHOUT_SETTLING` | passing through / leaving |

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008A_DIAGNOSTIC_AUDIT_ONLY Why the official outcomes are unresolved

All cases have 21 final dwell-window samples, exceeding the required 10. None satisfies either the 10 mm position bound or the 1 m/s speed bound in that final window, so none satisfies both. Each crossed the center once, left the bounded region, is receding at 20 ms, and has negligible endpoint force under the documented relative test. The primary audit category is therefore `CENTER_CROSSING_WITHOUT_SETTLING`; `LEFT_BOUNDED_REGION` and `FORCE_OR_ACCELERATION_NEAR_ZERO` are contributing diagnostics, not replacement outcome labels.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008A_DIAGNOSTIC_AUDIT_ONLY Per-trajectory details

### PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008A_DIAGNOSTIC_AUDIT_ONLY v_2_gamma_over_k

- official outcome and reason: `UNRESOLVED`; only 0/21 dwell samples satisfied the engineering bounds; required fraction is 1
- audit category: `CENTER_CROSSING_WITHOUT_SETTLING`; contributors: `LEFT_BOUNDED_REGION, FORCE_OR_ACCELERATION_NEAR_ZERO`
- final position / velocity: `[0.2511067247205286, 0.0, 0.0]` m / `[15.05440216062324, 0.0, 0.0]` m/s
- final normalized force: `[-1.1368944192608873e-89, -0.0, -0.0]`; provisional integrator acceleration: `[-1.1368944192608873e-89, -0.0, -0.0]` m/s^2 (uncalibrated)
- crossing times: `[0.0033201626359715334]` s; final motion: `{'approaching_or_receding': 'receding', 'speed_trend': 'effectively constant', 'position_magnitude_trend': 'increasing', 'behavior_summary': 'passing through / leaving'}`
- position-bound entry/exit and sampled duration: `{'value': 0.01, 'unit': 'm', 'first_entry_s': 0.0026999999999999993, 'last_entry_s': 0.0026999999999999993, 'first_exit_s': 0.0038999999999999972, 'last_exit_s': 0.0038999999999999972, 'sample_count': 13, 'sampled_occupancy_duration_s': 0.001299999999999998}`
- velocity-bound entry/exit and sampled duration: `{'value': 1.0, 'unit': 'm/s', 'first_entry_s': None, 'last_entry_s': None, 'first_exit_s': None, 'last_exit_s': None, 'sample_count': 0, 'sampled_occupancy_duration_s': 0.0}`
- final dwell position/velocity/both fractions: `0` / `0` / `0`
- final 5 ms trends: `{'tail_interval_s': [0.015, 0.02], 'tail_sample_count': 51, 'dx_dt_m_s': 15.054402160623125, 'dv_dt_m_s2': 0.0, 'd_abs_x_dt_m_s': 15.054402160623125, 'd_abs_v_dt_m_s2': 0.0}`
- final Gaussian envelopes: `{'+x_prime': 3.8195351901018855e-90, '-x_prime': 3.8195351901018855e-90, '+y_prime': 3.8195351901018855e-90, '-y_prime': 3.8195351901018855e-90, '+z': 1.4588849068425817e-179, '-z': 1.4588849068425817e-179}`; appreciably illuminated: `False` using threshold `0.001`
- plot: `PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008A_DIAGNOSTIC_AUDIT_ONLY_v_2_gamma_over_k.png`

### PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008A_DIAGNOSTIC_AUDIT_ONLY v_4_gamma_over_k

- official outcome and reason: `UNRESOLVED`; only 0/21 dwell samples satisfied the engineering bounds; required fraction is 1
- audit category: `CENTER_CROSSING_WITHOUT_SETTLING`; contributors: `LEFT_BOUNDED_REGION, FORCE_OR_ACCELERATION_NEAR_ZERO`
- final position / velocity: `[0.55229736024634, 0.0, 0.0]` m / `[30.11440217596665, 0.0, 0.0]` m/s
- final normalized force: `[-0.0, -0.0, -0.0]`; provisional integrator acceleration: `[-0.0, -0.0, -0.0]` m/s^2 (uncalibrated)
- crossing times: `[0.0016600545315840639]` s; final motion: `{'approaching_or_receding': 'receding', 'speed_trend': 'effectively constant', 'position_magnitude_trend': 'increasing', 'behavior_summary': 'passing through / leaving'}`
- position-bound entry/exit and sampled duration: `{'value': 0.01, 'unit': 'm', 'first_entry_s': 0.0014000000000000002, 'last_entry_s': 0.0014000000000000002, 'first_exit_s': 0.0019000000000000004, 'last_exit_s': 0.0019000000000000004, 'sample_count': 6, 'sampled_occupancy_duration_s': 0.0006000000000000003}`
- velocity-bound entry/exit and sampled duration: `{'value': 1.0, 'unit': 'm/s', 'first_entry_s': None, 'last_entry_s': None, 'first_exit_s': None, 'last_exit_s': None, 'sample_count': 0, 'sampled_occupancy_duration_s': 0.0}`
- final dwell position/velocity/both fractions: `0` / `0` / `0`
- final 5 ms trends: `{'tail_interval_s': [0.015, 0.02], 'tail_sample_count': 51, 'dx_dt_m_s': 30.114402175966756, 'dv_dt_m_s2': 5.602205987416447e-28, 'd_abs_x_dt_m_s': 30.114402175966756, 'd_abs_v_dt_m_s2': 5.602205987416447e-28}`
- final Gaussian envelopes: `{'+x_prime': 0.0, '-x_prime': 0.0, '+y_prime': 0.0, '-y_prime': 0.0, '+z': 0.0, '-z': 0.0}`; appreciably illuminated: `False` using threshold `0.001`
- plot: `PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008A_DIAGNOSTIC_AUDIT_ONLY_v_4_gamma_over_k.png`

### PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008A_DIAGNOSTIC_AUDIT_ONLY v_6_gamma_over_k

- official outcome and reason: `UNRESOLVED`; only 0/21 dwell samples satisfied the engineering bounds; required fraction is 1
- audit category: `CENTER_CROSSING_WITHOUT_SETTLING`; contributors: `LEFT_BOUNDED_REGION, FORCE_OR_ACCELERATION_NEAR_ZERO`
- final position / velocity: `[0.8534942494090819, 0.0, 0.0]` m / `[45.1744021797435, 0.0, 0.0]` m/s
- final normalized force: `[-0.0, -0.0, -0.0]`; provisional integrator acceleration: `[-0.0, -0.0, -0.0]` m/s^2 (uncalibrated)
- crossing times: `[0.001106696819160063]` s; final motion: `{'approaching_or_receding': 'receding', 'speed_trend': 'effectively constant', 'position_magnitude_trend': 'increasing', 'behavior_summary': 'passing through / leaving'}`
- position-bound entry/exit and sampled duration: `{'value': 0.01, 'unit': 'm', 'first_entry_s': 0.0009000000000000002, 'last_entry_s': 0.0009000000000000002, 'first_exit_s': 0.0013000000000000002, 'last_exit_s': 0.0013000000000000002, 'sample_count': 5, 'sampled_occupancy_duration_s': 0.0005}`
- velocity-bound entry/exit and sampled duration: `{'value': 1.0, 'unit': 'm/s', 'first_entry_s': None, 'last_entry_s': None, 'first_exit_s': None, 'last_exit_s': None, 'sample_count': 0, 'sampled_occupancy_duration_s': 0.0}`
- final dwell position/velocity/both fractions: `0` / `0` / `0`
- final 5 ms trends: `{'tail_interval_s': [0.015, 0.02], 'tail_sample_count': 51, 'dx_dt_m_s': 45.17440217974316, 'dv_dt_m_s2': 0.0, 'd_abs_x_dt_m_s': 45.17440217974316, 'd_abs_v_dt_m_s2': 0.0}`
- final Gaussian envelopes: `{'+x_prime': 0.0, '-x_prime': 0.0, '+y_prime': 0.0, '-y_prime': 0.0, '+z': 0.0, '-z': 0.0}`; appreciably illuminated: `False` using threshold `0.001`
- plot: `PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008A_DIAGNOSTIC_AUDIT_ONLY_v_6_gamma_over_k.png`

### PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008A_DIAGNOSTIC_AUDIT_ONLY v_7p5_gamma_over_k

- official outcome and reason: `UNRESOLVED`; only 0/21 dwell samples satisfied the engineering bounds; required fraction is 1
- audit category: `CENTER_CROSSING_WITHOUT_SETTLING`; contributors: `LEFT_BOUNDED_REGION, FORCE_OR_ACCELERATION_NEAR_ZERO`
- final position / velocity: `[1.079393006567809, 0.0, 0.0]` m / `[56.469402181204444, 0.0, 0.0]` m/s
- final normalized force: `[-0.0, -0.0, -0.0]`; provisional integrator acceleration: `[-0.0, -0.0, -0.0]` m/s^2 (uncalibrated)
- crossing times: `[0.0008853555628760331]` s; final motion: `{'approaching_or_receding': 'receding', 'speed_trend': 'effectively constant', 'position_magnitude_trend': 'increasing', 'behavior_summary': 'passing through / leaving'}`
- position-bound entry/exit and sampled duration: `{'value': 0.01, 'unit': 'm', 'first_entry_s': 0.0008000000000000001, 'last_entry_s': 0.0008000000000000001, 'first_exit_s': 0.001, 'last_exit_s': 0.001, 'sample_count': 3, 'sampled_occupancy_duration_s': 0.0002999999999999999}`
- velocity-bound entry/exit and sampled duration: `{'value': 1.0, 'unit': 'm/s', 'first_entry_s': None, 'last_entry_s': None, 'first_exit_s': None, 'last_exit_s': None, 'sample_count': 0, 'sampled_occupancy_duration_s': 0.0}`
- final dwell position/velocity/both fractions: `0` / `0` / `0`
- final 5 ms trends: `{'tail_interval_s': [0.015, 0.02], 'tail_sample_count': 51, 'dx_dt_m_s': 56.469402181204586, 'dv_dt_m_s2': -2.2408823949665788e-27, 'd_abs_x_dt_m_s': 56.469402181204586, 'd_abs_v_dt_m_s2': -2.2408823949665788e-27}`
- final Gaussian envelopes: `{'+x_prime': 0.0, '-x_prime': 0.0, '+y_prime': 0.0, '-y_prime': 0.0, '+z': 0.0, '-z': 0.0}`; appreciably illuminated: `False` using threshold `0.001`
- plot: `PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008A_DIAGNOSTIC_AUDIT_ONLY_v_7p5_gamma_over_k.png`

### PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008A_DIAGNOSTIC_AUDIT_ONLY v_9_gamma_over_k

- official outcome and reason: `UNRESOLVED`; only 0/21 dwell samples satisfied the engineering bounds; required fraction is 1
- audit category: `CENTER_CROSSING_WITHOUT_SETTLING`; contributors: `LEFT_BOUNDED_REGION, FORCE_OR_ACCELERATION_NEAR_ZERO`
- final position / velocity: `[1.305292178484379, 0.0, 0.0]` m / `[67.76440218233, 0.0, 0.0]` m/s
- final normalized force: `[-0.0, -0.0, -0.0]`; provisional integrator acceleration: `[-0.0, -0.0, -0.0]` m/s^2 (uncalibrated)
- crossing times: `[0.0007377953370147633]` s; final motion: `{'approaching_or_receding': 'receding', 'speed_trend': 'effectively constant', 'position_magnitude_trend': 'increasing', 'behavior_summary': 'passing through / leaving'}`
- position-bound entry/exit and sampled duration: `{'value': 0.01, 'unit': 'm', 'first_entry_s': 0.0006000000000000001, 'last_entry_s': 0.0006000000000000001, 'first_exit_s': 0.0008000000000000001, 'last_exit_s': 0.0008000000000000001, 'sample_count': 3, 'sampled_occupancy_duration_s': 0.00030000000000000014}`
- velocity-bound entry/exit and sampled duration: `{'value': 1.0, 'unit': 'm/s', 'first_entry_s': None, 'last_entry_s': None, 'first_exit_s': None, 'last_exit_s': None, 'sample_count': 0, 'sampled_occupancy_duration_s': 0.0}`
- final dwell position/velocity/both fractions: `0` / `0` / `0`
- final 5 ms trends: `{'tail_interval_s': [0.015, 0.02], 'tail_sample_count': 51, 'dx_dt_m_s': 67.76440218232914, 'dv_dt_m_s2': -2.2408823949665788e-27, 'd_abs_x_dt_m_s': 67.76440218232914, 'd_abs_v_dt_m_s2': -2.2408823949665788e-27}`
- final Gaussian envelopes: `{'+x_prime': 0.0, '-x_prime': 0.0, '+y_prime': 0.0, '-y_prime': 0.0, '+z': 0.0, '-z': 0.0}`; appreciably illuminated: `False` using threshold `0.001`
- plot: `PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008A_DIAGNOSTIC_AUDIT_ONLY_v_9_gamma_over_k.png`

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008A_DIAGNOSTIC_AUDIT_ONLY Unchanged classifier and cadence audit

- criteria: `{'label': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008A_DIAGNOSTIC_AUDIT_ONLY', 'title': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008A_DIAGNOSTIC_AUDIT_ONLY unchanged classifier criteria', 'position_bound_m': 0.01, 'velocity_bound_m_s': 1.0, 'dwell_window_s': 0.002, 'minimum_dwell_samples': 10, 'required_dwell_fraction': 1.0, 'escape_position_m': 2.0, 'escape_speed_m_s': 100.0, 'simulation_duration_s': 0.02, 'nominal_output_cadence_s': 9.99999999999994e-05, 'expected_inclusive_dwell_samples': 21, 'can_in_principle_satisfy_duration': True, 'can_in_principle_satisfy_sample_minimum': True, 'criteria_modified': False, 'current_criteria_equal_saved_run_008_criteria': True}`
- The 20 ms duration and approximately 0.1 ms output cadence can in principle provide the required 2 ms dwell interval and minimum 10 samples.
- The current unresolved results therefore point primarily to pass-through force/geometry behavior in this provisional model, not insufficient dwell duration, sample count, or numerical cadence. This is an engineering diagnosis, not a physical conclusion.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008A_DIAGNOSTIC_AUDIT_ONLY Run 008 consistency audit

- `{'label': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008A_DIAGNOSTIC_AUDIT_ONLY', 'title': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008A_DIAGNOSTIC_AUDIT_ONLY Run 008 consistency audit', 'initial_position_is_minus_50_mm': True, 'velocity_order_gamma_over_k': [2.0, 4.0, 6.0, 7.5, 9.0], 'velocity_order_exact': True, 'gaussian_mode_active': True, 'handoff_exact_all_cases': True, 'component_4_switch_correct_all_cases': True, 'pre_saturations_exact_all_cases': True, 'post_saturations_exact_all_cases': True, 'track': 'provisional', 'replication_valid': False}`

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_008A_DIAGNOSTIC_AUDIT_ONLY Scope boundary

No initial velocity, duration, classifier criterion, force model, beam geometry, or policy was changed. No capture threshold, boundary search, source distribution, stochastic effect, optimizer, or exact-force path was added.
