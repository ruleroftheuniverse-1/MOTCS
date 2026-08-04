# MgF Chirped-MOT Simulation and Control

This repository is an independent reproduction and extension of the frequency-chirped MgF magneto-optical-trap simulations developed by Rodriguez *et al.*

The project has two goals:

1. reproduce the paper’s force maps and trajectory behavior with an inspectable, source-tagged simulation;
2. once the baseline is reproduced, compare the paper’s linear frequency chirp with apparatus-constrained alternatives such as piecewise, spline, Fourier, feedback-derived, and optimizer-designed policies.

The repository is split into:

- **Track E -- exact reproduction**
- **Track P -- provisional modeling**

Track P uses explicit approximations and strict provenance. No provisional result is presented as an exact reproduction of Rodriguez *et al.*

---

## Current result

The rate-equation machinery has been reproduced successfully.

The published force structure has not.

The project now independently reproduces:

- the paper’s equilibrium rate equations;
- official `pylcp` `v1.0.2` behavior;
- polarization, detuning, linewidth, and saturation conventions;
- Gaussian beam geometry;
- force interpolation;
- event-aware trajectory integration;
- complex-number and basis-phase handling.

The independent paper-equation evaluator and pylcp agree to numerical precision.

However, the accepted provisional molecular model produces force surfaces that differ materially from Figures 2 and 3 of Rodriguez *et al.* The differences include:

- plane-wave force structure;
- force magnitude;
- spatial width;
- positive-force topology;
- level-resolved behavior of component `(4)`.

The discrepancy has been localized to the molecular-model objects supplied to the rate equations, most likely one or more of:

- the excited-state Hamiltonian and eigenvectors;
- magnetic tensors;
- transition dipole tensor;
- branching structure;
- basis ordering or transformations;
- effects of the full independent Doppelbauer `d` operator.

The project now has a versioned molecular-model interchange format that can import, validate, compare, and benchmark an author-provided model immediately.

A precise request for the original molecular matrices or their construction code has been sent to the paper’s authors.

---

## Status

| Capability | Status |
|---|---|
| Source-tagged MgF ground-state structure | Validated |
| Retained 12-ground / 4-excited basis | Validated |
| Dipole tensor shape `(3, 12, 4)` | Validated |
| pylcp polarization and force conventions | Validated |
| Ground magnetic-moment convention | Corrected and validated |
| Rodriguez effective excited `g′ = 0.001` | Implemented and validated |
| Source-aligned effective excited splitting | Implemented provisionally |
| Independent paper-equation evaluator | Validated |
| Complex and basis-phase fidelity | Validated |
| Static Track P force calculations | Authorized |
| Interpolated Track P force fields | Validated |
| Named provisional trajectories | Authorized |
| Paper force-map agreement | Failed |
| Molecular-model interchange | Ready |
| Control-policy ABI v2 | Validated |
| Apparatus schedule compiler | Validated on synthetic/source-incomplete profiles; not real hardware |
| Open-loop policy families | Validated structurally; no physical ranking |
| Feedback and exact replay | Validated on synthetic fixtures; not physically evaluated |
| Experiment/trial/checkpoint/replay protocol | Ready for model-independent and synthetic evaluation |
| Reproducible infrastructure release | Run 018 release manifest and integrity workflow |
| Author-model import | Awaiting source data |
| Capture-velocity calculation | Not authorized |
| Capture-boundary search | Not authorized |
| Chirp optimization | Not authorized |
| Exact Rodriguez reproduction | Blocked |

Current test status:

```text
326 passed
```

This count is verified with `python -m pytest -q` and recorded by the Run 018 release audit.

One known `pylcp` `ComplexWarning` remains visible. It was audited in Run 011D: the cast occurs after modulus-squared coupling, and the discarded imaginary component is exactly zero.

The current short status is [docs/current-project-status.md](docs/current-project-status.md); the complete history is [docs/run-index.md](docs/run-index.md).

---

## Scientific tracks

### Track E -- exact reproduction

Track E aims to reproduce the molecular model and results used by Rodriguez *et al.*

It remains blocked by unavailable molecular-model details, especially:

