# Run 011D complex-number fidelity audit

`PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011D_COMPLEX_NUMBER_FIDELITY_AUDIT_ONLY`

Run 011D is a read-only Track P diagnostic. It does not alter the accepted
Hamiltonian, dipoles, branching, force-field caches, or trajectory results. It
does not make Track E force-ready.

## Question and method

The audit asks whether the `ComplexWarning` emitted by pylcp 1.0.2 discards
physical phase information. It promotes the warning to an exception locally,
records its complete traceback, reconstructs the expression immediately before
the cast, and follows complex dtype and imaginary content from source matrices
through final force observables.

The diagnostic evaluator in `complex_fidelity_reference.py` keeps Hamiltonians,
magnetic tensors, eigenvectors, dipoles, polarizations, and coherent coupling
amplitudes complex. It rotates dipoles with a conjugate transpose and takes a
modulus squared only after the spherical coupling amplitudes have been summed.
Pumping, population, scattering, and force results are required to be real
within tolerance.

To isolate complex-number handling, the evaluator deliberately follows pylcp's
`numpy.linalg.eig` eigenvector convention. A Hermitian `eigh` call can select a
different arbitrary rotation within an exactly degenerate manifold; a
population-only rate model that omits coherences need not be invariant to that
rotation. This convention lock is separate from the tested diagonal-unitary
basis rephasings.

## Findings

- Every audited warning originates at installed `pylcp/rateeq.py:264` in
  `_calc_pumping_rates`, where a complex-typed `(12, 4)` pumping-rate expression
  is assigned to a float array.
- The warning-producing object is downstream of the coherent amplitude's
  modulus squared. Its measured imaginary content is exactly zero in the
  audited [3] and [3+1] cases; the complex dtype is propagated by a zero-
  imaginary excited-energy container.
- Circular-polarization and coupling amplitudes retain finite imaginary parts
  before modulus squared. All six beam polarizations are normalized and
  transverse.
- Accepted pylcp, the Run 011C independent paper-equation evaluator, and the
  complex-preserving evaluator agree to strict numerical tolerance at origin,
  sign-slope points, extrema, component-(4)-sensitive points, the dark region,
  and a strong-cancellation point.
- Sign, `+/-i`, and deterministic pseudorandom diagonal rephasings leave
  populations, scattering, force, and local slopes invariant below `1e-12`.
- pylcp's use of plain transpose is a latent limitation for a genuinely complex
  eigenbasis, but the accepted matrices and transforms are real to relevant
  precision. Replacing only that operation with conjugate transpose does not
  change current observables.
- Preserving complex amplitudes does not restore the paper's stated component
  (4) hierarchy and does not alter the Run 011C dark-state/cancellation result.

The warning disposition is `WARNING_IS_NUMERICAL_ROUNDOFF`. The final Run 011D
gate is `COMPLEX_FIDELITY_RULED_OUT`. The remaining leading candidates are the
unavailable paper excited-state eigenvectors, dipole tensor, or other private
molecular-matrix details; spontaneous branching remains unresolved.

Detailed machine-readable ledgers are quarantined under
`outputs/provisional/molecular_model_audit/run_011d/`. No warning is globally
suppressed. Capture, capture velocity, optimization, and exact replication
remain unauthorized; Track E remains blocked.
