# PROVISIONAL NOT_RODRIGUEZ_REPLICATION EXCITED_HYPERFINE_D_TERM_SENSITIVITY_ONLY audit

This is the Run 009D static-only audit. Track E remains blocked. No trajectory, capture calculation, source distribution, stochastic process, optimizer, or exact-force path is used here.

## Current retained four-state Hamiltonian

The pylcp basis order is `(F',mF) = (0,0), (1,-1), (1,0), (1,+1)`. The current collapsed `Astate` field-free block is diagonal in this basis:

```text
diag(-41.500001983, 13.833333994, 13.833333994, 13.833333994) MHz
```

Its eigenvectors are the basis unit vectors, modulo arbitrary rotations inside the degenerate `F'=1` subspace. Its `F'=0` to `F'=1` splitting is `55.333335977 MHz`, and its center of gravity is approximately zero. This splitting is not supported by the measured positive-parity constraint described below.

The construction passes these explicit inputs to pylcp 1.0.2 `XFmolecules.Astate`: `J=1/2`, `I=1/2`, `P=+1`, `B=15788.2 MHz`, `D=H=0`, `a=109 MHz`, `b=-52 MHz`, `c=0`, `eQq0=0`, `p=15 MHz`, `q=0`, with project-explicit magnetic inputs. The source supplies `b_F+2c/3`, not separate pylcp `b,c`, and `p+2q`, not separate `p,q`; those combinations are collapsed. The independent `d` term is absent because `Astate` has no `d` argument.

## Source constraints

The primary source is M. Doppelbauer et al., “Hyperfine-resolved optical spectroscopy of the A2Pi-X2Sigma+ transition in MgF,” J. Chem. Phys. 156, 134301 (2022), [DOI](https://doi.org/10.1063/5.0081902), [arXiv](https://arxiv.org/abs/2112.06555).

| constraint | value | location | kind |
|---|---:|---|---|
| `a(F)` | 109 MHz, SD 6 MHz, correlated SD 7 MHz | Table III, p. 5 | direct fit |
| `b_F(F)+2c/3` | -52 MHz, SD 14 MHz, correlated SD 16 MHz | Table III, p. 5 | direct fit combination |
| `d(F)` | 135 MHz, SD 7 MHz | Table III, p. 5 | direct fit |
| `p+2q` | 15 +/- 2 MHz | Table III, p. 5 | direct fit combination |
| positive-parity `J'=1/2,P'=+1` hyperfine splitting | less than 1 MHz | conclusion, p. 10 | directly reported bound |
| negative-parity `J'=1/2,P'=-1` splitting | 179 MHz | Sec. IV C, p. 5 | directly reported; not the cooling parity |

Equation (1) defines the magnetic hyperfine contribution containing

```text
a L_z I_z + b_F S.I + (c/3)(3 S_z I_z - S.I)
  - (d/2)(S_+ I_+ + S_- I_-).
```

Appendix A, Eqs. (A3)-(A4), places `d` in both diagonal elements and off-diagonal coupling between `J'=1/2` and `J'=3/2` Hund-case-(a) states. The paper estimates an excited `F'=1` hyperfine-mixing cycling loss of `1.2e-6`. Thus, the numerical value `d=135 MHz` alone cannot be inserted as a four-state diagonal shift, and the source itself shows physics beyond an `F'` splitting.

The exact positive-parity line separation is not tabulated as a resolved central value in the inspected paper. Table VI lists the two cooling lines only at integer-MHz precision. No Anderson, Xu, Pilgram, Norrgard, or Rodriguez value found in the existing project notes supersedes the direct Doppelbauer `<1 MHz` constraint.

## Projectors and named models

`mgf_mot.excited_hyperfine` constructs `P_0=diag(1,0,0,0)` and `P_1=I-P_0`. Tests require Hermiticity, idempotence, orthogonality, completeness, and ranks 1 and 3. They share the same direct-sum `(F',mF)` mapping as the accepted `g'=0.001` Zeeman operator.

- `PYLCP_COLLAPSED_ASTATE` preserves the existing 55.33 MHz comparison baseline.
- `NO_EXCITED_HYPERFINE_SPLITTING` is explicitly an engineering stress test.
- `SOURCE_ALIGNED_EFFECTIVE_FPRIME_SPLITTING` preserves the collapsed center of gravity and samples only the reported `0 <= delta < 1 MHz` interval using the projectors. The midpoint is a deterministic interval representative, not a fitted value. The 1 MHz endpoint is a conservative boundary stress, not a physical equality.
- `FULL_DOPPELBAUER_D_OPERATOR` fails closed. A validated reduction that eliminates the additional `J'=3/2` states and establishes the `F'=0` energy has not been completed.

The effective models alter eigenvalues only. They deliberately leave the working dipole tensor and transition strengths unchanged and therefore omit `d`-dependent eigenvector, mixing, and transition-strength corrections.

## Static decision rule

Run 009D holds the corrected ground tensor, `ExcitedZeemanModel.RODRIGUEZ_EFFECTIVE_G_0P001`, helicity translation, field, laser settings, Gaussian geometry, and dipole ordering fixed. It compares seven static cases: plane-wave and Gaussian `[3]`/`[3+1]`, plus Gaussian chirp snapshots at `-8 Gamma`, `-4.5 Gamma`, and `-1 Gamma`.

Whole-surface normalized RMS differences at or below 1% are `INSENSITIVE`, those at or below 5% are `WEAKLY_SENSITIVE`, and larger changes are `MATERIALLY_SENSITIVE`. A restoring/damping/reversal sign change or a changed zero-contour branch count is `TOPOLOGY_CHANGING`. The generated metadata contains maximum absolute differences, masked relative differences, zero-contour displacement, and extremum displacement.

The run report and metadata are authoritative for the final gate. Even a `PROVISIONAL_TRAJECTORY_FORCE_BACKEND_GO` authorizes only reconnection to named, non-capture provisional trajectory plumbing. It never authorizes capture searches or an exact-replication claim.

## Run 009D result

The `0`, `0.5`, and conservative `1 MHz` source-interval samples are statically `INSENSITIVE`: their whole-surface normalized RMS differences are approximately `0.15%` to `0.38%` across the seven cases. All restoring, damping, component-4, reversal, chirp-feature, force-scale, population-health, refined-topology, and Gaussian checks pass.

In contrast, the collapsed `55.333335977 MHz` model is `TOPOLOGY_CHANGING` relative to the interval midpoint, with whole-surface normalized RMS differences of roughly `13%` to `30%`. Retaining that collapsed field-free splitting would contaminate provisional motion studies.

Final gate: **`PROVISIONAL_TRAJECTORY_FORCE_BACKEND_GO`**. The selected Track P family is `SOURCE_ALIGNED_EFFECTIVE_FPRIME_SPLITTING`; `MID_RANGE_0P5_MHZ` is the reproducible interval representative and remains explicitly labeled as inferred, not measured. Provisional static and non-capture trajectory reconnection are authorized. Capture remains unauthorized, exact replication remains invalid, and Track E remains blocked.
