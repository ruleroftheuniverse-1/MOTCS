# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011C_PLANE_WAVE_MOLECULAR_MODEL_DIFFERENTIAL_AUDIT_ONLY

Run 011C is a static, plane-wave, read-only differential audit. It does not alter the accepted backend, rebuild a cache, integrate a trajectory, fit a paper figure, or authorize capture.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011C_PLANE_WAVE_MOLECULAR_MODEL_DIFFERENTIAL_AUDIT_ONLY Figure 2 sign calibration

`FIGURE_SIGN_CALIBRATION_VALIDATED`. Pixel x points right and physical x increases right; pixel y points down while physical v increases upward. Both colorbars run from positive yellow/green at the top to negative blue/purple at the bottom. Independent anchors reproduce the Run 011B sign without reading its calibration metadata.

The robust rendered local slopes are `-0.001108` for [3] and `0.0021175` for [3+1]. Figure 2(c)'s positive local slope is therefore not a global digitization inversion. White paths obscure pixels, and the paper's confinement statements concern complete trajectories; neither supports silently reversing the colorbar.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011C_PLANE_WAVE_MOLECULAR_MODEL_DIFFERENTIAL_AUDIT_ONLY Independent paper-equation reproduction

The reference evaluator implements Rodriguez Eqs. (1)-(5) directly and never calls `pylcp.rateeq` or the accepted backend force method. It diagonalizes the supplied manifolds, rotates the supplied dipole tensor, constructs optical and spontaneous rates, solves one combined 16-state equilibrium matrix, and computes every beam/component contribution from that shared population vector.

Across deterministic [3] and [3+1] points, maximum force difference is `4.337e-17`, maximum population difference is `1.381e-15`, and maximum per-laser total pumping-rate difference is `5.551e-17`. State-indexed pumping matrices at exactly zero field are compared only with an explicit degenerate-basis gauge warning. The local wrapper/API use is reproduced.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011C_PLANE_WAVE_MOLECULAR_MODEL_DIFFERENTIAL_AUDIT_ONLY Molecular matrices and identities

The complete accepted 12+4 zero-field, magnetic, dipole, branching, strength, and basis-transform objects are exported in `PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011C_PLANE_WAVE_MOLECULAR_MODEL_DIFFERENTIAL_AUDIT_ONLY_accepted_molecular_matrices.npz` with units and basis metadata. Hamiltonian/vector Hermiticity, `(3,12,4)` shape, branching normalization, polarization completeness, ground/excited strength sums, transformation unitarity, and basis-rephasing invariance pass. No incompatible one-sided basis transform was found.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011C_PLANE_WAVE_MOLECULAR_MODEL_DIFFERENTIAL_AUDIT_ONLY Component 4 and dark-state mechanism

The accepted [3+1] calculation has a restoring local slope `-0.0038437`, unlike the rendered Figure 2(c) slope. Enabling component (4) strengthens confinement relative to the same [3+1] saturation vector with it disabled. However, the shared-solution decomposition does not reproduce the paper's stated level hierarchy: the accepted upper-F=1 and F2 component-(4) terms are both restoring, with upper-F=1 larger. With component (4) alone, weak off-resonant coupling makes the solve unique but the upper-F=1 and F2 terms nearly cancel with the opposite nominal hierarchy. Population redistribution also changes components (1)-(3). This is direct evidence for a level-specific molecular-matrix mismatch, not a wrapper error.

As |x| grows from 0 to 6 normalized units in [3], the accepted force falls to `0.144` of its central value while scattering falls to `0.429`. Population accumulates in weakly coupled states and counterpropagating dominance gives way to stronger copropagating cancellation. Zeeman shifts, populated states, and beam fractions are tabulated at every point. This diagnoses the accepted model's early force loss, but cannot decide whether the paper differs through strengths, Zeeman matrices, eigenvectors, or branching without its matrices.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011C_PLANE_WAVE_MOLECULAR_MODEL_DIFFERENTIAL_AUDIT_ONLY Paper quantitative statements

| quantity | paper rough value | accepted value | classification |
|---|---:|---:|---|
| scattering rate | 0.125 Gamma | 0.1350 Gamma | MATCHES_WITHIN_DIGITIZATION_OR_TEXT_PRECISION |
| force magnitude | 0.05 hbar k Gamma | 0.0671 | WEAKLY_DIFFERENT |
| +/-z scattering fraction | 0.30 | 0.182 | MATCHES_WITHIN_DIGITIZATION_OR_TEXT_PRECISION |
| copropagating scattering fraction | 0.10 | 0.058 | MATCHES_WITHIN_DIGITIZATION_OR_TEXT_PRECISION |

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011C_PLANE_WAVE_MOLECULAR_MODEL_DIFFERENTIAL_AUDIT_ONLY pylcp history

The installed `pylcp 1.0.2` `rateeq.py`, `fields.py`, `hamiltonian.py`, and `hamiltonians/XFmolecules.py` are byte-identical to official tag `v1.0.2` (`a7cb104f...`, 2022-06-23), the latest official commit before the paper date. Official master through `53885b54...` contains no changes to those audited files. The paper's exact checkout is not published, so private modifications cannot be excluded.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011C_PLANE_WAVE_MOLECULAR_MODEL_DIFFERENTIAL_AUDIT_ONLY Splitting versus eigenvectors

Run 009D's insensitivity to a 0-1 MHz diagonal F'=0/F'=1 splitting does not test eigenvector changes, d-driven J'=1/2 to J'=3/2 mixing, altered dipoles, or omitted-state coupling. Run 011C does not invent the missing independent Doppelbauer d operator.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011C_PLANE_WAVE_MOLECULAR_MODEL_DIFFERENTIAL_AUDIT_ONLY Diagnosis ranking

Demonstrated local causes: none. Ruled out by this audit: global figure-sign inversion, rate-equation wrapper mismatch, released-pylcp version drift, and a local one-sided basis transform. The leading unresolved contributors are unpublished paper-specific matrices, excited-hyperfine eigenvectors/J mixing, the resulting dipole tensor, and downstream dark-state population differences. Exact excited Zeeman physics remains a secondary blocker.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011C_PLANE_WAVE_MOLECULAR_MODEL_DIFFERENTIAL_AUDIT_ONLY Final gate: MOLECULAR_MODEL_DISCREPANCY_NARROWED

**MOLECULAR_MODEL_DISCREPANCY_NARROWED**

The supplied local matrices are evaluated consistently by two independent equation paths, but the paper discrepancy cannot be assigned uniquely between excited eigenvectors and transition dipoles without the full d operator or paper-specific matrices.

`capture_authorized = false`; `capture_velocity_authorized = false`; `optimizer_authorized = false`; `exact_replication_valid = false`; Track E remains blocked.

# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011C_PLANE_WAVE_MOLECULAR_MODEL_DIFFERENTIAL_AUDIT_ONLY FINAL_MOLECULAR_MODEL_DISCREPANCY_NARROWED
