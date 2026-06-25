# MgF Hamiltonian validation layer

## Scope

This layer validates the part of the Rodriguez 16-state model that can be
constructed honestly with official `pylcp 1.0.2` today. It does not calculate
MOT forces and contains no beams, chirps, trajectories, Gaussian profiles, or
optimization.

Files:

- `src/mgf_mot/spectroscopy.py`: source-tagged spectroscopy ledger;
- `src/mgf_mot/mgf_backend.py`: official-backend adapter and strict factory;
- `scripts/validate_mgf_hamiltonian.py`: human-readable report;
- `tests/test_spectroscopy.py`: provenance and missing-value tests;
- `tests/test_mgf_backend.py`: structure and spacing tests.

Run:

```powershell
python scripts/validate_mgf_hamiltonian.py
python -m pytest
```

## Construction policy

Every physical numeric input is a `SourcedConstant` with:

- value or explicit `None`;
- units;
- paper/DOI;
- table/page/note locator;
- status (`exact`, `derived`, `approximate`, `unknown`, or
  `model_assumption`); and
- a note explaining conversions or limitations.

Calling `.require()` on an unknown value raises
`MissingSpectroscopyConstantError`. The backend factory accepts a mapping of
these tagged objects, so removing a required source value cannot fall through
to a `pylcp` default.

## Ground-state result

The adapter calls official `pylcp.hamiltonians.XFmolecules.Xstate` with the
Anderson ground constants as reproduced and convention-annotated by
Doppelbauer. In particular,

`pylcp b = b_F - c/3`

is stored as a derived value rather than copied from historical code defaults.

The resulting `X 2Sigma+(v=0,N=1)` model contains:

| Level | Degeneracy | Energy relative to lower F=1 (MHz) | Next spacing (MHz) |
|---|---:|---:|---:|
| lower `F=1` | 3 | 0.000000 | 109.731576 |
| `F=0` | 1 | 109.731576 | 120.327079 |
| upper `F=1` | 3 | 230.058655 | 9.268420 |
| `F=2` | 5 | 239.327075 | — |

These agree with the rounded Rodriguez Fig. 1 targets 109, 120, and 9 MHz.

`pylcp.Xstate` sorts its eigenvectors/eigenvalues but returns the original bare
basis array. The adapter therefore labels each eigenstate using the dominant
component of the returned eigenvector column. It does not incorrectly zip
sorted energies to unsorted bare labels.

## Excited-state result and hard limitation

Official `pylcp.Astate` enumerates the required positive-parity basis:

- one `F'=0, m_F'=0` state;
- three `F'=1, m_F'=-1,0,+1` states.

The adapter passes explicit zeros only to trigger this basis enumeration. The
returned placeholder Hamiltonian and magnetic operators are discarded. The
validation model reports all four excited energies as `UNKNOWN`.

Doppelbauer independently fits the excited hyperfine `d=135 MHz` term, while
public `pylcp 1.0.2 Astate` has no independently adjustable `d` operator. It
also expects separate parameters where the source constrains only
`b_F+2c/3` and `p+2q`. These combinations are not split or guessed.

Consequently:

- `build_mgf_validation_model_from_sources()` succeeds with an explicitly
  incomplete model object;
- `build_mgf_hamiltonian_from_sources()` raises
  `MgFBackendCapabilityError`; and
- no complete `pylcp.hamiltonian` is returned yet.

## Transition tensor

`pylcp.dipoleXandAstates` generates the official bare spherical coupling
tensor. A `pylcp 1.0.2` expression `UX == []` raises when `UX` is a NumPy
matrix, so the adapter calls the backend without `UX` and then performs the
backend's intended transformation explicitly for each spherical component:

`d_q(eigenbasis) = U_X.T @ d_q(bare)`

The resulting tensor has shape `(3, 12, 4)` in `q=-1,0,+1` order. This validates
structure only. Relative strength, phase, and polarization checks remain gates
before beams or forces are added.

## Reported g-factors

The script prints the effective values shown in Rodriguez Fig. 1 when available:

- lower `F=1`: approximately `-0.2`;
- `F=0`: unknown in the source ledger;
- upper `F=1`: approximately `+0.7`;
- `F=2`: approximately `+0.5`;
- excited state: `+0.001`, explicitly labeled as Rodriguez's representative
  simulation assumption, not a measured constant.

No magnetic-moment matrix is certified in this layer because the fluorine
nuclear g-factor convention and complete excited Zeeman parameterization remain
open.

## Test guarantees

The tests assert:

- 12 ground states and 4 excited basis states;
- dipole shape `(3,12,4)` with finite entries;
- level order `lower F=1`, `F=0`, `upper F=1`, `F=2`;
- degeneracies `3,1,3,5`;
- consecutive spacings within 1 MHz of `109,120,9`;
- all excited energies remain `None`;
- unresolved correlated constants remain unknown;
- every ledger entry has source metadata; and
- both a removed required ground value and complete Hamiltonian construction
  fail clearly.

## Factory Blocker Analysis

The installed `pylcp 1.0.2` molecular backend was inspected directly at
`.venv/Lib/site-packages/pylcp/hamiltonians/XFmolecules.py`. The detailed
interface audit is recorded in
[`docs/pylcp-xfmolecules-interface-notes.md`](pylcp-xfmolecules-interface-notes.md).