* the full independent Doppelbauer hyperfine `d` operator;
* coupling to states outside the retained four-state excited basis;
* exact excited-state eigenvectors and line positions;
* the precise Hamiltonian, magnetic, and dipole tensors used for the paper;
* the exact private pylcp checkout or molecular construction code.

Track E does not silently fall back to provisional physics.

The smallest useful author-provided payload would contain:

* ground zero-field Hamiltonian `H0_g`;
* ground magnetic tensor `μq_g`;
* excited zero-field Hamiltonian `H0_e`;
* excited magnetic tensor `μq_e`;
* transition tensor `d_q`;
* basis labels and ordering;
* units and spherical-component ordering;
* pylcp commit or checkout identifier.

A construction script or serialized pylcp Hamiltonian object would also suffice.

See:

```text
docs/author-request-molecular-model-package.md
docs/molecular-model-interchange.md
```

### Track P -- provisional modeling

Track P uses source-aligned effective approximations for controlled engineering studies.

Every Track P artifact is labeled:

```text
PROVISIONAL
NOT_RODRIGUEZ_REPLICATION
```

Track P currently authorizes:

* static rate-equation calculations;
* force-map and sensitivity studies;
* finite Gaussian beam modeling;
* force-field interpolation;
* named non-capture trajectories;
* molecular-model package export and comparison;
* model-independent control-policy infrastructure.

Track P does not authorize:

* a reported capture velocity;
* capture-boundary interpolation;
* source-distribution claims;
* stochastic loading predictions;
* optimized chirp claims;
* exact-reproduction claims.

The accepted Track P physics is frozen pending either:

* receipt of the paper molecular model; or
* new source-supported molecular information.

---

## Accepted provisional molecular model

### Basis

The retained model contains:

* `12` ground states;
* `4` excited states;
* dipole tensor shape `(3, 12, 4)`.

Ground-state spacings are:

```text
109.732 MHz
120.327 MHz
9.268 MHz
```

### Ground-state Zeeman convention

The raw `pylcp.XFmolecules.Xstate` magnetic-moment tensor produced weak-field energy slopes opposite the source-tagged MgF g-factors under:

```text
H = H₀ - μ·B
```

The project corrects this by negating the ground magnetic tensor exactly once at the Hamiltonian boundary.

The source-level magnetic field and polarization definitions remain unchanged.

### Excited-state Zeeman model

The accepted Track P model uses the representative value used by Rodriguez:

```text
g′ = +0.001
```

The effective operator gives weak-field slopes:

```text
F′=0: 0
F′=1: -g′μB, 0, +g′μB
```

The collapsed default pylcp tensor produces an effective:

```text
g ≈ 0.334
```

and materially changes several static observables. It is excluded from the accepted Track P path.

### Excited hyperfine model

Doppelbauer constrains the positive-parity cooling-state `F′=0/F′=1` splitting to less than `1 MHz`.

Track P uses:

```text
0.5 MHz
```

as a reproducible midpoint of the source-supported `0–1 MHz` interval.

This is not a measured value.

Static force surfaces were insensitive across the full `0–1 MHz` interval. The collapsed pylcp splitting of approximately `55.33 MHz` produced topology-changing differences.

The effective splitting model changes retained eigenvalues but does not reconstruct the full independent `d` operator or its coupling to states outside the retained basis.

---

## Molecular-model interchange

Run 012 introduced the versioned schema:

```text
mgf-mot-molecular-model-v1
```

A package contains:

* ground and excited Hamiltonians;
* magnetic tensors;
* transition dipoles;
* branching information;
* basis labels and ordering;
* units and tensor-axis meanings;
* source and approximation metadata;
* canonical content hashes.

Numerical arrays are stored in complex-safe compressed NumPy form with adjacent JSON metadata.

The loader has no fallback defaults. Missing or invalid fields fail explicitly.

The accepted provisional package hash is:

```text
1b9394706613011ab54cbd3c143b60e655487fee38fe9207af11750ddd03ae8c
```

The exported model reconstructs a standalone pylcp backend with exactly zero differences in:

* force;
* populations;
* pumping matrices.

The interchange layer distinguishes:

* basis permutations;
* state phases;
* degenerate-subspace rotations;
* global energy offsets;
* physically non-equivalent nondegenerate mixing.

Imported packages must pass:

