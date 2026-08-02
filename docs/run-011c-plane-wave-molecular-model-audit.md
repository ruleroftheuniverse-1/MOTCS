# PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011C_PLANE_WAVE_MOLECULAR_MODEL_DIFFERENTIAL_AUDIT_ONLY

Run 011C is a static, plane-wave, read-only audit of the molecular objects underneath the Run 011B force-shape discrepancy. It does not change the accepted backend, spectroscopy, dipoles, branching, Gaussian geometry, caches, or trajectories.

The executable audit is [audit_plane_wave_molecular_model.py](../scripts/audit_plane_wave_molecular_model.py). The independent equation implementation is [paper_rateeq_reference.py](../src/mgf_mot/paper_rateeq_reference.py). All output is quarantined under `outputs/provisional/molecular_model_audit/run_011c/` and carries the full provisional warning label.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011C_PLANE_WAVE_MOLECULAR_MODEL_DIFFERENTIAL_AUDIT_ONLY Figure 2 calibration

The independent calibration file [rodriguez_figure2_sign_calibration_run_011c.yaml](../configs/rodriguez_figure2_sign_calibration_run_011c.yaml) specifies its own three-point x, velocity, and colorbar anchors. It does not read Run 011B calibration metadata.

`FIGURE_SIGN_CALIBRATION_VALIDATED`

Pixel x increases to the right and physical x increases to the right. Pixel y increases downward while physical velocity increases upward. Both MgF colorbars place positive force at the top and negative force at the bottom. Reversing neither axis nor colorbar is justified. Robust samples give a negative `[3]` local spatial slope and a positive rendered `[3+1]` slope. The latter therefore is not a global image-extraction inversion. White trajectory overlays obscure local pixels, and the paper's statement about overall confinement is not itself a local `v=0` sign calibration.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011C_PLANE_WAVE_MOLECULAR_MODEL_DIFFERENTIAL_AUDIT_ONLY independent equations

The reference evaluator implements Rodriguez Eqs. (1)–(5) without constructing or calling `pylcp.rateeq` and without calling the accepted backend force method. Given the accepted matrices and beams, it:

1. diagonalizes ground and excited manifolds in the local magnetic field;
2. rotates the supplied dipole tensor consistently;
3. constructs every laser/component pumping matrix;
4. constructs spontaneous decay and branching;
5. solves one combined 16-state equilibrium matrix;
6. obtains every beam/component force from that same population vector.

Across the deterministic `[3]` and `[3+1]` points, its maximum differences from the accepted pylcp calculation are approximately `4.3e-17` in normalized force, `1.4e-15` in population, and `5.6e-17` in total pumping rate per physical laser. State-indexed pumping matrices at exactly zero field are basis-gauge dependent inside degenerate manifolds; invariant totals, populations, residuals, and forces are compared there.

This rules out a local rate-equation wrapper or force-algebra mismatch for the supplied matrices.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011C_PLANE_WAVE_MOLECULAR_MODEL_DIFFERENTIAL_AUDIT_ONLY matrix package

The audit exports the complete accepted objects:

- ground and excited zero-field Hamiltonians;
- ground and excited spherical magnetic tensors;
- ground bare-to-eigen and excited effective-basis transforms;
- complex `q=(-1,0,+1)` dipoles and squared strengths;
- spontaneous branching probabilities;
- basis labels, approximate `F,m_F` assignments, weak-field slopes, hashes, and units;
- a ledger of every nonzero transition and its intended components.

Hamiltonian and spherical-vector Hermiticity, `(3,12,4)` dipole shape, branching column sums, polarization-complete strengths, excited-state decay-strength sums, transform unitarity, and basis-rephasing invariance pass. No object was found transformed on only one side of an incompatible basis boundary.

These are internal consistency tests. They cannot prove equality to unpublished Rodriguez input matrices.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011C_PLANE_WAVE_MOLECULAR_MODEL_DIFFERENTIAL_AUDIT_ONLY component 4

The accepted backend itself has a restoring `[3+1]` small-signal slope and component `(4)` strengthens it relative to the same `[3+1]` saturation vector with component `(4)` disabled. This confirms that Run 011B's accepted-model slope was wired consistently.

The level-resolved mechanism does not reproduce the hierarchy stated in the paper. In the full accepted `[3+1]` shared solution, the upper-`F=1` and `F=2` component-(4) terms are both restoring and the upper-`F=1` magnitude is larger. With component `(4)` alone, weak off-resonant coupling makes the equilibrium solve unique, but upper-`F=1` and `F=2` nearly cancel with upper-`F=1` restoring and `F=2` anti-restoring. The paper describes the opposite polarization suitability. Enabling component `(4)` also redistributes populations and changes forces arising from components `(1)`–`(3)`.

This is evidence for a level-specific molecular-matrix difference—most directly a dipole/eigenvector/Zeeman combination—not a rate-equation summation error. It does not by itself identify which unpublished paper matrix differs.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011C_PLANE_WAVE_MOLECULAR_MODEL_DIFFERENTIAL_AUDIT_ONLY paper checks and pylcp history

At `x=0`, `v=sqrt(2) Gamma/k`, the accepted model gives a scattering rate near `0.135 Gamma`, force magnitude near `0.067 hbar*k*Gamma`, about `18%` of scattering from the `±z` beams, and about `5.8%` from copropagating beams. Against the paper's rough `0.125`, `0.05`, `30%`, and `10%` statements, the scattering and beam fractions are within the deliberately broad text precision while force magnitude is weakly different. These classifications are not fitting targets.

The official [pylcp repository](https://github.com/JQIamo/pylcp) tag [`v1.0.2`](https://github.com/JQIamo/pylcp/tree/v1.0.2), commit `a7cb104f38fa98840ec198d13ec20c432e8ee3ff` dated 2022-06-23, was the latest official commit before the 2023 paper date. The installed `rateeq.py`, `fields.py`, `hamiltonian.py`, and `hamiltonians/XFmolecules.py` match that tag. Official master through commit `53885b54b9b81ee63415bb25236d8aecd875db57` contains no changes to these four files. The exact paper checkout and any private matrices are not published, so private changes cannot be excluded.

Run 009D's weak sensitivity to a diagonal `0–1 MHz` splitting does not test excited-state eigenvectors, d-driven `J'=1/2`–`J'=3/2` mixing, altered transition dipoles, or coupling through omitted states. Run 011C does not invent the missing independent Doppelbauer `d` operator.

## PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_RUN_011C_PLANE_WAVE_MOLECULAR_MODEL_DIFFERENTIAL_AUDIT_ONLY diagnosis and gate

Ruled out here are a global Figure 2 sign-calibration error, local rate-equation wrapper mismatch, released-pylcp version drift, and a one-sided local basis transformation. The leading unresolved contributors are unpublished paper-specific matrices, the accepted-versus-paper dipole tensor, missing excited-hyperfine eigenvector/J mixing, level-specific magnetic matrices, and their downstream dark-state populations.

`MOLECULAR_MODEL_DISCREPANCY_NARROWED`

The discrepancy is narrowed to level-specific molecular matrix content, but cannot yet be uniquely separated between dipoles, eigenvectors, and magnetic operators.

`capture_authorized = false`; `capture_velocity_authorized = false`; `optimizer_authorized = false`; `exact_replication_valid = false`; Track E remains blocked.
