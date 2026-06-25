# Requirements for an honest MgF Hamiltonian

This is a pre-implementation gate for the Rodriguez et al. static MOT
replication. A Hamiltonian should not be added until every required quantity
below has a cited source, a unit, a sign convention, and a mapping to the chosen
`pylcp` basis.

## Target model boundary

The first model contains only the 16 Zeeman sublevels of

- `X 2Sigma+, v=0, N=1`, and
- one parity component of `A 2Pi_1/2, v'=0, J'=1/2`.

It excludes other rotational and vibrational manifolds except insofar as their
measured influence is already represented by effective constants. This follows
the Rodriguez model boundary; it is not a claim that those states do not exist.

## 1. Basis states and ordering

### Ground manifold: 12 states

Required coupled basis metadata:

`|X 2Sigma+, v=0, N=1, S=1/2, J, I_F=1/2, F, m_F, P=-1>`

- `J=1/2` gives `F=0,1` (1+3 states).
- `J=3/2` gives `F=1,2` (3+5 states).
- Total: 12 states.

### Excited manifold: 4 states

Required coupled basis metadata:

`|A 2Pi_1/2, v'=0, J'=1/2, I_F=1/2, F', m_F', P'=+1>`

- `F'=0,1` gives 1+3 states.
- Total: 4 states.

Before force code, freeze and document:

- the exact array ordering;
- phase conventions for coupled basis states;
- spherical-component order (`q=-1,0,+1` in `pylcp`);
- parity convention; and
- the transformation matrix from the Hund's-case basis to the field-free
  eigenbasis.

**Current status:** the official `pylcp.XFmolecules` builders generate these
basis sizes. The validation adapter records bare and dominant-eigenstate labels
and tests the 12+4 counts. A full phase-convention audit remains required before
laser polarization is attached.

## 2. Ground-state field-free Hamiltonian

Required information for `X(v=0,N=1)`:

- electron spin-rotation constant `gamma`;
- fluorine Fermi-contact hyperfine constant `b_F`;
- fluorine dipolar hyperfine constant `c`;
- the exact conversion between the source convention and the `pylcp` inputs
  (`b = b_F - c/3` in sources that report Frosch-Foley `b`);
- rotational constant `B` and centrifugal distortion `D` if the selected
  builder retains them, even though a single fixed `N` makes their contribution
  a common offset;
- whether nuclear spin-rotation or any other retained effective term is
  required at the target accuracy; and
- units and energy-zero convention.

Primary sources:

