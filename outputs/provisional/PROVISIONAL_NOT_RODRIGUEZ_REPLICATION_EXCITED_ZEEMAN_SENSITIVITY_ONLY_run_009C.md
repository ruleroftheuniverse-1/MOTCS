# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_EXCITED_ZEEMAN_SENSITIVITY_ONLY Run 009C

This is a static-only excited-state Zeeman sensitivity study. It runs no trajectory or capture calculation and makes no exact MgF/Rodriguez claim.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_EXCITED_ZEEMAN_SENSITIVITY_ONLY Current collapsed tensor

The pylcp tensor has shape `[3, 4, 4]`, units MHz/G, and basis order `F',mF=[(0, 0), (1, -1), (1, 0), (1, 1)]`. Its Cartesian components are Hermitian and its weak-field spectra are rotationally isotropic. It mixes F'=0 and F'=1, although that mixing does not give the nondegenerate F'=0 state a first-order shift.
The F'=1 result is `g=0.333719898` because the sole active collapsed Astate electronic-spin term projects to `gS/6=0.333719884`.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_EXCITED_ZEEMAN_SENSITIVITY_ONLY Explicit models and weak-field validation

| model | effective g | applied once | Hermitian | slopes match |
|---|---:|---|---|---|
| pylcp_collapsed_default | 0.3337198840603666 | True | True | None |
| zero_excited_zeeman | 0.0 | True | True | True |
| rodriguez_effective_g_0p001 | 0.001 | True | True | True |

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_EXCITED_ZEEMAN_SENSITIVITY_ONLY Static observables

| model | [3] dF/dx | [3] dF/dv | [3+1] dF/dx | [3+1] dF/dv | c4 improves | reversal | health |
|---|---:|---:|---:|---:|---|---|---|
| pylcp_collapsed_default | -0.00894088 | -0.00397668 | -0.152767 | -0.00364237 | True | True | True |
| zero_excited_zeeman | -0.0842032 | -0.00397668 | -0.226353 | -0.00364237 | True | True | True |
| rodriguez_effective_g_0p001 | -0.0839818 | -0.00397668 | -0.226114 | -0.00364237 | True | True | True |

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_EXCITED_ZEEMAN_SENSITIVITY_ONLY Sensitivity classification

Thresholds: <=1% `INSENSITIVE`, <=5% `WEAKLY_SENSITIVE`, larger same-topology changes `MATERIALLY_SENSITIVE`, and sign/classification changes `TOPOLOGY_CHANGING`. Extremum locations use one- and two-grid-step thresholds.
Zero versus g'=0.001 counts: `{'INSENSITIVE': 30, 'WEAKLY_SENSITIVE': 0, 'MATERIALLY_SENSITIVE': 0, 'TOPOLOGY_CHANGING': 0}`. g'=0.001 versus collapsed g~0.334 counts: `{'INSENSITIVE': 21, 'WEAKLY_SENSITIVE': 3, 'MATERIALLY_SENSITIVE': 6, 'TOPOLOGY_CHANGING': 0}`.
At this static scale, g'=0.001 is effectively indistinguishable from zero: `True`. The collapsed tensor materially changes at least one audited observable: `True`.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_EXCITED_ZEEMAN_SENSITIVITY_ONLY Approximation boundary and locks

The `g'=+0.001` value is the representative value used by Rodriguez et al. The direct-sum operator is a paper-aligned effective approximation, not a reconstruction of exact excited-state spectroscopy. The independent Doppelbauer `d` operator and exact F'=0/F'=1 spectroscopy remain unresolved, so Track E remains blocked.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_EXCITED_ZEEMAN_SENSITIVITY_ONLY Final gate: RODRIGUEZ_EFFECTIVE_G_OVERRIDE_JUSTIFIED

**RODRIGUEZ_EFFECTIVE_G_OVERRIDE_JUSTIFIED**

`trajectory_authorized = false`, `capture_authorized = false`, `exact_replication_valid = false`, and `exact_track_blocked = true` regardless of this result.

# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_EXCITED_ZEEMAN_SENSITIVITY_ONLY FINAL_RODRIGUEZ_EFFECTIVE_G_OVERRIDE_JUSTIFIED
