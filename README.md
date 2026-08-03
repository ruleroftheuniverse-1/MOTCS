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
| Author-model import | Awaiting source data |
| Capture-velocity calculation | Not authorized |
| Capture-boundary search | Not authorized |
| Chirp optimization | Not authorized |
| Exact Rodriguez reproduction | Blocked |

Current test status:

```text
209 passed