# Rodriguez et al. MgF Chirped-MOT Replication Parameters

Condensed working notes for the first replication step: a minimal static MgF force-map model in `pylcp`.

Primary target: reproduce the static MgF force-map structure before doing trajectories, chirps, or optimization.

---

## 1. Immediate replication goal

Build a minimal static MgF MOT force-map model that verifies:

- force sign conventions,
- magnetic-field-gradient conventions,
- polarization conventions,
- detuning conventions,
- basic restoring and damping structure,
- Rodriguez-style three- and four-frequency configurations.

This is a calibration step, not yet a loading or capture simulation.

---

## 2. Transition and basic constants

| Quantity | Paper value | Note |
|---|---:|---|
| Molecule | MgF | Lightweight laser-coolable molecule |
| Cooling transition | `X^2Σ+, v=0, N=1 -> A^2Π_1/2, v'=0, J'=1/2` | Main cycling transition |
| Optical angular frequency | `ω ≈ 2π × 834.3 THz` | Equivalent wavelength ≈ `359.3 nm` |
| Natural linewidth | `Γ = 2π × 20.9(2) MHz` | Use angular-frequency units consistently |
| Velocity unit | `Γ/k = 7.53(8) m/s` | Paper's natural velocity scale |
| Saturation intensity | `I_sat ≈ 60 mW/cm^2` | Effective two-level value |
| Recoil velocity | `2.6 cm/s` | Intro value |
| Vibrational leakage | `~3%` to `v >= 1` | Ignored in model; percent-level capture effect if `v=1` is repumped |

---

## 3. Level structure

The model uses 16 Zeeman sublevels total:

- `n_g = 12` ground states
- `n_e = 4` excited states

### Ground manifold

| Level | g-factor | Spacing |
|---|---:|---:|
| lower `F = 1` | `g = -0.2` | — |
| `F = 0` | not shown | `109 MHz` above lower `F=1` |
| upper `F = 1` | `g = 0.7` | `120 MHz` above `F=0` |
| `F = 2` | `g = 0.5` | `9 MHz` above upper `F=1` |

### Excited manifold

| Level | Value |
|---|---:|
| `F' = 0` | included |
| `F' = 1` | included |
| excited-state g-factor | nearly zero |
| simulation value | `g = 0.001` |

### Missing from Rodriguez article text

The paper does **not** fully tabulate the spectroscopic constants needed to reconstruct the full custom Hamiltonian from scratch. It refers out to MgF spectroscopy references for:

- spin-rotation constants,
- dipolar hyperfine constants,
- full transition dipole / Clebsch structure,
- exact excited `F'=0/F'=1` splitting.

So: use Rodriguez for target parameters and force-map behavior; fetch spectroscopy constants or locate a pylcp-compatible MgF model for faithful Hamiltonian construction.

---

## 4. MOT geometry

| Quantity | Value |
|---|---|
| Molecular beam direction | lab `x` |
| Capture simulations in paper | 1D motion along `x` |
| Full stability simulation | 3D |
| Magnetic field | `B = B'(-x xhat/2 - y yhat/2 + z zhat)` |
| Strong magnetic axis | `z` |
| MOT beam axes | `±x'`, `±y'`, `±z` |
| `x'`, `y'` relation to lab axes | rotated `45°` from lab `x`, `y` about `z` |
| Beam intensities | equal peak intensity for all six beams |

Canonical gradient:

| Quantity | Value |
|---|---:|
| `B'` | `2 mT/cm = 20 G/cm` |
| position unit | `ℏΓ / μ_B B' = 7.48(8) mm` |
| velocity unit | `Γ/k = 7.53(8) m/s` |

The `45°` geometry creates the `√2` projection factors in the force-map interpretation.

---

## 5. Beam profiles

### First static checkpoint

Use infinite plane waves.

This corresponds to the cleanest Fig. 2-style sign/topology check.

### Later Gaussian checkpoint

Use elliptical Gaussian beams:

| Quantity | Value |
|---|---:|
| `wxy` | `17.5 mm` |
| `wz` | `10 mm` |
| total laser power | `1 W` baseline |
| alternate powers in sweep | `0.5, 1.0, 1.5, 2.0 W` |

Beam-radius convention:

- beams with `k` in MOT `x-y` plane: radius `wxy` parallel to `x-y`, `wz` along `z`;
- beams with `k` along `z`: radius `wxy` along `x`, `wz` along `y`.

---

## 6. Frequency components

Each of the six MOT beams carries the same frequency components.

| Component | Addressed transition / role | Detuning | Polarization |
|---|---|---|---|
| `(1)` | lower `F = 1 -> F'` | red common `Δ` | `σ+` |
| `(2)` | `F = 0 -> F'` | red common `Δ` | `σ−` |
| `(3)` | upper `F = 1,2 -> F'` | red common `Δ` | `σ−` |
| `(4)` | upper `F = 1,2 -> F'`, confinement helper | blue `+2Γ` | `σ+` |

Paper detuning convention:

```text
Δ_m = ω_m(t) - [ω_F - ω_F']
```

For components `(1)` and `(2)`, `ω_F` is the relevant lower `F=1` or `F=0` ground-state energy.

For components `(3)` and `(4)`, `ω_F` is the mean energy of the upper `F=1` and `F=2` states.

---

## 7. Static force-map targets

### Fig. 2(b): MgF `[3]`

