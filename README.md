# MgF Chirped-MOT Simulation and Control

This repository is an independent reproduction and extension of the frequency-chirped MgF magneto-optical-trap simulations developed by Rodriguez *et al.*

The immediate project goal is to reproduce the paper’s static force fields and trajectory behavior with an inspectable, source-tagged simulation. The longer-term goal is to compare the paper’s linear frequency chirp against apparatus-constrained alternatives such as piecewise, spline, Fourier, feedback-derived, and optimizer-designed policies.

The repository is deliberately split between:

* **Track E -- exact reproduction**, which remains blocked by unresolved excited-state spectroscopy;
* **Track P -- provisional modeling**, which uses explicit, source-aligned approximations and carries strict provenance and claim limits.

No provisional result is presented as an exact reproduction of Rodriguez *et al.*

---

## Current status

| Capability                                     | Status                    |
| ---------------------------------------------- | ------------------------- |
| Source-tagged MgF ground-state structure       | Validated                 |
| 12-ground / 4-excited retained basis           | Validated                 |
| Dipole tensor `(3, 12, 4)`                     | Validated                 |
| pylcp polarization and force conventions       | Validated                 |
| Ground-state magnetic-moment convention        | Corrected and validated   |
| Rodriguez effective excited-state `g′ = 0.001` | Implemented and validated |
| Source-aligned excited `F′=0/F′=1` splitting   | Implemented provisionally |
| Static `[3]` and `[3+1]` rate-equation forces  | Authorized for Track P    |
| Gaussian chirp force fields                    | Authorized for Track P    |
| Interpolated pre/post-handoff force fields     | Validated                 |
| Provisional named trajectories                 | Authorized                |
| Capture-velocity calculation                   | Not authorized            |
| Capture-boundary search                        | Not authorized            |
| Source-distribution simulation                 | Not implemented           |
| Stochastic recoil and diffusion                | Not implemented           |
| Chirp optimization                             | Not authorized            |
| Exact Rodriguez reproduction                   | Blocked                   |

Current test status:

```text
181 passed
```

---

## Latest trajectory result

Track P Run 011 reconnects the accepted rate-equation force fields to the named Rodriguez-style trajectory protocol.

The run uses:

* initial position `x₀ = -50 mm`;
* initial motion along lab `+x`;
* finite elliptical-Gaussian beams;
* `wxy = 17.5 mm`;
* `wz = 10 mm`;
* `B′ = 2 mT/cm`;
* a linear chirp from `−8Γ` to `−Γ`;
* chirp duration `τ = 1 ms`;
* an exact handoff to the final `[3+1]` configuration;
* a total simulation interval of `20 ms`.

Results:

| Initial velocity | Integration termination               | Engineering outcome   |
| ---------------: | ------------------------------------- | --------------------- |
|          `2 Γ/k` | Completed 20 ms                       | `BOUNDED_FINAL_STATE` |
|          `4 Γ/k` | Completed 20 ms                       | `BOUNDED_FINAL_STATE` |
|          `6 Γ/k` | Force-field domain exit at `x=+60 mm` | `UNRESOLVED`          |
|        `7.5 Γ/k` | Force-field domain exit at `x=+60 mm` | `UNRESOLVED`          |
|          `9 Γ/k` | Force-field domain exit at `x=+60 mm` | `UNRESOLVED`          |

These are **provisional engineering outcomes**, not physical capture classifications.

`BOUNDED_FINAL_STATE` requires a configurable multi-sample final dwell window. A molecule merely crossing the trap center is not counted as bounded.

Run 011 passed:

* trajectory-timestep convergence;
* exact event handling at `τ = 1 ms`;
* pathwise direct rate-equation validation;
* provenance and cache validation;
* explicit force-field domain handling.

Worst pathwise interpolation error relative to the accepted force range was approximately `1.53%`.

---

## Scientific tracks

### Track E -- exact

Track E is the exact-reproduction path.

It remains blocked by the excited-state Hamiltonian, especially:

* the independent Doppelbauer hyperfine `d` operator;
* coupling to states outside the retained four-state excited basis;
* exact excited-state spectroscopy and line positions.

The public `pylcp` molecular backend does not expose the complete operator needed to reconstruct that Hamiltonian faithfully.

Track E does not silently fall back to provisional physics.

### Track P -- provisional

Track P supports controlled engineering and sensitivity studies using explicit source-aligned approximations.

Every Track P artifact is labeled:

```text
PROVISIONAL
NOT_RODRIGUEZ_REPLICATION
```

Track P currently authorizes:

* static rate-equation force calculations;
* policy-conditioned force snapshots;
* finite Gaussian beam modeling;
* force-field interpolation;
* named, non-capture trajectory studies.

It does not currently authorize:

* a reported capture velocity;
* capture-boundary interpolation;
* source-distribution claims;
* stochastic loading predictions;
* optimized chirp claims;
* exact reproduction claims.

See:

```text
docs/project-tracks.md
```

---

## Accepted provisional physics model

The accepted Track P backend uses:

### Molecular basis

* `12` ground states;
* `4` excited states;
* dipole tensor shape `(3, 12, 4)`.

Ground-state spacings reproduce the Rodriguez ordering:

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

The project corrects this by negating the ground magnetic-moment tensor exactly once at the Hamiltonian boundary.

Paper-level magnetic-field and polarization definitions remain unchanged.

### Excited-state Zeeman model

The accepted Track P model uses the Rodriguez representative value:

```text
g′ = +0.001
```

The effective operator is constructed so that the weak-field slopes are:

```text
F′=0: 0
F′=1: -g′μB, 0, +g′μB
```

The collapsed default pylcp tensor produces an effective `g ≈ 0.334` and materially distorts several static-force observables. It is excluded from the accepted trajectory path.

### Excited hyperfine model

Doppelbauer constrains the positive-parity cooling-state `F′=0/F′=1` splitting to less than `1 MHz`.

Track P uses:

```text
0.5 MHz
```

as a reproducible midpoint of the source-supported `0–1 MHz` interval.

This is **not a measured value**.

Static-force surfaces were insensitive across the full `0–1 MHz` interval, while the collapsed pylcp splitting of approximately `55.33 MHz` produced topology-changing differences.

The full independent `d` operator is not reconstructed.

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

with baseline gradient:

```text
B′ = 2 mT/cm
```

### Three-frequency `[3]` state

```text
detunings:  (-1, -1, -1, parked) Γ
saturation: (1.45, 1.45, 2.89, 0.00)
```

Component `(4)` is inactive.

### Four-frequency `[3+1]` state

```text
detunings:  (-1, -1, -1, +2) Γ
saturation: (1.45, 1.45, 2.17, 0.72)
```

Component `(4)` strengthens spatial confinement.

### Baseline chirp

For `0 ≤ t < τ`:

```text
Δ₁,₂,₃: -8Γ → -1Γ
τ:       1 ms
```

At `t = τ`, the policy switches instantaneously to `[3+1]`.

The trajectory integrator treats `τ` as a known discontinuity and splits RK4 steps so that integration lands exactly on the handoff time.

---

## Force fields

The trajectory path does not solve a fresh rate equation at every RK4 substage.

Instead, the project precomputes:

```text
F_pre(x, vx, Δ)
```

for the Gaussian pre-handoff `[3]` system, and:

```text
F_post(x, vx)
```

for the Gaussian post-handoff `[3+1]` system.

The accepted caches contain:

```text
pre-handoff grid:  (25, 33, 15)
post-handoff grid: (25, 33)
```

The pre-handoff detuning grid was refined from `1Γ` to `0.5Γ` after the initial grid failed the predefined important-extremum threshold.

Validation after refinement:

```text
RMS interpolation error / force range:      0.48%
maximum holdout error / force range:         2.04%
slowing-extremum error / force range:        2.2%–6.2%
```

Force fields store normalized force canonically as:

```text
Fx / (ℏkΓ)
```

SI acceleration is calculated only during trajectory integration:

```text
ax = Fnormalized ℏkΓ / m
```

The conversion is applied exactly once.

Force fields do not extrapolate. Queries outside the validated domain raise:

```text
ForceFieldDomainError
```

Trajectory integration records a typed domain-exit termination rather than silently clamping the force.

---

## Installation

Create or activate a Python environment, then install the project:

```powershell
python -m pip install -e ".[test]"
```

Run the full test suite:

```powershell
python -m pytest
```

Optional notebook dependencies:

```powershell
python -m pip install -e ".[notebook]"
```

---

## Key commands

### Validate the MgF Hamiltonian structure

```powershell
python scripts/validate_mgf_hamiltonian.py
```

### Inspect laser policies

```powershell
python scripts/inspect_policies.py
```

### Run the corrected static acceptance audit

```powershell
python scripts/run_provisional_rateeq_static_acceptance_audit_r1.py
```

### Run excited-state Zeeman sensitivity

```powershell
python scripts/run_provisional_excited_zeeman_sensitivity.py
```

### Run excited-hyperfine sensitivity

```powershell
python scripts/run_provisional_excited_hyperfine_sensitivity.py
```

### Build and validate force-field caches

```powershell
python scripts/build_and_validate_provisional_force_fields.py
```

This performs approximately `13,200` equilibrium-population solves when a valid cache is not available.

### Run accepted named trajectories

```powershell
python scripts/run_accepted_provisional_named_trajectories.py
```