* schema and unit validation;
* Hermiticity checks;
* basis and tensor-shape validation;
* transition-strength and branching sum rules;
* weak-field magnetic-slope checks;
* phase-rephasing invariance;
* equilibrium-solver health.

A valid import is not accepted automatically. It must first pass the paper-force benchmark.

### Commands

Export the accepted provisional model:

```powershell
python scripts/export_accepted_molecular_model.py
```

Validate a package:

```powershell
python scripts/validate_molecular_model_package.py <package>
```

Compare two packages:

```powershell
python scripts/compare_molecular_model_packages.py <package-a> <package-b>
```

Benchmark an imported model:

```powershell
python scripts/benchmark_imported_molecular_model.py <package>
```

---

## Paper benchmark

Run 011B digitized and compared the published force figures.

### Figure 3 spatial width

Digitized paper `1/e²` half-widths:

```text
24.5–29.5 mm
```

Accepted provisional model:

```text
18.4–21.2 mm
```

The paper’s rough spatial estimate:

```text
√2 wxy ≈ 25 mm
```

is consistent with the digitized figures.

### Figure 3 velocity width

Digitized paper widths:

```text
13.6–22.4 m/s
```

The paper’s rough textual estimate of approximately `7.5 m/s` understates the visible width.

### Figure 2

Plane-wave comparisons show structural differences before Gaussian envelopes or trajectory integration enter the calculation.

The apparent force-sign calibration was checked independently and retained.

### Figure 4

The accepted `7.5 Γ/k` trajectory begins to diverge from the published path at its first useful-force encounter. The saved data do not support an earlier divergence.

Final benchmark gate:

```text
PAPER_FORCE_SHAPE_DISCREPANCY_CONFIRMED
```

---

## Independent rate-equation validation

Run 011C implemented the paper equations independently of the high-level pylcp force backend.

Agreement with pylcp using identical molecular matrices:

```text
force difference:                  4.3e-17
population difference:             1.4e-15
per-laser pumping-total difference: 5.6e-17
```

Hamiltonian, magnetic, dipole, branching, and basis-transform checks passed.

This establishes that the local force discrepancy is not caused by the wrapper around pylcp or by a second implementation of the rate equations.

The accepted model also fails to reproduce the paper’s stated level-resolved component `(4)` hierarchy:

* `F=2` trapping;
* upper-`F=1` anti-trapping.

At increasing displacement, the accepted force falls to approximately:

```text
14.4% of its central value
```

while scattering remains at approximately:

```text
42.9% of its central value
```

Both weak-state population and cancellation between counter- and copropagating forces contribute.

---

## Complex-number fidelity

Run 011D traced the visible pylcp `ComplexWarning` to:

```text
pylcp/rateeq.py:264
```

The cast occurs after modulus-squared coupling.

The discarded imaginary magnitude is:

```text
0
```

A complex-preserving evaluator agrees with the accepted and independent evaluators within:

```text
4.2e-17
```

Basis rephasing invariance passes below:

```text
1e-12
```

Complex polarization and coupling phases remain intact upstream.

Final gate:

```text
COMPLEX_FIDELITY_RULED_OUT
```

---

## Optical configuration

The simulation uses six beams along:

```text
±x′
±y′
±z
```

where `x′` and `y′` are rotated by `45°` from lab `x` and `y`.

The magnetic field is:

```text
B = B′(-x x̂/2 - y ŷ/2 + z ẑ)
```

with:

```text
B′ = 2 mT/cm
```

### Three-frequency `[3]` state

```text
detunings:  (-1, -1, -1, parked) Γ
saturation: (1.45, 1.45, 2.89, 0.00)
```

### Four-frequency `[3+1]` state

```text
detunings:  (-1, -1, -1, +2) Γ
saturation: (1.45, 1.45, 2.17, 0.72)
```

### Baseline chirp

For `0 ≤ t < τ`:

```text
Δ₁,₂,₃: -8Γ → -1Γ
τ:       1 ms
```

At `t = τ`, the policy switches directly to `[3+1]`.

The trajectory integrator treats `τ` as a known discontinuity and lands exactly on the handoff time.

---

## Force fields

The trajectory path uses two separate precomputed force fields:

```text
F_pre(x, vx, Δ)
F_post(x, vx)
```

Accepted cache shapes:

```text
pre-handoff:  (25, 33, 15)
post-handoff: (25, 33)
```

Interpolation validation:

```text
RMS error / force range:              0.48%
maximum holdout error / force range:   2.04%
slowing-extremum error / force range:  2.2%–6.2%
```

Force is stored canonically as:

```text
Fx / (ℏkΓ)
```

SI acceleration is calculated during integration:

```text
ax = Fnormalized ℏkΓ / m
```

The conversion is applied exactly once.

The interpolator does not extrapolate. Outside-domain queries raise:

```text
ForceFieldDomainError
```

---

## Named provisional trajectories

Run 011 evaluated five named initial velocities from:

```text
x₀ = -50 mm
```

| Initial velocity | Integration termination   | Engineering outcome   |
| ---------------: | ------------------------- | --------------------- |
|          `2 Γ/k` | Completed 20 ms           | `BOUNDED_FINAL_STATE` |
|          `4 Γ/k` | Completed 20 ms           | `BOUNDED_FINAL_STATE` |
|          `6 Γ/k` | Domain exit at `x=+60 mm` | `UNRESOLVED`          |
|        `7.5 Γ/k` | Domain exit at `x=+60 mm` | `UNRESOLVED`          |
|          `9 Γ/k` | Domain exit at `x=+60 mm` | `UNRESOLVED`          |

These are provisional engineering outcomes, not capture classifications.

Run 011 passed:

* timestep convergence;
* exact handoff handling;
* pathwise direct-force validation;
* cache provenance checks;
* typed domain-exit handling.

Worst pathwise interpolation error relative to the accepted force range was approximately:

```text
1.53%
```

Run 011A found that the `7.5 Γ/k` molecule initially matches the slowing feature in velocity but remains outside its major spatial force region. Positive force near and after the handoff cancels its earlier slowing, and it exits approximately `0.90 m/s` faster than it entered.

The later figure benchmark showed that this behavior follows from a genuine force-shape discrepancy rather than a trajectory-integration error.

---

## Installation

Install the package and test dependencies:

```powershell
python -m pip install -e ".[test]"
```

Run the full suite:

```powershell
python -m pytest
```

Optional notebook dependencies:

```powershell
python -m pip install -e ".[notebook]"
```

---

## Core commands

Validate the MgF Hamiltonian structure:

```powershell
python scripts/validate_mgf_hamiltonian.py
```

Build and validate accepted force fields:

```powershell
python scripts/build_and_validate_provisional_force_fields.py
```

Run accepted named trajectories:

```powershell
python scripts/run_accepted_provisional_named_trajectories.py
```

Audit the Run 011 baseline discrepancy:

```powershell
python scripts/analyze_run_011_baseline_discrepancy.py
```

Digitize and compare paper force figures:

```powershell
python scripts/digitize_rodriguez_force_figures.py
python scripts/compare_accepted_force_to_rodriguez_figures.py
```

Audit the plane-wave molecular model:

```powershell
python scripts/audit_plane_wave_molecular_model.py
```

Audit complex-number fidelity:

```powershell
python scripts/audit_complex_number_fidelity.py
```

---

## Validation history

| Run     | Gate or result                              |
| ------- | ------------------------------------------- |
| 009B    | Ground magnetic-convention error identified |
| 009A-R1 | `PROVISIONAL_STATIC_GO`                     |
| 009C    | `RODRIGUEZ_EFFECTIVE_G_OVERRIDE_JUSTIFIED`  |
| 009D    | `PROVISIONAL_TRAJECTORY_FORCE_BACKEND_GO`   |
| 010     | `PROVISIONAL_FORCE_FIELD_INTERPOLATION_GO`  |
| 011     | `PROVISIONAL_NAMED_TRAJECTORY_GO`           |
| 011A    | `BASELINE_DISCREPANCY_NARROWED`             |
| 011B    | `PAPER_FORCE_SHAPE_DISCREPANCY_CONFIRMED`   |
| 011C    | `MOLECULAR_MODEL_DISCREPANCY_NARROWED`      |
| 011D    | `COMPLEX_FIDELITY_RULED_OUT`                |
| 012     | `MOLECULAR_MODEL_INTERCHANGE_READY`         |
| 013     | `CONTROL_POLICY_ABI_GO`                     |
| 014     | `APPARATUS_SCHEDULE_COMPILER_GO`            |
| 015     | `OPEN_LOOP_POLICY_FAMILIES_GO`              |
| 016     | `FEEDBACK_POLICY_INTERFACE_GO`              |
| 017     | `CONTROL_EXPERIMENT_INFRA_READY`            |
| 018     | Reproducible release and safe intake audit  |

