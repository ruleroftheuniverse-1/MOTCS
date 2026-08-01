# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_PYLCP_RATEEQ_STATIC_VALIDATION_ONLY Run 009

This static validation uses pylcp rate equations with the explicitly requested collapsed excited-state approximation. It is not exact and is not Rodriguez-valid.
The force calculation now uses one combined equilibrium-population rate-equation solve rather than the toy heuristic.
Exact Track E remains blocked. No trajectory was rerun, no capture result was calculated, and no agreement with Rodriguez is claimed.
All force-dependent Run 001-008 outcomes remain physically uninterpretable; their historical files were not changed.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_PYLCP_RATEEQ_STATIC_VALIDATION_ONLY Backend and units

- backend: `{'label': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_PYLCP_RATEEQ_STATIC_VALIDATION_ONLY', 'title': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_PYLCP_RATEEQ_STATIC_VALIDATION_ONLY backend status', 'track': 'provisional', 'backend_mode': 'pylcp_rate_equation', 'approximation_mode': 'collapsed_pylcp_astate', 'force_model': 'pylcp_rate_equation_combined_equilibrium_populations', 'physics_valid': True, 'physics_scope': 'static provisional rate-equation validation only', 'static_force_ready': True, 'trajectory_force_ready': False, 'replication_valid': False, 'force_unit': 'hbar*k*Gamma', 'warnings': ['PROVISIONAL backend: engineering/plumbing artifact only.', 'NOT_RODRIGUEZ_REPLICATION: exact excited-state d operator and Zeeman mappings are unresolved.', 'No approximate force output from this backend is force-ready by default.', 'PYLCP_RATEEQ_STATIC_VALIDATION_ONLY: no trajectories or capture result.', 'Helicity strings are interpreted relative to each beam k-vector using pylcp pol=+1/-1.', 'Component carrier offsets use the upper collapsed excited level and explicit addressed-role ground energies.'], 'omitted_terms': ['ground_fluorine_nuclear_g_factor', 'excited_hyperfine_d operator', 'excited_backend_gL', 'excited_backend_gl', 'excited_backend_glprime', 'excited_backend_gr', 'excited_backend_greprime', 'excited_backend_gN'], 'collapsed_terms': ['excited_b_F_plus_2c_over_3 -> pylcp Astate b+c/3 with c=0', 'excited_p_plus_2q -> pylcp Astate p with q=0'], 'supersedes_run_outputs': 'Run 008B supersedes physical interpretation of force-dependent Runs 001-008'}`
- force conversions: `{'label': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_PYLCP_RATEEQ_STATIC_VALIDATION_ONLY', 'title': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_PYLCP_RATEEQ_STATIC_VALIDATION_ONLY explicit force-unit conversions', 'force_unit': 'hbar*k*Gamma', 'normalized_examples': [0.01, 0.015, 0.03, 1.0], 'newtons': [2.4217257880128608e-21, 3.6325886820192916e-21, 7.265177364038583e-21, 2.421725788012861e-19], 'accelerations_m_s2': [33929.280470171885, 50893.920705257835, 101787.84141051567, 3392928.0470171887], 'round_trip_normalized': [0.009999999999999998, 0.015000000000000001, 0.030000000000000002, 1.0], 'normalized_force_conversion_count': 0, 'si_acceleration_conversion_count': 1}`

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_PYLCP_RATEEQ_STATIC_VALIDATION_ONLY Static topology and scale

| case | lasers | dF/dx | dF/dv | position | velocity | min | max | scale vs 0.03 / 0.015 |
|---|---:|---:|---:|---|---|---:|---:|---|
| plane_wave_3 | 18 | 0.172096 | -0.00402511 | anti-restoring | damping | -0.0365266 | 0.0365266 | comparable order / comparable order |
| plane_wave_3_plus_1 | 24 | 0.307137 | -0.00369145 | anti-restoring | damping | -0.0336547 | 0.0336547 | comparable order / comparable order |
| gaussian_3 | 18 | 0.170072 | -0.00402511 | anti-restoring | damping | -0.0365266 | 0.0365266 | comparable order / comparable order |
| gaussian_3_plus_1 | 24 | 0.303678 | -0.00369145 | anti-restoring | damping | -0.0336547 | 0.0336547 | comparable order / comparable order |
| gaussian_chirp_minus_8_gamma | 18 | 0.000511823 | 0.00057825 | anti-restoring | anti-damping | -0.00213952 | 0.00213952 | substantially smaller / comparable order |
| gaussian_chirp_minus_4p5_gamma | 18 | -0.04435 | 0.000230622 | restoring | anti-damping | -0.0017199 | 0.0017199 | substantially smaller / comparable order |
| gaussian_chirp_minus_1_gamma | 18 | 0.170072 | -0.00402511 | anti-restoring | damping | -0.0365266 | 0.0365266 | comparable order / comparable order |

Force-scale comparisons are descriptive order-of-magnitude labels only; they do not assert reproduction, validation, or disagreement.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_PYLCP_RATEEQ_STATIC_VALIDATION_ONLY Required behavior checks

- `{'label': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_PYLCP_RATEEQ_STATIC_VALIDATION_ONLY', 'title': 'PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_PYLCP_RATEEQ_STATIC_VALIDATION_ONLY required behavior comparisons', 'three_vs_three_plus_one_different': True, 'component_4_changes_optical_system': True, 'chirp_minus_8_vs_minus_4p5_different': True, 'chirp_minus_4p5_vs_minus_1_different': True, 'plane_gaussian_three_agree_at_origin': True, 'plane_gaussian_three_differ_away': True, 'origin_symmetry_all_cases': True, 'chirp_extrema_locations': {'gaussian_chirp_minus_8_gamma': {'maximum': {'x_m': 0.0, 'vx_m_s': -15.06}, 'minimum': {'x_m': 0.0, 'vx_m_s': 15.06}}, 'gaussian_chirp_minus_4p5_gamma': {'maximum': {'x_m': 0.0, 'vx_m_s': 9.4125}, 'minimum': {'x_m': 0.0, 'vx_m_s': -9.412500000000001}}, 'gaussian_chirp_minus_1_gamma': {'maximum': {'x_m': 0.0, 'vx_m_s': -9.412500000000001}, 'minimum': {'x_m': 0.0, 'vx_m_s': 9.4125}}}, 'chirp_topology_changed': True}`
- Frozen chirp topology is labeled changed when its force arrays differ; extrema locations are reported above without physical interpretation.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_PYLCP_RATEEQ_STATIC_VALIDATION_ONLY Combined populations and contributions

All active lasers enter one pylcp evolution matrix. The SVD equilibrium population is then used for total and per-laser forces. Per-beam and per-component entries in metadata are groupings of those contributions, not sums of independently solved systems.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_PYLCP_RATEEQ_STATIC_VALIDATION_ONLY Gaussian application

Each physical beam supplies its own elliptical envelope callable. That envelope multiplies each of the beam's active component saturations before pylcp constructs and sums pumping rates. No mean, weakest-beam, post-summation, or squared-saturation adapter is used.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_PYLCP_RATEEQ_STATIC_VALIDATION_ONLY Scope boundary

No trajectory integration, capture result, source distribution, stochastic recoil, optimizer, or exact-force path was added. The collapsed d-term and Zeeman limitations remain explicit.
