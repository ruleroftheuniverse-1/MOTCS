# Excited-state Zeeman sensitivity

Run 009C is labeled
`PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_EXCITED_ZEEMAN_SENSITIVITY_ONLY`.
It compares named excited-state magnetic models using the corrected Track P
ground Hamiltonian and static rate-equation force interface. It performs no
motion or capture calculation.

## Retained basis and pylcp tensor

The collapsed `A 2Pi1/2, J'=1/2, I=1/2` block returned by pylcp is ordered

1. `|F'=0,mF=0>`;
2. `|F'=1,mF=-1>`;
3. `|F'=1,mF=0>`;
4. `|F'=1,mF=+1>`.

`XFmolecules.Astate` returns `mu_q` in MHz/G with spherical order
`q=(-1,0,+1)`. pylcp subsequently uses `H=H0-mu.B`. In the collapsed project
call, `gS` is source-tagged while `gL`, `gl`, `glprime`, `gr`, `greprime`, and
`gN` are explicitly zero. The resulting rank-1 tensor has Hermitian Cartesian
components and rotationally equivalent weak-field spectra. It also has
off-diagonal `F'=0/F'=1` matrix elements.

Within the retained `F'=1` manifold the electronic-spin term projects to
`gF=gS/6=0.333719884...`, explaining the previously reported effective
`g approximately 0.334`. The `F'=0` level is nondegenerate and has zero
first-order shift; its coupling to `F'=1` affects higher-order finite-field
behavior.

## Named models

`ExcitedZeemanModel` permits only these explicit choices:

- `PYLCP_COLLAPSED_DEFAULT`: the existing comparison tensor;
- `ZERO_EXCITED_ZEEMAN`: a zero tensor near-zero comparison;
- `RODRIGUEZ_EFFECTIVE_G_0P001`: the source-tagged representative
  `g'=+0.001` direct-sum operator;
- `NEGATIVE_G_0P001_SIGN_DIAGNOSTIC`: an explicitly nonphysical convention
  diagnostic.

The effective operator is `mu_q=-g' muB F'_q`. This minus sign is required so
that `H=H0-mu.B` gives `dE/dB=g' muB mF`. The `F'=0` block is identically zero;
the `F'=1` slopes along each lab axis are `-g'muB, 0, +g'muB`. Cartesian
components are Hermitian and the spherical components obey
`mu_q^dagger=(-1)^q mu_-q`.

Selection occurs exactly once at the Hamiltonian boundary and is independent
of the ground-tensor correction. The backend default remains
`PYLCP_COLLAPSED_DEFAULT`; the Rodriguez model must be explicitly requested so
existing behavior is never silently replaced.

## Sensitivity thresholds

For scalar observables Run 009C uses:

- relative difference at most 1%: `INSENSITIVE`;
- above 1% through 5%: `WEAKLY_SENSITIVE`;
- above 5% without a sign/classification change: `MATERIALLY_SENSITIVE`;
- sign or topology change: `TOPOLOGY_CHANGING`.

Extremum shifts of at most one grid step are insensitive, at most two are
weakly sensitive, and larger shifts are material.

The `g'=0` versus `g'=0.001` comparison is insensitive for every audited
observable. The collapsed tensor versus `g'=0.001` comparison contains
material changes, most notably the spatial slopes, while retaining the same
restoring/damping topology. Thus the collapsed tensor is unsuitable as a
paper-aligned choice for later motion studies.

## Result and boundary

Run 009C returns `RODRIGUEZ_EFFECTIVE_G_OVERRIDE_JUSTIFIED`. The explicit
`RODRIGUEZ_EFFECTIVE_G_0P001` model is therefore the preferred Track P static
choice, but it still requires explicit selection.

This is a paper-aligned effective approximation, not exact excited-state
spectroscopy. The independent Doppelbauer `d` operator and exact
`F'=0/F'=1` spectroscopy remain unresolved. Track E remains blocked, and
trajectory, capture, and exact-replication authorization remain false.