---

## Validation history

The major scientific and numerical gates are:

### Convention sanity

A minimal pylcp MOT test verified:

* restoring and damping signs;
* polarization reversal;
* magnetic-gradient reversal;
* combined reversal;
* normalized force units.

### Run 009B -- convention correction

Identified a ground-state magnetic-moment sign mismatch at the pylcp Hamiltonian boundary.

The correction was centralized and applied exactly once.

### Run 009A-R1 -- static acceptance

Gate:

```text
PROVISIONAL_STATIC_GO
```

The corrected provisional backend produced:

* restoring and damping `[3]` forces;
* stronger `[3+1]` confinement;
* correct reversal behavior;
* coherent chirp-feature movement;
* healthy population solves;
* plausible force scales.

### Run 009C -- excited Zeeman sensitivity

Gate:

```text
RODRIGUEZ_EFFECTIVE_G_OVERRIDE_JUSTIFIED
```

The Rodriguez `g′=0.001` model was validated and selected for Track P.

### Run 009D -- excited hyperfine sensitivity

Gate:

```text
PROVISIONAL_TRAJECTORY_FORCE_BACKEND_GO
```

The source-supported `0–1 MHz` effective splitting family was statically insensitive.

### Run 010 -- force-field interpolation

Gate:

```text
PROVISIONAL_FORCE_FIELD_INTERPOLATION_GO
```

Separate pre- and post-handoff force fields passed holdout, topology, refinement, domain, and provenance checks.

### Run 011 -- named trajectories

Gate:

```text
PROVISIONAL_NAMED_TRAJECTORY_GO
```

The five named trajectories passed timestep and pathwise force validation.

---

## Historical plumbing artifacts

Runs 001–008 developed and tested:

* convention handling;
* policy interfaces;
* handoff events;
* trajectory integration;
* outcome classification;
* Gaussian geometry;
* artifact quarantine and provenance.

Those runs used a heuristic force model that was later shown to:

* ignore detuning and component identity;
* ignore Hamiltonian and transition topology;
* apply Gaussian attenuation incorrectly;
* omit the physical `ℏkΓ/m` acceleration conversion.

Their force-dependent trajectory outcomes are physically uninterpretable.

They remain in the repository as software-development history and regression plumbing tests. Run 011 supersedes them for provisional force-dependent trajectory work.

---

## Repository structure

```text
configs/
    Source and run configurations

docs/
    Physics assumptions, convention ledgers, validation reports,
    track definitions, and interface documentation

notebooks/
    Executed convention and exploratory notebooks

outputs/provisional/
    Quarantined Track P reports, metadata, arrays, plots, and caches

scripts/
    Reproducible validation and execution entry points

src/mgf_mot/
    Hamiltonians, spectroscopy, policies, force backends,
    Gaussian beams, interpolation, trajectories, and outcomes

tests/
    Unit, regression, provenance, physics-convention,
    interpolation, and trajectory tests
```

---

## Scientific limitations

Current provisional results do not include:

* the full independent Doppelbauer `d` operator;
* coupling to all excited states outside the retained four-state basis;
* exact excited-state line positions;
* stochastic spontaneous-emission momentum kicks;
* stimulated-emission diffusion;
* sub-Doppler forces;
* vibrational leakage and repumping dynamics;
* molecular source distributions;
* beam misalignment or intensity imbalance;
* experimental technical noise;
* capture-boundary estimation;
* optimized chirp policies.

The rate-equation approximation also omits optical coherences and is not expected to reproduce detailed cloud temperature or sub-Doppler dynamics.

---

## Next milestones

The next authorized work is:

1. analyze the accepted Run 011 trajectory behavior;
2. define a paper-grounded provisional capture protocol;
3. validate the force-field domain for capture-boundary work;
4. add a deterministic initial-velocity sweep only after the capture criterion is approved;
5. add source and apparatus realism incrementally;
6. implement alternative chirp-policy families;
7. authorize optimization only after baseline reproduction and sensitivity checks.

Exact Track E work continues separately through:

* author correspondence;
* spectroscopy extraction;
* reconstruction of the independent excited-state `d` operator;
* validation against measured excited-state line positions.

---

## References

* Rodriguez, K. J., Pilgram, N. H., Barker, D. S., Eckel, S. P., and Norrgard, E. B., “Simulations of a frequency-chirped magneto-optical trap of MgF,” *Physical Review A* 108, 033105 (2023).
* `pylcp` -- Python Laser Cooling Physics:

  * https://github.com/JQIamo/pylcp
* NIST PRIME:

  * https://www.nist.gov/programs-projects/platform-realizing-integrated-molecule-experiments-prime
* Doppelbauer *et al.*, MgF excited-state spectroscopy and hyperfine constraints.
