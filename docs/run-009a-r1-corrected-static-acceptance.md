# Run 009A-R1 corrected static acceptance audit

`PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_009A_R1_CORRECTED_GROUND_ZEEMAN_RATEEQ_STATIC_ACCEPTANCE_AUDIT_ONLY`
is the historical-preserving rerun of the Run 009A static acceptance audit.

The rerun constructs a new provisional pylcp rate-equation backend using
`GroundZeemanConvention.PROJECT_ENERGY_SLOPE_CORRECTED`. The raw ground-state
magnetic-moment tensor is negated exactly once while constructing the pylcp
Hamiltonian. No force result is negated downstream. The source YAML paper
labels, direct beam-relative polarization translation, quadrupole field, beam
directions, dipole tensor, and provisional excited-state tensor are unchanged.

## Provenance chain

The R1 metadata stores SHA-256 hashes for the original Run 009 arrays, metadata,
and report; the original Run 009A NO-GO metadata, report, and diagnostic plot;
and the Run 009B reconciliation metadata and report. The hashes are recorded
before and after R1. Source Rodriguez YAML hashes are handled the same way.
Corrected arrays, metadata, and plots have new fully labeled filenames.

The original anti-restoring arrays remain historical diagnostics. They are
superseded only for provisional engineering use and are never overwritten.

## Audit scope

R1 regenerates seven static surfaces: plane-wave and elliptical-Gaussian `[3]`
and `[3+1]`, plus Gaussian `[3]` snapshots at `-8 Gamma`, `-4.5 Gamma`, and
`-1 Gamma`. It audits every regenerated grid point for population and SVD
health, lab-x geometry, local finite-difference sensitivity, component `(4)`
ablation, the four-case reversal matrix, chirp extrema, force units, Gaussian
application, and 2x slice refinement.

Topology preservation and quantitative slope convergence are reported
separately. A refined slice can retain restoring/damping topology while still
carrying a warning that a coarse numerical slope changed by more than the
historical 25% screen.

## Mandatory lock

Even a `PROVISIONAL_STATIC_GO` authorizes only further provisional static
study. It never authorizes a trajectory or capture calculation. Metadata fixes
`trajectory_authorized`, `capture_authorized`, and `exact_replication_valid` to
false because the excited-state magnetic tensor is unresolved: the collapsed
provisional tensor gives effective `g` approximately `0.334`, whereas the
Rodriguez representative treatment uses `g = 0.001`. Track E remains blocked.
