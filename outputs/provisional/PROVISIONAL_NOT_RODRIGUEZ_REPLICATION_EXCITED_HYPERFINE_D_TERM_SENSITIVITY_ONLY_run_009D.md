# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_EXCITED_HYPERFINE_D_TERM_SENSITIVITY_ONLY Run 009D

This is a static-only provisional sensitivity audit. It runs no trajectory or capture calculation and is not an exact MgF/Rodriguez reproduction.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_EXCITED_HYPERFINE_D_TERM_SENSITIVITY_ONLY Current collapsed Astate audit

Basis: `[(0, 0), (1, -1), (1, 0), (1, 1)]`. Matrix shape: `[4, 4]`. Eigenvalues: `[-41.50000198335131, 13.833333994450435, 13.833333994450435, 13.833333994450435]` MHz. Eigenvectors are the corresponding basis unit vectors (up to degenerate-subspace rotations).
The collapsed splitting is `55.333335978 MHz`; it is not source-supported for the positive-parity cooling state. The independent `d=135(7) MHz` term is absent.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_EXCITED_HYPERFINE_D_TERM_SENSITIVITY_ONLY Source boundary

Doppelbauer Eq. (1) defines the independent `d` operator and Table III reports `135 +/- 7 MHz`. The conclusion reports the positive-parity `J'=1/2` hyperfine splitting as less than 1 MHz. Appendix A shows `d`-dependent coupling to `J'=3/2`; therefore the projector model changes energies only and omits eigenvector/transition-strength corrections.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_EXCITED_HYPERFINE_D_TERM_SENSITIVITY_ONLY Projectors and candidate Hamiltonians

Projector validation: `{'basis_order': [[0, 0], [1, -1], [1, 0], [1, 1]], 'shape_f0': [4, 4], 'shape_f1': [4, 4], 'hermitian': True, 'idempotent': True, 'orthogonal': True, 'complete': True, 'dimensions': [1, 3]}`. The F'=0 and F'=1 dimensions are 1 and 3 and are compatible with the direct-sum `g'=0.001` operator.
| candidate | splitting MHz | source family | stress | Hermitian | changes eigenvectors |
|---|---:|---|---|---|---|
| pylcp_collapsed | 55.333336 | False | False | True | False |
| zero_splitting_stress | 0 | False | True | True | False |
| source_mid_range_0p5_mhz | 0.5 | True | False | True | False |
| source_upper_boundary_stress_1_mhz | 1 | True | True | True | False |

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_EXCITED_HYPERFINE_D_TERM_SENSITIVITY_ONLY Static observables

| candidate | [3] dF/dx | [3] dF/dv | [3+1] dF/dx | [3+1] dF/dv | c4 | reversal | health |
|---|---:|---:|---:|---:|---|---|---|
| pylcp_collapsed | -0.0839818 | -0.00397668 | -0.226114 | -0.00364237 | True | True | True |
| zero_splitting_stress | -0.163187 | -0.0063896 | -0.515825 | -0.00547165 | True | True | True |
| source_mid_range_0p5_mhz | -0.162758 | -0.00644235 | -0.512186 | -0.00552434 | True | True | True |
| source_upper_boundary_stress_1_mhz | -0.162285 | -0.00649741 | -0.508593 | -0.00557899 | True | True | True |

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_EXCITED_HYPERFINE_D_TERM_SENSITIVITY_ONLY Whole-surface sensitivity

- `pylcp_collapsed_vs_source_mid_range_0p5_mhz`: **TOPOLOGY_CHANGING**; per-surface maximum absolute, normalized RMS, masked relative, zero-contour, and extremum displacements are recorded in metadata.
- `zero_splitting_stress_vs_source_mid_range_0p5_mhz`: **INSENSITIVE**; per-surface maximum absolute, normalized RMS, masked relative, zero-contour, and extremum displacements are recorded in metadata.
- `source_upper_boundary_stress_1_mhz_vs_source_mid_range_0p5_mhz`: **INSENSITIVE**; per-surface maximum absolute, normalized RMS, masked relative, zero-contour, and extremum displacements are recorded in metadata.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_EXCITED_HYPERFINE_D_TERM_SENSITIVITY_ONLY Answers and authorization

1. The collapsed model produces 55.333335977 MHz and is not supported by the positive-parity spectroscopy constraint.
2. A center-of-gravity-preserving F'-projector model over the reported 0 to <1 MHz interval is defensible as an effective diagonal family, not as a full `d` operator.
3. The sourced `d` term requires J'=3/2 mixing beyond diagonal splitting; a full retained-basis operator was not invented.
4. Source-range sensitivity is `INSENSITIVE`. The collapsed-model comparison is `TOPOLOGY_CHANGING` and may contaminate provisional motion if retained.
5. The preferred Track P family is `SOURCE_ALIGNED_EFFECTIVE_FPRIME_SPLITTING`; the 0.5 MHz midpoint is merely a reproducible interval representative.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_EXCITED_HYPERFINE_D_TERM_SENSITIVITY_ONLY Final gate: PROVISIONAL_TRAJECTORY_FORCE_BACKEND_GO

**PROVISIONAL_TRAJECTORY_FORCE_BACKEND_GO**

`provisional_static_authorized = true`; `provisional_trajectory_authorized = true`; `capture_authorized = false`; `exact_replication_valid = false`; `exact_track_blocked = true`.
This gate, if GO, authorizes reconnecting only the named provisional rate-equation backend to non-capture trajectory plumbing. It does not authorize capture thresholds or replication claims.

# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_EXCITED_HYPERFINE_D_TERM_SENSITIVITY_ONLY FINAL_PROVISIONAL_TRAJECTORY_FORCE_BACKEND_GO