Three-frequency static molecular MOT.

| Quantity | Value |
|---|---:|
| Beam model | infinite plane waves |
| Components | `(1)–(3)` |
| Common detuning | `Δ = -Γ` |
| Component `(4)` | off |
| Saturation vector | `s = (1.45, 1.45, 2.89, 0)` |
| Relative saturation | `s_tilde = (0.25, 0.25, 0.50, 0)` |
| Magnetic gradient | `B' = 20 G/cm = 2 mT/cm` |
| Expected capture scale | `v_c ≈ 4 Γ/k ≈ 32 m/s` |

### Fig. 2(c): MgF `[3+1]`

Four-frequency static molecular MOT.

| Quantity | Value |
|---|---:|
| Beam model | infinite plane waves |
| Components `(1)–(3)` | `Δ = -Γ` |
| Component `(4)` | `Δ_4 = +2Γ` |
| Saturation vector | `s = (1.45, 1.45, 2.17, 0.72)` |
| Relative saturation | `s_tilde = (0.25, 0.25, 0.375, 0.125)` |
| Magnetic gradient | `B' = 20 G/cm = 2 mT/cm` |
| Main effect | improved spatial confinement, reduced damping for faster molecules |

Use these as the first real pylcp checkpoints.

---

## 8. Gaussian static-force checkpoint

Fig. 3 uses three-frequency Gaussian force profiles.

| Quantity | Value |
|---|---:|
| Components | `(1)–(3)` |
| Saturation vector | `s = (1.45, 1.45, 2.89, 0)` |
| Beam model | elliptical Gaussian |
| `wxy` | `17.5 mm` |
| `wz` | `10 mm` |
| Total power | `1 W` |
| Detunings plotted | `Δ = -8Γ, -6Γ, -4Γ, -2Γ` |
| Approx force scale | `~0.03 ℏkΓ` |
| Velocity half-width | `~Γ/k ≈ 7.5 m/s` |
| Spatial half-width along molecular-beam direction | `~√2 wxy ≈ 25 mm` |
| Beam-size saturation threshold | `wxy ≳ 21 mm` helps little |

This is the bridge from static signs to chirp capture.

---

## 9. Chirp values for later

Not needed for the first static pass, but useful to keep nearby.

| Quantity | Value |
|---|---:|
| Chirped components | `m = 1,2,3` |
| Chirp type | linear |
| Initial detuning | `Δ_I = -8Γ` |
| Final detuning | `Δ_F = -Γ` |
| Duration | `τ = 1 ms` |
| Initial molecule position | `x_0 = -50 mm` |
| Baseline radii | `wxy = 17.5 mm`, `wz = 10 mm` |
| Baseline power | `1 W` |
| Capture velocity at 1 W | `v_c = 7.5 Γ/k ≈ 57 m/s` |
| Max reported capture velocity | `80 m/s = 10.5 Γ/k`, at `2 W` |
| Ineffective/effective regime split | around `v_c = 45 m/s` |
| 0.5 W force estimate | `f ≈ 0.015 ℏkΓ` |
| 0.5 W needed chirp duration | `τ ≳ 1.6 ms` |

Chirp law:

```text
Δ_m(t) = Δ_I + ((Δ_F - Δ_I)/τ)t,   0 < t < τ
Δ_m(t) = Δ_F,                      t > τ
```

for `m = 1,2,3`.

After the chirp, component `(4)` is added for the `[3+1]` confinement configuration.

---

## 10. Paper-internal inconsistency

There is a likely typo in Sec. V.

Earlier static/capture sections use:

```text
s = (1.45, 1.45, 2.17, 0.72)
s_tilde = (0.25, 0.25, 0.375, 0.125)
```

But the stability section says:

```text
s = (1.45, 1.45, 0.72, 2.17)
```

while still giving:

```text
s_tilde = (0.25, 0.25, 0.375, 0.125)
```

Those are inconsistent if component order remains `(s1, s2, s3, s4)`.

Working assumption:

```text
s_[3+1] = (1.45, 1.45, 2.17, 0.72)
```

Use this for the static force-map replication.

Later, test both orderings if reproducing Sec. V stability.

---

## 11. First implementation acceptance checks

The static replication step passes only if:

1. `F(0,0) ≈ 0` by symmetry.
2. Nominal configuration gives restoring force near the trap center.
3. Nominal red-detuned configuration gives damping near zero velocity.
4. Flipping magnetic gradient flips the restoring sign.
5. Flipping polarization flips the restoring sign.
6. Flipping both restores the original sign.
7. Force magnitudes are within a plausible `ℏkΓ` scale.
8. Three-frequency `[3]` and four-frequency `[3+1]` force maps qualitatively resemble Rodriguez Fig. 2.
9. Gaussian three-frequency force maps qualitatively resemble Rodriguez Fig. 3.

---

## 12. Immediate build order

1. Encode constants and parameter sheet.
2. Implement quadrupole field and six-beam geometry.
3. Implement/locate MgF Hamiltonian and transition couplings.
4. Implement three-frequency `[3]` force evaluator.
5. Plot `F_x(x, v_x)` for Fig. 2-style plane-wave comparison.
6. Add four-frequency `[3+1]`.
7. Add reversal diagnostics.
8. Add Gaussian beam profiles.
9. Compare Fig. 3-style detuning surfaces.
10. Only then move to trajectories and chirps.