Runs 001–008 remain as software-development history and regression plumbing tests. Their heuristic-force trajectory outcomes are physically uninterpretable and superseded by Run 011. See [the run index](docs/run-index.md) for the complete ledger.

---

## Model-independent control and release stack

Runs 013–017 provide deterministic control-policy specifications; synthetic/source-incomplete apparatus compilation; open-loop policy representations; observation-only synthetic feedback and exact replay; and experiment, metric, trial, checkpoint, resume, and replay protocols. These interfaces do not show that any alternative policy improves MgF performance.

Run 018 adds a semantic release manifest, artifact catalog, authorization ledger, environment snapshot, CI checks, package-build inspection, and preserve-first author-model intake:

```powershell
python scripts/generate_release_manifest.py
python scripts/verify_release_integrity.py
python scripts/show_project_status.py
python scripts/audit_model_independent_boundaries.py
python scripts/verify_package_build_run_018.py
```

Synthetic feedback success is not physical evidence. Synthetic apparatus profiles are not real hardware descriptions. The optimizer adapter is an interface boundary only: no optimizer has been implemented or run.

---

## Repository structure

```text
configs/
    Source parameters, run configurations, and digitization anchors

docs/
    Track definitions, convention ledgers, scientific audits,
    interchange documentation, and author-request materials

examples/
    Molecular-model package templates

notebooks/
    Executed convention and exploratory notebooks

outputs/provisional/
    Quarantined reports, metadata, arrays, plots, caches,
    digitized paper data, and molecular-model packages

scripts/
    Reproducible validation, benchmark, export, and audit entry points

src/mgf_mot/
    Molecular models, policies, rate equations, force fields,
    interpolation, trajectories, package interchange, and diagnostics

tests/
    Unit, regression, provenance, convention, physics,
    interpolation, trajectory, digitization, and interchange tests
```

---

## Scientific limitations

Current provisional results do not include:

* the original paper molecular matrices;
* the full independent Doppelbauer `d` operator;
* all excited states coupled by that operator;
* exact excited-state line positions and eigenvectors;
* stochastic spontaneous-emission recoil;
* stimulated-emission diffusion;
* sub-Doppler forces;
* vibrational leakage and full repumping dynamics;
* molecular source distributions;
* beam imperfections or technical noise;
* capture-boundary estimation;
* optimized chirp policies.

The rate-equation model omits optical coherences and is not intended to predict detailed sub-Doppler temperature.

---

## Next milestones

### Upon receipt of an author model

1. validate the imported package;
2. compare it with the accepted provisional package;
3. run the compact Figure 2 and Figure 3 benchmark;
4. determine whether it reproduces the published force structure;
5. authorize cache rebuilding only after a successful static benchmark;
6. rerun named trajectories only after the new force fields pass interpolation validation.

### While the molecular model is pending

Work may continue on model-independent maintenance: documentation, deterministic schemas, serialization/provenance, CI, package integrity, and synthetic regression fixtures. Existing policy, apparatus, feedback, and experiment interfaces may be reused without physical evaluation.

Capture searches and quantitative optimization remain locked until the baseline force model is reproduced or a clearly separate provisional research program is approved.

---

## References

* Rodriguez, K. J., Pilgram, N. H., Barker, D. S., Eckel, S. P., and Norrgard, E. B., “Simulations of a frequency-chirped magneto-optical trap of MgF,” *Physical Review A* 108, 033105 (2023).
* `pylcp` -- Python Laser Cooling Physics:

  * [https://github.com/JQIamo/pylcp](https://github.com/JQIamo/pylcp)
* NIST PRIME:

  * [https://www.nist.gov/programs-projects/platform-realizing-integrated-molecule-experiments-prime](https://www.nist.gov/programs-projects/platform-realizing-integrated-molecule-experiments-prime)
* Doppelbauer *et al.*, MgF excited-state spectroscopy and hyperfine constraints.
