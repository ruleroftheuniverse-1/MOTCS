# MgF exact backend extension plan

This document records whether a small local extension around official
`pylcp 1.0.2` can faithfully represent the Rodriguez/Doppelbauer MgF excited
Hamiltonian before static force-map construction. It is a backend feasibility
gate only. No MOT force maps, beams, chirps, trajectories, Gaussian profiles,
or optimizers are introduced here.

## Current `pylcp.Astate` interface

Installed source inspected:

`.venv/Lib/site-packages/pylcp/hamiltonians/XFmolecules.py`

Accepted inputs:

```python
Astate(
    J,
    I,
    P,
    B=0.0,
    D=0.0,
    H=0.0,
    a=0.0,
    b=0.0,
    c=0.0,
    eQq0=0.0,
    p=0.0,
    q=0.0,
    gS=2.00231930436092,
    gL=1,
    gl=0,
    glprime=0,
    gr=0,
    greprime=0,
    gN=0,
    muB=1.3996244917100003,
    muN=0.0007622593218797592,
    return_basis=False,
)
```

For the retained `J'=1/2`, single-parity four-state block, the field-free
Hamiltonian construction is:

```python
H_0 = nuclearspinorbit(a) + fermicontact(b+c/3)
```

`lambda_doubling(p+2q)` is included only when more than one parity is requested.
`rotation(B,D,H)` is included only when more than one `J` is requested.
For fluorine `I=1/2`, the electric quadrupole term is not included.

The magnetic operator uses `gS`, `gL`, `gl`, `glprime`, `gr`, `greprime`, `gN`,
`muB`, and `muN`.

## Required MgF/Doppelbauer inputs

The current source ledger contains:

| Required quantity | Current ledger key | Status |
|---|---|---|
| `J'=1/2` | `excited_J` | exact |
| fluorine `I=1/2` | `fluorine_I` | exact |
| selected parity | `excited_parity` | exact |
| rotational `B` | `excited_rotational_B` | exact, common/unused for single `J` |
| hyperfine `a` | `excited_hyperfine_a` | exact |
| measured hyperfine combination | `excited_b_F_plus_2c_over_3` | exact |
| independent hyperfine term | `excited_hyperfine_d` | exact value, missing operator implementation |
| lambda-doubling combination | `excited_p_plus_2q` | exact, common/unused for single parity |
| electron g factor | `electron_g_factor` | exact |
| magneton unit scalings | `bohr_magneton_muB`, `nuclear_magneton_muN` | exact, passed explicitly |

Still unresolved:

| Needed quantity | Ledger key(s) | Status |
|---|---|---|
| separate backend `b`, `c` | `excited_backend_b`, `excited_backend_c` | unknown; source currently represented as a fitted combination |
| separate backend `p`, `q` | `excited_backend_p`, `excited_backend_q` | unknown; only `p+2q` currently represented |
| positive-parity `F'=0/F'=1` splitting | `excited_F0_F1_splitting` | unknown until complete operator is built and validated |
| full excited Zeeman map | `excited_backend_gL`, `excited_backend_gl`, `excited_backend_glprime`, `excited_backend_gr`, `excited_backend_greprime`, `excited_backend_gN` | unknown/ambiguous |
| ground nuclear Zeeman convention | `ground_fluorine_nuclear_g_factor` | unknown |

## Mismatch table

| Topic | `pylcp.Astate` behavior | MgF/Doppelbauer need | Consequence |
|---|---|---|---|
| independent `d` term | no argument and no separate visible operator | Doppelbauer fits `d=135 MHz` independently | exact local extension cannot be a thin wrapper |
| hyperfine combination | field-free term uses `b+c/3` | ledger has `b_F+2c/3` plus independent `d` | collapsing into `b+c/3` is approximate |
| lambda doubling | `p+2q` only appears when multiple parities are requested | ledger has `p+2q` | harmless/common for current single parity, but not a full parity model |
| rotation | `B,D,H` only appear when multiple `J` values are requested | ledger has `B`; `D,H` not represented | harmless/common for current single `J`, not a full rotational model |
| Zeeman | full Brown-Carrington-like parameter set accepted | MgF-specific values and signs are not source-mapped | exact static MOT force calculations remain blocked |
| Rodriguez `g=0.001` | no direct effective-level-g input | Rodriguez uses a representative near-zero value | usable only as labeled approximation, not exact backend |

