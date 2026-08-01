# Polarization and Zeeman convention ledger

This ledger records the conventions reconciled in Track P Run 009B. Its
artifacts are labeled
`PROVISIONAL_NOT_RODRIGUEZ_REPLICATION_POLARIZATION_ZEEMAN_RECONCILIATION_ONLY`.
It does not make the collapsed MgF Hamiltonian exact or authorize trajectories.

## Convention table

| Object | Mathematical definition | Source | Code representation | Independently verified? |
|---|---|---|---|---|
| Lab coordinates | Right handed, `x cross y = z` | Rodriguez geometry | ordinary Cartesian triples | Yes |
| Rotated axes | `x'=(x+y)/sqrt(2)`, `y'=(-x+y)/sqrt(2)`, hence `x' cross y'=z` | Rodriguez Sec. II | `geometry.X_PRIME`, `geometry.Y_PRIME` | Yes |
| Beam propagation | `+/-x'`, `+/-y'`, `+/-z`, all unit vectors | Rodriguez Sec. II | `MOT_BEAM_DIRECTIONS` | Yes |
| Magnetic field | `B=B'(-x/2,-y/2,z)`, positive `B'=0.2 T/m` | Rodriguez Sec. II | `quadrupole_field` | Yes; unchanged |
| Paper component labels | `(1) sigma+`, `(2) sigma-`, `(3) sigma-`, `(4) sigma+` | Rodriguez Fig. 1 | YAML `polarization` strings | Yes; YAML unchanged |
| pylcp scalar polarization | Integer `+/-1` defines circular polarization using each beam's own `k` direction as quantization axis | installed `pylcp.fields.laserBeam.__parse_constant_polarization` | `pol=+1/-1` | Yes, by actual vectors |
| Translation of paper labels | Direct beam-relative mapping: `sigma+ -> +1`, `sigma- -> -1` | named project translation checked against pylcp vectors | `paper_helicity_to_pylcp_pol` | Yes |
| Cartesian electric field | Complex transverse unit vector obtained from pylcp's stored spherical vector | installed `laserBeam.cartesian_pol` | complex three-vector | Yes for both helicities and all six beams |
| Counterpropagating relation | Equal scalar `pol` on opposite `k` gives phase-equivalent conjugate Cartesian vectors and reversed fixed-axis `q` intensities | installed pylcp behavior | saved Run 009B metadata | Yes |
| Rotated transverse handedness | `Im(epsilon* cross epsilon).k` has one consistent sign for each scalar `pol` across all beam directions | direct numerical audit | saved Run 009B metadata | Yes; no Mapping E |
| Spherical vector order | `[(Ax-iAy)/sqrt(2), Az, -(Ax+iAy)/sqrt(2)]`, ordered `q=(-1,0,+1)` | installed `pylcp.common.cart2spherical` | first array axis | Yes |
| Dipole tensor order | first tensor axis is `q=(-1,0,+1)` | `XFmolecules.dipoleXandAstates`, loop over `arange(-1,2)` | `(3,12,4)` array | Yes |
| Dipole/light contraction | `d[-1] epsilon[+1] + d[0] epsilon[0] + d[+1] epsilon[-1]` | installed `pylcp.rateeq._calc_pumping_rates` | reversed polarization index | Yes; light `q` drives `Delta m=q` |
| Magnetic Hamiltonian | `H=H0-mu.B` | installed `pylcp.hamiltonian.return_full_H` and `diag_static_field` | Hamiltonian `mu_q` block | Yes |
| Project energy convention | `dE/dB=g_F mu_B m_F` | standard convention used by the Run 009B acceptance request and Rodriguez Fig. 1 labels | finite-difference ledger | Yes |
| Ground effective g signs | lower `F=1: -0.2`; upper `F=1: +0.7`; `F=2: +0.5` | Rodriguez Fig. 1 | source-tagged spectroscopy constants | Yes against corrected slopes |
| Raw Xstate ground tensor | when passed directly as pylcp `mu_q`, gives effective signs `+0.208`, `-0.709`, `-0.501` under the project energy convention | installed Xstate plus numerical `Bx` audit | `RAW_XFMOLECULES` | Yes; globally reversed |
| Corrected ground translation | negate the raw ground tensor once before passing it to pylcp | Run 009B demonstrated convention correction | `PROJECT_ENERGY_SLOPE_CORRECTED` | Yes |
| Excited provisional Zeeman tensor | partial collapsed Astate model retains electron-spin response while unresolved terms are zero | existing approximation boundary | excited `mu_q` is not changed by Run 009B | No faithful MgF validation; effective magnitude is about `0.334`, not `0.001` |

## Actual polarization findings

Run 009B saves the `k` vector, scalar `pol`, Cartesian polarization, spherical
components relative to lab x/y/z, normalization, and `epsilon dot k` for both
helicity classes on all six physical beams. Every vector is normalized and
transverse. Equal scalar signs on counterpropagating beams produce opposite
fixed-axis circular components, as required when helicity is beam-relative.

This rules out Mapping E (a rotated-frame handedness error). It also means a
global scalar-helicity inversion can make a force restoring but is not evidence
that the paper labels were translated incorrectly. Mapping B remains a named,
rejected diagnostic rather than a selectable nominal convention.

## Dipole ordering finding

The tensor's first index is unambiguously `(-1,0,+1)`. Its nonzero elements
obey `Delta m=-q_tensor`. pylcp contracts each tensor component with the
opposite electric-field component, so the resulting light selection rule is
`Delta m=q_light`. Selected allowed transitions pass and forbidden elements
are zero to the audit tolerance. Mapping C is therefore not justified.

## Zeeman sign finding

At `Bx=-1e-4 G`, zero, and `Bx=+1e-4 G`, Run 009B evaluates the first-order
sublevel energies. With raw Xstate output passed directly as `mu_q`, every
identified nonzero ground manifold has the opposite `dE/dB` sign from the
source-tagged MgF g factor. This is not resolved by changing the positive
apparatus gradient.

The accepted translation negates the ground Xstate tensor once at the
Hamiltonian boundary. It leaves the source g factors, field, YAML labels,
dipole tensor, and excited tensor untouched. The corrected compact static
matrix is restoring and damping for `[3]`; `[3+1]` has a more negative spatial
slope, and component `(4)` changes confinement in the intended direction.

## Remaining boundary

The convention error is identified, but the provisional excited tensor is not
a faithful representation of Rodriguez's representative `g=+0.001`. The
independent Doppelbauer `d` operator and exact excited Zeeman mapping also
remain unresolved. Corrected static grids must be regenerated and Run 009A
rerun before considering any later gate. Trajectories remain unauthorized.

Primary references:

- [Rodriguez et al., arXiv:2305.04879](https://arxiv.org/abs/2305.04879)
- [official pylcp v1.0.2 XFmolecules source](https://github.com/JQIamo/pylcp/blob/v1.0.2/pylcp/hamiltonians/XFmolecules.py)
- [official pylcp v1.0.2 fields source](https://github.com/JQIamo/pylcp/blob/v1.0.2/pylcp/fields.py)
- [official pylcp v1.0.2 rate-equation source](https://github.com/JQIamo/pylcp/blob/v1.0.2/pylcp/rateeq.py)