- Anderson, Allen, and Ziurys,
  [JCP 100, 824 (1994)](https://doi.org/10.1063/1.466565);
- Doppelbauer et al.,
  [JCP 156, 134301 (2022)](https://doi.org/10.1063/5.0081902),
  which reproduces the relevant ground constants and explicitly notes the
  `b`/`b_F` conversion.

Required validation:

- reproduce the four zero-field hyperfine energies and the consecutive
  splittings shown by Rodriguez;
- reproduce the level ordering and dominant `(J,F)` character;
- compare against the transition frequencies reported by Xu 2019 and Pilgram
  2024; and
- establish one explicit reference energy before converting to units of
  `hbar*Gamma`.

**Current status:** source-tagged Anderson/Doppelbauer constants are transcribed
in `spectroscopy.py`. The ground `b_F -> pylcp b` conversion is explicit and
tested. Official `pylcp.Xstate` reproduces consecutive spacings of 109.732,
120.327, and 9.268 MHz. Ground magnetic operators remain uncertified.

## 3. Excited-state field-free Hamiltonian

Required information for the selected positive-parity
`A 2Pi_1/2(v'=0,J'=1/2)` component:

- the exact `F'=0` and `F'=1` energy separation;
- nuclear spin-orbit constant `a`;
- the Fermi-contact/dipolar combination reported as `b_F+2c/3`;
- the independent parity-sensitive hyperfine constant `d`;
- `p+2q` and `A+gamma` only if they affect the retained parity/J manifold or
  are needed to derive its absolute origin;
- the sign and parity convention for every term; and
- a decision, justified from the equations, about which common energy offsets
  may be removed in a single-J, single-parity model.

Primary source:

- Doppelbauer et al.,
  [JCP 156, 134301 (2022)](https://doi.org/10.1063/5.0081902), especially its
  effective-Hamiltonian appendix and fitted-parameter table.

Important implementation question:

The public `pylcp 1.0.2` `Astate` API accepts `a`, `b`, and `c` but no explicit
`d` parameter, while Doppelbauer treats `d` as an independently fitted term.
Source inspection found no independently adjustable `d` operator; the current
Fermi-contact term uses the `b+c/3` combination. A reviewed extension is likely
required. Do not force `d` into another parameter by analogy.

Required validation:

- reproduce the reported positive-parity `F'=0,1` splitting;
- reproduce selected observed line positions from Doppelbauer/Pilgram;
- verify that dropping other `J` or parity states does not change the target
  splitting beyond the declared tolerance.

**Current status:** blocked. The spectroscopy data and unresolved combinations
are recorded, but excited energies remain explicit `None` values. The strict
factory raises rather than using `Astate` defaults. An explicit provisional
`ApproximationMode.COLLAPSED_PYLCP_ASTATE` exists only to make the collapsed
model auditable; it is not exact and is not force-ready by default.

## 4. Magnetic Hamiltonians and g-factors

### Ground state

Required:

- electronic spin Zeeman term and sign of `g_S` in the package convention;
- fluorine nuclear Zeeman term and whether it is retained;
- any rotational/anisotropic terms required by the desired accuracy;
- conversion of `mu_B B` to the Hamiltonian's frequency units; and
- validation that low-field slopes reproduce the effective Rodriguez values
  for the lower `F=1`, upper `F=1`, and `F=2` levels.

### Excited state

Rodriguez explains that a faithful `2Pi_1/2` Zeeman Hamiltonian can involve six
electronic/rotational interactions plus one nuclear term. Required inputs or a
justified effective replacement are:

- `g_S`, `g_L'`, rotational and anisotropic g-factors;
- parity-dependent `g_l'` and `g_re'` terms;
- fluorine nuclear g-factor if retained;
- all signs under the selected Brown-Carrington convention; and
- the sign of the effective excited-state g-factor.

Rodriguez states that the sign was unknown and uses **`g=+0.001` as a
representative simulation value**. That value may be used only when explicitly
labeled as the Rodriguez modeling assumption, not as a measured MgF constant.
An implementation that claims higher spectroscopic fidelity needs a newer
measured or calculated source.

Required validation:

- finite-field eigenvalue slopes for every state;
- rotational invariance of spectra for fields along x, y, and z;
- agreement between full magnetic matrices and the effective level g-factors
  near zero field; and
- the gradient/polarization reversal checks already established in the
  `pylcp` convention sanity notebook.

**Current status:** the official backend includes a broad `2Pi` Zeeman model,
but the MgF-specific inputs are not fully fixed by Rodriguez. Its representative
`+0.001` assumption is sufficient for replication only if labeled exactly as such.

## 5. Transition dipole strengths and Clebsch factors

Required:

- all three spherical matrices `d_q`, `q=-1,0,+1`, between the frozen 12-state
  and 4-state bases;
- basis phases and the direction of the matrix (`ground x excited` in the
  current `pylcp` helper);
- rotation of the bare angular matrices by the ground/excited eigenvector
  matrices;
- normalization convention used by `pylcp.hamiltonian` and `rateeq`;
- whether an absolute reduced electronic dipole is needed or whether total
  `Gamma` plus saturation-normalized intensities completely fixes the force;
  and
- selection-rule and parity assumptions for the selected rotational branch.

Candidate generator:

- `pylcp.hamiltonians.XFmolecules.dipoleXandAstates` produces a tensor of the
  correct shape from angular momentum algebra.

Required validation:

- Hermiticity/shape and forbidden-transition zeros;
- `Delta m_F=q` selection rules in the package's spherical convention;
- sums of squared amplitudes from each excited state;
- invariance of total strength under basis rotation;
- selected relative line strengths from Doppelbauer/Pilgram; and
- an independent comparison to the Xu rate-equation branching factors where
  conventions permit.

**Current status:** the official generator produces the bare tensor, and the
adapter transparently applies the intended ground eigenvector rotation outside
the buggy `UX` argument. Shape `(3,12,4)`, finite values, and missing-value
behavior are tested. Physical line-strength validation is still required.

## 6. Decay and branching assumptions

Required:

- total `A 2Pi_1/2(v'=0)` decay rate `Gamma`, with a chosen source and
  uncertainty;
- angular branching fractions among the 12 included ground Zeeman states,
  derived consistently from the validated `d_q` matrices;
- normalization of all decay channels in `pylcp.rateeq`;
- an explicit choice to ignore or include decay outside `X(v=0,N=1)`;
- vibrational branching fractions and rotational leakage only if those channels
  are represented; and
- the treatment of dark states/coherences implicit in the rate-equation
  approximation.

Primary source for total decay and vibrational branching:

- Norrgard et al.,
  [PRA 108, 032809 (2023)](https://doi.org/10.1103/PhysRevA.108.032809).

For the first Rodriguez static replication, vibrational leakage may be ignored
because Rodriguez explicitly ignores it. The code and documentation must say so;
the in-manifold branching still must sum correctly.

Required validation:

- every excited state's included branching sum;
- the expected maximum multilevel scattering-rate scale;
- force normalization in `hbar*k*Gamma`; and
- comparison to Rodriguez/Xu force magnitudes only after the same saturation
  convention is established.

## 7. Laser polarization and detuning conventions

Required:

- `pylcp` spherical-component order and handedness;
- distinction between a numeric beam `pol=+1/-1` (helicity relative to that
  beam's propagation direction) and a `sigma+/-` label relative to the local
  magnetic quantization axis;
- mapping of Rodriguez components (1)-(4) to those beam helicities;
- behavior as the local magnetic field crosses zero;
- the detuning definition and the sign of all ground/excited energy offsets;
- use of the mean upper `F=1,2` energy for components (3) and (4); and
- the 45-degree x-prime/y-prime beam rotation already encoded in the project.

Required validation:

- nominal red detuning damps near zero velocity;
- nominal configuration restores near zero displacement;
- one gradient or polarization flip reverses the restoring sign;
- both flips recover the nominal sign;
- force vanishes at the symmetric origin; and
- a direct inspection of the local polarization projections for representative
  positive and negative positions.

**Current status:** generic conventions were verified in the executed sanity
notebook. They must be rechecked after inserting the multilevel dipole matrices;
the simple-model result is not proof of the MgF mapping.

## 8. Unit and normalization ledger

Before construction, document one unit system for:

- field-free energies and detunings (preferably angular frequency normalized to
  `Gamma`, with all MHz inputs converted explicitly);
- magnetic moment operators and magnetic field;
- position and velocity;
- laser intensity/saturation per beam and per frequency component;
- wave number `k`; and
- output force `hbar*k*Gamma`.

The ledger must distinguish ordinary frequency `MHz` from angular frequency
`2*pi MHz`. No parameter should be passed to `pylcp` until its expected unit has
been verified from source or a reproducing example.

## Implementation gate

Hamiltonian implementation may begin only after the following artifacts exist:

1. a source table containing every numeric input, uncertainty, DOI/table/equation,
   original symbol, original units, and converted units;
2. a convention map from Anderson/Doppelbauer notation to `pylcp` arguments;
3. a reviewed answer for the excited-state `d` term;
4. a reviewed choice between the full excited Zeeman operator and Rodriguez's
   explicitly representative `g=+0.001` replication assumption;
5. expected zero-field energies, low-field g slopes, and selected line strengths
   recorded as tests; and
6. a transparent fix or adapter for the `dipoleXandAstates(..., UX=array)` issue.

The recommended next implementation step is **A: adapt the official
`pylcp.XFmolecules` backend**, adding only the smallest reviewed extension needed
for the sourced MgF excited-state Hamiltonian. If the `d`/Zeeman audit shows that
the public backend cannot represent the cited effective Hamiltonian without a
substantial rewrite, fall back to **B: construct only the missing operator terms
from the explicitly identified spectroscopy equations**, while retaining the
official basis, dipole, and rate-equation machinery.

## Current gate status

- Source ledger: implemented for the present inputs, including unknowns and
  source locators.
- Ground convention mapping: implemented and numerically validated.
- Excited `d` audit: public `pylcp 1.0.2` has no independently adjustable term;
  extension required.
- Excited Zeeman choice: Rodriguez `g=+0.001` is recorded only as an approximate
  replication assumption; no magnetic operator is claimed yet.
- Level tests: ground ordering/spacings and 12+4 structure implemented.
- Dipole `UX` issue: transparent adapter implemented and documented.
- Complete Hamiltonian gate: **still closed**; strict construction fails clearly.
- Provisional approximation: opt-in only; it reports the omitted independent
  `d` term, collapsed `b_F+2c/3` mapping, zeroed unresolved Zeeman terms, and
  confirms that no undocumented pylcp defaults are used.