## Candidate extension mechanisms

### Wrapper function

Not sufficient. A wrapper can pass explicit constants and prevent defaults, but
it cannot add a missing operator to `H_0`.

### Subclass

Not applicable. `Astate` is a function returning arrays, not a class with
override hooks.

### Local copied-and-modified builder

Plausible minimal exact path, but not yet justified. The smallest defensible
extension would copy only the `Astate` builder into local project code, add an
explicit `d` parameter and corresponding matrix element from the cited
Doppelbauer/Brown-Carrington equations, preserve the existing basis and Zeeman
calculation, and require source-tagged constants for every nonzero term.

This should be implemented only after the exact `d` operator formula and
conventions are transcribed and reviewed.

### Documented patch file

Useful as a review artifact after the local copied builder is proven, but less
useful for the current project because we need tests and source-ledger checks
inside the repo.

## Proposed minimal extension

Current proposed mode name:

`ExactBackendMode.LOCAL_EXTENDED_ASTATE`

Current implementation status:

- added as a feasibility mode;
- does not construct a Hamiltonian yet;
- fails closed with a blocker report;
- uses the existing validated 12+4 structural layer and transition tensor;
- records that no undocumented `pylcp` defaults are used.

The future implementation, once justified, should:

1. keep official `pylcp.Xstate` for the ground field-free structure;
2. keep official `dipoleXandAstates` plus the transparent `U_X.T @ d_q` adapter;
3. copy only the minimum `Astate` field-free logic needed to add `d`;
4. pass `muB` and `muN` explicitly;
5. either source-map the full excited Zeeman parameters or explicitly choose a
   reviewed effective-Zeeman representation;
6. validate `F'=0/F'=1` energies and selected line positions before any force
   calculation.

## Risks

- The symbol `d` may have a convention that is not a simple extra diagonal
  term in the current `Astate` basis.
- The fitted combination `b_F+2c/3` may not map cleanly to `b+c/3` once `d` is
  included.
- A single-`J`, single-parity model may hide common offsets that matter when
  validating against optical line positions.
- Excited magnetic forces depend on the Zeeman operator, not just zero-field
  energy splittings.
- Rodriguez's `g=+0.001` assumption may reproduce the paper's modeling choice,
  but it is not a spectroscopic MgF constant.
- A copied builder can drift from upstream `pylcp`; the copy must be small and
  heavily commented.

## Tests needed before exact force-map testing

Backend-only tests needed:

- exact mode fails if any required source-tagged constant is missing;
- exact mode reports no undocumented defaults;
- local extended basis remains four excited states;
- full model remains 12 ground states and dipole tensor remains `(3, 12, 4)`;
- ground spacings remain 109, 120, and 9 MHz to Rodriguez tolerance;
- `d=0` local extension reproduces official `Astate` for the same inputs;
- nonzero `d` reproduces a hand-calculated matrix element or published
  splitting;
- positive-parity `F'=0/F'=1` splitting matches a cited value or cited line
  positions;
- low-field excited-state slopes match the chosen exact or explicitly reviewed
  effective Zeeman model.

Current tests cover the fail-closed subset: source constants are checked first,
no undocumented defaults are reported, the validated 12+4/dipole/ground-spacing
layer is preserved, and exact mode refuses construction.

## Force-readiness decision

Current decision: **B. Do not implement the exact local extension yet.**

The source-tagged values for `d`, `a`, `B`, `p+2q`, and the hyperfine
combination are present, but the actual independent `d` operator and the
excited Zeeman mapping are not yet transcribed and validated. Therefore
`ExactBackendMode.LOCAL_EXTENDED_ASTATE` is a feasibility mode, not a force-ready
backend.

Before exact static force maps are honest, obtain or transcribe:

1. the explicit matrix element/operator for Doppelbauer's independent `d` term
   in the same basis/convention as `pylcp.Astate`;
2. a validated mapping from Doppelbauer's hyperfine constants to the local
   extended builder;
3. the positive-parity `F'=0/F'=1` splitting or enough line positions to
   validate it;
4. the excited Zeeman constants/sign conventions, or a reviewed decision to use
   Rodriguez's `g=+0.001` only as a labeled approximation;
5. the fluorine nuclear g-factor/convention for exact magnetic matrices.