### Backend inputs versus MgF source ledger

`Xstate` accepts `N`, `I`, `B`, `gamma`, `b`, `c`, `CI`, `q0`, `q2`, `gS`,
`gI`, `muB`, and `muN`. The source ledger supplies all field-free ground inputs
without using package defaults. The `b` argument is the documented conversion
`b_F-c/3`. The remaining ground caveat is magnetic: the fluorine nuclear
g-factor and sign convention are not yet certified, so the ground magnetic
operator is not treated as a faithful MgF result.

`Astate` accepts `J`, `I`, `P`, `B`, `D`, `H`, `a`, `b`, `c`, `eQq0`, `p`,
`q`, `gS`, `gL`, `gl`, `glprime`, `gr`, `greprime`, `gN`, `muB`, and `muN`.
The MgF source ledger supplies the structural quantum numbers, `B`, `a`, and
the measured combinations `b_F+2c/3` and `p+2q`. It does not honestly supply
separate backend values for `b`, `c`, `p`, and `q`, and the current source
ledger does not contain certified values for the excited Zeeman parameters.

For the retained single-`J`, single-parity excited basis, pylcp's `B`, `D`, `H`,
`p`, and `q` terms are common or not included in the field-free 4-state block.
That observation does not solve the problem, because the hyperfine and Zeeman
operators are still needed before the Hamiltonian can be called faithful.

### Independent Doppelbauer `d` term

The blocker is not just a missing number. Doppelbauer fits an independent
excited hyperfine `d=135 MHz` term. Public `pylcp 1.0.2 Astate` has no `d`
argument and the inspected implementation exposes no separate equivalent
operator. Its implemented hyperfine terms are nuclear spin-orbit `a` and a
Fermi-contact-like term using `b+c/3`.

Current decision:

- existing backend argument: not available;
- combination of existing arguments: not justified;
- unmodified backend: not faithful for the Doppelbauer excited Hamiltonian;
- local extension/wrapper: possible, but it must implement the actual sourced
  `d` operator and validate line positions before being accepted as exact.

### Exact mode

`build_mgf_hamiltonian_from_sources()` remains strict by default. It raises
`MgFBackendCapabilityError` listing the unresolved source-to-backend mappings
and the backend limitation. This is the correct result for exact mode today.

### Explicit provisional approximation mode

The code now includes `ApproximationMode.COLLAPSED_PYLCP_ASTATE`. This mode is
opt-in and returns a pylcp-compatible two-block object only together with an
audit report. It is deliberately not force-ready by default.

The report states that:

- the ground fluorine nuclear g-factor is unknown and set to zero only in this
  explicit approximation;
- Doppelbauer `d=135 MHz` is omitted because `Astate` has no `d` input;
- `b_F+2c/3` is collapsed into the `Astate` `b+c/3` slot by setting
  `b=-52 MHz`, `c=0`;
- `p+2q` is passed as `p=15 MHz`, `q=0`, even though that term is common/unused
  for the retained single parity in pylcp;
- excited `D` and `H` are set to zero because they are common/unused in the
  retained single-`J` block; and
- all unresolved excited Zeeman parameters are explicitly zeroed rather than
  inherited from pylcp defaults.

Tests assert that exact mode fails clearly, approximation mode must be
requested explicitly, the approximation report lists the collapsed/missing
physics, and no undocumented pylcp defaults are used.

### Exact backend feasibility mode

The code also includes `ExactBackendMode.LOCAL_EXTENDED_ASTATE` as a feasibility
mode. It does not construct a Hamiltonian yet. It exists to answer whether a
small local extension of `pylcp.Astate` is justified from the current
source-tagged ledger.

Current answer: not yet. The exact feasibility report says:

- the `d=135 MHz` value is source-tagged, but the corresponding operator matrix
  element has not been implemented or audited from the spectroscopy equations;
- collapsing Doppelbauer `b_F+2c/3` and `d` into pylcp's `b+c/3` slot would be
  approximate, not exact;
- excited Zeeman inputs `gL`, `gl`, `glprime`, `gr`, `greprime`, and `gN` are
  not source-mapped to MgF with pylcp sign conventions;
- Rodriguez's `g=+0.001` is a representative near-zero simulation assumption,
  not an exact replacement for the full excited Zeeman operator;
- the fluorine nuclear g-factor/convention remains uncertified for exact
  ground magnetic matrices; and
- the proposed local extension has not been validated against Doppelbauer line
  positions or an explicitly sourced `F'=0/F'=1` splitting.

The detailed implementation plan and blocker list are in
[`docs/mgf-exact-backend-extension-plan.md`](mgf-exact-backend-extension-plan.md).

## Result

The validation layer **passes the Rodriguez 12+4 structural check and
ground-state spacing check**. Exact complete MgF Hamiltonian construction
remains **blocked**, visibly and intentionally, by the independent excited-state
`d` term and unresolved source-to-backend mappings.

A pylcp-compatible provisional object can now be built only through
`ApproximationMode.COLLAPSED_PYLCP_ASTATE`. It is labeled as approximate,
reports omitted/collapsed physics, uses no undocumented pylcp defaults, and is
not force-ready by default. No force calculation should be added until the exact
gate is resolved or the approximation is separately reviewed and accepted.
