# pylcp `XFmolecules.py` interface notes

These notes are based on the installed `pylcp 1.0.2` source at
`.venv/Lib/site-packages/pylcp/hamiltonians/XFmolecules.py`. They are an
interface audit only; no MgF MOT force maps, beams, chirps, trajectories,
Gaussian profiles, or optimizers are introduced here.

## `Xstate` accepted inputs

Signature:

```python
Xstate(
    N,
    I,
    B=0.0,
    gamma=0.0,
    b=0.0,
    c=0.0,
    CI=0.0,
    q0=0,
    q2=0,
    gS=2.00231930436092,
    gI=5.5856946893,
    muB=1.3996244917100003,
    muN=0.0007622593218797592,
    return_basis=False,
)
```

Field-free terms implemented:

- fixed `N`, `I` basis for `X 2Sigma+`;
- spin-rotation through `gamma`;
- isotropic hyperfine through `b+c/3`;
- dipolar hyperfine through `c`;
- nuclear spin-rotation through `CI`;
- electric quadrupole through `q0`, `q2` only when `I >= 1`;
- rotation through `B` only when more than one `N` is requested.

Magnetic terms implemented:

- electron spin Zeeman through `gS`, `muB`;
- nuclear spin Zeeman through `gI`, `muN`.

MgF source mapping status:

| pylcp input | MgF source status |
|---|---|
| `N` | source-tagged as `ground_N=1` |
| `I` | source-tagged as fluorine `I=1/2` |
| `B` | source-tagged Anderson/Doppelbauer value |
| `gamma` | source-tagged Anderson/Doppelbauer value |
| `b` | derived from `b_F-c/3` |
| `c` | source-tagged Anderson/Doppelbauer value |
| `CI` | explicit model-boundary zero |
| `q0`, `q2` | explicit zeros because `I=1/2` |
| `gS` | source-tagged CODATA value |
| `gI` | still unknown for certified magnetic matrices |
| `muB`, `muN` | source-tagged pylcp/scipy constants, passed explicitly |

The ground field-free Hamiltonian is therefore source-supported and validated.
The ground magnetic operator is not certified until the fluorine nuclear
g-factor and convention choice are source-checked.

## `Astate` accepted inputs

Signature:

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

Field-free terms implemented:

- `A 2Pi_1/2` Hund's case (a) basis for selected `J`, `I`, and parity `P`;
- rotation through `B`, `D`, `H`, but only when more than one `J` is requested;
- lambda doubling through `p+2q`, but only when more than one parity is
  requested;
- nuclear spin-orbit through `a`;
- Fermi-contact-like hyperfine through `b+c/3`;
- electric quadrupole through `eQq0` only when `I >= 1`.

Magnetic terms implemented:

- orbital/electronic/rotational terms through `gS`, `gL`, `gl`, `glprime`,
  `gr`, and `greprime`;
- nuclear spin term through `gN`;
- `muB` and `muN` unit scaling.

MgF source mapping status:

| pylcp input | MgF source status |
|---|---|
| `J` | source-tagged as `J'=1/2` |
| `I` | source-tagged as fluorine `I=1/2` |
| `P` | source-tagged selected parity |
| `B` | source-tagged Doppelbauer value, but common/unused for single `J` |
| `D`, `H` | not source-tagged for this layer; common/unused for single `J` |
| `a` | source-tagged Doppelbauer value |
| `b`, `c` | blocked: Doppelbauer source currently represented as the combination `b_F+2c/3`, not separate pylcp `b`, `c` inputs |
| `eQq0` | zero for `I=1/2` |
| `p`, `q` | blocked as separate values; Doppelbauer gives `p+2q`, and the term is common/unused for the retained single parity |
| `gS` | source-tagged CODATA value |
| `gL`, `gl`, `glprime`, `gr`, `greprime`, `gN` | unresolved MgF mappings |
| `muB`, `muN` | source-tagged pylcp/scipy constants, passed explicitly |

## Independent Doppelbauer `d` term

The installed `Astate` implementation has no `d` argument and no visible
separate operator corresponding to Doppelbauer's independently fitted excited
hyperfine `d=135 MHz` term. It cannot be represented by an existing backend
argument without collapsing it into another physical term.

Current classification:

- existing backend argument: **not found**;
- combination/transformation of existing arguments: **not justified** from the
  inspected source;
- local extension/wrapper around official backend: **possible next path**, but
  it must implement the actual operator from Doppelbauer/Brown-Carrington and
  validate line positions;
- unmodified backend: **not faithful** for the sourced Doppelbauer excited
  Hamiltonian.

## `dipoleXandAstates` accepted inputs

Signature:

```python
dipoleXandAstates(
    xbasis,
    abasis,
    I=0.5,
    S=0.5,
    UX=[],
    return_intermediate=False,
)
```

It returns the spherical transition tensor in `q=-1,0,+1` order with shape
`(3, n_ground, n_excited)`. The installed implementation compares `UX == []`;
passing a NumPy array for `UX` raises. The project therefore calls the official
bare tensor generator and applies the intended ground eigenbasis rotation
explicitly as `U_X.T @ d_q`.

## Exact and provisional factory status

Exact source-tagged factory:

- succeeds for the ground field-free Hamiltonian;
- succeeds for excited basis enumeration;
- succeeds for the `(3, 12, 4)` transition tensor;
- fails clearly before constructing a complete `pylcp.hamiltonian`.

Explicit provisional approximation:

- `ApproximationMode.COLLAPSED_PYLCP_ASTATE` can build a pylcp-compatible
  two-block object only when requested explicitly;
- it reports every collapsed or omitted physical term;
- it records that no undocumented pylcp defaults were used;
- it is not force-ready by default and should not be used for Rodriguez force
  maps without a separate review.
