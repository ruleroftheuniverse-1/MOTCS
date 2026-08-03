# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011D_COMPLEX_NUMBER_FIDELITY_AUDIT_ONLY

Run 011D is a read-only diagnostic. It does not change accepted matrices, pylcp source, force caches, trajectories, or physics configuration, and it does not suppress warnings globally.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011D_COMPLEX_NUMBER_FIDELITY_AUDIT_ONLY Warning capture and disposition

`WARNING_IS_NUMERICAL_ROUNDOFF`

Warnings promoted to exceptions localize every audited instance to installed `pylcp/rateeq.py`, line 264, in `_calc_pumping_rates`. A complex128 pumping-rate expression is assigned to a float64 `Rijl` slice of shape `(12,4)`. The expression is complex-typed because the otherwise-real diagonal energies live in complex containers.

Maximum discarded imaginary content across audited [3] and [3+1] lasers is `0.000e+00`. The warned object is already a rate after the coherent dipole-polarization amplitude has been modulus-squared. Genuine circular-polarization and spherical-amplitude phases, as large as order unity, remain upstream and are not discarded by this cast.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011D_COMPLEX_NUMBER_FIDELITY_AUDIT_ONLY End-to-end complex path

The complex-fidelity evaluator retains complex Hamiltonians, magnetic tensors, eigenvectors, dipoles, spherical polarizations, and coherent coupling amplitudes. It uses `U† d U`; only Hermitian eigenvalues, modulus-squared rates, population probabilities, scattering, and force are required to become real. Final observable imaginary residuals are below tolerance.

Across origin, ±dx, ±dv, both configurations' extrema, component-(4)-sensitive points, a dark region, and strong cancellation, the maximum accepted-versus-complex force difference is `4.163e-17`, per-laser scattering difference `4.857e-17`, grouped-population difference `1.221e-15`, and total-scattering difference `1.249e-16`.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011D_COMPLEX_NUMBER_FIDELITY_AUDIT_ONLY Basis conjugation and phase invariance

The complex reference uses conjugate transpose and all signs-only, ±i, and deterministic pseudorandom rephasings preserve populations, per-beam scattering, total scattering, force, and slopes below `1e-12`: `True`.

The local static MgF dipole construction uses `.T` on a real source transform, while pylcp 1.0.2's dynamic rotation also uses `.T`. Plain transpose is not generally correct for complex eigenvectors; this is a latent general-complex basis limitation. For the current accepted real-basis matrices, however, the conjugate-transpose force result is numerically identical, so it does not explain the Rodriguez discrepancy.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011D_COMPLEX_NUMBER_FIDELITY_AUDIT_ONLY Spherical polarization

All six beam directions have normalized, transverse Cartesian and spherical polarizations with explicitly recorded real and imaginary components and helicity. Couplings coherently sum all q amplitudes before modulus-squared. No cast removes circular-polarization phase before rate construction.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011D_COMPLEX_NUMBER_FIDELITY_AUDIT_ONLY Component 4 and dark states

The complex path leaves the component-(4) result unchanged. The accepted paper hierarchy is reproduced: `False`; the Run 011C conclusion changes: `False`. Upper-F=1/F2 terms, population redistribution, counterpropagating force, copropagating force, and slopes are recorded for [3], [3+1], component-(4)-disabled, and component-(4)-alone systems.

At `x=6`, `v=sqrt(2) Gamma/k`, accepted and complex-preserving grouped populations, beam scattering, force cancellation, weak-state indices, and dominant complex amplitudes agree. Premature real casting does not strengthen the accepted dark-state formation or cancellation.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011D_COMPLEX_NUMBER_FIDELITY_AUDIT_ONLY Diagnosis update

Demonstrated: the pylcp complex-container-to-real-rate warning and a latent non-general `.T` basis-rotation expression. Ruled out as causes of the current force discrepancy: complex cast/phase loss, basis conjugation for the actual accepted real matrices, spherical-polarization complexity, and rate-equation wrapper use. Excited eigenvectors, dipoles, and unpublished paper matrices remain the leading candidates; paper branching remains unresolved.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011D_COMPLEX_NUMBER_FIDELITY_AUDIT_ONLY Final gate: COMPLEX_FIDELITY_RULED_OUT

**COMPLEX_FIDELITY_RULED_OUT**

The warning does not discard a physical amplitude, the correct complex path is phase invariant and agrees with accepted observables, and the component-(4)/dark-state discrepancies persist.

`capture_authorized = false`; `capture_velocity_authorized = false`; `optimizer_authorized = false`; `exact_replication_valid = false`; Track E remains blocked.

COMPLEX_FIDELITY_RULED_OUT
